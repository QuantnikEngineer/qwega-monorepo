export function openChatSocket({ onEvent, onClose }) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
  ws.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)); }
    catch { onEvent({ type: 'error', message: 'bad event from server' }); }
  };
  ws.onclose = () => onClose?.();
  return {
    send: (projectId, message) => {
      const payload = JSON.stringify({ type: 'chat', projectId, message });
      if (ws.readyState === WebSocket.OPEN) ws.send(payload);
      else ws.addEventListener('open', () => ws.send(payload), { once: true });
    },
    close: () => ws.close(),
    raw: ws,
  };
}
