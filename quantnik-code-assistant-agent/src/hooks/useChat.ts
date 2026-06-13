import { useCallback, useRef, useState } from "react";

export type Turn = {
  id?: string;
  role: "user" | "assistant" | "meta";
  content: string;
  isHtml?: boolean;
  tone?: "muted" | "dark";
};
const REQUEST_TIMEOUT_MS = 5 * 60 * 1000 + 15_000;

type UseChatOptions = {
  onComplete?: (timedOut: boolean) => void;
};

export type ChatExecStatus = "awaiting" | "executing" | "complete" | "attention";

export function useChat(opts: UseChatOptions = {}) {
  const { onComplete } = opts;
  const [messages, setMessages] = useState<Turn[]>([]);
  const [commandOutput, setCommandOutput] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [spinnerText, setSpinnerText] = useState("Thinking...");
  const [lastCommand, setLastCommand] = useState("");
  const [chatStatus, setChatStatus] = useState<ChatExecStatus>("awaiting");
  const chimedRef = useRef(false);
  const streamingIndexRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const toolCallPayloadRef = useRef<Map<string, any>>(new Map());
  const activeSessionIdRef = useRef<string | null>(null);
  const sseAbortRef = useRef<AbortController | null>(null);

  const appendTurn = useCallback((turn: Turn) => {
    setMessages((prev) => {
      if (turn.role === "assistant") {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.content === turn.content) {
          return prev;
        }
      }
      return [...prev, turn];
    });
  }, []);

  const appendAssistantDedup = useCallback((content: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === "assistant" && last.content === content) {
        return prev;
      }
      return [...prev, { role: "assistant", content }];
    });
  }, []);

  const startAssistantStream = useCallback((text: string) => {
    setMessages((prev) => {
      const lastIdx = prev.length - 1;
      const last = prev[lastIdx];
      if (last && last.role === "assistant") {
        if (last.content === text) {
          streamingIndexRef.current = lastIdx;
          return prev;
        }
        if (text.startsWith(last.content)) {
          const copy = prev.slice();
          copy[lastIdx] = { role: "assistant", content: text };
          streamingIndexRef.current = lastIdx;
          return copy;
        }
      }
      streamingIndexRef.current = prev.length;
      return [...prev, { role: "assistant", content: text }];
    });
  }, []);

  const updateAssistantStream = useCallback((text: string) => {
    setMessages((prev) => {
      const idx = streamingIndexRef.current;
      if (idx === null || idx < 0 || idx >= prev.length) {
        return prev;
      }
      const copy = prev.slice();
      const current = copy[idx];
      if (current && current.role === "assistant") {
        const existing = current.content;
        if (!text) return prev;
        if (text === existing || existing.endsWith(text)) {
          return prev;
        }
        if (text.startsWith(existing)) {
          copy[idx] = { role: "assistant", content: text };
          return copy;
        }
        copy[idx] = { role: "assistant", content: existing + text };
      }
      return copy;
    });
  }, []);

  const sendMessage = useCallback(
    async (content: string, repo?: string, model?: string, autonomy?: string, reasoning?: string) => {
      if (!content.trim()) return;
      if (loading || inFlightRef.current) return;

      inFlightRef.current = true;

      const userTurn: Turn = { role: "user", content };
      const history = [...messages, userTurn].filter((t): t is { role: "user" | "assistant"; content: string } => t.role === "user" || t.role === "assistant");
      appendTurn(userTurn);
      setCommandOutput([]);
      setLoading(true);
      setSpinnerText("Thinking...");
      setLastCommand("");
      setChatStatus("executing");
      chimedRef.current = false;
      streamingIndexRef.current = null;
      toolCallPayloadRef.current.clear();

      const existingSessionId = activeSessionIdRef.current;
      const isFollowUp = !!existingSessionId;

      try {
        let sessionId: string;

        if (isFollowUp) {
          // Send follow-up to existing session
          const followUpResponse = await fetch("/api/chat/follow-up", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json"
            },
            body: JSON.stringify({
              sessionId: existingSessionId,
              message: content,
              model: model?.trim() || undefined,
              autonomy: autonomy?.trim().toLowerCase() || undefined,
              reasoning: reasoning?.trim().toLowerCase() || undefined
            })
          });

          if (!followUpResponse.ok) {
            const text = await followUpResponse.text().catch(() => "");
            // If session expired/not found, fall through to create a new session
            if (followUpResponse.status === 404 || followUpResponse.status === 410) {
              activeSessionIdRef.current = null;
              // Fall through to create new session below
            } else {
              appendTurn({ role: "assistant", content: text || `Error: HTTP ${followUpResponse.status}` });
              setLoading(false);
              setChatStatus("attention");
              return;
            }
          } else {
            sessionId = existingSessionId;
            // SSE stream is already open; new events will arrive automatically
            inFlightRef.current = false;
            return;
          }
        }

        // Create new session
        const controller = new AbortController();
        sseAbortRef.current = controller;

        const response = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json"
          },
          body: JSON.stringify({
            message: content,
            history,
            repo: repo?.trim() || undefined,
            model: model?.trim() || undefined,
            autonomy: autonomy?.trim().toLowerCase() || undefined,
            reasoning: reasoning?.trim().toLowerCase() || undefined
          }),
          signal: controller.signal
        });

        if (!response.ok) {
          const text = await response.text().catch(() => "");
          appendTurn({ role: "assistant", content: text || `Error: HTTP ${response.status}` });
          setLoading(false);
          setChatStatus("attention");
          return;
        }

        const sessionPayload = (await response.json().catch(() => null)) as { sessionId?: string } | null;
        sessionId = typeof sessionPayload?.sessionId === "string" ? sessionPayload.sessionId : "";
        if (!sessionId) {
          appendTurn({ role: "assistant", content: "Error: server did not return a chat session id" });
          setLoading(false);
          setChatStatus("attention");
          return;
        }

        activeSessionIdRef.current = sessionId;

        const eventsResponse = await fetch(`/api/chat/events?sessionId=${encodeURIComponent(sessionId)}`, {
          method: "GET",
          headers: {
            Accept: "text/event-stream"
          },
          signal: controller.signal
        });

        if (!eventsResponse.ok || !eventsResponse.body) {
          const text = await eventsResponse.text().catch(() => "");
          appendTurn({ role: "assistant", content: text || `Error: HTTP ${eventsResponse.status}` });
          setLoading(false);
          setChatStatus("attention");
          return;
        }

        const reader = eventsResponse.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let eventName = "message";
        let lineRemainder = "";
        let sawResponseError = false;
        let sawRenderableAssistantOutput = false;

        const flush = () => {
          if (!buffer) return;
          try {
            const payload = JSON.parse(buffer);
            handleEvent(payload, eventName);
          } catch (err) {
            appendTurn({ role: "assistant", content: buffer });
          } finally {
            buffer = "";
            eventName = "message";
          }
        };

        const toolStatus = (payload: any) => {
          const name = payload?.toolName || payload?.name || payload?.tool || "tool";
          switch (name) {
            case "LS":
              return "Listing files...";
            case "Read":
              return "Reading files...";
            case "Grep":
              return "Searching...";
            case "Glob":
              return "Finding files...";
            default:
              return "Running tool...";
          }
        };

        const escapeHtml = (value: string) =>
          value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");

        const toDisplayText = (value: any): string => {
          if (typeof value === "string") return value;
          try {
            return JSON.stringify(value);
          } catch {
            return String(value);
          }
        };

        const truncateWithHoverHtml = (value: string, max = 100) => {
          if (value.length <= max) {
            return `<span>${escapeHtml(value)}</span>`;
          }
          const short = value.slice(0, max);
          return `<span class="meta-truncate" title="${escapeHtml(value)}">${escapeHtml(short)}...</span>`;
        };

        const appendCommandOutputHtml = (html: string, tone: "muted" | "dark" = "muted", id?: string) => {
          setCommandOutput((prev) => [...prev, { id, role: "meta", content: html, isHtml: true, tone } as Turn]);
        };

        const upsertCommandOutputHtml = (id: string, html: string, tone: "muted" | "dark" = "muted") => {
          setCommandOutput((prev) => {
            const idx = prev.findIndex((turn) => (turn as any).id === id);
            if (idx === -1) {
              return [...prev, { id, role: "meta", content: html, isHtml: true, tone } as Turn];
            }
            const copy = prev.slice();
            const existing = copy[idx] as any;
            copy[idx] = { ...existing, role: "meta", content: html, isHtml: true, tone } as Turn;
            return copy;
          });
        };

        const extractSystemSessionId = (payload: any): string => {
          if (typeof payload?.session_id === "string") return payload.session_id;
          if (payload?.name === "session_id" && typeof payload?.value === "string") return payload.value;
          const params = payload?.parameters;
          if (typeof params?.session_id === "string") return params.session_id;
          if (params?.name === "session_id" && typeof params?.value === "string") return params.value;
          return "";
        };

        const toolCallIdOf = (payload: any): string => {
          const raw = payload?.id ?? payload?.toolCallId ?? payload?.call_id;
          return raw == null ? "" : String(raw);
        };

        const formatToolCallHtml = (payload: any, status: "In Progress" | "Complete") => {
          const id = toolCallIdOf(payload) || "unknown";
          const toolName = String(payload?.toolName || payload?.name || payload?.tool || "tool");
          const params = toDisplayText(payload?.parameters ?? payload?.args ?? payload?.input ?? "");
          const statusClass = status === "Complete" ? "complete" : "in-progress";
          const content = [
            `<span class="meta-label">tool_call</span>`,
            `<span class="meta-kv">id=<span class="meta-value">${escapeHtml(id)}</span></span>`,
            `<span class="meta-kv">toolName=<span class="meta-value">${escapeHtml(toolName)}</span></span>`,
            `<span class="meta-kv">parameters=${truncateWithHoverHtml(params)}</span>`,
            `<span class="meta-status ${statusClass}">${status}</span>`
          ].join(" ");
          return `<span class="meta-event meta-event-tool-call">${content}</span>`;
        };

        const formatToolResultHtml = (payload: any) => {
          const id = toolCallIdOf(payload) || "unknown";
          const isError = Boolean(payload?.isError ?? payload?.error);
          const value = toDisplayText(payload?.value ?? payload?.result ?? payload?.text ?? payload?.error ?? "");
          const content = [
            `<span class="meta-label">tool_result</span>`,
            `<span class="meta-kv">id=<span class="meta-value">${escapeHtml(id)}</span></span>`,
            `<span class="meta-kv">isError=<span class="meta-value">${escapeHtml(String(isError))}</span></span>`,
            `<span class="meta-kv">value=${truncateWithHoverHtml(value)}</span>`
          ].join(" ");
          return `<span class="meta-event meta-event-tool-result">${content}</span>`;
        };

        const formatSystemHtml = (payload: any) => {
          const subtype = typeof payload?.subtype === "string" ? payload.subtype : "";
          const sessionId = extractSystemSessionId(payload);
          const content = [
            `<span class="meta-label">system</span>`,
            `<span class="meta-kv">subtype=<span class="meta-value">${escapeHtml(subtype || "unknown")}</span></span>`,
            sessionId
              ? `<span class="meta-kv">session_id=<span class="meta-value">${escapeHtml(sessionId)}</span></span>`
              : ""
          ]
            .filter(Boolean)
            .join(" ");
          return `<span class="meta-event meta-event-system">${content}</span>`;
        };

        const formatCompletionMetaHtml = (payload: any) => {
          const finalText = toDisplayText(payload?.finalText ?? "");
          const content = [
            `<span class="meta-label">completion</span>`,
            `<span class="meta-kv">finalText=${truncateWithHoverHtml(finalText)}</span>`
          ].join(" ");
          return `<span class="meta-event meta-event-completion">${content}</span>`;
        };

        const formatMessageMetaHtml = (payload: any) => {
          const role = typeof payload?.role === "string" ? payload.role : "unknown";
          const text = toDisplayText(payload?.text ?? payload?.value ?? payload ?? "");
          const content = [
            `<span class="meta-label">message</span>`,
            `<span class="meta-kv">role=<span class="meta-value">${escapeHtml(role)}</span></span>`,
            `<span class="meta-kv">text=${truncateWithHoverHtml(text)}</span>`
          ].join(" ");
          return `<span class="meta-event meta-event-message">${content}</span>`;
        };

        const toMetaPayloadText = (payload: any) => {
          try {
            return JSON.stringify(payload);
          } catch {
            return String(payload);
          }
        };

        const toEventClass = (evt: string) => evt.toLowerCase().replace(/[^a-z0-9_-]/g, "-");

        const formatGenericMetaHtml = (evt: string, payload: any, extraClass?: string) => {
          const className = ["meta-event", `meta-event-${toEventClass(evt)}`, extraClass].filter(Boolean).join(" ");
          return `<span class="${className}"><span class="meta-label">${escapeHtml(evt)}</span> <span class="meta-value">${escapeHtml(toMetaPayloadText(payload))}</span></span>`;
        };

        const handleEvent = (payload: any, evt: string) => {
          if (!payload) return;

          if (evt === "system") {
            appendCommandOutputHtml(formatSystemHtml(payload), "muted");
          } else if (evt === "tool_call") {
            const toolCallId = toolCallIdOf(payload);
            if (toolCallId) {
              toolCallPayloadRef.current.set(toolCallId, payload);
              upsertCommandOutputHtml(`tool-call:${toolCallId}`, formatToolCallHtml(payload, "In Progress"), "muted");
            } else {
              appendCommandOutputHtml(formatToolCallHtml(payload, "In Progress"), "muted");
            }
          } else if (evt === "tool_result") {
            const toolCallId = toolCallIdOf(payload);
            appendCommandOutputHtml(formatToolResultHtml(payload), "muted");
            if (toolCallId) {
              const originalCall = toolCallPayloadRef.current.get(toolCallId);
              if (originalCall) {
                upsertCommandOutputHtml(`tool-call:${toolCallId}`, formatToolCallHtml(originalCall, "Complete"), "muted");
              }
            }
          } else if (evt === "completion") {
            appendCommandOutputHtml(formatCompletionMetaHtml(payload), "muted");
          } else if (evt === "message") {
            appendCommandOutputHtml(formatMessageMetaHtml(payload), "muted");
          } else if (evt === "response" && payload?.error) {
            appendCommandOutputHtml(formatGenericMetaHtml(evt, payload, "meta-event-error"), "muted");
          } else if (evt === "turn_complete") {
            appendCommandOutputHtml(formatGenericMetaHtml(evt, payload), "muted");
          } else {
            appendCommandOutputHtml(formatGenericMetaHtml(evt, payload), "muted");
          }

          if (evt === "message" && payload.role === "assistant" && typeof payload.text === "string") {
            setMessages((prev) => [...prev, { role: "assistant", content: payload.text }]);
            streamingIndexRef.current = null;
            sawRenderableAssistantOutput = true;
            setLoading(false);
          } else if (evt === "response" && payload.error) {
            sawResponseError = true;
            const errorText =
              payload.error?.data?.error || payload.error?.data?.raw || payload.error?.message || "Unknown response error";
            appendTurn({ role: "assistant", content: `error: ${String(errorText)}` });
            sawRenderableAssistantOutput = true;
            setLoading(false);
            streamingIndexRef.current = null;
          } else if (evt === "response" && payload.result) {
            const resultText =
              typeof payload.result === "string" ? payload.result : JSON.stringify(payload.result, null, 2);
            if (streamingIndexRef.current == null) {
              appendAssistantDedup(resultText);
              sawRenderableAssistantOutput = true;
            }
            setLoading(false);
            streamingIndexRef.current = null;
          } else if (evt === "error" && payload.message) {
            appendTurn({ role: "assistant", content: `error: ${String(payload.message)}` });
            sawRenderableAssistantOutput = true;
            setLoading(false);
            inFlightRef.current = false;
            streamingIndexRef.current = null;
          } else if (evt === "completion") {
            const finalText = typeof payload.finalText === "string" ? payload.finalText.trim() : "";
            // if (finalText && !sawRenderableAssistantOutput) {
            //   // Render completion.finalText as assistant-visible chat content when no prior assistant output was shown.
            //   appendAssistantDedup(finalText);
            //   sawRenderableAssistantOutput = true;
            // }
            sawRenderableAssistantOutput = true;
            setLoading(false);
            inFlightRef.current = false;
          } else if (evt === "system") {
            const subtype = typeof payload.subtype === "string" ? payload.subtype : "update";
            setSpinnerText(`System: ${subtype}...`);
            setLoading(true);
          } else if (evt === "tool_call") {
            setSpinnerText(toolStatus(payload));
            setLoading(true);
          } else if (evt === "command" && typeof payload.text === "string") {
            setLastCommand(payload.text);
          } else if (evt === "tool_result") {
            // keep current assistant stream index so cumulative stream events
            // continue updating the same turn instead of creating duplicates
          } else if (evt === "stderr" || evt === "stderr_raw") {
            if (payload.text) {
              appendTurn({ role: "assistant", content: `stderr: ${payload.text}` });
              sawRenderableAssistantOutput = true;
            }
          } else if (evt === "turn_complete") {
            // Turn finished but session stays alive for follow-ups
            sawRenderableAssistantOutput = true;
            setLoading(false);
            inFlightRef.current = false;
            setChatStatus("complete");
            streamingIndexRef.current = null;
            if (!chimedRef.current) {
              onComplete?.(false);
              chimedRef.current = true;
            }
          } else if (evt === "exit") {
            setLoading(false);
            activeSessionIdRef.current = null;
            const isServerExit = payload && ("code" in payload || "timedOut" in payload);
            if (isServerExit && !chimedRef.current) {
              onComplete?.(Boolean(payload.timedOut));
              chimedRef.current = true;
            }
            if (isServerExit && payload.timedOut) {
              appendTurn({ role: "assistant", content: "request timed out before the model returned a final answer" });
            } else if (
              isServerExit &&
              Number(payload.code) !== 0 &&
              streamingIndexRef.current == null &&
              !sawResponseError
            ) {
              appendTurn({ role: "assistant", content: `command exited with code ${payload.code}` });
            } else if (isServerExit && Number(payload.code) === 0 && !sawRenderableAssistantOutput) {
              appendTurn({ role: "assistant", content: "No response text was produced for this prompt." });
            }

            if (isServerExit) {
              const exitCode = Number(payload.code);
              if (payload.timedOut || exitCode !== 0 || sawResponseError) {
                setChatStatus("attention");
              } else {
                setChatStatus("complete");
              }
            }

            // finalize stream for safety
            streamingIndexRef.current = null;
          }
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (!value) continue;
          const chunk = decoder.decode(value, { stream: true });
          const combined = lineRemainder + chunk;
          const lines = combined.split(/\r?\n/);
          lineRemainder = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              const raw = line.slice(5);
              buffer += raw.startsWith(" ") ? raw.slice(1) : raw;
            } else if (!line.trim()) {
              flush();
            }
          }
        }

        if (lineRemainder.startsWith("data:")) {
          const raw = lineRemainder.slice(5);
          buffer += raw.startsWith(" ") ? raw.slice(1) : raw;
        }

        flush();
        await reader.releaseLock();
        setLoading(false);
        // SSE stream ended — session is done (server sent exit event)
        activeSessionIdRef.current = null;
        sseAbortRef.current = null;
      } catch (err) {
        const isAbort = err instanceof Error && err.name === "AbortError";
        appendTurn({
          role: "assistant",
          content: isAbort ? "request timed out while waiting for server response" : err instanceof Error ? err.message : String(err)
        });
        setLoading(false);
        setChatStatus("attention");
        activeSessionIdRef.current = null;
        sseAbortRef.current = null;
      } finally {
        inFlightRef.current = false;
      }
    },
    [appendAssistantDedup, appendTurn, loading, messages, onComplete]
  );

  return { messages, commandOutput, loading, spinnerText, lastCommand, chatStatus, sendMessage };
}
