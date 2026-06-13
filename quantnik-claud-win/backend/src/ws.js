import { WebSocketServer } from 'ws';
import crypto from 'node:crypto';
import { URL } from 'node:url';
import { db } from './db.js';
import { runTurn } from './claude/session.js';
import { userForToken } from './routes/auth.js';

export function attachWebSocket(server) {
  // Don't auto-accept upgrades — we need to check the auth token first.
  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (request, socket, head) => {
    let url;
    try { url = new URL(request.url, `http://${request.headers.host}`); }
    catch { socket.write('HTTP/1.1 400 Bad Request\r\n\r\n'); socket.destroy(); return; }
    if (url.pathname !== '/ws') return; // not ours; let other handlers (if any) deal with it
    const token = url.searchParams.get('token');
    const user = userForToken(token);
    if (!user) {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }
    wss.handleUpgrade(request, socket, head, (ws) => {
      ws.user = user;
      wss.emit('connection', ws, request);
    });
  });

  // Heartbeat — terminate any client whose pong hasn't come back within
  // one interval. Catches half-open connections (laptop slept, network
  // dropped, browser tab killed) instead of leaking them forever and
  // tying up turn-state. Without this, dead connections used to keep
  // pending permission promises pinned for the lifetime of the service.
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (ws.isAlive === false) {
        try { ws.terminate(); } catch {}
        continue;
      }
      ws.isAlive = false;
      try { ws.ping(); } catch {}
    }
  }, 30_000);
  wss.on('close', () => clearInterval(heartbeat));

  wss.on('connection', (ws) => {
    ws.isAlive = true;
    ws.on('pong', () => { ws.isAlive = true; });
    const pending = new Map();

    const send = (event) => {
      if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(event));
    };

    const requestPermission = (details) =>
      new Promise((resolve) => {
        const requestId = crypto.randomUUID();
        pending.set(requestId, resolve);
        send({ type: 'permission_request', requestId, ...details });
      });

    ws.on('message', async (raw) => {
      let msg;
      try { msg = JSON.parse(raw.toString()); }
      catch { return send({ type: 'error', message: 'invalid json' }); }

      if (msg.type === 'permission_response') {
        const resolve = pending.get(msg.requestId);
        if (resolve) {
          pending.delete(msg.requestId);
          resolve({ decision: msg.decision || 'deny', message: msg.message });
        }
        return;
      }

      if (msg.type !== 'chat') return;
      const { projectId, message } = msg;

      const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(projectId);
      if (!project) return send({ type: 'error', message: 'project not found' });
      // Access gate — the WS-upgrade auth already proved who the user is.
      // Quantnik is a shared workbench: any authenticated user can chat in
      // any project. Admin-only behavior is limited to /api/admin/*.

      db.prepare('INSERT INTO messages (project_id, role, payload) VALUES (?, ?, ?)')
        .run(projectId, 'user', JSON.stringify({ text: message }));

      // Per-token deltas, usage ticks, and session-status pings exist for the
      // live UI only — persisting them would balloon the messages table by
      // 10-100× per turn and is useless for the resume-history path (the SDK
      // already replays the final assistant blocks). Send to the WS, skip DB.
      const EPHEMERAL = new Set([
        'assistant_text_delta',
        'assistant_thinking_delta',
        'assistant_text_start',
        'assistant_text_stop',
        'thinking_start',
        'usage_update',
        'ttft',
        'system_event',
      ]);

      try {
        const { sessionId } = await runTurn({
          project,
          userMessage: message,
          onEvent: (event) => {
            send(event);
            // The SDK emits a `result` event at the end of each turn carrying
            // total_cost_usd + final usage. Persist it for the admin overview.
            // Failures here must not break the chat — wrap in try/catch.
            if (event.type === 'result') {
              try {
                const u = event.usage || {};
                db.prepare(`INSERT INTO usage_events
                  (project_id, user_id, model, session_id,
                   input_tokens, output_tokens,
                   cache_creation_input_tokens, cache_read_input_tokens,
                   total_cost_usd, duration_ms)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
                  projectId,
                  ws.user?.id ?? null,
                  project.model ?? null,
                  event.sessionId ?? null,
                  u.input_tokens ?? 0,
                  u.output_tokens ?? 0,
                  u.cache_creation_input_tokens ?? 0,
                  u.cache_read_input_tokens ?? 0,
                  event.totalCostUsd ?? 0,
                  event.durationMs ?? null,
                );
              } catch (e) {
                console.warn('[ws] usage_events insert failed:', e?.message);
              }
            }
            if (EPHEMERAL.has(event.type)) return;
            db.prepare('INSERT INTO messages (project_id, role, payload) VALUES (?, ?, ?)')
              .run(projectId, 'assistant', JSON.stringify(event));
          },
          requestPermission,
        });
        if (sessionId && sessionId !== project.last_session_id) {
          db.prepare('UPDATE projects SET last_session_id = ? WHERE id = ?').run(sessionId, projectId);
        }
        send({ type: 'done' });
      } catch (err) {
        console.error(err);
        send({ type: 'error', message: err?.message || String(err) });
      }
    });

    ws.on('close', () => {
      for (const resolve of pending.values()) {
        resolve({ decision: 'deny', message: 'WebSocket closed' });
      }
      pending.clear();
    });
  });

  return wss;
}
