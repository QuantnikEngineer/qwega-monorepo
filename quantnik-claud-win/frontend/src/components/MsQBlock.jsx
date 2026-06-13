// Ms. Q — chatbot. Lives at the top of the Chat panel as a real
// conversational surface (not a Q&A widget). Default-expanded, multi-turn,
// addresses the user by name, persists history per project to localStorage.
//
// Doesn't touch the main chat thread — independent input + answer area,
// no WebSocket use. Project-scoped retrieval: the backend pulls top-K
// chunks from the project's Context Engine (plus inherited org sources)
// and bundles Project Facts (LOC, files, repos, sources) into every turn,
// so metadata questions get conversational answers without citations.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { Btn, Pill, S } from './ui.jsx';

const LS_COLLAPSED_PREFIX = 'quantnik.brain.collapsed';
const LS_HISTORY_PREFIX   = 'quantnik.brain.history.';

// Cap stored history so the per-project key doesn't grow unbounded. The
// backend already trims to last 12 turns on read; this is the client-side
// retention budget.
const MAX_LOCAL_TURNS = 40;

function migrateBranding(text) {
  return String(text || '')
    .replaceAll('Quantnik Brain', 'Ms. Q')
    .replaceAll('Quantnik BRAIN', 'Ms. Q')
    .replaceAll('Context Fabric', 'Context Engine');
}

function migrateHistoryBranding(items) {
  if (!Array.isArray(items)) return [];
  return items.map((msg) => (
    msg && typeof msg === 'object'
      ? { ...msg, content: migrateBranding(msg.content) }
      : msg
  ));
}

// Lightweight inline-markdown for chatbot answers. No external lib —
// matches the style we used in the prior single-shot version. Escapes
// HTML first; then bold / inline-code / citations / line breaks.
function renderAnswer(text) {
  if (!text) return null;
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let html = esc(text);
  html = html.replace(/`([^`]+)`/g, '<code style="color:var(--w-phosphor);background:#eef4ff;padding:2px 6px;border-radius:6px">$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  html = html.replace(/\[(\d+)\]/g, '<span style="color:var(--w-phosphor);font-weight:600">[$1]</span>');
  html = html.replace(/\n/g, '<br/>');
  return <div style={{ color: 'var(--w-text-0)', font: '500 13px/1.65 var(--w-display)' }} dangerouslySetInnerHTML={{ __html: html }} />;
}

// Static greeter — varies a tiny bit so reopening doesn't feel canned.
// The model's own dynamic opener fires on the first user message that's
// just "hi" / "hello" / etc. (see system prompt). This is the always-shown
// "I'm here" greeting that appears the moment the user opens the block on
// a fresh project — no LLM call needed, instant.
function greeting(firstName) {
  const name = firstName || 'friend';
  const variants = [
    `Hey ${name} — I'm Ms. Q, your project's autobiographer.\n\nI've read everything you've ingested into the Context Engine: the code, the BRDs, the orchestrator's chat history, anything you've thrown at me. Ask me anything about this project and I'll dig.`,
    `Hi ${name} — Ms. Q reporting in.\n\nI know what's been ingested, what the repos look like, how many lines of code, what the orchestrator said three Tuesdays ago. Want a guided tour, or do you have something specific in mind?`,
    `${name}! What do you want to find out today?\n\nI've got the project's code metrics, every doc you've ingested, the BRD, the chat history. If it's in the Context Engine, I can pull it. If it's not, I'll point you at how to add it.`,
    `Hey ${name} ☕ Coffee or work first?\n\nReady when you are. I can answer questions about this project's code, docs, BRDs, prior agent runs — anything you've ingested. Or just ask "what do you know about this project" and I'll lay it out.`,
  ];
  return variants[Math.floor(Math.random() * variants.length)];
}

// First-name extraction: cheap and consistent with the backend's logic.
function firstNameFromMe(me) {
  if (!me?.user) return null;
  const explicit = me.user.name && String(me.user.name).trim();
  if (explicit) return explicit.split(/[ .]/)[0];
  if (me.user.email) {
    const local = String(me.user.email).split('@')[0];
    const first = local.split(/[.\-_+]/)[0];
    return first.replace(/^./, (c) => c.toUpperCase());
  }
  return null;
}

function CitationCard({ c }) {
  return (
    <div style={{
      padding: '6px 9px',
      background: 'var(--w-bg-1)',
      borderLeft: `2px solid var(--w-${c.source.scope === 'org' ? 'cyan' : 'phosphor'})`,
      borderRadius: 2,
      marginTop: 4,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
        <span style={{ color: 'var(--w-text-0)', font: '500 10.5px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.document.title || c.document.uri}>
          [{c.n}] {c.document.title || c.document.externalId || c.document.uri || '(untitled)'}
        </span>
        <span style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', flex: '0 0 auto' }}>
          score {c.score.toFixed(2)}
        </span>
      </div>
      <pre style={{ margin: '4px 0 0', color: 'var(--w-text-2)', font: '10px/1.5 var(--w-mono)', whiteSpace: 'pre-wrap', background: 'transparent', maxHeight: 56, overflow: 'hidden' }}>
        {c.preview}{c.preview.length >= 280 ? '…' : ''}
      </pre>
    </div>
  );
}

function Bubble({ msg, firstName }) {
  const isUser = msg.role === 'user';
  return (
    <div style={{
      display: 'flex',
      gap: 10,
      padding: '10px 14px',
      flexDirection: isUser ? 'row-reverse' : 'row',
    }}>
      <div style={{
        flex: '0 0 28px',
        height: 28,
        borderRadius: 14,
        background: isUser ? '#eef2f7' : 'linear-gradient(135deg, #2563eb, #14b8a6)',
        border: `1px solid var(--w-${isUser ? 'line' : 'phosphor'})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: isUser ? 'var(--w-text-1)' : '#fff',
        font: '700 12px/1 var(--w-display)',
      }}>
        {isUser ? (firstName?.[0]?.toUpperCase() || 'U') : 'Q'}
      </div>
      <div style={{
        maxWidth: '78%',
        background: isUser ? '#eef4ff' : 'transparent',
        border: isUser ? '1px solid var(--w-line)' : 'none',
        borderRadius: 14,
        padding: isUser ? '8px 12px' : '4px 0 0',
      }}>
        {isUser
          ? <div style={{ color: 'var(--w-text-0)', font: '500 13px/1.55 var(--w-display)', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
          : renderAnswer(msg.content)}

        {/* Citations + metadata for assistant turns */}
        {!isUser && msg.meta && (
          <div style={{ marginTop: 6 }}>
            {msg.meta.citations?.length > 0 && (
              <details>
                <summary style={{ color: 'var(--w-text-3)', font: '10px/1.4 var(--w-mono)', cursor: 'pointer', userSelect: 'none' }}>
                  ▸ {msg.meta.citations.length} citation{msg.meta.citations.length === 1 ? '' : 's'} · scanned {msg.meta.candidateCount} chunks
                </summary>
                <div style={{ marginTop: 4 }}>
                  {msg.meta.citations.map((c) => <CitationCard key={c.chunkId} c={c} />)}
                </div>
              </details>
            )}
            <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              <span style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)' }}>
                {msg.meta.model}
                {' · '}${msg.meta.costUsd?.toFixed(4) ?? '0.0000'}
                {' · '}retrieval {msg.meta.retrievalMs}ms · gen {msg.meta.generationMs}ms
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function MsQBlock({ project }) {
  const projectId = project?.id || 'noproj';
  const historyKey = LS_HISTORY_PREFIX + projectId;
  const collapsedKey = LS_COLLAPSED_PREFIX + '.' + projectId;

  // Collapsed state — default EXPANDED on first visit to make Ms. Q
  // visible by default. Once the user collapses it, the choice persists
  // per-project.
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(collapsedKey) === '1'; }
    catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem(collapsedKey, collapsed ? '1' : '0'); } catch {}
  }, [collapsed, collapsedKey]);

  const [firstName, setFirstName] = useState(null);
  const [history, setHistory] = useState(() => {
    try {
      const raw = localStorage.getItem(historyKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return migrateHistoryBranding(parsed);
    } catch { return []; }
  });

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const scrollRef = useRef(null);
  const greetingShownRef = useRef(false);

  // Load the human's first name once per mount.
  useEffect(() => {
    api.me().then((m) => setFirstName(firstNameFromMe(m))).catch(() => setFirstName(null));
  }, []);

  // Reset state when switching projects.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(historyKey);
      setHistory(raw ? migrateHistoryBranding(JSON.parse(raw) || []) : []);
    } catch { setHistory([]); }
    setInput('');
    setError('');
    greetingShownRef.current = false;
  }, [projectId, historyKey]);

  // Greeting — added to displayed history the first time we render with an
  // empty conversation, AFTER firstName has resolved (so it can address by
  // name). Marked as "_greeter" so it isn't sent back to the model as
  // conversation context (would be redundant; the system prompt covers it).
  useEffect(() => {
    if (greetingShownRef.current) return;
    if (history.length > 0) {
      greetingShownRef.current = true;
      return;
    }
    if (firstName === null) return; // wait until /me resolves
    greetingShownRef.current = true;
    setHistory([{
      role: 'assistant',
      content: greeting(firstName),
      _greeter: true,
      at: Date.now(),
    }]);
    // eslint-disable-next-line
  }, [firstName, history.length]);

  // Persist history to localStorage on every change. Trim to MAX_LOCAL_TURNS.
  useEffect(() => {
    try {
      const trimmed = history.slice(-MAX_LOCAL_TURNS);
      localStorage.setItem(historyKey, JSON.stringify(trimmed));
    } catch {}
  }, [history, historyKey]);

  // Auto-scroll to latest message.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history, busy]);

  const submit = async (e) => {
    e?.preventDefault?.();
    const q = input.trim();
    if (!q || !projectId || projectId === 'noproj') return;
    setError('');
    setInput('');
    // Compose the local history we send to the backend — excludes the
    // synthetic greeter (it's UI-only) and includes the new user turn.
    const sendable = history.filter((m) => !m._greeter).map(({ role, content }) => ({ role, content }));
    const newUserMsg = { role: 'user', content: q, at: Date.now() };
    setHistory((h) => [...h, newUserMsg]);
    setBusy(true);
    try {
      const r = await api.askMsQ({
        scope: 'project',
        projectId,
        question: q,
        history: sendable,
        topK: 6,
      });
      setHistory((h) => [...h, {
        role: 'assistant',
        content: r.answer || '(empty response)',
        at: Date.now(),
        meta: {
          citations: r.citations || [],
          candidateCount: r.candidateCount,
          retrieved: r.retrieved,
          model: r.model,
          via: r.via,
          fellBackReason: r.fellBackReason,
          costUsd: r.costUsd,
          retrievalMs: r.retrievalMs,
          generationMs: r.generationMs,
        },
      }]);
    } catch (e) {
      setError(e.message);
      // Drop the user turn we just optimistically added, so retry doesn't
      // re-stack it on the next attempt.
      setHistory((h) => h.slice(0, -1));
      setInput(q);
    }
    setBusy(false);
  };

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const clearHistory = () => {
    if (!confirm('Clear this conversation with Ms. Q? The retrieval index is unaffected.')) return;
    setHistory([]);
    greetingShownRef.current = false;
    try { localStorage.removeItem(historyKey); } catch {}
  };

  // ───────────────── Collapsed pill ─────────────────
  if (collapsed) {
    return (
      <div
        onClick={() => setCollapsed(false)}
        style={{
          margin: '14px 24px',
          padding: '12px 16px',
          border: '1px solid var(--w-line)',
          background: '#fff',
          borderRadius: 16,
          boxShadow: '0 10px 35px rgba(31,41,55,0.06)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          userSelect: 'none',
        }}
        title="open Ms. Q"
      >
        <span style={{ width: 28, height: 28, borderRadius: 10, background: 'linear-gradient(135deg, #2563eb, #14b8a6)', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', font: '800 13px/1 var(--w-display)' }}>Q</span>
        <span style={{ color: 'var(--w-text-0)', font: '800 14px/1 var(--w-display)' }}>Ms. Q</span>
        <span style={{ color: 'var(--w-text-2)', font: '500 12.5px/1.4 var(--w-display)' }}>
          {firstName ? `${firstName}, click to chat — ` : 'click to chat — '}
          ask anything about this project
        </span>
        <span style={{ marginLeft: 'auto', color: 'var(--w-phosphor)', font: '700 14px/1 var(--w-display)' }}>Open</span>
      </div>
    );
  }

  // ───────────────── Expanded chatbot ─────────────────
  return (
    <div style={{
      margin: '14px 24px',
      border: '1px solid var(--w-line)',
      background: '#fff',
      borderRadius: 20,
      boxShadow: '0 18px 50px rgba(31,41,55,0.08)',
      display: 'flex',
      flexDirection: 'column',
      // Reserve a generous chunk of vertical space so the chatbot is
      // visually prominent and the conversation has room to breathe.
      minHeight: 380,
      maxHeight: 560,
    }}>

      {/* Hero header — taller than the prior small pill, with personality */}
      <div style={{
        padding: '12px 18px',
        borderBottom: '1px solid var(--w-line)',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        background: 'linear-gradient(135deg, #eff6ff, #f0fdfa)',
      }}>
        <div style={{
          flex: '0 0 36px',
          height: 36,
          borderRadius: 12,
          background: 'linear-gradient(135deg, #2563eb, #14b8a6)',
          border: 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff',
          font: '800 16px/1 var(--w-display)',
        }}>Q</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ color: 'var(--w-text-0)', font: '800 15px/1 var(--w-display)' }}>
              Ms. Q
            </span>
            <Pill tone="phosphor" dot>online</Pill>
            <span style={{ color: 'var(--w-text-3)', font: '11px/1.4 var(--w-mono)' }}>
              · grounded in <a href={`/projects/${projectId}/context`} style={{ color: 'var(--w-phosphor)', textDecoration: 'none', fontWeight: 700 }}>Context Engine</a>
            </span>
          </div>
          <div style={{ color: 'var(--w-text-2)', font: '500 12px/1.4 var(--w-display)', marginTop: 4 }}>
            {firstName ? `Hey ${firstName} — ` : ''}ask anything about this project. I'll dig through the code, the docs, the agent history.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flex: '0 0 auto' }}>
          <Btn tone="ghost" onClick={clearHistory} style={{ padding: '7px 10px', borderRadius: 999 }}>
            Clear
          </Btn>
          <Btn tone="ghost" onClick={() => setCollapsed(true)} style={{ padding: '7px 10px', borderRadius: 999 }}>
            Minimize
          </Btn>
        </div>
      </div>

      {/* Conversation thread */}
      <div ref={scrollRef} style={{
        flex: 1,
        overflowY: 'auto',
        padding: '4px 0 6px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {history.map((m, i) => <Bubble key={m.at || i} msg={m} firstName={firstName} />)}
        {busy && (
          <div style={{ padding: '8px 18px', color: 'var(--w-text-3)', font: '600 12px/1.4 var(--w-display)', fontStyle: 'italic' }}>
            Thinking<span className="w-caret" />
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ margin: '0 14px 8px', padding: '8px 10px', border: '1px solid var(--w-red)', color: 'var(--w-red)', font: '600 12px/1.5 var(--w-display)', borderRadius: 10 }}>
          {error}
        </div>
      )}

      {/* Composer */}
      <form onSubmit={submit} style={{ display: 'flex', gap: 10, padding: '12px 14px 14px', borderTop: '1px solid var(--w-line)' }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder={firstName ? `Hey ${firstName} — what do you want to find out?` : `What do you want to find out?`}
          rows={2}
          style={{
            flex: 1,
            font: '500 13px/1.55 var(--w-display)',
            resize: 'vertical',
            minHeight: 40,
            maxHeight: 160,
            background: 'var(--w-bg-1)',
            color: 'var(--w-text-0)',
            border: '1px solid var(--w-line)',
            borderRadius: 12,
            padding: '8px 10px',
          }}
        />
        <Btn tone="primary" type="submit" disabled={busy || !input.trim()} style={{ alignSelf: 'flex-end', borderRadius: 999, padding: '9px 16px' }}>
          {busy ? 'Thinking...' : 'Ask'}
        </Btn>
      </form>
    </div>
  );
}
