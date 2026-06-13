import { useEffect, useState } from 'react';
import { api, authToken } from '../lib/api.js';
import quantnikLogo from '../assets/quantnik-logo.png';

// Renders <children> only when the user has a valid session. Otherwise
// shows a centred login / register card. On successful auth, the children
// remount and the rest of the app loads with the token already in
// localStorage (api.js + ws.js read it on every call).
export function AuthGate({ children }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [user, setUser] = useState(null);    // null = unauthed; object = authed
  const [checked, setChecked] = useState(false); // initial probe done?
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);

  // Initial probe: if a token exists, ask /auth/me. On success → render
  // the app. On 401 → clear and show the login screen.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authToken.get()) { setChecked(true); return; }
      const me = await api.me();
      if (cancelled) return;
      if (me?.user) setUser(me.user);
      else authToken.clear();
      setChecked(true);
    })();
    const handler = () => { setUser(null); authToken.clear(); };
    window.addEventListener('wega:auth-expired', handler);
    return () => { cancelled = true; window.removeEventListener('wega:auth-expired', handler); };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      const fn = mode === 'login' ? api.login : api.register;
      const payload = mode === 'login'
        ? { email: form.email.trim(), password: form.password }
        : { email: form.email.trim(), password: form.password, name: form.name.trim() };
      const result = await fn(payload);
      if (result?.token) authToken.set(result.token);
      if (result?.user) setUser(result.user);
      if (mode === 'register' && result?.claimedProjects > 0) {
        // First-ever user inherited the legacy projects. Surface a friendly
        // one-shot toast via the chat (rendered in-flow below).
        console.log(`[auth] first user — claimed ${result.claimedProjects} existing projects`);
      }
    } catch (e) {
      setError(e.message || 'authentication failed');
    } finally {
      setBusy(false);
    }
  };

  // Initial /auth/me probe pending — render nothing rather than flash the
  // login screen for users who already have a valid session.
  if (!checked) return null;
  if (user) return children;

  return (
    <div className="q-auth-shell" style={{
      position: 'fixed', inset: 0,
      display: 'flex',
      background: '#f5f7fa',
      fontFamily: 'var(--w-mono)',
      color: '#1b2330',
    }}>
      <div className="q-auth-brand" style={{
        flex: '1 1 0',
        minWidth: 0,
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(160deg,#eef4ff 0%,#e9effb 45%,#f3eefe 100%)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '52px 56px',
      }}>
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(#c9d6f5 1.2px, transparent 1.2px)', backgroundSize: '26px 26px', opacity: 0.4 }} />
        <div style={{ position: 'absolute', top: -120, left: -80, width: 380, height: 380, borderRadius: '50%', background: 'radial-gradient(circle,rgba(91,155,255,.32),transparent 68%)' }} />
        <div style={{ position: 'absolute', bottom: -140, right: -60, width: 420, height: 420, borderRadius: '50%', background: 'radial-gradient(circle,rgba(124,92,255,.22),transparent 68%)' }} />

        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 13 }}>
          <img src={quantnikLogo} alt="Quantnik" style={{ width: 46, height: 46, borderRadius: 13, boxShadow: '0 6px 18px rgba(37,99,235,.28)' }} />
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
            <span style={{ fontSize: 21, fontWeight: 800, letterSpacing: '-.01em' }}>Quantnik</span>
            <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '.2em', textTransform: 'uppercase', color: '#8a94a3' }}>Workbench</span>
          </div>
        </div>

        <div style={{ position: 'relative', maxWidth: 440 }}>
          <h1 style={{ fontSize: 38, lineHeight: 1.12, fontWeight: 800, letterSpacing: '-.025em', margin: '0 0 18px' }}>Intelligence,<br />automated.</h1>
          <p style={{ fontSize: 15.5, lineHeight: 1.65, color: '#5a6678', margin: '0 0 30px' }}>
            A project-scoped agent workbench — your repos, docs, Jira & Confluence, wired into one conversation that ships software end to end.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
            {['Project-scoped agents & skills', 'Atlassian-native — Jira & Confluence', 'Private by default — your data stays yours'].map((item, i) => (
              <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 13 }}>
                <span style={{ width: 30, height: 30, borderRadius: 9, background: '#fff', border: '1px solid #dfe7f5', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 1px 3px rgba(16,24,40,.05)' }}>
                  <span style={{ width: 11, height: 11, borderRadius: 3, background: i === 0 ? 'linear-gradient(135deg,#2563eb,#5b9bff)' : i === 1 ? 'linear-gradient(135deg,#0d9488,#34d399)' : 'linear-gradient(135deg,#7c5cff,#a78bfa)', transform: 'rotate(45deg)' }} />
                </span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#3a4456' }}>{item}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5, color: '#8a94a3' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#16a34a' }} />
          <span>All systems operational</span>
          <span style={{ color: '#c3cbd8' }}>·</span>
          <span>v0.4.2-α</span>
        </div>
      </div>

      <div className="q-auth-panel" style={{
        flex: '0 0 540px',
        width: 540,
        background: '#fff',
        borderLeft: '1px solid #e8ebf1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 56px',
      }}>
        <div style={{ width: '100%', maxWidth: 392 }}>
          <div style={{ marginBottom: 30 }}>
            <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: '#aab2bf', marginBottom: 8 }}>
              {mode === 'login' ? 'Quantnik · Sign in' : 'Quantnik · Get started'}
            </div>
            <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em', margin: 0, color: '#1b2330' }}>
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p style={{ fontSize: 14, color: '#7b8494', margin: '8px 0 0', lineHeight: 1.55 }}>
              {mode === 'login' ? 'Sign in to pick up where your agents left off.' : 'Spin up your first project-scoped workbench in seconds.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: 4, background: '#f1f3f7', borderRadius: 12, padding: 4, marginBottom: 26 }}>
          {['login', 'register'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(''); }}
              style={{
                flex: 1,
                background: mode === m ? '#fff' : 'transparent',
                border: 0,
                padding: '10px 0',
                color: mode === m ? '#1b2330' : '#8a94a3',
                font: `${mode === m ? 700 : 600} 13.5px/1 var(--w-mono)`,
                cursor: 'pointer',
                borderRadius: 9,
                boxShadow: mode === m ? '0 1px 2px rgba(16,24,40,.1)' : 'none',
              }}
            >{m === 'login' ? 'sign in' : 'create account'}</button>
          ))}
          </div>

          <form onSubmit={submit}>
          {mode === 'register' && (
            <>
              <label style={labelStyle}>Full name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Your name"
                style={inputStyle}
                autoFocus
              />
            </>
          )}

          <label style={labelStyle}>Email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="you@company.com"
            required
            autoFocus={mode === 'login'}
            style={inputStyle}
          />

          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <label style={labelStyle}>Password {mode === 'register' && <span style={{ color: '#9aa4b2' }}>· 8+ characters</span>}</label>
            {mode === 'login' && <span style={{ fontSize: 12, fontWeight: 600, color: '#2563eb' }}>Forgot?</span>}
          </div>
          <div style={{ position: 'relative' }}>
            <input
              type={showPw ? 'text' : 'password'}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="••••••••"
              required
              minLength={mode === 'register' ? 8 : undefined}
              style={{ ...inputStyle, paddingRight: 56 }}
            />
            <button type="button" onClick={() => setShowPw((v) => !v)} style={{
              position: 'absolute', top: '50%', right: 8, transform: 'translateY(-50%)',
              border: 0, background: 'transparent', color: '#9aa4b2', fontSize: 12, fontWeight: 700,
              padding: '6px 9px', borderRadius: 8, cursor: 'pointer',
            }}>{showPw ? 'HIDE' : 'SHOW'}</button>
          </div>

          {mode === 'login' && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 9, margin: '18px 0 22px', cursor: 'pointer', userSelect: 'none' }}>
              <button type="button" onClick={() => setRemember((v) => !v)} style={{
                width: 18, height: 18, borderRadius: 5, border: `1.5px solid ${remember ? '#2563eb' : '#cdd4e0'}`,
                background: remember ? '#2563eb' : '#fff', color: '#fff', fontSize: 11, fontWeight: 800, padding: 0,
              }}>{remember ? '✓' : ''}</button>
              <span style={{ fontSize: 13, color: '#5a6678' }}>Keep me signed in</span>
            </label>
          )}

          {error && (
            <p style={{ color: '#dc2626', font: '13px/1.4 var(--w-mono)', margin: '4px 0 12px' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            style={{
              width: '100%',
              background: 'linear-gradient(135deg,#2563eb,#2f6ef0)',
              color: '#fff',
              border: 0,
              padding: '14px 0',
              font: '700 14.5px/1 var(--w-mono)',
              borderRadius: 12,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.6 : 1,
              marginTop: 6,
              boxShadow: '0 4px 12px rgba(37,99,235,.3)',
            }}
          >
            {busy ? (mode === 'login' ? 'Signing in…' : 'Creating…') : (mode === 'login' ? 'Sign in →' : 'Create account →')}
          </button>
        </form>

          <p style={{ color: '#9aa4b2', font: '12.5px/1.6 var(--w-mono)', margin: '26px 0 0', textAlign: 'center' }}>
          Your projects are private — every user sees only their own.
          </p>
        </div>
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block',
  font: '700 12px/1 var(--w-mono)',
  color: '#5a6678',
  letterSpacing: '.04em',
  margin: '0 0 8px',
  paddingTop: 14,
};
const inputStyle = {
  width: '100%',
  background: '#fafbfd',
  border: '1px solid #d8dde6',
  borderRadius: 11,
  padding: '13px 15px',
  color: '#1b2330',
  font: '14.5px/1.4 var(--w-mono)',
  outline: 'none',
};

// Small sign-out button + email label that can be embedded in the app
// header. Reads the cached user from /auth/me on mount.
export function AuthHeader() {
  const [user, setUser] = useState(null);
  useEffect(() => {
    if (authToken.get()) api.me().then((r) => setUser(r?.user || null));
  }, []);
  if (!user) return null;
  const signOut = async () => {
    await api.logout();
    authToken.clear();
    window.dispatchEvent(new CustomEvent('wega:auth-expired'));
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, font: '12.5px/1 var(--w-mono)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.25 }}>
        <span style={{ color: '#2b3442', fontWeight: 600 }}>{user.email}</span>
        <span style={{ color: '#9aa4b2', fontSize: 11.5 }}>Signed in</span>
      </div>
      <span style={{
        width: 32, height: 32, borderRadius: '50%',
        background: 'linear-gradient(135deg,#e7ecf5,#d6deeb)',
        color: '#56627a', fontSize: 12.5, fontWeight: 700,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}>{(user.name || user.email || 'Q').split(/[\\s@.]+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase()}</span>
      <button
        type="button"
        onClick={signOut}
        style={{
          background: '#fff', border: '1px solid #e2e6ee',
          color: '#5a6678', font: '600 12.5px/1 var(--w-mono)',
          padding: '7px 12px', borderRadius: 9, cursor: 'pointer',
        }}
      >Sign out</button>
    </div>
  );
}
