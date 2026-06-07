import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Terminal, ChevronDown, ChevronUp, X, Maximize2, Minimize2, GripHorizontal } from 'lucide-react';

export interface DroidTerminalEvent {
  type: 'droid_terminal';
  event: 'command' | 'stdout' | 'message' | 'stderr' | 'system' | 'exit' | 'error' | 'tool_call' | 'tool_result' | 'completion' | 'reasoning' | 'turn_complete';
  text: string;
  data?: any;
  role?: string;
  exit_code?: number;
  timed_out?: boolean;
  code_session_id?: string;
  _forwarded_from?: string;
  _source_orchestrator?: string;
  timestamp?: number;
}

interface DroidTerminalProps {
  events: DroidTerminalEvent[];
  isActive: boolean;
  onClose?: () => void;
  isDarkMode?: boolean;
}

const EVENT_COLORS: Record<string, string> = {
  command: '#e0a526',
  stdout: '#c9d1d9',
  message: '#58a6ff',
  stderr: '#f85149',
  system: '#8b949e',
  exit: '#3fb950',
  error: '#f85149',
  tool_call: '#d2a8ff',
  tool_result: '#a5d6ff',
  completion: '#3fb950',
  reasoning: '#d4a574',
  turn_complete: '#3fb950',
};

const EVENT_PREFIXES: Record<string, string> = {
  command: '$ ',
  stdout: '',
  message: '',
  stderr: 'stderr: ',
  system: '[system] ',
  exit: '',
  error: '[error] ',
  tool_call: '',
  tool_result: '',
  completion: '',
  reasoning: '',
  turn_complete: '[turn complete] ',
};

const MIN_HEIGHT = 60;
const MAX_HEIGHT = 600;
const DEFAULT_HEIGHT = 100;

export function DroidTerminal({ events, isActive, onClose, isDarkMode = true }: DroidTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [terminalHeight, setTerminalHeight] = useState(DEFAULT_HEIGHT);
  const isDragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDragging.current = true;
    dragStartY.current = e.clientY;
    dragStartHeight.current = terminalHeight;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  }, [terminalHeight]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      // Dragging up = negative delta = increase height (handle is at top)
      const delta = dragStartY.current - e.clientY;
      setTerminalHeight(Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, dragStartHeight.current + delta)));
    };
    const onUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  // Detect user scroll to disable auto-scroll
  const handleScroll = () => {
    if (!terminalRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = terminalRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;
    setAutoScroll(isAtBottom);
  };

  if (!isActive && events.length === 0) return null;

  const exitEvent = events.find(e => e.event === 'exit');
  const isFinished = !!exitEvent;
  const exitCode = exitEvent?.exit_code ?? null;

  const statusColor = isFinished
    ? exitCode === 0 ? '#3fb950' : '#f85149'
    : '#e0a526';
  const statusText = isFinished
    ? exitCode === 0 ? 'Completed' : `Exited (${exitCode})`
    : 'Running';

  return (
    <div
      className="droid-terminal-container"
      style={{
        border: `1px solid ${isDarkMode ? 'rgba(91,141,239,0.3)' : 'rgba(91,141,239,0.2)'}`,
        borderRadius: '8px',
        overflow: 'hidden',
        background: isDarkMode ? '#0c1121' : '#e8eefb',
        margin: '8px 0',
        ...(isExpanded ? {
          position: 'fixed',
          top: '10%',
          left: '10%',
          right: '10%',
          bottom: '10%',
          zIndex: 1000,
          margin: 0,
          boxShadow: '0 24px 48px rgba(30,60,140,0.35)',
        } : {}),
      }}
    >
      {/* Terminal Header */}
      <div
        className="droid-terminal-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: isDarkMode ? '#0f1526' : '#dce4f6',
          borderBottom: `1px solid ${isDarkMode ? 'rgba(91,141,239,0.2)' : 'rgba(91,141,239,0.25)'}`,
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setIsCollapsed(prev => !prev)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal style={{ width: 14, height: 14, color: '#5B8DEF' }} />
          <span style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            fontFamily: "'Fira Code', 'Consolas', monospace",
            color: isDarkMode ? '#c9d1d9' : '#24292f',
            letterSpacing: '0.3px',
          }}>
            Droid Terminal
          </span>
          {/* Status indicator */}
          <span style={{
            fontSize: '0.65rem',
            padding: '1px 6px',
            borderRadius: '3px',
            background: `${statusColor}22`,
            color: statusColor,
            fontWeight: 600,
            border: `1px solid ${statusColor}44`,
          }}>
            {!isFinished && (
              <span style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: statusColor,
                marginRight: 4,
                animation: 'terminalPulse 1.5s ease-in-out infinite',
              }} />
            )}
            {statusText}
          </span>
          <span style={{
            fontSize: '0.65rem',
            color: isDarkMode ? '#8b949e' : '#57606a',
          }}>
            {events.filter(e => e.event !== 'exit').length} events
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            onClick={(e) => { e.stopPropagation(); setIsExpanded(prev => !prev); }}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '2px',
              color: '#8b949e',
              display: 'flex',
              alignItems: 'center',
            }}
            title={isExpanded ? 'Minimize' : 'Maximize'}
          >
            {isExpanded ? <Minimize2 style={{ width: 12, height: 12 }} /> : <Maximize2 style={{ width: 12, height: 12 }} />}
          </button>
          {isCollapsed ? (
            <ChevronDown style={{ width: 14, height: 14, color: '#8b949e' }} />
          ) : (
            <ChevronUp style={{ width: 14, height: 14, color: '#8b949e' }} />
          )}
          {onClose && (
            <button
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '2px',
                color: '#8b949e',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Close terminal"
            >
              <X style={{ width: 12, height: 12 }} />
            </button>
          )}
        </div>
      </div>

      {/* Resize Handle — at top of body */}
      {!isCollapsed && !isExpanded && (
        <div
          className="droid-terminal-resize-handle"
          onMouseDown={onResizeStart}
          style={{
            height: '7px',
            cursor: 'ns-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: isDarkMode ? '#0f1526' : '#dce4f6',
            borderBottom: `1px solid ${isDarkMode ? 'rgba(91,141,239,0.12)' : 'rgba(91,141,239,0.08)'}`,
            transition: 'background 0.15s',
          }}
          title="Drag to resize"
        >
          <GripHorizontal style={{ width: 16, height: 7, color: isDarkMode ? 'rgba(91,141,239,0.45)' : 'rgba(91,141,239,0.35)' }} />
        </div>
      )}

      {/* Terminal Body */}
      {!isCollapsed && (
        <div
          ref={terminalRef}
          onScroll={handleScroll}
          className="droid-terminal-body"
          style={{
            height: isExpanded ? 'calc(100% - 41px)' : `${terminalHeight}px`,
            overflowY: 'auto',
            padding: '8px 12px',
            fontFamily: "'Fira Code', 'Consolas', 'Courier New', monospace",
            fontSize: '0.78rem',
            lineHeight: '1.6',
            color: isDarkMode ? '#c9d1d9' : '#24292f',
            background: isDarkMode ? '#0d1117' : '#ffffff',
          }}
        >
          {events.length === 0 && isActive && (
            <div style={{ color: '#8b949e', fontStyle: 'italic', fontSize: '0.75rem' }}>
              Waiting for droid output...
            </div>
          )}
          {events.map((event, idx) => (
            <TerminalLine key={idx} event={event} />
          ))}
          {isActive && !isFinished && (
            <div style={{ display: 'inline-block' }}>
              <span className="terminal-cursor" style={{
                display: 'inline-block',
                width: '8px',
                height: '14px',
                background: '#5B8DEF',
                animation: 'terminalBlink 1s step-end infinite',
                verticalAlign: 'text-bottom',
              }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TerminalLine({ event }: { event: DroidTerminalEvent }) {
  const color = EVENT_COLORS[event.event] || '#c9d1d9';
  const prefix = EVENT_PREFIXES[event.event] || '';
  const text = event.text || '';

  // Don't render empty lines (except exit, tool_call, tool_result, completion, reasoning which use data)
  if (!text && event.event !== 'exit' && event.event !== 'tool_call' && event.event !== 'tool_result' && event.event !== 'completion' && event.event !== 'reasoning') return null;

  if (event.event === 'exit') {
    const exitCode = event.exit_code ?? 0;
    const timedOut = event.timed_out ?? false;
    return (
      <div style={{
        marginTop: '8px',
        paddingTop: '6px',
        borderTop: '1px solid rgba(139,148,158,0.2)',
        color: exitCode === 0 ? '#3fb950' : '#f85149',
        fontSize: '0.75rem',
      }}>
        {timedOut ? '⏰ Session timed out' : exitCode === 0 ? '✓ Process completed successfully' : `✗ Process exited with code ${exitCode}`}
      </div>
    );
  }

  if (event.event === 'command') {
    return (
      <div style={{
        color,
        marginBottom: '4px',
        padding: '4px 8px',
        background: 'rgba(224,165,38,0.08)',
        borderRadius: '4px',
        borderLeft: '3px solid #e0a526',
      }}>
        <span style={{ opacity: 0.6, marginRight: '4px' }}>$</span>
        <span style={{ fontWeight: 600 }}>{text}</span>
      </div>
    );
  }

  if (event.event === 'system') {
    const subtype = event.data?.subtype || '';
    const name = event.data?.name || '';
    const value = event.data?.value || text;
    return (
      <div style={{ color, fontSize: '0.72rem', opacity: 0.7 }}>
        <span style={{ color: '#6e7681' }}>[{subtype || 'system'}]</span>
        {name && <span style={{ color: '#8b949e' }}> {name}=</span>}
        <span>{typeof value === 'string' ? value : JSON.stringify(value)}</span>
      </div>
    );
  }

  if (event.event === 'stderr') {
    return (
      <div style={{
        color,
        fontSize: '0.72rem',
        opacity: 0.8,
        paddingLeft: '8px',
        borderLeft: '2px solid rgba(248,81,73,0.3)',
      }}>
        {text}
      </div>
    );
  }

  if (event.event === 'error') {
    return (
      <div style={{
        color,
        padding: '4px 8px',
        background: 'rgba(248,81,73,0.08)',
        borderRadius: '4px',
        borderLeft: '3px solid #f85149',
      }}>
        ❌ {text}
      </div>
    );
  }

  if (event.event === 'tool_call') {
    const toolName = event.data?.toolName || event.data?.name || event.data?.tool || 'tool';
    const toolId = event.data?.id || event.data?.toolCallId || event.data?.call_id || '';
    const params = event.data?.parameters || event.data?.args || event.data?.input;
    const paramsStr = params ? (typeof params === 'string' ? params : JSON.stringify(params)) : '';
    const truncated = paramsStr.length > 120 ? paramsStr.slice(0, 120) + '...' : paramsStr;
    return (
      <div style={{
        color,
        fontSize: '0.72rem',
        padding: '3px 8px',
        marginBottom: '2px',
        background: 'rgba(210,168,255,0.06)',
        borderRadius: '4px',
        borderLeft: '3px solid #d2a8ff',
      }}>
        <span style={{ color: '#d2a8ff', fontWeight: 600 }}>tool_call</span>
        {toolId && <span style={{ color: '#8b949e' }}> id={toolId}</span>}
        <span style={{ color: '#c9d1d9' }}> {toolName}</span>
        {truncated && (
          <span style={{ color: '#6e7681', marginLeft: '4px' }} title={paramsStr}>({truncated})</span>
        )}
      </div>
    );
  }

  if (event.event === 'tool_result') {
    const toolId = event.data?.id || event.data?.toolCallId || event.data?.call_id || '';
    const isError = Boolean(event.data?.isError || event.data?.error);
    const value = event.data?.value ?? event.data?.result ?? event.data?.text ?? event.data?.error ?? text;
    const valueStr = typeof value === 'string' ? value : JSON.stringify(value);
    const truncated = valueStr.length > 120 ? valueStr.slice(0, 120) + '...' : valueStr;
    return (
      <div style={{
        color: isError ? '#f85149' : color,
        fontSize: '0.72rem',
        padding: '3px 8px',
        marginBottom: '2px',
        background: isError ? 'rgba(248,81,73,0.06)' : 'rgba(165,214,255,0.06)',
        borderRadius: '4px',
        borderLeft: `3px solid ${isError ? '#f85149' : '#a5d6ff'}`,
      }}>
        <span style={{ color: isError ? '#f85149' : '#a5d6ff', fontWeight: 600 }}>tool_result</span>
        {toolId && <span style={{ color: '#8b949e' }}> id={toolId}</span>}
        {isError && <span style={{ color: '#f85149' }}> error</span>}
        <span style={{ color: '#6e7681', marginLeft: '4px' }} title={valueStr}>{truncated}</span>
      </div>
    );
  }

  if (event.event === 'completion') {
    const finalText = event.data?.finalText || text;
    const truncated = finalText.length > 150 ? finalText.slice(0, 150) + '...' : finalText;
    return (
      <div style={{
        color,
        fontSize: '0.72rem',
        padding: '3px 8px',
        marginTop: '4px',
        background: 'rgba(63,185,80,0.06)',
        borderRadius: '4px',
        borderLeft: '3px solid #3fb950',
      }}>
        <span style={{ color: '#3fb950', fontWeight: 600 }}>completion</span>
        {truncated && <span style={{ color: '#8b949e', marginLeft: '4px' }} title={finalText}>{truncated}</span>}
      </div>
    );
  }

  if (event.event === 'reasoning') {
    const reasoningText = event.data?.text || text;
    const reasoningId = event.data?.id || '';
    const truncated = reasoningText.length > 200 ? reasoningText.slice(0, 200) + '...' : reasoningText;
    return (
      <div style={{
        color: '#d4a574',
        fontSize: '0.72rem',
        padding: '3px 8px',
        marginBottom: '2px',
        background: 'rgba(212,165,116,0.06)',
        borderRadius: '4px',
        borderLeft: '3px solid #d4a574',
      }}>
        <span style={{ color: '#d4a574', fontWeight: 600 }}>reasoning</span>
        {reasoningId && <span style={{ color: '#6e7681' }}> id={reasoningId.slice(0, 8)}</span>}
        <div style={{
          color: '#8b949e',
          marginTop: '2px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          lineHeight: '1.4',
        }} title={reasoningText}>
          {truncated}
        </div>
      </div>
    );
  }

  // stdout / message - the main output
  return (
    <div style={{ color, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {prefix}{formatTerminalText(text)}
    </div>
  );
}

function formatTerminalText(text: string): React.ReactElement {
  // Simple formatting: highlight file paths, code blocks
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code key={i} style={{
              background: 'rgba(110,118,129,0.15)',
              padding: '1px 4px',
              borderRadius: '3px',
              fontSize: '0.76rem',
            }}>
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

DroidTerminal.displayName = 'DroidTerminal';
