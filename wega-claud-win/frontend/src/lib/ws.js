// Resilient chat WebSocket with exponential-backoff reconnect.
//
// Previously a single WebSocket; if the server restarted (or a network
// blip dropped the socket) the frontend silently lost connectivity and
// .send() would buffer to a never-reopening socket. Users only saw "no
// response" when sending a chat message — looked like a hung agent but
// was really a dead socket.
//
// New behaviour:
//   - Auto-reconnect with backoff: 500ms → 1s → 2s → 4s → … capped at 15s.
//   - .send() queues messages while disconnected; the queue is flushed
//     in order once a fresh socket opens.
//   - onConnectionChange callback fires on every state change so the UI
//     can surface a 'reconnecting…' pill.
//   - .close() suppresses reconnect (use when navigating away).

export function openChatSocket({ onEvent, onClose, onConnectionChange }) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  // Carry the auth token on the WS upgrade. The server rejects (401) the
  // upgrade if the token is missing or invalid, so the auto-reconnect loop
  // below will also tear down cleanly when a session expires.
  const tok = localStorage.getItem('wega.auth.token') || '';
  const url = `${proto}://${window.location.host}/ws${tok ? `?token=${encodeURIComponent(tok)}` : ''}`;

  let ws = null;
  let closedByUs = false;
  let attempts = 0;
  let reconnectTimer = null;
  const sendQueue = [];

  const setState = (state) => onConnectionChange?.(state);

  const flushQueue = () => {
    while (sendQueue.length && ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(sendQueue.shift()); } catch { break; }
    }
  };

  const connect = () => {
    setState('connecting');
    ws = new WebSocket(url);

    ws.onopen = () => {
      attempts = 0;
      setState('open');
      flushQueue();
    };

    ws.onmessage = (e) => {
      try { onEvent(JSON.parse(e.data)); }
      catch { onEvent({ type: 'error', message: 'bad event from server' }); }
    };

    ws.onclose = () => {
      onClose?.();
      if (closedByUs) { setState('closed'); return; }
      setState('reconnecting');
      const delay = Math.min(15_000, 500 * Math.pow(2, attempts));
      attempts++;
      reconnectTimer = setTimeout(connect, delay);
    };

    ws.onerror = () => { /* close handler will retry */ };
  };

  connect();

  // Queue + send an already-serialised JSON payload. Used by anything that
  // isn't a simple chat message (permission_response, future control frames).
  const sendJson = (obj) => {
    const payload = JSON.stringify(obj);
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(payload); return; } catch {}
    }
    sendQueue.push(payload);
  };

  return {
    send: (projectId, message) => sendJson({ type: 'chat', projectId, message }),
    sendJson,
    close: () => {
      closedByUs = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try { ws?.close(); } catch {}
    },
    raw: () => ws,
  };
}
