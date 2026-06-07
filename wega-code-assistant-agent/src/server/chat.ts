import { getLocalRepoInfo } from "./repo";
import { buildPrompt } from "./prompt";
import { parseAndFlush } from "./stream";
import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable as NodeReadable } from "node:stream";
import { randomUUID } from "node:crypto";
import { appendFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { Readable } from "node:stream";

type HistoryTurn = { role: "user" | "assistant"; content: string };
const CHAT_TIMEOUT_MS = 15 * 60 * 1000;
const DEFAULT_CHAT_STALL_TIMEOUT_MS = 15 * 60 * 1000;
const parsedStallTimeoutMs = Number(process.env.REPO_CHAT_STALL_TIMEOUT_MS);
const CHAT_STALL_TIMEOUT_MS =
  Number.isFinite(parsedStallTimeoutMs) && parsedStallTimeoutMs > 0
    ? parsedStallTimeoutMs
    : DEFAULT_CHAT_STALL_TIMEOUT_MS;
const SESSION_RETENTION_MS = 10 * 60 * 1000;
const SESSION_IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes idle before auto-close
const MAX_SESSION_EVENTS = 2000;
const META_LOG_DIR = join(process.cwd(), "logs", "chat-meta");
type DroidProc = {
  child: ChildProcessByStdio<null, NodeReadable, NodeReadable>;
  exited: Promise<number>;
};

type ChatEvent = { id: number; event: string; data: any };
type ChatSession = {
  id: string;
  events: ChatEvent[];
  subscribers: Set<(entry: ChatEvent) => void>;
  nextEventId: number;
  finished: boolean;
  cleanupTimer: ReturnType<typeof setTimeout> | null;
  idleTimer: ReturnType<typeof setTimeout> | null;
  metaLogFileName: string | null;
  pendingMetaLines: string[];
  proc: DroidProc | null;
  repoRoot: string;
  repoWorkdir: string;
};

const sessions = new Map<string, ChatSession>();
// Maps external client/orchestrator sessionId → internal chat sessionId
const clientSessionMap = new Map<string, string>();
const ensureMetaLogDirPromise = mkdir(META_LOG_DIR, { recursive: true });

export async function handleChatRequest(req: Request): Promise<Response> {
  const payload = (await req.json().catch(() => null)) as any;
  if (!payload || typeof payload.message !== "string" || !payload.message.trim()) {
    return new Response(JSON.stringify({ error: "Missing message" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  // const historyRaw = Array.isArray(payload.history) ? (payload.history as HistoryTurn[]) : [];
  // const history: HistoryTurn[] = historyRaw
  //   .map((turn): HistoryTurn => ({
  //     role: turn?.role === "assistant" ? "assistant" : "user",
  //     content: String(turn?.content ?? "")
  //   }))
  //   .filter((turn) => turn.content.length > 0);
  const history: HistoryTurn[] = [];

  let repoInfo;
  const repoInput = typeof payload.repo === "string" ? payload.repo : undefined;
  try {
    repoInfo = await getLocalRepoInfo(repoInput);
  } catch (err) {
    console.error("Local repository not found", err);
    return new Response(
      JSON.stringify({
        error: "repository not found",
        details:
          err instanceof Error
            ? err.message
            : repoInput
              ? `Could not resolve repository from input: ${repoInput}`
              : "local repository missing under ./repos"
      }),
      {
      status: 500,
      headers: { "Content-Type": "application/json" }
      }
    );
  }

  const modelInput = typeof payload.model === "string" ? payload.model.trim() : "";
  const autonomyRaw = typeof payload.autonomy === "string" ? payload.autonomy.trim().toLowerCase() : "";
  const autonomyInput = ["full", "high", "medium", "low"].includes(autonomyRaw) ? autonomyRaw : "";
  const reasoningRaw = typeof payload.reasoning === "string" ? payload.reasoning.trim().toLowerCase() : "";
  const reasoningInput = ["high", "medium", "low"].includes(reasoningRaw) ? reasoningRaw : "";
  const trimmedMsg = payload.message.length > 8000 ? payload.message.slice(0, 8000) : payload.message;
  // const prompt = buildPrompt(trimmedMsg, history);
  const prompt = buildPrompt(trimmedMsg, []);

  console.log("[chat] incoming request", {
    repoWorkdir: repoInfo.workdir,
    model: modelInput || "(default)",
    autonomy: autonomyInput || "(default)",
    reasoning: reasoningInput || "(default)",
    messageLength: trimmedMsg.length,
    historyTurns: history.length,
  });

  const session = createSession(repoInfo.repoRoot, repoInfo.workdir);

  let proc: DroidProc;
  let commandPreview = "";
  try {
    const droidExec = runDroidExec(
      prompt,
      repoInfo.workdir,
      modelInput || undefined,
      autonomyInput || undefined,
      reasoningInput || undefined
    );
    proc = droidExec.proc;
    commandPreview = droidExec.command;
  } catch (err) {
    closeSessionWithError(
      session,
      "Failed to start droid process",
      err instanceof Error ? err.message : String(err)
    );
    return new Response(
      JSON.stringify({
        error: "Failed to start droid process",
        details: err instanceof Error ? err.message : String(err)
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" }
      }
    );
  }

  session.proc = proc;
  emitToSession(session, "command", { text: commandPreview });
  runSessionInBackground(session, proc, repoInfo.repoRoot);

  // Link external client sessionId to internal chat sessionId (for kill lookups)
  const clientSessionId = typeof payload.clientSessionId === "string" ? payload.clientSessionId.trim() : "";
  if (clientSessionId) {
    clientSessionMap.set(clientSessionId, session.id);
  }

  return new Response(JSON.stringify({ sessionId: session.id }), {
    headers: {
      "Content-Type": "application/json; charset=utf-8"
    }
  });
}

export async function handleKillSessionRequest(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const sessionId = url.searchParams.get("sessionId")?.trim();
  if (!sessionId) {
    return new Response(JSON.stringify({ error: "Missing sessionId" }), {
      status: 400,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  // Look up session by internal ID first, then by client/orchestrator session ID
  let session = sessions.get(sessionId);
  if (!session) {
    const internalId = clientSessionMap.get(sessionId);
    if (internalId) {
      session = sessions.get(internalId);
    }
  }
  if (!session) {
    return new Response(JSON.stringify({ status: "ok", detail: "session not found (already ended)" }), {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  // Kill the droid child process if still running
  if (session.proc && !session.finished) {
    try {
      session.proc.child.kill();
      console.log(`[chat] killed droid process for session ${sessionId} (user requested)`);
    } catch {
      // ignore — process may have already exited
    }
  }

  // Force-finish the session
  if (!session.finished) {
    emitToSession(session, "exit", { code: 1, timedOut: false, killedByUser: true });
    finishSession(session);
  }

  // Clean up the client mapping
  clientSessionMap.delete(sessionId);

  return new Response(JSON.stringify({ status: "ok", sessionId }), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export async function handleChatFollowUpRequest(req: Request): Promise<Response> {
  const payload = (await req.json().catch(() => null)) as any;
  if (!payload || typeof payload.message !== "string" || !payload.message.trim()) {
    return new Response(JSON.stringify({ error: "Missing message" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const sessionId = typeof payload.sessionId === "string" ? payload.sessionId.trim() : "";
  if (!sessionId) {
    return new Response(JSON.stringify({ error: "Missing sessionId" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const session = sessions.get(sessionId);
  if (!session) {
    return new Response(JSON.stringify({ error: "Session not found or expired" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (session.finished) {
    return new Response(JSON.stringify({ error: "Session already finished" }), {
      status: 410,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (session.proc) {
    return new Response(JSON.stringify({ error: "Session is busy — a turn is still in progress" }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Cancel idle timer since a new turn is starting
  if (session.idleTimer) {
    clearTimeout(session.idleTimer);
    session.idleTimer = null;
  }

  const modelInput = typeof payload.model === "string" ? payload.model.trim() : "";
  const autonomyRaw = typeof payload.autonomy === "string" ? payload.autonomy.trim().toLowerCase() : "";
  const autonomyInput = ["full", "high", "medium", "low"].includes(autonomyRaw) ? autonomyRaw : "";
  const reasoningRaw = typeof payload.reasoning === "string" ? payload.reasoning.trim().toLowerCase() : "";
  const reasoningInput = ["high", "medium", "low"].includes(reasoningRaw) ? reasoningRaw : "";
  const trimmedMsg = payload.message.length > 8000 ? payload.message.slice(0, 8000) : payload.message;
  const prompt = buildPrompt(trimmedMsg, []);

  console.log("[chat] follow-up request", {
    sessionId: session.id,
    repoWorkdir: session.repoWorkdir,
    model: modelInput || "(default)",
    messageLength: trimmedMsg.length,
  });

  let proc: DroidProc;
  let commandPreview = "";
  try {
    const droidExec = runDroidExec(
      prompt,
      session.repoWorkdir,
      modelInput || undefined,
      autonomyInput || undefined,
      reasoningInput || undefined
    );
    proc = droidExec.proc;
    commandPreview = droidExec.command;
  } catch (err) {
    closeSessionWithError(
      session,
      "Failed to start droid process",
      err instanceof Error ? err.message : String(err)
    );
    return new Response(
      JSON.stringify({
        error: "Failed to start droid process",
        details: err instanceof Error ? err.message : String(err),
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  session.proc = proc;
  emitToSession(session, "command", { text: commandPreview });
  runSessionInBackground(session, proc, session.repoRoot);

  return new Response(JSON.stringify({ status: "ok", sessionId: session.id }), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export async function handleChatEventsRequest(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const sessionId = url.searchParams.get("sessionId")?.trim();
  if (!sessionId) {
    return new Response(JSON.stringify({ error: "Missing sessionId" }), {
      status: 400,
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });
  }

  const session = sessions.get(sessionId);
  if (!session) {
    return new Response(JSON.stringify({ error: "Session not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });
  }

  const lastEventIdRaw = Number(url.searchParams.get("lastEventId") ?? "-1");
  const lastEventId = Number.isFinite(lastEventIdRaw) ? lastEventIdRaw : -1;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      let closed = false;
      let heartbeat: ReturnType<typeof setInterval> | null = null;
      let subscriber: ((entry: ChatEvent) => void) | null = null;

      const closeStream = () => {
        if (closed) return;
        closed = true;
        if (heartbeat) {
          clearInterval(heartbeat);
          heartbeat = null;
        }
        if (subscriber) {
          session.subscribers.delete(subscriber);
          subscriber = null;
        }
        try {
          controller.close();
        } catch {
          // no-op
        }
      };

      const sendEntry = (entry: ChatEvent) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`id: ${entry.id}\n`));
          controller.enqueue(encoder.encode(`event: ${entry.event}\n`));
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(entry.data)}\n\n`));
        } catch {
          closeStream();
        }
      };

      subscriber = (entry: ChatEvent) => {
        sendEntry(entry);
        if (session.finished && entry.event === "exit") {
          closeStream();
        }
      };

      for (const entry of session.events) {
        if (entry.id > lastEventId) {
          sendEntry(entry);
          // If replaying and session is already finished with an exit event, close after replay
        }
      }

      if (session.finished) {
        closeStream();
        return;
      }

      session.subscribers.add(subscriber);

      heartbeat = setInterval(() => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(":keepalive\n\n"));
        } catch {
          closeStream();
        }
      }, 15_000);
    },
    cancel() {
      // subscriber cleanup is handled by closeStream in start
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
      "Transfer-Encoding": "chunked"
    }
  });
}

function createSession(repoRoot: string, repoWorkdir: string): ChatSession {
  const id = randomUUID();
  const session: ChatSession = {
    id,
    events: [],
    subscribers: new Set(),
    nextEventId: 1,
    finished: false,
    cleanupTimer: null,
    idleTimer: null,
    metaLogFileName: null,
    pendingMetaLines: [],
    proc: null,
    repoRoot,
    repoWorkdir,
  };
  sessions.set(id, session);
  return session;
}

function emitToSession(session: ChatSession, event: string, data: any): void {
  if (session.cleanupTimer) {
    clearTimeout(session.cleanupTimer);
    session.cleanupTimer = null;
  }

  const entry: ChatEvent = {
    id: session.nextEventId++,
    event,
    data
  };

  session.events.push(entry);
  if (session.events.length > MAX_SESSION_EVENTS) {
    session.events.shift();
  }

  for (const subscriber of session.subscribers) {
    try {
      subscriber(entry);
    } catch {
      // ignore subscriber errors
    }
  }

  spoolMetaLine(session, event, data);
}

function finishSession(session: ChatSession): void {
  if (session.finished) return;
  session.finished = true;

  if (session.idleTimer) {
    clearTimeout(session.idleTimer);
    session.idleTimer = null;
  }

  if (!session.metaLogFileName) {
    const fallbackName = safeLogFileName(session.id);
    if (fallbackName) {
      session.metaLogFileName = fallbackName;
      flushPendingMetaLines(session);
    }
  }

  if (session.cleanupTimer) {
    clearTimeout(session.cleanupTimer);
  }
  session.cleanupTimer = setTimeout(() => {
    sessions.delete(session.id);
    // Also clean up any client session mapping pointing to this session
    for (const [clientId, internalId] of clientSessionMap) {
      if (internalId === session.id) {
        clientSessionMap.delete(clientId);
        break;
      }
    }
  }, SESSION_RETENTION_MS);
}

function startSessionIdleTimer(session: ChatSession): void {
  if (session.idleTimer) {
    clearTimeout(session.idleTimer);
  }
  session.idleTimer = setTimeout(() => {
    if (session.finished) return;
    console.log(`[chat] session ${session.id} idle timeout — closing`);
    emitToSession(session, "exit", { code: 0, timedOut: false, reason: "idle_timeout" });
    finishSession(session);
  }, SESSION_IDLE_TIMEOUT_MS);
}

function closeSessionWithError(session: ChatSession, message: string, details?: string, code = 1, timedOut = false): void {
  emitToSession(session, "response", { error: { message, details } });
  emitToSession(session, "exit", { code, timedOut });
  finishSession(session);
}

function spoolMetaLine(session: ChatSession, event: string, payload: any): void {
  const line = `${event}: ${toMetaPayloadText(payload)}`;

  if (!session.metaLogFileName) {
    const discoveredSessionId = extractSessionIdFromInitEvent(event, payload);
    if (discoveredSessionId) {
      session.metaLogFileName = safeLogFileName(discoveredSessionId);
    }
  }

  if (!session.metaLogFileName) {
    session.pendingMetaLines.push(line);
    return;
  }

  if (session.pendingMetaLines.length > 0) {
    session.pendingMetaLines.push(line);
    flushPendingMetaLines(session);
    return;
  }

  appendMetaLines(session.metaLogFileName, [line]);
}

function flushPendingMetaLines(session: ChatSession): void {
  if (!session.metaLogFileName || session.pendingMetaLines.length === 0) return;
  const lines = session.pendingMetaLines.splice(0, session.pendingMetaLines.length);
  appendMetaLines(session.metaLogFileName, lines);
}

function extractSessionIdFromInitEvent(event: string, payload: any): string | null {
  if (event !== "system" || !payload || typeof payload !== "object") {
    return null;
  }

  const subtype = typeof payload.subtype === "string" ? payload.subtype : "";
  if (subtype !== "init") {
    return null;
  }

  if (payload.name === "session_id" && typeof payload.value === "string" && payload.value.trim()) {
    return payload.value.trim();
  }

  if (typeof payload.session_id === "string" && payload.session_id.trim()) {
    return payload.session_id.trim();
  }

  const params = payload.parameters;
  if (params && typeof params === "object") {
    if (typeof params.session_id === "string" && params.session_id.trim()) {
      return params.session_id.trim();
    }
    if (params.name === "session_id" && typeof params.value === "string" && params.value.trim()) {
      return params.value.trim();
    }
  }

  return null;
}

function safeLogFileName(value: string): string {
  const cleaned = value
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "-")
    .replace(/\.+$/g, "")
    .slice(0, 160);
  return cleaned || "session";
}

function toMetaPayloadText(payload: any): string {
  try {
    return JSON.stringify(payload);
  } catch {
    return String(payload);
  }
}

function appendMetaLines(fileName: string, lines: string[]): void {
  void (async () => {
    try {
      await ensureMetaLogDirPromise;
      const filePath = join(META_LOG_DIR, `${fileName}.log`);
      await appendFile(filePath, `${lines.join("\n")}\n`, "utf-8");
    } catch (err) {
      console.error("failed to write chat meta log", err);
    }
  })();
}

function runSessionInBackground(session: ChatSession, proc: DroidProc, repoRoot: string): void {
  const decoder = new TextDecoder();
  let buffer = "";
  let timedOut = false;
  let closed = false;
  let lastStderr = "";
  let stallTimeout: ReturnType<typeof setTimeout> | null = null;

  const closeOnce = (code: number, errorMessage?: string, errorDetails?: string) => {
    if (closed) return;
    closed = true;
    if (stallTimeout) {
      clearTimeout(stallTimeout);
      stallTimeout = null;
    }
    if (errorMessage) {
      emitToSession(session, "response", {
        error: { message: errorMessage, details: errorDetails }
      });
    }
    emitToSession(session, "exit", { code, timedOut });
    finishSession(session);
  };

  const resetStallTimeout = () => {
    if (stallTimeout) {
      clearTimeout(stallTimeout);
    }
    stallTimeout = setTimeout(() => {
      try {
        proc.child.kill();
      } catch {
        // ignore
      }
      closeOnce(
        1,
        "agent stalled without progress",
        "No new events were received from droid. Check droid login and model availability."
      );
    }, CHAT_STALL_TIMEOUT_MS);
  };

  resetStallTimeout();

  // [DISABLED] Absolute timer — commented out to rely only on stall timer for now
  // const timeout = setTimeout(() => {
  //   timedOut = true;
  //   try {
  //     proc.child.kill();
  //   } catch {
  //     // ignore
  //   }
  // }, CHAT_TIMEOUT_MS);

  (async () => {
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const stdout = Readable.toWeb(proc.child.stdout) as ReadableStream<Uint8Array>;
      reader = stdout.getReader();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;
        resetStallTimeout();
        buffer += decoder.decode(value, { stream: true });
        buffer = parseAndFlush(buffer, (event, data) => emitToSession(session, event, data), repoRoot);
      }

      if (buffer.trim()) {
        const flushed = parseAndFlush(`${buffer}\n`, (event, data) => emitToSession(session, event, data), repoRoot);
        if (flushed.trim()) {
          emitToSession(session, "message", { role: "assistant", text: flushed.trim() });
        }
        buffer = "";
      }
    } catch (err) {
      closeOnce(1, "stdout stream failed", err instanceof Error ? err.message : String(err));
    } finally {
      try {
        reader?.releaseLock();
      } catch {
        // no-op
      }
    }
  })();

  (async () => {
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const stderr = Readable.toWeb(proc.child.stderr) as ReadableStream<Uint8Array>;
      reader = stderr.getReader();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;
        resetStallTimeout();
        const chunk = decoder.decode(value, { stream: true });
        if (chunk.trim()) {
          const text = chunk.trim();
          lastStderr = `${lastStderr}\n${text}`.trim().slice(-4000);
          emitToSession(session, "stderr", { text });
        }
      }
    } catch (err) {
      emitToSession(session, "stderr", { text: err instanceof Error ? err.message : String(err) });
    } finally {
      try {
        reader?.releaseLock();
      } catch {
        // no-op
      }
    }
  })();

  proc.exited
    .then((code: number) => {
      // clearTimeout(timeout); // [DISABLED] absolute timer
      if (stallTimeout) {
        clearTimeout(stallTimeout);
        stallTimeout = null;
      }
      if (closed) return;

      if (code !== 0) {
        console.error(`[chat] droid exited with code ${code}`, {
          sessionId: session.id,
          timedOut,
          stderr: lastStderr || "(empty)",
        });
        closeOnce(
          code,
          `droid exited with code ${code}`,
          timedOut ? "request timed out" : lastStderr || "No stderr captured. Check droid login and model availability."
        );
        return;
      }

      // Successful exit — emit turn_complete but keep session alive for follow-ups
      closed = true;
      session.proc = null;
      emitToSession(session, "turn_complete", { code, timedOut: false });
      startSessionIdleTimer(session);
    })
    .catch((err: unknown) => {
      // clearTimeout(timeout); // [DISABLED] absolute timer
      closeOnce(1, "droid process failed", err instanceof Error ? err.message : String(err));
    });
}

function runDroidExec(  
  prompt: string,
  cwd: string,
  modelOverride?: string,
  autonomyOverride?: string,
  reasoningOverride?: string
) {
  const args = ["exec", "--output-format", "debug"];
  const model = modelOverride || process.env.DROID_MODEL_ID || process.env.REPO_CHAT_MODEL_ID || "glm-5";
  args.push("-m", model);
  const autonomy = autonomyOverride || process.env.DROID_AUTONOMY || "high";
  args.push("--auto", autonomy);
  const reasoning = reasoningOverride || process.env.DROID_REASONING || process.env.REPO_CHAT_REASONING;
  if (reasoning) {
    args.push("-r", reasoning);
  }
  args.push(prompt);
  const command = ["droid", ...args].map((part) => quoteCliArg(part)).join(" ");
  console.log("[chat] spawning droid", { command, cwd });
  const pathSep = process.platform === "win32" ? ";" : ":";
  const extraPath = process.env.MCP_EXTRA_PATH ?? "";
  // Ensure the spawned droid (and its MCP children) can resolve mcp-atlassian
  // and npx regardless of how Node was started. In Cloud Run this guarantees
  // /usr/local/bin (mcp-atlassian, npx, node) and /root/.local/bin (droid)
  // are always on PATH; locally MCP_EXTRA_PATH can point to e.g. the Python
  // user-Scripts dir on Windows.
  const composedPath = [
    extraPath,
    "/root/.local/bin",
    "/usr/local/bin",
    "/usr/bin",
    process.env.PATH ?? "",
  ]
    .filter(Boolean)
    .join(pathSep);
  const child = spawn("droid", args, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      PATH: composedPath,
    },
  });
  const exited = new Promise<number>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code: number | null) => resolve(code ?? 1));
  });
  const proc: DroidProc = { child, exited };
  return { proc, command };
}

function quoteCliArg(value: string): string {
  if (!value) return '""';
  if (!/[\s"']/g.test(value)) return value;
  return `"${value.replace(/"/g, '\\"')}"`;
}
