import { query } from '@anthropic-ai/claude-agent-sdk';
import fs from 'node:fs';
import { db } from '../db.js';
import { getMcpServersFromEnv, resolveProjectPath } from '../config.js';
import { applyProviderEnv } from '../routes/llm.js';

function buildQueryOptions(project, repoPaths, requestPermission, resumeId, llmModel, abortController) {
  return {
    cwd: resolveProjectPath(project),
    model: llmModel || project.model || 'claude-opus-4-7[1m]',
    // Auto-accept file edits; prompt the user via canUseTool (→ PermissionCard
    // in the chat UI) for Bash, MCPs, and anything else with real side effects.
    // The bypassPermissions default + allowDangerouslySkipPermissions=true
    // combo skipped EVERY permission check, including dangerous shell-outs.
    permissionMode: project.permission_mode || 'acceptEdits',
    allowDangerouslySkipPermissions: false,
    // Watchdog hook — the consumeTurn loop aborts via this controller when a
    // tool_use sits without a tool_result longer than MCP_TOOL_TIMEOUT_MS
    // (default 180s). Without this a wedged stdio MCP (Confluence, Jira, etc.)
    // can hang the whole turn indefinitely.
    abortController,
    settingSources: ['user', 'project', 'local'],
    skills: 'all',
    mcpServers: getMcpServersFromEnv(),
    sandbox: { enabled: false },
    additionalDirectories: repoPaths,
    // Stream the underlying Anthropic Messages API events to the host (us),
    // so we can relay token-by-token text deltas and live usage updates to
    // the WS client. Matches what `claude` CLI shows in the terminal.
    includePartialMessages: true,
    canUseTool: async (toolName, input, opts) => {
      const decision = await requestPermission({
        toolName,
        input,
        title: opts.title,
        displayName: opts.displayName,
        decisionReason: opts.decisionReason,
        blockedPath: opts.blockedPath,
        suggestions: opts.suggestions || [],
      });
      if (decision.decision === 'deny') {
        return { behavior: 'deny', message: decision.message || 'Denied by user' };
      }
      const result = { behavior: 'allow', updatedInput: input };
      if (decision.decision === 'allow_always' && opts.suggestions?.length) {
        result.updatedPermissions = opts.suggestions;
      }
      return result;
    },
    ...(resumeId ? { resume: resumeId } : {}),
  };
}

async function consumeTurn(iter, onEvent, initialSessionId, abortController) {
  let sessionId = initialSessionId;

  // Track whether a given content-block index has streamed text deltas so we
  // know to suppress the duplicate full `assistant.text` block emitted at the
  // end of the same message (otherwise the user sees the text twice).
  const streamedTextBlocks = new Set();
  let streamingMessageStarted = false;

  // Per-tool watchdog. Each tool_use we observe gets parked here; the matching
  // tool_result removes it. A timer scans the map every 5s and aborts the
  // query via abortController if any tool has been pending longer than
  // MCP_TOOL_TIMEOUT_MS. Without this a wedged stdio MCP server (e.g. the
  // Confluence stdio MCP hanging on a large ADF body) hangs the whole turn.
  const TOOL_TIMEOUT_MS = Number(process.env.MCP_TOOL_TIMEOUT_MS || 180_000);
  const pendingTools = new Map(); // toolUseId → { startedAt, name }
  let watchdogFired = false;
  const watchdog = setInterval(() => {
    if (watchdogFired) return;
    const now = Date.now();
    for (const [id, info] of pendingTools) {
      if (now - info.startedAt > TOOL_TIMEOUT_MS) {
        watchdogFired = true;
        onEvent({
          type: 'assistant_text',
          text: `⏱ Tool \`${info.name}\` (id ${id.slice(0, 8)}) exceeded ${Math.round(TOOL_TIMEOUT_MS / 1000)}s without responding — aborting this turn. The most common cause is a stdio MCP server (Jira / Confluence / Figma) hanging on a slow upstream call. Retry the same prompt; if it keeps timing out on the same tool, break the request into smaller steps or check the MCP server logs.`,
        });
        try { abortController?.abort(new Error(`tool ${info.name} timed out`)); } catch {}
        pendingTools.clear();
        return;
      }
    }
  }, 5000);

  try {
    for await (const msg of iter) {
    if (msg.type === 'system' && msg.subtype === 'init') {
      if (msg.session_id) sessionId = msg.session_id;
      onEvent({
        type: 'session',
        sessionId,
        tools: msg.tools || [],
        mcpServers: msg.mcp_servers || [],
        agents: msg.agents || [],
        model: msg.model,
        cwd: msg.cwd,
      });
      continue;
    }

    // Surface auxiliary status / retry / hook / tool-progress events so the UI
    // can show what the CLI shows ("retrying after 429", "Bash output streaming",
    // "hook X running"). Ephemeral — see ws.js for non-persistence filter.
    if (msg.type === 'system') {
      onEvent({ type: 'system_event', subtype: msg.subtype, payload: msg });
      continue;
    }

    // Token-level streaming. Anthropic Messages API events come through as
    // `stream_event` payloads — relay text/thinking deltas and live usage.
    if (msg.type === 'stream_event' && msg.event) {
      const ev = msg.event;
      if (ev.type === 'message_start' && msg.ttft_ms != null) {
        onEvent({ type: 'ttft', ms: msg.ttft_ms });
      }
      if (ev.type === 'content_block_start' && ev.content_block?.type === 'thinking') {
        onEvent({ type: 'thinking_start', index: ev.index });
      }
      if (ev.type === 'content_block_delta' && ev.delta) {
        if (ev.delta.type === 'text_delta' && ev.delta.text) {
          streamedTextBlocks.add(ev.index);
          if (!streamingMessageStarted) {
            streamingMessageStarted = true;
            onEvent({ type: 'assistant_text_start', index: ev.index });
          }
          onEvent({ type: 'assistant_text_delta', index: ev.index, textDelta: ev.delta.text });
        } else if (ev.delta.type === 'thinking_delta' && ev.delta.thinking) {
          onEvent({ type: 'assistant_thinking_delta', index: ev.index, textDelta: ev.delta.thinking });
        }
      }
      if (ev.type === 'content_block_stop') {
        onEvent({ type: 'assistant_text_stop', index: ev.index });
      }
      if (ev.type === 'message_delta' && ev.usage) {
        onEvent({ type: 'usage_update', usage: ev.usage });
      }
      continue;
    }

    if (msg.type === 'assistant' && msg.message?.content) {
      // ALWAYS emit assistant_text for every text block — even when deltas
      // streamed it live. ws.js filters delta events as ephemeral (not
      // persisted), so without this final event the reply would only exist
      // in the live stream and disappear on hard-refresh / WS reconnect.
      // The frontend handler dedups against the streaming bubble it already
      // rendered (matching text → skip the append).
      for (const block of msg.message.content) {
        if (block.type === 'text') {
          onEvent({ type: 'assistant_text', text: block.text });
        } else if (block.type === 'tool_use') {
          pendingTools.set(block.id, { startedAt: Date.now(), name: block.name });
          onEvent({ type: 'tool_use', id: block.id, name: block.name, input: block.input });
        }
      }
      // Reset for the next assistant message (which starts a fresh block-index space).
      streamedTextBlocks.clear();
      streamingMessageStarted = false;
      continue;
    }

    if (msg.type === 'user' && msg.message?.content) {
      for (const block of msg.message.content) {
        if (block.type === 'tool_result') {
          pendingTools.delete(block.tool_use_id);
          onEvent({
            type: 'tool_result',
            id: block.tool_use_id,
            content: block.content,
            isError: !!block.is_error,
          });
        }
      }
      continue;
    }

    if (msg.type === 'result') {
      onEvent({
        type: 'result',
        subtype: msg.subtype,
        durationMs: msg.duration_ms,
        totalCostUsd: msg.total_cost_usd,
        usage: msg.usage,
      });
    }
    }
  } finally {
    clearInterval(watchdog);
  }
  return sessionId;
}

export async function runTurn({ project, userMessage, onEvent, requestPermission }) {
  const repoPaths = db
    .prepare('SELECT path FROM project_repos WHERE project_id = ?')
    .all(project.id)
    .map((r) => r.path)
    .filter((p) => fs.existsSync(p));

  let resumeId = project.last_session_id || null;

  // Apply the project's LLM provider env vars before kicking off the SDK.
  // process.env mutation is fine here because this is the only inference path
  // and quantnik is single-tenant; the SDK's subprocess inherits these at spawn.
  const providerResult = applyProviderEnv(project, process.env);
  if (providerResult.wired === false) {
    onEvent({
      type: 'assistant_text',
      text: `⚠ ${providerResult.error}`,
    });
    onEvent({ type: 'result', subtype: 'provider_not_wired', durationMs: 0, totalCostUsd: 0, usage: {} });
    return { sessionId: resumeId };
  }
  if (providerResult.warning) {
    onEvent({
      type: 'assistant_text',
      text: `⚠ ${providerResult.warning}`,
    });
  }
  let llmModel = providerResult.model;

  // Cap at 2 attempts: primary, plus one recovery for stale/too-long session
  // state. Provider throttling is surfaced cleanly; there is no AWS fallback.
  for (let attempt = 1; attempt <= 2; attempt++) {
    const abortController = new AbortController();
    const iter = query({
      prompt: userMessage,
      options: buildQueryOptions(project, repoPaths, requestPermission, resumeId, llmModel, abortController),
    });
    try {
      const sessionId = await consumeTurn(iter, onEvent, resumeId, abortController);
      return { sessionId };
    } catch (err) {
      const msg = err?.message || String(err);

      // Recoverable error (a): resumed session no longer exists on disk.
      const stale = resumeId && attempt === 1 && /No conversation found with session ID/i.test(msg);

      // Recoverable error (b): cumulative conversation exceeded the model's
      // context window. Resuming with the same history would loop forever, so
      // wipe `last_session_id` AND the messages table for this project to give
      // the SDK a fresh slate, then retry the current user message once.
      const tooLong = attempt === 1 && /Prompt is too long|context.*(window|length).*(exceeded|too long)|input is too long/i.test(msg);

      // Provider throttling/overload. Quantnik is Anthropic-direct here, so
      // report the actual provider state instead of silently jumping to AWS.
      const rateLimited = /\b429\b|\b529\b|\b503\b|\b502\b|rate.?limit|overloaded/i.test(msg);

      // Non-recoverable but expected: watchdog fired on a hung tool. The
      // assistant_text explaining the abort already went to the user from
      // inside consumeTurn; here we just close out the turn gracefully so
      // the WS doesn't surface a raw error stack and the user can retry.
      const watchdogAbort = /aborted|abort.*signal|timed out|tool .* timed out/i.test(msg) && !tooLong && !stale && !rateLimited;
      if (watchdogAbort) {
        onEvent({ type: 'result', subtype: 'aborted_tool_timeout', durationMs: 0, totalCostUsd: 0, usage: {} });
        return { sessionId: resumeId };
      }

      if (rateLimited) {
        onEvent({
          type: 'assistant_text',
          text: `⚠ Anthropic returned a rate-limit or overload error. Retry in a minute, or use a lower-traffic model if this persists. Original error: ${msg.slice(0, 160)}`,
        });
        onEvent({ type: 'result', subtype: 'provider_rate_limited', durationMs: 0, totalCostUsd: 0, usage: {} });
        return { sessionId: resumeId };
      }

      if (!stale && !tooLong) throw err;

      if (tooLong) {
        db.prepare('UPDATE projects SET last_session_id = NULL WHERE id = ?').run(project.id);
        db.prepare('DELETE FROM messages WHERE project_id = ?').run(project.id);
        onEvent({
          type: 'assistant_text',
          text: '(context window full — wiped the prior conversation and restarting this turn in a fresh session. Earlier messages were dropped.)',
        });
        resumeId = null;
        continue;
      }
      if (stale) {
        db.prepare('UPDATE projects SET last_session_id = NULL WHERE id = ?').run(project.id);
        onEvent({
          type: 'assistant_text',
          text: `(prior session ${resumeId.slice(0, 7)} no longer exists on disk — starting a fresh one.)`,
        });
        resumeId = null;
        continue;
      }
    }
  }

  // Defensive: should not reach here (loop returns or throws on each iteration).
  return { sessionId: null };
}
