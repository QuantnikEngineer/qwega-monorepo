import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { openChatSocket } from '../lib/ws.js';
import { Pill, KeyCap, Btn, S, formatModel } from './ui.jsx';
import { QuantnikBrainBlock } from './QuantnikBrainBlock.jsx';

const STATUS_TONE = {
  running: { tone: 'cyan', label: 'RUN', border: 'var(--w-cyan)' },
  ok:      { tone: 'phosphor', label: 'OK', border: 'var(--w-phosphor)' },
  err:     { tone: 'red', label: 'ERR', border: 'var(--w-red)' },
  warn:    { tone: 'amber', label: 'WARN', border: 'var(--w-amber)' },
  bg:      { tone: 'violet', label: 'BG', border: 'var(--w-violet)' },
};

function formatNum(n) {
  if (n == null) return '—';
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return n.toLocaleString();
  return String(n);
}

function PermissionCard({ req, onDecide }) {
  const title = req.title || `Claude wants to use ${req.toolName}`;
  const inputPreview = JSON.stringify(req.input, null, 2);
  return (
    <div style={{
      border: '1px solid var(--w-violet)',
      borderLeft: '2px solid var(--w-violet)',
      borderRadius: 3,
      background: 'rgba(179,136,255,0.06)',
      padding: '12px 14px',
      margin: '8px 0',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <Pill tone="violet" dot>permission</Pill>
        <span style={{ color: 'var(--w-text-0)', font: '600 12.5px/1.3 var(--w-mono)' }}>{title}</span>
      </div>
      {req.decisionReason && (
        <div style={{ color: 'var(--w-text-2)', font: '11.5px/1.4 var(--w-mono)', marginBottom: 6 }}>{req.decisionReason}</div>
      )}
      {req.blockedPath && (
        <div style={{ color: 'var(--w-text-2)', font: '11.5px/1.4 var(--w-mono)', marginBottom: 6 }}>
          blocked path: <S c="var(--w-amber)">{req.blockedPath}</S>
        </div>
      )}
      <pre style={{
        margin: '8px 0',
        padding: '8px 10px',
        background: 'var(--w-bg-1)',
        border: '1px solid var(--w-line)',
        borderRadius: 3,
        color: 'var(--w-text-1)',
        font: '11.5px/1.5 var(--w-mono)',
        maxHeight: 200, overflow: 'auto',
        whiteSpace: 'pre-wrap', wordBreak: 'break-all',
      }}>{inputPreview}</pre>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <Btn tone="danger" onClick={() => onDecide('deny')}>[ × ] deny</Btn>
        <Btn tone="ghost" onClick={() => onDecide('allow')}>[ ✓ ] allow once</Btn>
        <Btn tone="primary" onClick={() => onDecide('allow_always')}>[ ✓ ] allow always</Btn>
      </div>
    </div>
  );
}

function ToolUseBlock({ name, input, idx }) {
  const inputStr = typeof input === 'string' ? input : JSON.stringify(input, null, 2);
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: '2px solid var(--w-cyan)',
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      overflow: 'hidden',
      margin: '6px 0',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px',
        background: 'var(--w-bg-3)',
        borderBottom: '1px solid var(--w-line)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>#{String(idx).padStart(3, '0')}</span>
          <Pill tone="cyan" dot>tool · CALL</Pill>
          <span style={{ color: 'var(--w-text-1)', font: '12px/1.3 var(--w-mono)' }}>{name}</span>
        </div>
      </div>
      <pre style={{
        margin: 0,
        padding: '8px 12px',
        background: 'var(--w-bg-1)',
        color: 'var(--w-text-1)',
        font: '11.5px/1.55 var(--w-mono)',
        whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        maxHeight: 220, overflow: 'auto',
      }}>{inputStr}</pre>
    </div>
  );
}

function ToolResultBlock({ content, isError, idx }) {
  const text = Array.isArray(content)
    ? content.map((c) => (typeof c === 'string' ? c : c.text || JSON.stringify(c))).join('\n')
    : (typeof content === 'string' ? content : JSON.stringify(content, null, 2));
  const status = isError ? 'err' : 'ok';
  const t = STATUS_TONE[status];
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid ${t.border}`,
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      overflow: 'hidden',
      margin: '6px 0',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '6px 12px',
        background: 'var(--w-bg-3)',
        borderBottom: '1px solid var(--w-line)',
      }}>
        <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>#{String(idx).padStart(3, '0')}</span>
        <Pill tone={t.tone} dot={status === 'running'}>← result · {t.label}</Pill>
      </div>
      <pre style={{
        margin: 0,
        padding: '8px 12px',
        background: 'var(--w-bg-1)',
        color: isError ? 'var(--w-red)' : 'var(--w-text-1)',
        font: '11.5px/1.55 var(--w-mono)',
        whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        maxHeight: 240, overflow: 'auto',
      }}>{text}</pre>
    </div>
  );
}

function UserLine({ text, when }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '12px 0', borderBottom: '1px dashed var(--w-line)' }}>
      <span style={{ color: 'var(--w-phosphor)', font: '600 13px/1.5 var(--w-mono)' }}>❯</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', marginBottom: 4, letterSpacing: '0.12em', textTransform: 'uppercase' }}>USER{when ? ` · ${when}` : ''}</div>
        <div style={{ color: 'var(--w-text-0)', font: '13px/1.55 var(--w-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{text}</div>
      </div>
    </div>
  );
}

// Extended-thinking content from the model. Collapsed by default — the user
// can click the header to expand. Mirrors the CLI's chevron-collapsed
// "thinking..." block. Streams a caret while the deltas are still arriving.
// Compact, expandable feed of the SDK's auxiliary events that would otherwise
// be invisible during a streaming turn — api retries, hook lifecycle, tool
// progress, ttft markers, extended-thinking start. Shown below the
// "thinking…" indicator so the user always sees what the agent is doing now.
function LiveTracePanel({ trace, expanded, onToggle }) {
  const [openRows, setOpenRows] = useState(new Set());
  const toggleRow = (i) => {
    setOpenRows((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  };
  const recent = trace.slice(-12); // show last 12 rows; older summarised
  const hidden = trace.length - recent.length;
  return (
    <div style={{
      margin: '4px 0 10px 26px',
      border: '1px solid var(--w-line)',
      borderLeft: '2px solid var(--w-amber)',
      borderRadius: 3,
      background: 'var(--w-bg-2)',
      overflow: 'hidden',
    }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: '100%', textAlign: 'left',
          background: 'var(--w-bg-3)', border: 0,
          padding: '5px 10px',
          color: 'var(--w-text-2)',
          font: '10px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <span style={{ display: 'inline-block', transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 120ms' }}>›</span>
        live trace · {trace.length} event{trace.length === 1 ? '' : 's'}
        <span style={{ marginLeft: 'auto', color: 'var(--w-text-3)' }} className="w-pulse">●</span>
      </button>
      {expanded && (
        <div style={{ padding: '4px 0', maxHeight: 240, overflowY: 'auto' }}>
          {hidden > 0 && (
            <div style={{ color: 'var(--w-text-3)', font: '10px/1.4 var(--w-mono)', padding: '4px 12px' }}>
              … {hidden} earlier event{hidden === 1 ? '' : 's'} hidden
            </div>
          )}
          {recent.map((row, i) => {
            const idx = trace.length - recent.length + i;
            const isOpen = openRows.has(idx);
            const when = new Date(row.at).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            return (
              <div key={idx} style={{ borderTop: i === 0 ? 0 : '1px dashed var(--w-line)' }}>
                <button
                  type="button"
                  onClick={() => toggleRow(idx)}
                  style={{
                    width: '100%', textAlign: 'left',
                    background: 'transparent', border: 0,
                    padding: '4px 12px',
                    display: 'flex', alignItems: 'center', gap: 8,
                    cursor: 'pointer',
                    font: '11px/1.4 var(--w-mono)',
                    color: 'var(--w-text-1)',
                  }}
                >
                  <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', width: 56, flex: '0 0 56px' }}>{when}</span>
                  <span style={{ color: 'var(--w-amber)', font: '10.5px/1 var(--w-mono)', minWidth: 80 }}>{row.type}</span>
                  <span style={{ color: 'var(--w-text-1)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.summary}</span>
                </button>
                {isOpen && (
                  <pre style={{
                    margin: 0,
                    padding: '4px 12px 8px 76px',
                    background: 'var(--w-bg-1)',
                    color: 'var(--w-text-2)',
                    font: '10.5px/1.45 var(--w-mono)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                    maxHeight: 200, overflow: 'auto',
                  }}>{JSON.stringify(row.payload, null, 2)}</pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ClaudeThinking({ text, streaming }) {
  const [open, setOpen] = useState(false);
  const charCount = (text || '').length;
  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 0' }}>
      <span style={{ color: 'var(--w-text-3)', font: '600 12px/1.5 var(--w-mono)', width: 14, flex: '0 0 14px' }}>∴</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          style={{
            background: 'transparent', border: 0, padding: 0, cursor: 'pointer',
            color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
          aria-expanded={open}
        >
          <span style={{ transition: 'transform 120ms', transform: open ? 'rotate(90deg)' : 'none', display: 'inline-block' }}>›</span>
          THINKING{streaming ? ' · streaming' : ''} · {charCount} chars
          {streaming && <span className="w-caret" style={{ marginLeft: 4 }} />}
        </button>
        {open && (
          <div style={{
            marginTop: 6, padding: '8px 10px',
            background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 4,
            color: 'var(--w-text-2)', font: 'italic 12px/1.55 var(--w-mono)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {text}
          </div>
        )}
      </div>
    </div>
  );
}

function ClaudeText({ text, model, streaming }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '12px 0' }}>
      <span style={{ color: 'var(--w-cyan)', font: '600 12px/1.5 var(--w-mono)', width: 14, flex: '0 0 14px' }}>◊</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', marginBottom: 6, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          CLAUDE{model ? ` · ${formatModel(model)}` : ''}
        </div>
        <div style={{ color: 'var(--w-text-0)', font: '13px/1.6 var(--w-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text}
          {streaming && <span className="w-caret" style={{ marginLeft: 2 }} />}
        </div>
      </div>
    </div>
  );
}

function ResultLine({ subtype, durationMs, totalCostUsd, usage }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px',
      margin: '8px 0',
      background: 'var(--w-bg-1)',
      border: '1px solid var(--w-line)',
      borderRadius: 3,
      color: 'var(--w-text-2)',
      font: '11px/1 var(--w-mono)',
    }}>
      <Pill tone="phosphor" dot>turn · {subtype || 'done'}</Pill>
      <span>{durationMs ? `${(durationMs / 1000).toFixed(1)}s` : ''}</span>
      {totalCostUsd != null && <span style={{ color: 'var(--w-phosphor)' }}>${totalCostUsd.toFixed(4)}</span>}
      {usage && <span style={{ color: 'var(--w-text-3)' }}>· in {formatNum(usage.input_tokens)} · out {formatNum(usage.output_tokens)}</span>}
    </div>
  );
}

function TokenMeter({ usage, cost, contextWindow = 200000 }) {
  const inTokens = usage?.input_tokens || 0;
  const outTokens = usage?.output_tokens || 0;
  const cacheRead = usage?.cache_read_input_tokens || 0;
  const cacheCreate = usage?.cache_creation_input_tokens || 0;
  // Context size = everything the model saw on the last turn (input + both
  // cache buckets). The agent SDK splits the system+history into cached and
  // fresh chunks, so showing only input_tokens drastically underestimates it.
  const total = inTokens + cacheRead + cacheCreate;
  const pct = Math.min(100, (total / contextWindow) * 100);
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderRadius: 3,
      background: 'var(--w-bg-2)',
      padding: '10px 14px',
      minWidth: 260,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: 'var(--w-text-2)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>context window</span>
        <span style={{ color: 'var(--w-phosphor)', font: '10.5px/1 var(--w-mono)' }}>{pct.toFixed(1)}%</span>
      </div>
      <div style={{ height: 6, background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 2, position: 'relative', overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct}%`, background: 'linear-gradient(90deg, var(--w-phosphor) 0%, var(--w-cyan) 100%)', boxShadow: '0 0 8px var(--w-phosphor-glow)' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, font: '11px/1.4 var(--w-mono)' }}>
        <div>
          <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>in</div>
          <div style={{ color: 'var(--w-text-0)' }}>{formatNum(inTokens)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>out</div>
          <div style={{ color: 'var(--w-text-0)' }}>{formatNum(outTokens)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>cost</div>
          <div style={{ color: 'var(--w-phosphor)' }}>${(cost || 0).toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}

function RecentCmd({ cmd, onClick, count, when }) {
  return (
    <div onClick={onClick} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderBottom: '1px dashed var(--w-line)', cursor: 'pointer' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ color: 'var(--w-phosphor)', font: '11px/1 var(--w-mono)' }}>↺</span>
        <span style={{ color: 'var(--w-text-1)', font: '11px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={cmd}>{cmd}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
        {when && <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>{when}</span>}
        {count > 1 && <Pill style={{ padding: '1px 5px', fontSize: 9.5 }}>×{count}</Pill>}
      </div>
    </div>
  );
}

const STATUS_ICON = {
  pending:  { icon: '○', color: 'var(--w-text-3)' },
  running:  { icon: '◐', color: 'var(--w-cyan)', pulse: true },
  done:     { icon: '✓', color: 'var(--w-phosphor)' },
  skipped:  { icon: '↷', color: 'var(--w-text-2)' },
  failed:   { icon: '✕', color: 'var(--w-red)' },
};

function OrchestratorStatusPanel({ status, minimized, onToggle, onClose }) {
  const { phases, percent, complete, currentPhase, doneCount, runningCount, failedCount, total } = status;
  const headerColor = failedCount > 0 ? 'var(--w-red)' : complete ? 'var(--w-phosphor)' : 'var(--w-cyan)';
  const subtitle = complete
    ? 'pipeline complete'
    : currentPhase
      ? `running · phase ${currentPhase.number} of ${total} — ${currentPhase.name}`
      : `${doneCount} of ${total} done`;

  // Draggable position — null means "use default top-right anchor".
  const [pos, setPos] = React.useState(() => {
    try {
      const raw = localStorage.getItem('wega-orch-pos-v2');
      if (!raw) return null;
      const p = JSON.parse(raw);
      if (typeof p?.x === 'number' && typeof p?.y === 'number') return p;
    } catch {}
    return null;
  });
  const dragState = React.useRef(null); // { startX, startY, originX, originY }
  const panelRef = React.useRef(null);

  const onHeaderMouseDown = (e) => {
    // Ignore drags that start on the minimize / close buttons.
    if (e.target?.dataset?.noDrag === '1') return;
    if (e.button !== 0) return;
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Translate the current absolute-anchor (default top:16, right:16) into a
    // concrete left/top inside the parent so subsequent moves are smooth.
    const parent = panelRef.current.offsetParent?.getBoundingClientRect();
    const originX = rect.left - (parent?.left ?? 0);
    const originY = rect.top - (parent?.top ?? 0);
    dragState.current = { startX: e.clientX, startY: e.clientY, originX, originY };
    e.preventDefault();
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };
  const onMove = (e) => {
    if (!dragState.current) return;
    const { startX, startY, originX, originY } = dragState.current;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    const parent = panelRef.current?.offsetParent?.getBoundingClientRect();
    const w = panelRef.current?.offsetWidth ?? 320;
    const h = panelRef.current?.offsetHeight ?? 200;
    let nextX = originX + dx;
    let nextY = originY + dy;
    if (parent) {
      // Keep at least 40px of the panel inside the parent so it can't be
      // dragged completely off-screen.
      const minX = 40 - w;
      const minY = 0;
      const maxX = parent.width - 40;
      const maxY = parent.height - 30;
      nextX = Math.max(minX, Math.min(maxX, nextX));
      nextY = Math.max(minY, Math.min(maxY, nextY));
    }
    setPos({ x: nextX, y: nextY });
  };
  const onUp = () => {
    if (dragState.current && pos) {
      try { localStorage.setItem('wega-orch-pos-v2', JSON.stringify(pos)); } catch {}
    }
    dragState.current = null;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  };
  // Persist on every position settle.
  React.useEffect(() => {
    if (pos) {
      try { localStorage.setItem('wega-orch-pos-v2', JSON.stringify(pos)); } catch {}
    }
  }, [pos]);

  // Default anchor sits below the chat's top stat bar (which hosts the
  // TokenMeter on the right) so a freshly-spawned panel doesn't cover the
  // context-window readout. User can drag it anywhere.
  const positionStyle = pos
    ? { left: pos.x, top: pos.y }
    : { top: 150, right: 24 };

  const resetPosition = (e) => {
    e.preventDefault();
    setPos(null);
    try { localStorage.removeItem('wega-orch-pos-v2'); } catch {}
  };

  return (
    <div ref={panelRef} style={{
      position: 'absolute',
      ...positionStyle,
      width: minimized ? 260 : 320,
      zIndex: 25,
      background: 'rgba(13, 19, 24, 0.92)',
      backdropFilter: 'blur(8px)',
      WebkitBackdropFilter: 'blur(8px)',
      border: '1px solid var(--w-line-strong)',
      borderRadius: 6,
      boxShadow: '0 10px 30px rgba(0,0,0,0.5), 0 0 24px var(--w-phosphor-veil)',
      overflow: 'hidden',
      transition: dragState.current ? 'none' : 'width 0.18s ease',
      userSelect: dragState.current ? 'none' : 'auto',
    }}>
      {/* Header */}
      <div
        onMouseDown={onHeaderMouseDown}
        onDoubleClick={resetPosition}
        title="drag to move · double-click to reset position"
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px',
          borderBottom: '1px solid var(--w-line)',
          background: 'var(--w-bg-2)',
          cursor: dragState.current ? 'grabbing' : 'grab',
        }}>
        <span className={runningCount > 0 ? 'w-pulse' : ''} style={{ color: headerColor, font: '13px/1 var(--w-mono)' }}>
          {complete ? '✅' : failedCount > 0 ? '⚠' : '⟳'}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ color: 'var(--w-text-0)', font: '600 11.5px/1.2 var(--w-mono)', letterSpacing: '0.04em' }}>
            SDLC ORCHESTRATOR
          </div>
          <div style={{ color: 'var(--w-text-3)', font: '10px/1.3 var(--w-mono)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {subtitle}
          </div>
        </div>
        <span style={{ color: headerColor, font: '600 13px/1 var(--w-display)' }}>
          {Math.round(percent)}%
        </span>
        <span
          data-no-drag="1"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={onToggle}
          title={minimized ? 'expand' : 'minimize'}
          style={{ color: 'var(--w-text-3)', cursor: 'pointer', font: '12px/1 var(--w-mono)', padding: '0 4px' }}
        >
          {minimized ? '▢' : '–'}
        </span>
        <span
          data-no-drag="1"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={onClose}
          title="dismiss"
          style={{ color: 'var(--w-text-3)', cursor: 'pointer', font: '12px/1 var(--w-mono)', padding: '0 4px' }}
        >×</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: 'var(--w-bg-1)', position: 'relative', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${percent}%`,
          background: failedCount > 0
            ? 'linear-gradient(90deg, var(--w-amber), var(--w-red))'
            : complete
              ? 'var(--w-phosphor)'
              : 'linear-gradient(90deg, var(--w-phosphor), var(--w-cyan))',
          boxShadow: '0 0 8px var(--w-phosphor-glow)',
          transition: 'width 0.4s ease',
        }} />
      </div>

      {/* Phase list */}
      {!minimized && (
        <div style={{ padding: '8px 4px', maxHeight: 320, overflowY: 'auto' }}>
          {phases.map((ph) => {
            const t = STATUS_ICON[ph.status] || STATUS_ICON.pending;
            const isCurrent = currentPhase?.number === ph.number;
            const isRunningRow = ph.status === 'running';
            return (
              <div
                key={ph.number}
                className={isRunningRow ? 'w-row-glow' : ''}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '5px 10px',
                  borderRadius: 3,
                  background: isRunningRow ? undefined : (isCurrent ? 'var(--w-phosphor-veil)' : 'transparent'),
                  fontWeight: isRunningRow ? 600 : 400,
                }}
              >
                <span
                  className={t.pulse ? 'w-pulse' : ''}
                  style={{
                    color: t.color,
                    font: '12px/1 var(--w-mono)',
                    width: 14, textAlign: 'center', flex: '0 0 14px',
                  }}
                >{t.icon}</span>
                <span style={{
                  color: 'var(--w-text-3)',
                  font: '10px/1 var(--w-mono)',
                  width: 14, flex: '0 0 14px',
                }}>{ph.number}</span>
                <span style={{
                  color: isCurrent
                    ? 'var(--w-phosphor)'
                    : ph.status === 'done'
                      ? 'var(--w-text-0)'
                      : ph.status === 'failed'
                        ? 'var(--w-red)'
                        : 'var(--w-text-1)',
                  font: `${isCurrent ? '600' : '400'} 11.5px/1.3 var(--w-mono)`,
                  flex: 1,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{ph.name}</span>
                <span style={{
                  color: t.color,
                  font: '10px/1 var(--w-mono)',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  flex: '0 0 auto',
                }}>{ph.status}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function timeAgo(when) {
  if (!when) return '';
  const s = Math.floor((Date.now() - when) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export function Chat({ project, onProjectUpdated, pendingSend, onPendingSent, onSessionInfo }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [pendingPerm, setPendingPerm] = useState(null);
  const [allSkills, setAllSkills] = useState([]);
  const [slashIndex, setSlashIndex] = useState(0);
  const [uploadingFor, setUploadingFor] = useState(null);
  const [usage, setUsage] = useState(null);
  const [costAcc, setCostAcc] = useState(0);
  const [sessionMeta, setSessionMeta] = useState({});
  const [sparkSamples, setSparkSamples] = useState([]);
  const [ttftMs, setTtftMs] = useState(null);
  const [wsState, setWsState] = useState('connecting'); // connecting | open | reconnecting | closed
  const [liveTrace, setLiveTrace] = useState([]); // rolling stream of ephemeral events
  const [traceExpanded, setTraceExpanded] = useState(true); // show trace by default
  const [serverPhases, setServerPhases] = useState(null); // GET /api/phases/<id> — server-authoritative
  const sockRef = useRef(null);
  const logRef = useRef(null);
  const textareaRef = useRef(null);
  const planningFileRef = useRef(null);
  const orchestratorFileRef = useRef(null);
  const attachFileRef = useRef(null);

  useEffect(() => {
    setMessages([]);
    setPendingPerm(null);
    setUsage(null);
    setCostAcc(0);
    setSparkSamples([]);
    setSessionMeta({});
    setServerPhases(null);

    // Server-authoritative phase state. Poll every 4s while streaming, and
    // also re-fetch immediately after every assistant_text arrival (handled
    // in the WS branch below). Returns null when the API isn't available
    // (legacy build) — parser then provides the fallback.
    const refreshPhases = () => {
      api.listPhases(project.id).then((data) => {
        if (data && data.anyTracked) setServerPhases(data.phases);
        else setServerPhases(null);
      });
    };
    refreshPhases();
    const phasePoll = setInterval(refreshPhases, 4000);

    api.getMessages(project.id).then((msgs) => {
      setMessages(msgs);
      // Seed live counters from history so the context-window % and the
      // running total cost don't sit at 0 on page load. The "current" usage
      // is the last result event; cost is the sum of every successful turn.
      let latestUsage = null;
      let costSum = 0;
      const samples = [];
      for (const m of msgs) {
        const p = m.payload;
        if (!p || p.type !== 'result') continue;
        if (p.usage) latestUsage = p.usage;
        if (typeof p.totalCostUsd === 'number') costSum += p.totalCostUsd;
        if (typeof p.durationMs === 'number') samples.push(p.durationMs);
      }
      if (latestUsage) setUsage(latestUsage);
      if (costSum > 0) setCostAcc(costSum);
      if (samples.length) setSparkSamples(samples.slice(-30));
    });
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
        if (event.type === 'session') {
          setSessionMeta({ model: event.model, cwd: event.cwd, sessionId: event.sessionId });
          onSessionInfo?.({ tools: event.tools || [], mcpServers: event.mcpServers || [], usage: null });
          onProjectUpdated?.();
          return;
        }
        if (event.type === 'done') { setStreaming(false); return; }
        if (event.type === 'permission_request') { setPendingPerm(event); return; }
        if (event.type === 'result') {
          if (event.usage) setUsage(event.usage);
          if (event.totalCostUsd) setCostAcc((c) => c + event.totalCostUsd);
          setSparkSamples((s) => [...s.slice(-29), event.durationMs || 0]);
        }
        // Live token / cost ticks emitted mid-turn by the SDK's
        // `message_delta` events. Feed them straight into the TokenMeter so
        // the counters move while the model is still writing.
        if (event.type === 'usage_update' && event.usage) {
          setUsage((prev) => ({ ...(prev || {}), ...event.usage }));
          return; // ephemeral — don't append to messages
        }
        // CLI-parity streaming: append text deltas to the last assistant
        // bubble in place, creating one if the prior message isn't a streaming
        // text bubble. assistant_text_stop just freezes it; assistant_text_start
        // is just a heads-up. Final `assistant_text` (when it arrives) is
        // suppressed server-side if any delta streamed for that block.
        if (event.type === 'assistant_text_delta') {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.payload?.type === 'assistant_text' && last.streaming) {
              const merged = {
                ...last,
                payload: { ...last.payload, text: (last.payload.text || '') + event.textDelta },
              };
              return [...prev.slice(0, -1), merged];
            }
            return [
              ...prev,
              {
                role: 'assistant',
                streaming: true,
                payload: { type: 'assistant_text', text: event.textDelta },
                id: `stream-${Date.now()}-${Math.random()}`,
              },
            ];
          });
          return;
        }
        if (event.type === 'assistant_text_stop') {
          // Freeze the cursor on the last streaming bubble — it's done growing.
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.streaming) {
              return [...prev.slice(0, -1), { ...last, streaming: false }];
            }
            return prev;
          });
          return;
        }
        if (event.type === 'ttft' && typeof event.ms === 'number') {
          setTtftMs(event.ms);
          setLiveTrace((t) => [...t.slice(-49), { at: Date.now(), type: 'ttft', summary: `first token in ${event.ms}ms`, payload: event }]);
          return;
        }
        if (event.type === 'system_event') {
          // The SDK relays auxiliary events like api_retry, hook lifecycle,
          // tool progress, session_status, etc. Surface them as compact rows
          // in the live-trace panel so users see *what* is happening between
          // tool calls — instead of staring at a 'thinking…' indicator.
          const sub = event.subtype || 'system';
          const label = sub.replace(/_/g, ' ');
          setLiveTrace((t) => [...t.slice(-49), { at: Date.now(), type: sub, summary: label, payload: event.payload || event }]);
          return;
        }
        if (event.type === 'thinking_start') {
          setLiveTrace((t) => [...t.slice(-49), { at: Date.now(), type: 'thinking', summary: 'agent entered extended-thinking', payload: event }]);
          return;
        }
        if (event.type === 'assistant_thinking_delta' && event.textDelta) {
          // Thinking deltas merge into the most recent assistant_thinking
          // bubble while it's still streaming. Distinct payload type so we
          // can render it differently (dim, collapsed by default).
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.payload?.type === 'assistant_thinking' && last.streaming) {
              const merged = {
                ...last,
                payload: { ...last.payload, text: (last.payload.text || '') + event.textDelta },
              };
              return [...prev.slice(0, -1), merged];
            }
            return [
              ...prev,
              {
                role: 'assistant',
                streaming: true,
                payload: { type: 'assistant_thinking', text: event.textDelta },
                id: `think-${Date.now()}-${Math.random()}`,
              },
            ];
          });
          return;
        }
        if (event.type === 'assistant_text_start' || event.type === 'thinking_start' || event.type === 'system_event') {
          return; // ephemeral signaling, no UI change
        }
        // Dedup: server emits the final assistant_text after deltas finished
        // (so the row is persisted for refresh-survival), but the UI already
        // rendered the same text into the streaming bubble. If the last
        // message is a non-streaming text bubble with matching content,
        // attach the canonical id from the persisted event but DON'T append
        // a second row.
        if (event.type === 'assistant_text') {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'assistant' && last.payload?.type === 'assistant_text'
                && !last.streaming && last.payload.text === event.text) {
              return prev; // already shown, skip duplicate append
            }
            return [
              ...prev,
              { role: 'assistant', payload: event, id: `tmp-${Date.now()}-${Math.random()}` },
            ];
          });
          return;
        }
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', payload: event, id: `tmp-${Date.now()}-${Math.random()}` },
        ]);
      },
      onClose: () => setStreaming(false),
      onConnectionChange: setWsState,
    });
    sockRef.current = sock;
    return () => { clearInterval(phasePoll); sock.close(); };
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
    return allSkills.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 20);
  }, [slashMatch, allSkills]);
  const popupOpen = slashMatch && filteredSkills.length > 0;

  useEffect(() => { setSlashIndex(0); }, [slashMatch?.[1], filteredSkills.length]);

  // Track recent user messages for re-run sidebar
  const recentCommands = useMemo(() => {
    const counts = new Map();
    for (const m of messages) {
      if (m.role !== 'user') continue;
      const txt = (m.payload?.text || '').trim();
      if (!txt) continue;
      const existing = counts.get(txt) || { count: 0, last: 0 };
      counts.set(txt, { count: existing.count + 1, last: m.created_at ? m.created_at * 1000 : Date.now() });
    }
    return [...counts.entries()]
      .map(([cmd, { count, last }]) => ({ cmd, count, last }))
      .sort((a, b) => b.last - a.last)
      .slice(0, 8);
  }, [messages]);

  // Parse the latest SDLC PIPELINE STATUS block emitted by sdlc-orchestrator
  // so we can render a floating progress window in the chat view. Tolerant
  // of multiple agent rendering shapes:
  //   "Phase 1 — BRD: done"
  //   "Phase 1 — BRD: [done]"
  //   "Phase 1 — BRD: ✅ done | skipped"
  //   "**Phase 1 — BRD**: done"
  //   "| 1 | BRD | done |"   (markdown table)
  //   "Phase 1 BRD ✅ done"  (no separator at all)
  const orchestratorStatus = useMemo(() => {
    // SERVER-AUTHORITATIVE PATH — if the orchestrator has been POSTing to
    // /api/phases/<projectId>, use that as truth and bypass the parser.
    // No more agent-emission discipline required for accuracy.
    if (serverPhases && serverPhases.length > 0) {
      const allDone = serverPhases.every((p) => p.status === 'done' || p.status === 'skipped');
      const anyTracked = serverPhases.some((p) => p.status !== 'pending');
      if (anyTracked) {
        const totalPhases = serverPhases.length;
        const doneCount = serverPhases.filter((p) => p.status === 'done' || p.status === 'skipped').length;
        const runningCount = serverPhases.filter((p) => p.status === 'running').length;
        const failedCount = serverPhases.filter((p) => p.status === 'failed').length;
        const percent = totalPhases ? ((doneCount + runningCount * 0.5) / totalPhases) * 100 : 0;
        const currentPhase = serverPhases.find((p) => p.status === 'running')
          || (allDone ? null : serverPhases.find((p) => p.status === 'pending'));
        const latestAt = Math.max(...serverPhases.map((p) => p.updated_at || 0));
        return {
          phases: serverPhases.map((p) => ({ number: p.number, name: p.name, status: p.status })),
          total: totalPhases,
          doneCount,
          runningCount,
          failedCount,
          percent,
          complete: allDone,
          currentPhase,
          at: latestAt,
          source: 'server',
        };
      }
    }
    // CLIENT PARSER PATH — fallback for legacy runs that didn't POST.
    const PHASE_KEYS = ['running', 'done', 'skipped', 'failed', 'pending']; // priority order
    const STATUS_SYNONYMS = {
      'in progress': 'running',
      'in-progress': 'running',
      'complete': 'done',
      'completed': 'done',
      'success': 'done',
      'success ✅': 'done',
      '✅': 'done',
      '✓': 'done',
      'skip': 'skipped',
      'fail': 'failed',
      'error': 'failed',
      'errored': 'failed',
      '❌': 'failed',
      '✕': 'failed',
      '⚠': 'failed',
    };

    const PHASE_NAMES = {
      1: 'BRD',
      2: 'User Stories',
      3: 'Feature Dev',
      4: 'Vulnerability',
      5: 'Tech Debt',
      6: 'Test Cases',
      7: 'Test Scripts',
      8: 'Boot',
      9: 'Test Execution',
      10: 'Deployment',
      11: 'Sanity Checks',
    };

    function detectStatus(s) {
      const clean = s.toLowerCase().replace(/[*_`#\[\]]/g, '').trim();
      for (const [syn, canon] of Object.entries(STATUS_SYNONYMS)) {
        if (clean.includes(syn)) return canon;
      }
      for (const k of PHASE_KEYS) {
        if (new RegExp(`\\b${k}\\b`, 'i').test(clean)) return k;
      }
      return null;
    }

    function extractPhasesFromText(txt) {
      const lines = txt.split('\n');
      const phases = [];
      for (const line of lines) {
        // Pattern A: "Phase N — Name: status" (and any markdown wrappers)
        // Pattern B: "Phase N. Name: status" or "Phase N - Name: status"
        // Pattern C: "Phase N: status" (numbered short form, name inferred)
        const a = line.match(/Phase\s+(\d+)\s*[—\-:.]+\s*([^:│|]+?)(?:[:|│]\s*(.+))?$/i);
        // Pattern D: markdown table row "| N | Name | status |"
        const d = line.match(/^\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*(?:\||$)/);

        let num = null, rawName = null, rawStatus = null;
        if (d) {
          num = parseInt(d[1], 10);
          rawName = d[2];
          rawStatus = d[3];
        } else if (a) {
          num = parseInt(a[1], 10);
          rawName = a[2];
          rawStatus = a[3] || line; // if no explicit status part, scan the whole line
        } else {
          continue;
        }
        if (num < 1 || num > 11) continue;
        const name = (rawName || '').replace(/[*_`#]/g, '').replace(/\s+/g, ' ').trim() || PHASE_NAMES[num] || `Phase ${num}`;
        const status = detectStatus(rawStatus || '') || 'pending';
        phases.push({ number: num, name, status });
      }
      // De-dup by phase number, keep first seen.
      const seen = new Set();
      return phases.filter((p) => (seen.has(p.number) ? false : seen.add(p.number)))
        .sort((a, b) => a.number - b.number);
    }

    // Build the panel state incrementally so the user sees live phase
    // transitions instead of having to wait for a full STATUS block.
    //
    // Two scans:
    //   (1) Find the most recent FULL STATUS block as the baseline — it
    //       carries all 11 phases with explicit statuses.
    //   (2) After the baseline, walk every subsequent assistant_text and
    //       overlay any 'Phase N — Name: <status>' lines that appear (even
    //       outside a STATUS block) — last-write-wins per phase number.
    //
    // Fallback: if NO full STATUS block exists anywhere in the history
    // (orchestrator skipped emitting one and only printed narrative phase
    // lines), construct a synthetic baseline from any phase-line mentions
    // found anywhere in assistant_text — the panel still appears.
    //
    // The result: the panel updates as soon as the agent emits any single
    // phase status line, without needing to print the whole block.
    let baseline = null;
    let baselineIdx = -1;
    let baselineAt = null;
    let complete = false;
    for (let i = messages.length - 1; i >= 0; i--) {
      const p = messages[i].payload;
      if (!p || p.type !== 'assistant_text' || !p.text) continue;
      const txt = p.text;
      const hasHeader = /SDLC PIPELINE\s+(STATUS|COMPLETE)/i.test(txt);
      if (!hasHeader) continue;
      const phases = extractPhasesFromText(txt);
      if (phases.length < 3) continue;
      baseline = phases;
      baselineIdx = i;
      baselineAt = messages[i].created_at || Date.now() / 1000;
      complete = /SDLC PIPELINE\s+COMPLETE/i.test(txt) || phases.every((p) => p.status === 'done' || p.status === 'skipped');
      break;
    }
    if (!baseline) {
      // Synthetic baseline path — no full STATUS block was ever emitted.
      // Scan every assistant_text for any phase-line mention and build the
      // baseline from there. If we find at least one phase mention, render
      // the panel; otherwise return null (probably not an orchestrator run).
      const synth = new Map();
      let synthAt = null;
      for (let i = 0; i < messages.length; i++) {
        const p = messages[i].payload;
        if (!p || p.type !== 'assistant_text' || !p.text) continue;
        const phases = extractPhasesFromText(p.text);
        for (const ph of phases) {
          if (ph.status && ph.status !== 'pending') {
            synth.set(ph.number, { number: ph.number, name: PHASE_NAMES[ph.number] || ph.name, status: ph.status });
            synthAt = messages[i].created_at || synthAt;
          }
        }
      }
      if (synth.size === 0) return null;
      baseline = [...synth.values()];
      baselineIdx = -1; // no anchor message — the overlay scan below will be a no-op (synth already absorbed everything)
      baselineAt = synthAt || Date.now() / 1000;
    }

    // Backfill missing canonical phases as 'pending' so a partial render
    // (e.g. agent forgot to print Phase 1) still surfaces an 11-row panel.
    if (baseline.length < 11) {
      const have = new Set(baseline.map((p) => p.number));
      for (const numStr of Object.keys(PHASE_NAMES)) {
        const num = parseInt(numStr, 10);
        if (!have.has(num)) baseline.push({ number: num, name: PHASE_NAMES[num], status: 'pending' });
      }
      baseline.sort((a, b) => a.number - b.number);
    }

    // Overlay newer per-line updates emitted after the baseline message.
    const phaseMap = new Map(baseline.map((p) => [p.number, { ...p }]));
    let foundAt = baselineAt;
    for (let i = baselineIdx + 1; i < messages.length; i++) {
      const p = messages[i].payload;
      if (!p || p.type !== 'assistant_text' || !p.text) continue;
      const partials = extractPhasesFromText(p.text);
      if (!partials.length) continue;
      for (const ph of partials) {
        if (!phaseMap.has(ph.number)) continue; // out-of-range, skip
        const detectedStatus = ph.status && ph.status !== 'pending' ? ph.status : null;
        if (!detectedStatus) continue;
        phaseMap.set(ph.number, { ...phaseMap.get(ph.number), name: ph.name || phaseMap.get(ph.number).name, status: detectedStatus });
        foundAt = messages[i].created_at || foundAt;
      }
      if (/SDLC PIPELINE\s+COMPLETE/i.test(p.text)) complete = true;
    }
    const found = [...phaseMap.values()].sort((a, b) => a.number - b.number);

    // INFERENCE 1 — sequential ordering. Phases run in order. If Phase N
    // is running or done, every Phase M < N must be done unless explicitly
    // marked skipped or failed. The orchestrator sometimes forgets to emit
    // 'Phase M: done' lines and the panel sticks showing earlier phases
    // as 'running' forever.
    const maxStartedNumber = Math.max(
      0,
      ...found.filter((p) => p.status === 'running' || p.status === 'done').map((p) => p.number)
    );
    for (const p of found) {
      if (p.number < maxStartedNumber && (p.status === 'pending' || p.status === 'running')) {
        p.status = 'done';
      }
    }

    // INFERENCE 2 — stale-running. If the latest assistant_text mentioned a
    // phase as 'running' but the user has since sent a follow-up message
    // AND the agent replied to that follow-up, the running phase finished
    // in between (otherwise the agent couldn't engage with the follow-up).
    // Find the last 'running' emission timestamp, then check whether a
    // user→assistant exchange happened after it.
    let lastRunningAt = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.payload?.type === 'assistant_text' && /Phase\s+\d+[^:]*:\s*[^\n]*\brunning\b/i.test(m.payload.text || '')) {
        lastRunningAt = m.created_at || 0;
        break;
      }
    }
    if (lastRunningAt) {
      const userAfter = messages.some((m) => m.role === 'user' && (m.created_at || 0) > lastRunningAt);
      const assistantAfterUser = userAfter && messages.some((m, idx) =>
        m.role === 'assistant'
        && (m.created_at || 0) > lastRunningAt
        && messages.slice(0, idx).some((u) => u.role === 'user' && (u.created_at || 0) > lastRunningAt)
      );
      if (assistantAfterUser) {
        for (const p of found) {
          if (p.status === 'running') p.status = 'done';
        }
      }
    }

    if (!complete) {
      complete = found.every((p) => p.status === 'done' || p.status === 'skipped');
    }
    const totalPhases = found.length;
    const doneCount = found.filter((p) => p.status === 'done' || p.status === 'skipped').length;
    const runningCount = found.filter((p) => p.status === 'running').length;
    const failedCount = found.filter((p) => p.status === 'failed').length;
    const percent = totalPhases ? ((doneCount + runningCount * 0.5) / totalPhases) * 100 : 0;
    const currentPhase = found.find((p) => p.status === 'running')
      || (complete ? null : found.find((p) => p.status === 'pending'));
    return {
      phases: found,
      total: totalPhases,
      doneCount,
      runningCount,
      failedCount,
      percent,
      complete,
      currentPhase,
      at: foundAt,
      source: 'parser',
    };
  }, [messages, serverPhases]);

  const [statusDismissed, setStatusDismissed] = useState(false);
  const [statusMinimized, setStatusMinimized] = useState(false);
  const statusSig = orchestratorStatus
    ? `${orchestratorStatus.at}:${orchestratorStatus.phases.map((p) => `${p.number}${p.status[0]}`).join('')}`
    : null;
  // Reset dismissal whenever a new status block appears.
  useEffect(() => { setStatusDismissed(false); }, [statusSig]);

  // Extract Atlassian URLs referenced anywhere in this chat so the right rail
  // can show every Jira issue and Confluence page the agent (or user) created.
  const atlassianRefs = useMemo(() => {
    const jira = new Map();        // key -> { key, summary?, url }
    const confluence = new Map();  // url -> { title, url }

    // Walk all message payloads collecting text we should scan.
    const texts = [];
    const inputs = [];
    const results = [];

    for (const m of messages) {
      const p = m.payload;
      if (!p) {
        if (m.role === 'user' && typeof m.payload?.text === 'string') texts.push(m.payload.text);
        continue;
      }
      if (p.type === 'assistant_text' && p.text) texts.push(p.text);
      if (p.type === 'tool_use') inputs.push({ name: p.name, input: p.input });
      if (p.type === 'tool_result') {
        const t = Array.isArray(p.content)
          ? p.content.map((c) => (typeof c === 'string' ? c : c.text || JSON.stringify(c))).join('\n')
          : typeof p.content === 'string' ? p.content : JSON.stringify(p.content);
        results.push({ text: t });
      }
      if (m.role === 'user' && typeof p.text === 'string') texts.push(p.text);
    }

    // 1) Pull anything that looks like an Atlassian browse/wiki URL out of text.
    const urlRe = /https?:\/\/([\w-]+)\.atlassian\.net\/(browse\/[A-Z][A-Z0-9_]+-\d+|wiki\/[^\s)"'`<]+)/g;
    const scanText = (s) => {
      if (!s) return;
      let m;
      while ((m = urlRe.exec(s)) !== null) {
        const site = m[1];
        const path = m[2];
        const url = `https://${site}.atlassian.net/${path}`;
        if (path.startsWith('browse/')) {
          const key = path.slice('browse/'.length);
          if (!jira.has(key)) jira.set(key, { key, url });
        } else {
          // wiki/spaces/<space>/pages/<id>/<slug...>  OR  wiki/pages/viewpage.action?pageId=<id>
          let title = '';
          const slugMatch = path.match(/\/pages\/\d+\/([^/?#]+)/);
          if (slugMatch) {
            try { title = decodeURIComponent(slugMatch[1]).replace(/\+/g, ' '); }
            catch { title = slugMatch[1].replace(/\+/g, ' '); }
          } else {
            const idMatch = path.match(/pageId=(\d+)/);
            title = idMatch ? `Page ${idMatch[1]}` : 'Confluence page';
          }
          if (!confluence.has(url)) confluence.set(url, { title, url });
        }
      }
    };

    for (const t of texts) scanText(t);
    for (const r of results) scanText(r.text);

    // 2) Capture create-issue/page calls so we get titles even before the agent prints the URL.
    const siteFromUrl = (() => {
      for (const v of jira.values()) return v.url.match(/https?:\/\/([\w-]+)\.atlassian\.net/)?.[1];
      for (const v of confluence.values()) return v.url.match(/https?:\/\/([\w-]+)\.atlassian\.net/)?.[1];
      return null;
    })();

    // Pair each create tool_use with its next tool_result (linear scan).
    let pendingCreates = []; // {kind: 'jira'|'confluence', summary, type?}
    for (const m of messages) {
      const p = m.payload;
      if (!p) continue;
      if (p.type === 'tool_use') {
        const name = p.name || '';
        const input = p.input || {};
        if (
          name === 'mcp__Jira__jira_post' &&
          typeof input.path === 'string' &&
          /\/rest\/api\/\d+\/issue(\/|\?|$)/.test(input.path) &&
          input.body?.fields?.summary
        ) {
          pendingCreates.push({
            kind: 'jira',
            summary: input.body.fields.summary,
            type: input.body.fields.issuetype?.name || '',
          });
        } else if (name === 'mcp__claude_ai_Atlassian__createJiraIssue' && input.summary) {
          pendingCreates.push({
            kind: 'jira',
            summary: input.summary,
            type: input.issueTypeName || '',
          });
        } else if (
          name === 'mcp__Confluence__conf_post' &&
          typeof input.path === 'string' &&
          /\/wiki\/api\/v2\/pages/.test(input.path) &&
          input.body?.title
        ) {
          pendingCreates.push({ kind: 'confluence', summary: input.body.title });
        } else if (name === 'mcp__claude_ai_Atlassian__createConfluencePage' && input.title) {
          pendingCreates.push({ kind: 'confluence', summary: input.title });
        }
      }
      if (p.type === 'tool_result' && pendingCreates.length > 0) {
        const pc = pendingCreates.shift();
        const t = Array.isArray(p.content)
          ? p.content.map((c) => (typeof c === 'string' ? c : c.text || JSON.stringify(c))).join('\n')
          : typeof p.content === 'string' ? p.content : JSON.stringify(p.content);
        if (pc.kind === 'jira') {
          const km = t.match(/\bkey:\s*"?([A-Z][A-Z0-9_]+-\d+)"?/) || t.match(/"key"\s*:\s*"([A-Z][A-Z0-9_]+-\d+)"/);
          if (km) {
            const key = km[1];
            const site = siteFromUrl || 'sandboxwipro2025';
            const url = `https://${site}.atlassian.net/browse/${key}`;
            jira.set(key, { key, summary: pc.summary, url, type: pc.type });
          }
        } else {
          const im = t.match(/\bid:\s*"?(\d+)"?/) || t.match(/"id"\s*:\s*"(\d+)"/);
          const wm = t.match(/\bwebui:\s*"?([^"\s]+)"?/) || t.match(/"webui"\s*:\s*"([^"]+)"/);
          if (im) {
            const id = im[1];
            const site = siteFromUrl || 'sandboxwipro2025';
            const url = wm
              ? `https://${site}.atlassian.net/wiki${wm[1]}`
              : `https://${site}.atlassian.net/wiki/pages/viewpage.action?pageId=${id}`;
            confluence.set(url, { title: pc.summary, url });
          }
        }
      }
    }

    return {
      // Only surface Epics in the Jira rail — drop stories, tasks, and unknown-type
      // URLs (the bare-URL regex path can't determine type, so those are excluded).
      jira: [...jira.values()].filter((j) => j.type === 'Epic'),
      confluence: [...confluence.values()],
    };
  }, [messages]);

  const decidePermission = (decision) => {
    if (!pendingPerm) return;
    // Use the lib's sendJson — survives WS reconnects (queues + flushes) and
    // doesn't depend on `.raw` being a property (it's a function now).
    sockRef.current?.sendJson?.({
      type: 'permission_response',
      requestId: pendingPerm.requestId,
      decision,
    });
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        payload: { type: 'assistant_text', text: `[permission ${decision}] ${pendingPerm.title || pendingPerm.toolName}` },
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
    setTtftMs(null); // fresh turn — clear last TTFT so the pill updates
    setLiveTrace([]); // fresh turn — drop the prior trace
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
    setTtftMs(null);
  };

  const handleUpload = async (skillName, file) => {
    if (!file) return;
    setUploadingFor(skillName);
    try {
      const meta = await api.uploadFile(project.id, file);
      const msg = `Use the ${skillName} skill on the uploaded file at \`${meta.relativePath}\` (original name: ${meta.originalName}, size: ${meta.size} bytes, type: ${meta.mimeType || 'unknown'}). Read it first, then proceed.`;
      send(msg);
    } catch (e) { alert(`upload failed: ${e.message}`); }
    setUploadingFor(null);
  };

  // Universal attach — uploads any file (incl. images, pdfs, docs) and appends a
  // @uploads/<path> reference to whatever the user is composing. The user keeps
  // typing and decides when to send.
  const handleAttach = async (file) => {
    if (!file) return;
    setUploadingFor('attach');
    try {
      const meta = await api.uploadFile(project.id, file);
      const ref = `@${meta.relativePath}`;
      setInput((prev) => {
        const sep = prev && !prev.endsWith(' ') && !prev.endsWith('\n') ? ' ' : '';
        return `${prev}${sep}${ref} `;
      });
      setTimeout(() => textareaRef.current?.focus(), 0);
    } catch (e) { alert(`upload failed: ${e.message}`); }
    setUploadingFor(null);
  };

  const pickSkill = (skill) => {
    setInput(`/${skill.name} `);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const onKey = (e) => {
    if (popupOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSlashIndex((i) => (i + 1) % filteredSkills.length); return; }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSlashIndex((i) => (i - 1 + filteredSkills.length) % filteredSkills.length); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pickSkill(filteredSkills[slashIndex]); return; }
      if (e.key === 'Escape')    { e.preventDefault(); setInput(''); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const resetSession = async () => {
    if (!confirm('clear chat history and start a fresh Claude session?')) return;
    await api.resetSession(project.id);
    setMessages([]);
    setUsage(null);
    setCostAcc(0);
    onProjectUpdated?.();
  };

  let toolIdx = 0;

  const renderMessage = (m) => {
    if (m.role === 'user') {
      const when = m.created_at ? new Date(m.created_at * 1000).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }) : '';
      return <UserLine key={m.id || m.created_at} text={m.payload?.text || ''} when={when} />;
    }
    const p = m.payload;
    if (!p) return null;
    if (p.type === 'assistant_text') return <ClaudeText key={m.id} text={p.text} model={sessionMeta.model} streaming={m.streaming} />;
    if (p.type === 'assistant_thinking') return <ClaudeThinking key={m.id} text={p.text} streaming={m.streaming} />;
    if (p.type === 'tool_use')    { toolIdx++; return <ToolUseBlock key={m.id} name={p.name} input={p.input} idx={toolIdx} />; }
    if (p.type === 'tool_result') return <ToolResultBlock key={m.id} content={p.content} isError={p.isError} idx={toolIdx} />;
    if (p.type === 'result')      return <ResultLine key={m.id} {...p} />;
    if (p.type === 'error')       return <ToolResultBlock key={m.id} content={p.message} isError idx={toolIdx} />;
    return null;
  };

  return (
    <div style={{ display: 'flex', flex: 1, minHeight: 0, background: 'var(--w-bg-0)', position: 'relative' }}>
      {/* Floating SDLC orchestrator status — hoisted to the chat row so the
          user can drag it anywhere in the chat view, including over the
          right rail. It's no longer confined to the center stream column. */}
      {orchestratorStatus && !statusDismissed && (
        <OrchestratorStatusPanel
          status={orchestratorStatus}
          minimized={statusMinimized}
          onToggle={() => setStatusMinimized((v) => !v)}
          onClose={() => setStatusDismissed(true)}
        />
      )}
      {/* Center stream */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top stat bar */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          padding: '14px 22px',
          borderBottom: '1px solid var(--w-line)',
          background: 'var(--w-bg-1)',
          gap: 20,
          flex: '0 0 auto',
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
              session · {(sessionMeta.sessionId || project.last_session_id || '—').slice(0, 7)}
            </div>
            <div style={{ font: '15px/1.3 var(--w-mono)', color: 'var(--w-text-0)' }}>
              <span style={{ color: 'var(--w-phosphor)' }}>{project.name}</span>
              <span style={{ color: 'var(--w-text-3)' }}> ━ </span>
              <span style={{ color: 'var(--w-text-1)' }} title={project.path}>
                {project.path.split(/[/\\]/).slice(-2).join('/')}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              {wsState !== 'open' ? (
                <Pill tone="amber" dot title="WebSocket dropped — reconnecting with backoff. Your typed messages are queued and will flush on reconnect.">
                  {wsState === 'connecting' ? 'connecting…' : wsState === 'reconnecting' ? 'reconnecting…' : 'disconnected'}
                </Pill>
              ) : (
                <Pill tone={streaming ? 'cyan' : 'phosphor'} dot>{streaming ? 'agent streaming' : 'agent ready'}</Pill>
              )}
              {ttftMs != null && (
                <Pill title="time to first token — model latency before output started">
                  ttft · {ttftMs < 1000 ? `${ttftMs}ms` : `${(ttftMs / 1000).toFixed(2)}s`}
                </Pill>
              )}
              <Pill>{messages.filter((m) => m.payload?.type === 'tool_use').length} tool calls</Pill>
              <Pill>git · {project.path.includes('chirp') ? 'main' : '—'}</Pill>
            </div>
          </div>
          <TokenMeter usage={usage} cost={costAcc} />
        </div>

        {/* Quantnik Brain — chat-side RAG Q&A. Collapsed by default. */}
        <QuantnikBrainBlock project={project} />

        {/* Stream */}
        <div ref={logRef} style={{ flex: 1, overflowY: 'auto', padding: '0 22px' }}>
          {messages.length === 0 && (
            <div style={{ padding: '40px 0', color: 'var(--w-text-3)', font: '12px/1.6 var(--w-mono)', textAlign: 'center' }}>
              no messages yet. ask claude anything to begin.<span className="w-caret" />
            </div>
          )}
          {messages.map(renderMessage)}
          {pendingPerm && <PermissionCard req={pendingPerm} onDecide={decidePermission} />}
          {streaming && !pendingPerm && (() => {
            // Derive a context-aware activity label from the latest event types.
            // Falls back to "thinking…" only when truly nothing else has happened.
            const lastMsg = messages[messages.length - 1];
            const lastTrace = liveTrace[liveTrace.length - 1];
            let label = 'thinking…';
            if (lastMsg?.streaming && lastMsg.payload?.type === 'assistant_text') label = 'writing reply…';
            else if (lastMsg?.streaming && lastMsg.payload?.type === 'assistant_thinking') label = 'reasoning (extended thinking)…';
            else if (lastMsg?.payload?.type === 'tool_use') label = `running tool · ${lastMsg.payload.name}`;
            else if (lastMsg?.payload?.type === 'tool_result') label = 'processing result…';
            else if (lastTrace?.type === 'api_retry') label = `retrying API call · ${lastTrace.summary}`;
            else if (lastTrace?.summary) label = lastTrace.summary;
            return (
              <div>
                <div style={{ display: 'flex', gap: 12, padding: '12px 0 0' }}>
                  <span style={{ color: 'var(--w-cyan)', font: '600 12px/1.5 var(--w-mono)', width: 14, flex: '0 0 14px' }} className="w-pulse">◊</span>
                  <div style={{ color: 'var(--w-text-1)', font: '12px/1 var(--w-mono)' }}>{label}<span className="w-caret" style={{ marginLeft: 4 }} /></div>
                </div>
                {liveTrace.length > 0 && (
                  <LiveTracePanel
                    trace={liveTrace}
                    expanded={traceExpanded}
                    onToggle={() => setTraceExpanded((v) => !v)}
                  />
                )}
              </div>
            );
          })()}
          {/* Idle / awaiting-input indicator. Distinguish between:
              • "your turn" — the agent literally asked a question or printed
                a 'reply with…' prompt and is blocking on the answer. Cyan,
                assertive copy.
              • "ready" — the agent finished its work and is just sitting
                idle waiting for whatever you want to do next. Dim, lower-key.
              The difference matters: an orchestrator finishing Phase 11
              shouldn't shout "your turn" — the pipeline is done. */}
          {!streaming && !pendingPerm && messages.length > 0
            && messages[messages.length - 1].role === 'assistant' && (() => {
            // Walk back across assistant_text + tool_use messages from the
            // tail until we hit a user message or run out — we want the
            // "outgoing" tail of the assistant's turn, not just the very
            // last event (which is often a `result subtype=success`).
            let i = messages.length - 1;
            let pending = false;
            for (; i >= 0; i--) {
              const m = messages[i];
              if (m.role === 'user') break;
              if (m.payload?.type === 'assistant_text' && m.payload.text) {
                const t = m.payload.text;
                if (/\?\s*$|reply with|reply `|please (paste|reply|choose|share|enter|provide)|which (failures|to)|all-defaults|⚠.*input required|source material required/i.test(t)) {
                  pending = true; break;
                }
                // Looks like a completion: 'complete', 'done', 'finished', 'no further input', 'idle'.
                if (/\b(complete|done|finished|no further input required|idle)\b/i.test(t)) {
                  pending = false; break;
                }
              }
            }
            return pending ? (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px', margin: '14px 0 6px',
                border: '1px solid var(--w-cyan)',
                borderLeft: '3px solid var(--w-cyan)',
                borderRadius: 4,
                background: 'color-mix(in srgb, var(--w-cyan) 8%, var(--w-bg-1))',
                font: '12px/1.4 var(--w-mono)', color: 'var(--w-text-0)',
              }}>
                <span className="w-pulse" style={{ color: 'var(--w-cyan)', font: '600 14px/1 var(--w-mono)' }}>➜</span>
                <span><strong style={{ color: 'var(--w-cyan)' }}>your turn</strong> — agent is waiting for input. type a reply below to continue.</span>
              </div>
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 14px', margin: '14px 0 4px',
                color: 'var(--w-text-3)', font: '11px/1.4 var(--w-mono)',
                opacity: 0.7,
              }}>
                <span style={{ color: 'var(--w-phosphor)', font: '600 11px/1 var(--w-mono)' }}>✓</span>
                <span>agent idle — send a follow-up any time, or close the tab.</span>
              </div>
            );
          })()}
        </div>

        {/* Input */}
        <div style={{ flex: '0 0 auto', padding: '14px 22px', borderTop: '1px solid var(--w-line)', background: 'var(--w-bg-1)', position: 'relative' }}>
          {popupOpen && (
            <div style={{
              position: 'absolute',
              bottom: 'calc(100% + 4px)',
              left: 22, right: 22,
              maxHeight: 260,
              overflowY: 'auto',
              background: 'var(--w-bg-2)',
              border: '1px solid var(--w-line-strong)',
              borderRadius: 3,
              boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
              zIndex: 10,
            }}>
              {filteredSkills.map((s, i) => (
                <div
                  key={s.name}
                  onMouseEnter={() => setSlashIndex(i)}
                  onMouseDown={(e) => { e.preventDefault(); pickSkill(s); }}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    background: i === slashIndex ? 'var(--w-phosphor-veil)' : 'transparent',
                    borderBottom: '1px dashed var(--w-line)',
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--w-phosphor)', font: '600 12.5px/1.3 var(--w-mono)' }}>/{s.name}</span>
                    <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>· {s.source}</span>
                  </div>
                  {s.description && <div style={{ color: 'var(--w-text-2)', font: '11.5px/1.5 var(--w-mono)', marginTop: 2 }}>{s.description}</div>}
                </div>
              ))}
            </div>
          )}

          <div style={{
            border: '1px solid var(--w-line-strong)',
            background: 'var(--w-bg-2)',
            borderRadius: 3,
            padding: '12px 14px',
            boxShadow: '0 0 16px var(--w-phosphor-veil)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              <span>compose · markdown · /skill</span>
              <span style={{ flex: 1, borderBottom: '1px dashed var(--w-line)' }} />
              <span>shift+enter for newline</span>
              <KeyCap>↵</KeyCap>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span style={{ color: 'var(--w-phosphor)', font: '600 14px/1 var(--w-mono)', paddingTop: 6 }}>$</span>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder='ask claude — type / to pick a skill'
                rows={2}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none', outline: 'none',
                  color: 'var(--w-text-0)',
                  font: '13px/1.5 var(--w-mono)',
                  resize: 'none',
                }}
              />
            </div>
            <input ref={planningFileRef} type="file" style={{ display: 'none' }} onChange={(e) => { handleUpload('sdlc-planning', e.target.files?.[0]); e.target.value = ''; }} />
            <input ref={orchestratorFileRef} type="file" style={{ display: 'none' }} onChange={(e) => { handleUpload('sdlc-orchestrator', e.target.files?.[0]); e.target.value = ''; }} />
            <input
              ref={attachFileRef}
              type="file"
              accept="image/*,application/pdf,.md,.txt,.csv,.json,.docx,.doc,.pptx,.xlsx,.log,.zip,.html,.xml,.yaml,.yml"
              style={{ display: 'none' }}
              onChange={(e) => { handleAttach(e.target.files?.[0]); e.target.value = ''; }}
            />
            <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <Btn
                tone="line"
                onClick={() => attachFileRef.current?.click()}
                disabled={streaming || uploadingFor !== null}
                style={{ padding: '4px 10px' }}
                title="attach a file (image, pdf, doc, etc.) — appends @uploads/... to your message"
              >
                {uploadingFor === 'attach' ? 'uploading…' : '📎 attach file'}
              </Btn>
              {allSkills.slice(0, 4).map((s) => (
                <Pill key={s.name} tone={s.source === 'project' ? 'phosphor' : 'default'} onClick={() => pickSkill(s)}>
                  /{s.name}
                </Pill>
              ))}
              {activeUploadSkill && (
                <Btn
                  tone="line"
                  onClick={() => {
                    const ref = activeUploadSkill === 'sdlc-planning' ? planningFileRef : orchestratorFileRef;
                    ref.current?.click();
                  }}
                  disabled={streaming || uploadingFor !== null}
                  style={{ padding: '4px 10px' }}
                >
                  {uploadingFor === activeUploadSkill ? 'uploading…' : `→ ${activeUploadSkill}`}
                </Btn>
              )}
              <div style={{ flex: 1 }} />
              <Btn tone="ghost" style={{ padding: '4px 10px' }} onClick={resetSession} disabled={streaming}>[ ↺ ] reset</Btn>
              <Btn tone="primary" onClick={() => send()} disabled={streaming || !input.trim()}>[ ↵ ] send</Btn>
            </div>
          </div>
        </div>
      </div>

      {/* Right rail */}
      <div style={{ width: 300, flex: '0 0 300px', borderLeft: '1px solid var(--w-line)', background: 'var(--w-bg-1)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 16px 10px' }}>
          <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>// session</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, font: '11.5px/1.5 var(--w-mono)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--w-text-2)' }}>model</span>
              <span style={{ color: 'var(--w-text-0)' }}>{formatModel(sessionMeta.model || project.model) || '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--w-text-2)' }}>permission</span>
              <span style={{ color: 'var(--w-amber)' }}>{project.permission_mode}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--w-text-2)' }}>tools</span>
              <span style={{ color: 'var(--w-text-0)' }}>{(onSessionInfo && sessionMeta.sessionId) ? '—' : '—'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--w-text-2)' }}>messages</span>
              <span style={{ color: 'var(--w-text-0)' }}>{messages.length}</span>
            </div>
          </div>
        </div>

        <div style={{ padding: '16px 16px 6px', borderTop: '1px dashed var(--w-line)', minHeight: 0, flex: '1 1 0', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flex: '0 0 auto' }}>
            <span style={{ color: 'var(--w-cyan)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
              // confluence <span style={{ color: 'var(--w-text-3)' }}>· {project.name}</span>
            </span>
            <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>{atlassianRefs.confluence.length}</span>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: 200, flex: '1 1 auto' }}>
            {atlassianRefs.confluence.length === 0 ? (
              <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', padding: '6px 0' }}>no pages yet.</div>
            ) : (
              atlassianRefs.confluence.map((p) => (
                <a
                  key={p.url}
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={p.url}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 4px',
                    borderBottom: '1px dashed var(--w-line)',
                    textDecoration: 'none',
                    color: 'var(--w-text-1)',
                  }}
                >
                  <span style={{ color: 'var(--w-cyan)', font: '11px/1 var(--w-mono)', flex: '0 0 auto' }}>▤</span>
                  <span style={{
                    font: '11px/1.3 var(--w-mono)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                  }}>
                    {p.title}
                  </span>
                  <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>↗</span>
                </a>
              ))
            )}
          </div>
        </div>

        <div style={{ padding: '12px 16px 6px', borderTop: '1px dashed var(--w-line)', minHeight: 0, flex: '1 1 0', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flex: '0 0 auto' }}>
            <span style={{ color: 'var(--w-amber)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
              // jira · epics <span style={{ color: 'var(--w-text-3)' }}>· {project.name}</span>
            </span>
            <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>{atlassianRefs.jira.length}</span>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: 200, flex: '1 1 auto' }}>
            {atlassianRefs.jira.length === 0 ? (
              <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', padding: '6px 0' }}>no epics yet.</div>
            ) : (
              atlassianRefs.jira.map((j) => (
                <a
                  key={j.key}
                  href={j.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={j.url}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 4px',
                    borderBottom: '1px dashed var(--w-line)',
                    textDecoration: 'none',
                    color: 'var(--w-text-1)',
                  }}
                >
                  <span style={{
                    color: 'var(--w-amber)',
                    font: '600 10.5px/1 var(--w-mono)',
                    flex: '0 0 auto',
                    minWidth: 56,
                  }}>{j.key}</span>
                  <span style={{
                    font: '11px/1.3 var(--w-mono)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                  }}>
                    {j.summary || j.key}
                  </span>
                  <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', flex: '0 0 auto' }}>↗</span>
                </a>
              ))
            )}
          </div>
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px dashed var(--w-line)', flex: '0 0 auto' }}>
          <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>// signal · turn latency</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 24 }}>
            {sparkSamples.length === 0 && (
              <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>—</span>
            )}
            {sparkSamples.map((v, i) => {
              const max = Math.max(...sparkSamples, 1);
              const h = Math.max(2, (v / max) * 22);
              return (
                <div key={i} style={{
                  width: 6, height: h,
                  background: 'var(--w-phosphor)',
                  boxShadow: '0 0 6px var(--w-phosphor-glow)',
                  opacity: 0.4 + (i / sparkSamples.length) * 0.6,
                }} />
              );
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', marginTop: 4 }}>
            <span>oldest</span>
            <span>now</span>
          </div>
        </div>
      </div>
    </div>
  );
}
