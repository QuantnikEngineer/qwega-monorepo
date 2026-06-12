import React from 'react';
import wiproLogo from '../assets/wipro-logo.png';

export const S = ({ c, children }) => <span style={{ color: c }}>{children}</span>;

// Single source of truth for "what model name do we put on screen". The
// raw model id can take several forms depending on the provider:
//   - Anthropic direct:  claude-opus-4-7  ·  claude-sonnet-4-6  ·  claude-haiku-4-5-20251001
//   - Bedrock:           us.anthropic.claude-sonnet-4-6  ·  us.anthropic.claude-3-5-haiku-20241022-v1:0
//                        global.anthropic.claude-sonnet-4-6  ·  anthropic.claude-sonnet-4-6
//   - Vertex:            claude-3-7-sonnet@20250219
//   - Foundry:           claude-opus-4-7
// All of those should display as e.g. "sonnet-4-6" / "haiku-4-5" / "opus-4-7"
// so the status bar / sidebar pill / dashboard hint stay compact and
// readable regardless of how the project happens to be wired.
//
// Returns '' on empty/null. Idempotent — already-pretty strings pass through.
export function formatModel(raw) {
  if (!raw) return '';
  let s = String(raw);
  // Strip Bedrock cross-region prefixes (us. · global. · eu. · apac. · ca.)
  s = s.replace(/^(?:us|global|eu|apac|ca|sa)\.anthropic\./, '');
  // Strip the bare Bedrock foundation-model namespace
  s = s.replace(/^anthropic\./, '');
  // Strip the Anthropic-direct prefix
  s = s.replace(/^claude-/, '');
  // Strip Vertex @YYYYMMDD suffix
  s = s.replace(/@\d{8}$/, '');
  // Strip trailing Bedrock version + date suffixes: -20251001-v1:0  ·  -v1:0  ·  :0
  s = s.replace(/-\d{8}-v\d+:\d+$/, '');
  s = s.replace(/-\d{8}$/, '');
  s = s.replace(/-v\d+:\d+$/, '');
  return s;
}

export const WiproMark = ({ size = 28 }) => (
  <img
    src={wiproLogo}
    alt="Wipro"
    width={size}
    height={size}
    className="w-wipro-mark"
    style={{ display: 'block', width: size, height: size, objectFit: 'contain' }}
  />
);

export const WiproLockup = ({ mark = 28, type = 16 }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
    <WiproMark size={mark} />
    <span style={{ font: `700 ${type}px var(--w-display)`, color: 'var(--w-text-0)', letterSpacing: '0.04em' }}>
      WEGA<span style={{ color: 'var(--w-phosphor)', marginLeft: 2 }}>_</span>
    </span>
  </div>
);

const PILL_TONES = {
  default:  { bg: 'rgba(140,200,180,0.06)', fg: 'var(--w-text-1)', bd: 'var(--w-line)' },
  phosphor: { bg: 'var(--w-phosphor-veil)', fg: 'var(--w-phosphor)', bd: 'var(--w-line-strong)' },
  cyan:     { bg: 'rgba(0,229,255,0.08)', fg: 'var(--w-cyan)', bd: 'rgba(0,229,255,0.25)' },
  magenta:  { bg: 'rgba(255,46,136,0.08)', fg: 'var(--w-magenta)', bd: 'rgba(255,46,136,0.25)' },
  amber:    { bg: 'rgba(255,176,0,0.08)', fg: 'var(--w-amber)', bd: 'rgba(255,176,0,0.25)' },
  red:      { bg: 'rgba(255,71,87,0.08)', fg: 'var(--w-red)', bd: 'rgba(255,71,87,0.25)' },
  violet:   { bg: 'rgba(179,136,255,0.08)', fg: 'var(--w-violet)', bd: 'rgba(179,136,255,0.25)' },
};

export const Pill = ({ tone = 'default', children, style = {}, dot = false, onClick }) => {
  const t = PILL_TONES[tone] || PILL_TONES.default;
  return (
    <span
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '2px 8px',
        borderRadius: 3,
        background: t.bg,
        color: t.fg,
        border: `1px solid ${t.bd}`,
        font: '500 10.5px/1.4 var(--w-mono)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      {dot && <span className="w-dot" style={{ background: t.fg, color: t.fg }} />}
      {children}
    </span>
  );
};

export const KeyCap = ({ children }) => (
  <span style={{
    display: 'inline-block',
    padding: '1px 6px',
    border: '1px solid var(--w-line)',
    borderBottomWidth: 2,
    borderRadius: 3,
    background: 'var(--w-bg-3)',
    color: 'var(--w-text-1)',
    font: '11px/1 var(--w-mono)',
  }}>{children}</span>
);

const BTN_TONES = {
  ghost:   { bg: 'transparent', fg: 'var(--w-text-1)', bd: 'var(--w-line)' },
  primary: { bg: 'var(--w-phosphor)', fg: '#03110a', bd: 'var(--w-phosphor)' },
  line:    { bg: 'transparent', fg: 'var(--w-phosphor)', bd: 'var(--w-line-strong)' },
  danger:  { bg: 'transparent', fg: 'var(--w-red)', bd: 'rgba(255,71,87,0.35)' },
};

export const Btn = ({ tone = 'ghost', children, style = {}, icon = null, sub = null, onClick, disabled, type = 'button', title }) => {
  const t = BTN_TONES[tone] || BTN_TONES.ghost;
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '6px 12px',
        background: t.bg, color: t.fg,
        border: `1px solid ${t.bd}`,
        borderRadius: 3,
        font: '500 12px/1 var(--w-mono)',
        letterSpacing: '0.04em',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        ...style,
      }}
    >
      {icon}
      <span>{children}</span>
      {sub && <span style={{ opacity: 0.7, marginLeft: 6 }}>{sub}</span>}
    </button>
  );
};

export const WindowFrame = ({ title = 'wega', theme = 'dark', children, cpu = 4, mem = 312, headerExtras = null }) => {
  const [time, setTime] = React.useState(() => new Date());
  React.useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 30_000);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{
      position: 'relative',
      width: '100%', height: '100%',
      background: 'var(--w-bg-0)',
      color: 'var(--w-text-0)',
      font: '13px/1.5 var(--w-mono)',
      overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
    }} className="w-scan">
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px',
        borderBottom: '1px solid var(--w-line)',
        background: 'var(--w-bg-1)',
        flex: '0 0 auto',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <span style={{ width: 11, height: 11, borderRadius: '50%', border: '1px solid var(--w-line)' }} />
            <span style={{ width: 11, height: 11, borderRadius: '50%', border: '1px solid var(--w-line)' }} />
            <span style={{ width: 11, height: 11, borderRadius: '50%', border: '1px solid var(--w-line-strong)', background: 'var(--w-phosphor-veil)' }} />
          </div>
          <span style={{ color: 'var(--w-text-2)', marginLeft: 6 }}>
            <span style={{ color: 'var(--w-phosphor)' }}>~</span>
            <span> / </span>
            {title}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, color: 'var(--w-text-2)', font: '11px/1 var(--w-mono)' }}>
          {headerExtras}
          <span><span style={{ color: 'var(--w-phosphor)' }}>●</span> {theme}</span>
          <span>cpu <span style={{ color: 'var(--w-text-1)' }}>{cpu}%</span></span>
          <span>mem <span style={{ color: 'var(--w-text-1)' }}>{mem}<span style={{ color: 'var(--w-text-3)' }}>mb</span></span></span>
          <span>{time.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
};

export const TabBar = ({ tabs, active, onSelect, model, permissionMode }) => (
  <div style={{
    display: 'flex', alignItems: 'stretch',
    borderBottom: '1px solid var(--w-line)',
    background: 'var(--w-bg-1)',
    flex: '0 0 auto',
    paddingLeft: 8,
  }}>
    {tabs.map((t) => {
      const isActive = t.id === active;
      return (
        <div
          key={t.id}
          onClick={() => onSelect && onSelect(t.id)}
          style={{
            padding: '10px 16px',
            cursor: 'pointer',
            position: 'relative',
            color: isActive ? 'var(--w-phosphor)' : 'var(--w-text-2)',
            font: '500 12.5px/1 var(--w-mono)',
            letterSpacing: '0.04em',
            display: 'flex', alignItems: 'center', gap: 6,
            borderRight: '1px solid var(--w-line)',
            background: isActive ? 'var(--w-bg-2)' : 'transparent',
          }}
        >
          <span style={{ color: isActive ? 'var(--w-phosphor)' : 'var(--w-text-3)', marginRight: 2 }}>{t.glyph}</span>
          <span>{t.id}</span>
          {t.badge && <Pill tone={t.badgeTone || 'phosphor'} style={{ marginLeft: 4, padding: '1px 5px', fontSize: 9.5 }}>{t.badge}</Pill>}
          {isActive && (
            <span style={{ position: 'absolute', left: 0, right: 0, bottom: -1, height: 2, background: 'var(--w-phosphor)', boxShadow: '0 0 12px var(--w-phosphor-glow)' }} />
          )}
        </div>
      );
    })}
    <div style={{ flex: 1, borderBottom: '1px solid transparent' }} />
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px', color: 'var(--w-text-2)', font: '11px/1 var(--w-mono)', borderLeft: '1px solid var(--w-line)' }}>
      {model && (
        <span>
          <span style={{ color: 'var(--w-phosphor)' }}>claude</span>
          <span style={{ color: 'var(--w-text-3)' }}>@</span>
          {formatModel(model)}
        </span>
      )}
      {model && permissionMode && <span style={{ color: 'var(--w-text-3)' }}>·</span>}
      {permissionMode && (
        <Pill tone={permissionMode === 'bypassPermissions' ? 'amber' : 'cyan'} dot>{permissionMode}</Pill>
      )}
    </div>
  </div>
);

export const StatusBar = ({ left = [], right = [] }) => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '5px 14px',
    borderTop: '1px solid var(--w-line)',
    background: 'var(--w-bg-1)',
    color: 'var(--w-text-2)',
    font: '10.5px/1 var(--w-mono)',
    flex: '0 0 auto',
    letterSpacing: '0.04em',
  }}>
    <div style={{ display: 'flex', gap: 18 }}>{left.map((x, i) => <span key={i}>{x}</span>)}</div>
    <div style={{ display: 'flex', gap: 18 }}>{right.map((x, i) => <span key={i}>{x}</span>)}</div>
  </div>
);

export const ScreenFrame = ({ title, subtitle, breadcrumb, action, children }) => (
  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--w-bg-0)', minHeight: 0 }}>
    <div style={{
      padding: '18px 28px',
      borderBottom: '1px solid var(--w-line)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
      gap: 20,
      background: 'var(--w-bg-1)',
      flex: '0 0 auto',
    }}>
      <div>
        {breadcrumb && (
          <div style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
            {breadcrumb}
          </div>
        )}
        <div style={{ font: '20px/1.2 var(--w-display)', color: 'var(--w-text-0)', letterSpacing: '0.02em' }}>{title}</div>
        {subtitle && <div style={{ color: 'var(--w-text-2)', font: '12px/1.5 var(--w-mono)', marginTop: 4, maxWidth: 720 }}>{subtitle}</div>}
      </div>
      {action}
    </div>
    <div style={{ flex: 1, overflow: 'auto', padding: '20px 28px' }}>
      {children}
    </div>
  </div>
);

export const SectionLabel = ({ tone = 'phosphor', children, right }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
    <span style={{ color: `var(--w-${tone})`, font: '11px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
      {children}
    </span>
    <span style={{ flex: 1, borderBottom: '1px dashed var(--w-line)' }} />
    {right}
  </div>
);
