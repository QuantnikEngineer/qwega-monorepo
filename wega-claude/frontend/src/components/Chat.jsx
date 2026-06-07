import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { openChatSocket } from '../lib/ws.js';

function PermissionCard({ req, onDecide }) {
  const title = req.title || `Claude wants to use ${req.toolName}`;
  const inputPreview = JSON.stringify(req.input, null, 2);
  return (
    <div className="msg" style={{ background: '#2a2238', border: '1px solid #c08aff', maxWidth: '100%' }}>
      <div className="label" style={{ color: '#c08aff' }}>Permission needed</div>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      {req.decisionReason && (
        <div style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 6 }}>{req.decisionReason}</div>
      )}
      {req.blockedPath && (
        <div style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 6 }}>
          Blocked path: <code>{req.blockedPath}</code>
        </div>
      )}
      <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto' }}>{inputPreview}</pre>
      <div className="row" style={{ marginTop: 10 }}>
        <button onClick={() => onDecide('deny')}>Deny</button>
        <button onClick={() => onDecide('allow')}>Allow once</button>
        <button className="primary" onClick={() => onDecide('allow_always')}>
          Allow always (this session)
        </button>
      </div>
    </div>
  );
}

function MessageView({ m }) {
  if (m.role === 'user') {
    return <div className="msg user"><div className="label">You</div>{m.payload.text}</div>;
  }
  const p = m.payload;
  if (p.type === 'assistant_text') {
    return <div className="msg assistant"><div className="label">Claude</div>{p.text}</div>;
  }
  if (p.type === 'tool_use') {
    return (
      <div className="msg tool">
        <div className="label">→ tool: {p.name}</div>
        <pre>{JSON.stringify(p.input, null, 2)}</pre>
      </div>
    );
  }
  if (p.type === 'tool_result') {
    const text = Array.isArray(p.content)
      ? p.content.map((c) => c.text || '').join('\n')
      : (typeof p.content === 'string' ? p.content : JSON.stringify(p.content));
    return (
      <div className={`msg tool ${p.isError ? 'error' : ''}`}>
        <div className="label">← tool result {p.isError ? '(error)' : ''}</div>
        <pre>{text}</pre>
      </div>
    );
  }
  if (p.type === 'result') {
    return (
      <div className="msg tool">
        <div className="label">turn complete</div>
        <pre>{`${p.subtype} · ${p.durationMs}ms · $${p.totalCostUsd?.toFixed?.(4) ?? '?'}`}</pre>
      </div>
    );
  }
  if (p.type === 'error') {
    return <div className="msg error"><div className="label">Error</div>{p.message}</div>;
  }
  return null;
}

export function Chat({ project, onProjectUpdated, pendingSend, onPendingSent }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [pendingPerm, setPendingPerm] = useState(null);
  const [allSkills, setAllSkills] = useState([]);
  const [slashIndex, setSlashIndex] = useState(0);
  const [uploadingFor, setUploadingFor] = useState(null);
  const sockRef = useRef(null);
  const logRef = useRef(null);
  const textareaRef = useRef(null);
  const planningFileRef = useRef(null);
  const orchestratorFileRef = useRef(null);

  useEffect(() => {
    setMessages([]);
    setPendingPerm(null);
    api.getMessages(project.id).then(setMessages);
    Promise.all([
      api.listSkills(project.id).catch(() => []),
      api.inheritedSkills().catch(() => ({ user: [], plugins: [] })),
    ]).then(([projectSkills, inherited]) => {
      const merged = [
        ...projectSkills.map((s) => ({ name: s.name, source: 'project', description: '' })),
        ...(inherited.user || []).map((s) => ({ name: s.name, source: 'user', description: s.description })),
        ...(inherited.plugins || []).map((s) => ({
          name: s.name, source: `plugin: ${s.plugin}`, description: s.description,
        })),
      ];
      const seen = new Set();
      setAllSkills(merged.filter((s) => (seen.has(s.name) ? false : seen.add(s.name))));
    });
    const sock = openChatSocket({
      onEvent: (event) => {
        if (event.type === 'session') { onProjectUpdated?.(); return; }
        if (event.type === 'done') { setStreaming(false); return; }
        if (event.type === 'permission_request') { setPendingPerm(event); return; }
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', payload: event, id: `tmp-${Date.now()}-${Math.random()}` },
        ]);
      },
      onClose: () => setStreaming(false),
    });
    sockRef.current = sock;
    return () => sock.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const slashMatch = useMemo(() => input.match(/^\/([a-zA-Z0-9_-]*)$/), [input]);
  const activeUploadSkill = useMemo(() => {
    const m = input.match(/Use the (sdlc-planning|sdlc-orchestrator) skill/i);
    return m ? m[1].toLowerCase() : null;
  }, [input]);
  const filteredSkills = useMemo(() => {
    if (!slashMatch) return [];
    const q = slashMatch[1].toLowerCase();
    return allSkills
      .filter((s) => s.name.toLowerCase().includes(q))
      .slice(0, 20);
  }, [slashMatch, allSkills]);
  const popupOpen = slashMatch && filteredSkills.length > 0;

  useEffect(() => { setSlashIndex(0); }, [slashMatch?.[1], filteredSkills.length]);

  const decidePermission = (decision) => {
    if (!pendingPerm) return;
    sockRef.current.raw.send(JSON.stringify({
      type: 'permission_response',
      requestId: pendingPerm.requestId,
      decision,
    }));
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        payload: {
          type: 'assistant_text',
          text: `[permission ${decision}] ${pendingPerm.title || pendingPerm.toolName}`,
        },
        id: `perm-${pendingPerm.requestId}`,
      },
    ]);
    setPendingPerm(null);
  };

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!pendingSend || streaming) return;
    if (!sockRef.current) return;
    const text = pendingSend.message;
    setMessages((prev) => [...prev, { role: 'user', payload: { text }, id: `u-${Date.now()}` }]);
    sockRef.current.send(project.id, text);
    setStreaming(true);
    onPendingSent?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingSend?.at]);

  const send = (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || streaming) return;
    setMessages((prev) => [...prev, { role: 'user', payload: { text }, id: `u-${Date.now()}` }]);
    sockRef.current.send(project.id, text);
    if (overrideText === undefined) setInput('');
    setStreaming(true);
  };

  const handleUpload = async (skillName, file) => {
    if (!file) return;
    setUploadingFor(skillName);
    try {
      const meta = await api.uploadFile(project.id, file);
      const msg = `Use the ${skillName} skill on the uploaded file at \`${meta.relativePath}\` (original name: ${meta.originalName}, size: ${meta.size} bytes, type: ${meta.mimeType || 'unknown'}). Read it first, then proceed.`;
      send(msg);
    } catch (e) {
      alert(`Upload failed: ${e.message}`);
    }
    setUploadingFor(null);
  };

  const pickSkill = (skill) => {
    setInput(`Use the ${skill.name} skill: `);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const onKey = (e) => {
    if (popupOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSlashIndex((i) => (i + 1) % filteredSkills.length); return; }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSlashIndex((i) => (i - 1 + filteredSkills.length) % filteredSkills.length); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        pickSkill(filteredSkills[slashIndex]);
        return;
      }
      if (e.key === 'Escape') { e.preventDefault(); setInput(''); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const resetSession = async () => {
    if (!confirm('Clear chat history and start a fresh Claude session?')) return;
    await api.resetSession(project.id);
    setMessages([]);
    onProjectUpdated?.();
  };

  return (
    <div className="pane">
      <div className="chat-log" ref={logRef}>
        {messages.length === 0 && <div className="empty">No messages yet. Ask Claude anything to begin.</div>}
        {messages.map((m) => <MessageView key={m.id || m.created_at + Math.random()} m={m} />)}
        {pendingPerm && <PermissionCard req={pendingPerm} onDecide={decidePermission} />}
        {streaming && !pendingPerm && <div className="empty">…</div>}
      </div>
      <div className="composer">
        {popupOpen && (
          <div className="slash-popup">
            {filteredSkills.map((s, i) => (
              <div
                key={s.name}
                className={`slash-item ${i === slashIndex ? 'active' : ''}`}
                onMouseEnter={() => setSlashIndex(i)}
                onMouseDown={(e) => { e.preventDefault(); pickSkill(s); }}
              >
                <div>
                  <span className="name">/{s.name}</span>{' '}
                  <span className="meta">· {s.source}</span>
                </div>
                {s.description && <div className="desc">{s.description}</div>}
              </div>
            ))}
          </div>
        )}
        <input
          ref={planningFileRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => { handleUpload('sdlc-planning', e.target.files?.[0]); e.target.value = ''; }}
        />
        <input
          ref={orchestratorFileRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => { handleUpload('sdlc-orchestrator', e.target.files?.[0]); e.target.value = ''; }}
        />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Message Claude — type / to pick a skill (Enter to send, Shift+Enter for newline)"
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {activeUploadSkill && (
            <button
              onClick={() => {
                const ref = activeUploadSkill === 'sdlc-planning' ? planningFileRef : orchestratorFileRef;
                ref.current?.click();
              }}
              disabled={streaming || uploadingFor !== null}
              title={`Attach a file for ${activeUploadSkill}`}
            >
              {uploadingFor === activeUploadSkill ? 'Uploading…' : `Attach file → ${activeUploadSkill}`}
            </button>
          )}
          <button className="primary" onClick={send} disabled={streaming}>Send</button>
          <button onClick={resetSession} disabled={streaming}>Reset</button>
        </div>
      </div>
    </div>
  );
}
