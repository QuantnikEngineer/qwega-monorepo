import { handleChatEventsRequest, handleChatRequest, handleChatFollowUpRequest, handleKillSessionRequest } from "./chat";
import { lockLocalRepoWorkspace, syncLocalRepoWorkspace } from "./repo-lock";
import { setSessionConfig, getSessionConfig, clearSessionConfig, getSessionConfigSummary, type SessionConfig } from "./session-config";
import "dotenv/config";
import { build } from "esbuild";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { join, normalize, dirname } from "node:path";
import { Readable } from "node:stream";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

type ModelOption = { label: string; value: string };

const require = createRequire(import.meta.url);
const swaggerUiDistPath = dirname(require.resolve("swagger-ui-dist/package.json"));
const swaggerSpec = JSON.parse(
  await readFile(join(dirname(fileURLToPath(import.meta.url)), "swagger.json"), "utf-8")
);

const ALLOWED_ORIGINS = (process.env.CORS_ALLOWED_ORIGINS ?? "*").split(",").map((o) => o.trim());

function setCorsHeaders(req: IncomingMessage, res: ServerResponse): void {
  const origin = req.headers.origin ?? "";
  if (ALLOWED_ORIGINS.includes("*") || ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", ALLOWED_ORIGINS.includes("*") ? "*" : origin);
  }
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");
  res.setHeader("Access-Control-Max-Age", "86400");
}

await build({
  entryPoints: ["src/main.tsx"],
  bundle: true,
  outfile: "public/app.js",
  format: "esm",
  platform: "browser",
  minify: true,
  sourcemap: false,
  jsx: "automatic"
});

const port = Number(process.env.PORT ?? 4300);
const hostname = process.env.HOST ?? "localhost";

const server = createServer(async (req, res) => {
  try {
    setCorsHeaders(req, res);
    const url = new URL(req.url ?? "/", `http://${hostname}:${port}`);

    // Log incoming API requests (skip static assets and swagger UI)
    if (url.pathname.startsWith("/api/") || req.method === "OPTIONS") {
      const origin = req.headers.origin ?? "same-origin";
      const ua = req.headers["user-agent"] ?? "unknown";
      const timestamp = new Date().toISOString();
      console.log(
        `[${timestamp}] ${req.method} ${url.pathname}${url.search}` +
        ` | origin=${origin}` +
        ` | ip=${req.socket.remoteAddress}` +
        ` | ua=${ua.slice(0, 80)}`
      );

      const start = performance.now();
      const origEnd = res.end.bind(res);
      res.end = ((...args: any[]) => {
        const duration = (performance.now() - start).toFixed(1);
        console.log(
          `[${new Date().toISOString()}] ${req.method} ${url.pathname} → ${res.statusCode} (${duration}ms)`
        );
        return origEnd(...args);
      }) as typeof res.end;
    }

    // Handle CORS preflight
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    // --- Swagger UI routes ---
    if (url.pathname === "/api-docs" || url.pathname === "/api-docs/") {
      res.writeHead(301, { Location: "/api-docs/index.html" });
      res.end();
      return;
    }

    if (url.pathname === "/api-docs/swagger.json") {
      sendNodeResponse(res, new Response(JSON.stringify(swaggerSpec), {
        headers: { "Content-Type": "application/json; charset=utf-8" }
      }));
      return;
    }

    if (url.pathname.startsWith("/api-docs/")) {
      const assetName = url.pathname.replace("/api-docs/", "");
      const safeName = normalize(assetName).replace(/^([/\\])+/, "");
      // Serve swagger-initializer.js override to point at our spec
      if (safeName === "swagger-initializer.js") {
        const initScript = `window.onload = function() {
  window.ui = SwaggerUIBundle({
    url: "/api-docs/swagger.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: "StandaloneLayout"
  });
};`;
        sendNodeResponse(res, new Response(initScript, {
          headers: { "Content-Type": "text/javascript; charset=utf-8" }
        }));
        return;
      }
      const assetPath = join(swaggerUiDistPath, safeName);
      try {
        const content = await readFile(assetPath);
        sendNodeResponse(res, new Response(content, {
          headers: { "Content-Type": contentTypeFor(safeName) }
        }));
      } catch {
        sendNodeResponse(res, new Response("Not found", { status: 404 }));
      }
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/markdown") {
      const filePath = join(process.cwd(), "public", "data", "mcp-boilerplate.md");
      try {
        const content = await readFile(filePath);
        sendNodeResponse(res, new Response(content, {
          headers: { "Content-Type": "text/markdown; charset=utf-8" }
        }));
      } catch {
        sendNodeResponse(res, new Response("markdown not found", { status: 404 }));
      }
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/chat") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const response = await handleChatRequest(request);
      await sendNodeResponse(res, response);
      return;
    }

    // POST /api/chat/follow-up — Send a follow-up message within an existing session
    if (req.method === "POST" && url.pathname === "/api/chat/follow-up") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const response = await handleChatFollowUpRequest(request);
      await sendNodeResponse(res, response);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/chat/events") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const response = await handleChatEventsRequest(request);
      await sendNodeResponse(res, response);
      return;
    }

    // DELETE /api/chat/kill?sessionId=xxx — Kill droid process for a session
    if (req.method === "DELETE" && url.pathname === "/api/chat/kill") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const response = await handleKillSessionRequest(request);
      await sendNodeResponse(res, response);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/models") {
      const models = await loadModelOptions();
      sendNodeResponse(res, new Response(JSON.stringify({ models }), {
        headers: { "Content-Type": "application/json; charset=utf-8" }
      }));
      return;
    }

    // --- Session Config API ---
    // POST /api/config — Set session-scoped configuration (repo URL, git credentials, etc.)
    if (req.method === "POST" && url.pathname === "/api/config") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const payload = (await request.json().catch(() => null)) as any;
      if (!payload || typeof payload !== "object" || !payload.sessionId) {
        sendNodeResponse(res, new Response(JSON.stringify({ error: "Missing sessionId in request body" }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
        return;
      }

      const sessionId = String(payload.sessionId);
      const config: SessionConfig = {};
      if (typeof payload.repoRemoteUrl === "string") config.repoRemoteUrl = payload.repoRemoteUrl;
      if (typeof payload.gitUsername === "string") config.gitUsername = payload.gitUsername;
      if (typeof payload.gitToken === "string") config.gitToken = payload.gitToken;
      if (typeof payload.repoRootDir === "string") config.repoRootDir = payload.repoRootDir;
      if (typeof payload.commitAuthorName === "string") config.commitAuthorName = payload.commitAuthorName;
      if (typeof payload.commitAuthorEmail === "string") config.commitAuthorEmail = payload.commitAuthorEmail;
      if (typeof payload.modelId === "string") config.modelId = payload.modelId;
      if (typeof payload.reasoning === "string") config.reasoning = payload.reasoning;

      setSessionConfig(sessionId, config);
      console.log(`[session-config] Config set for session ${sessionId}:`, getSessionConfigSummary(sessionId));

      sendNodeResponse(res, new Response(JSON.stringify({
        status: "ok",
        sessionId,
        applied: getSessionConfigSummary(sessionId)
      }), {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" }
      }));
      return;
    }

    // GET /api/config?sessionId=xxx — Get session config summary (tokens redacted)
    if (req.method === "GET" && url.pathname === "/api/config") {
      const sessionId = url.searchParams.get("sessionId");
      if (!sessionId) {
        sendNodeResponse(res, new Response(JSON.stringify({ error: "Missing sessionId parameter" }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
        return;
      }
      sendNodeResponse(res, new Response(JSON.stringify({
        sessionId,
        config: getSessionConfigSummary(sessionId)
      }), {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" }
      }));
      return;
    }

    // DELETE /api/config?sessionId=xxx — Clear session config
    if (req.method === "DELETE" && url.pathname === "/api/config") {
      const sessionId = url.searchParams.get("sessionId");
      if (!sessionId) {
        sendNodeResponse(res, new Response(JSON.stringify({ error: "Missing sessionId parameter" }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
        return;
      }
      clearSessionConfig(sessionId);
      sendNodeResponse(res, new Response(JSON.stringify({ status: "ok", sessionId }), {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" }
      }));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/repo/lock") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const payload = (await request.json().catch(() => null)) as any;
      if (!payload || typeof payload !== "object") {
        sendNodeResponse(res, new Response(JSON.stringify({ error: "Invalid request body" }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
        return;
      }

      try {
        const result = await lockLocalRepoWorkspace({
          mode: payload.mode,
          folderMode: payload.folderMode,
          folderName: String(payload.folderName ?? ""),
          branchName: String(payload.branchName ?? ""),
          overwriteExisting: Boolean(payload.overwriteExisting),
          sessionId: typeof payload.sessionId === "string" ? payload.sessionId : undefined,
        });
        sendNodeResponse(res, new Response(JSON.stringify(result), {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
      } catch (err) {
        sendNodeResponse(res, new Response(JSON.stringify({
          error: "Failed to configure local repo workspace",
          details: err instanceof Error ? err.message : String(err)
        }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
      }
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/repo/sync") {
      const request = await toWebRequest(req, `http://${hostname}:${port}`);
      const payload = (await request.json().catch(() => null)) as any;
      if (!payload || typeof payload !== "object") {
        sendNodeResponse(res, new Response(JSON.stringify({ error: "Invalid request body" }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
        return;
      }

      try {
        const result = await syncLocalRepoWorkspace({
          direction: payload.direction,
          localPath: String(payload.localPath ?? ""),
          branchName: String(payload.branchName ?? ""),
          sessionId: typeof payload.sessionId === "string" ? payload.sessionId : undefined,
        });
        sendNodeResponse(res, new Response(JSON.stringify(result), {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
      } catch (err) {
        sendNodeResponse(res, new Response(JSON.stringify({
          error: "Failed to sync local repo workspace",
          details: err instanceof Error ? err.message : String(err)
        }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8" }
        }));
      }
      return;
    }

    // serve static assets from ./public (url paths are absolute)
    const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
    const safePath = normalize(pathname).replace(/^([/\\])+/, "");
    const filePath = join(process.cwd(), "public", safePath);
    try {
      const content = await readFile(filePath);
      sendNodeResponse(res, new Response(content, {
        headers: { "Content-Type": contentTypeFor(pathname) }
      }));
      return;
    } catch {
      // fallthrough to 404
    }

    sendNodeResponse(res, new Response("Not found", { status: 404 }));
  } catch (err) {
    console.error("request handling failed", err);
    sendNodeResponse(
      res,
      new Response(
        JSON.stringify({
          error: "Internal server error",
          details: err instanceof Error ? err.message : String(err)
        }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" }
        }
      )
    );
  }
});

server.listen(port, hostname);

console.log(`droid chat demo ready at http://${hostname}:${port}`);
console.log(`swagger docs available at http://${hostname}:${port}/api-docs`);

async function toWebRequest(req: IncomingMessage, baseUrl: string): Promise<Request> {
  const url = new URL(req.url ?? "/", baseUrl).toString();
  const method = req.method ?? "GET";
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) {
      for (const item of value) headers.append(key, item);
    } else if (typeof value === "string") {
      headers.set(key, value);
    }
  }

  if (method === "GET" || method === "HEAD") {
    return new Request(url, { method, headers });
  }

  const bodyChunks: Buffer[] = [];
  for await (const chunk of req) {
    bodyChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  return new Request(url, {
    method,
    headers,
    body: Buffer.concat(bodyChunks)
  });
}

async function sendNodeResponse(res: ServerResponse, response: Response): Promise<void> {
  res.statusCode = response.status;
  response.headers.forEach((value, key) => {
    res.setHeader(key, value);
  });

  if (!response.body) {
    res.end();
    return;
  }

  await new Promise<void>((resolve, reject) => {
    Readable.fromWeb(response.body as unknown as NodeReadableStream).pipe(res).on("finish", resolve).on("error", reject);
  });
}

function contentTypeFor(pathname: string): string {
  if (pathname === "/app" || pathname === "/app.js") return "text/javascript; charset=utf-8";
  if (pathname.endsWith(".html")) return "text/html; charset=utf-8";
  if (pathname.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (pathname.endsWith(".css")) return "text/css; charset=utf-8";
  if (pathname.endsWith(".svg")) return "image/svg+xml";
  if (pathname.endsWith(".json")) return "application/json; charset=utf-8";
  if (pathname.endsWith(".mp3")) return "audio/mpeg";
  if (pathname.endsWith(".png")) return "image/png";
  if (pathname.endsWith(".jpg") || pathname.endsWith(".jpeg")) return "image/jpeg";
  return "application/octet-stream";
}

async function loadModelOptions(): Promise<ModelOption[]> {
  const filePath = join(process.cwd(), "models.json");
  let raw = "";
  try {
    raw = await readFile(filePath, "utf-8");
  } catch {
    return [];
  }

  let parsed: any;
  try {
    parsed = JSON.parse(raw) as any;
  } catch (err) {
    console.error("failed to parse models.json", err);
    return [];
  }

  const source = parsed?.models;

  if (Array.isArray(source)) {
    return source
      .map((item) => {
        if (typeof item === "string") return toModelOption(item);
        if (item && typeof item === "object") {
          const label = typeof (item as any).label === "string" ? (item as any).label.trim() : "";
          const value = typeof (item as any).value === "string" ? (item as any).value.trim() : "";
          if (!label || !value) return null;
          return { label, value };
        }
        return null;
      })
      .filter((item): item is ModelOption => Boolean(item));
  }

  if (source && typeof source === "object") {
    return Object.values(source)
      .map((item) => (typeof item === "string" ? toModelOption(item) : null))
      .filter((item): item is ModelOption => Boolean(item));
  }

  return [];
}

function toModelOption(label: string): ModelOption {
  const trimmed = label.trim();
  const paren = trimmed.match(/\(([^()]+)\)\s*$/);
  if (paren && paren[1]) {
    return { label: trimmed, value: paren[1].trim().toLowerCase() };
  }

  const value = trimmed
    .toLowerCase()
    .replace(/[^a-z0-9.]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return { label: trimmed, value: value || trimmed };
}
