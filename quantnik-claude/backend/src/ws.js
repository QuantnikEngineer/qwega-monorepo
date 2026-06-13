import { WebSocketServer } from 'ws';
import crypto from 'node:crypto';
import { db } from './db.js';
import { runTurn } from './claude/session.js';

export function attachWebSocket(server) {
  const wss = new WebSocketServer({ server, path: '/ws' });

  wss.on('connection', (ws) => {
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

      db.prepare('INSERT INTO messages (project_id, role, payload) VALUES (?, ?, ?)')
        .run(projectId, 'user', JSON.stringify({ text: message }));

      try {
        const { sessionId } = await runTurn({
          project,
          userMessage: message,
          onEvent: (event) => {
            send(event);
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
