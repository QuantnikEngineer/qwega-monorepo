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
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--w-bg-0)',
      padding: 24,
    }}>
      <div style={{
        width: 420,
        background: 'var(--w-bg-1)',
        border: '1px solid var(--w-line)',
        borderLeft: '3px solid var(--w-phosphor)',
        borderRadius: 6,
        padding: '28px 28px 22px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <img src={quantnikLogo} alt="Quantnik" style={{ height: 34, width: 'auto', objectFit: 'contain' }} />
          <span style={{ color: 'var(--w-text-3)', font: '11px/1 var(--w-mono)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>Quantnik · Sign in</span>
        </div>

        {/* Mode tabs */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 18, borderBottom: '1px solid var(--w-line)' }}>
          {['login', 'register'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(''); }}
              style={{
                flex: 1,
                background: 'transparent', border: 0,
                padding: '8px 0',
                color: mode === m ? 'var(--w-phosphor)' : 'var(--w-text-3)',
                font: `${mode === m ? 600 : 400} 12px/1 var(--w-mono)`,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                cursor: 'pointer',
                borderBottom: mode === m ? '2px solid var(--w-phosphor)' : '2px solid transparent',
                marginBottom: -1,
              }}
            >{m === 'login' ? 'sign in' : 'create account'}</button>
          ))}
        </div>

        <form onSubmit={submit}>
          {mode === 'register' && (
            <>
              <label style={labelStyle}>name <span style={{ color: 'var(--w-text-3)' }}>(optional)</span></label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Your name"
                style={inputStyle}
                autoFocus
              />
            </>
          )}

          <label style={labelStyle}>email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="you@example.com"
            required
            autoFocus={mode === 'login'}
            style={inputStyle}
          />

          <label style={labelStyle}>password {mode === 'register' && <span style={{ color: 'var(--w-text-3)' }}>· 8+ characters</span>}</label>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder={mode === 'register' ? 'min 8 characters' : ''}
            required
            minLength={mode === 'register' ? 8 : undefined}
            style={inputStyle}
          />

          {error && (
            <p style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)', margin: '4px 0 12px' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            style={{
              width: '100%',
              background: 'var(--w-phosphor)',
              color: 'var(--w-bg-0)',
              border: 0,
              padding: '10px 0',
              font: '600 12px/1 var(--w-mono)',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              borderRadius: 3,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.6 : 1,
              marginTop: 6,
            }}
          >
            {busy ? '…' : (mode === 'login' ? '[ ↵ ] sign in' : '[ + ] create account')}
          </button>
        </form>

        <p style={{ color: 'var(--w-text-3)', font: '10.5px/1.5 var(--w-mono)', marginTop: 14 }}>
          Your projects are private — every user sees only their own.
        </p>
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block',
  font: '10.5px/1 var(--w-mono)',
  color: 'var(--w-text-2)',
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  margin: '14px 0 6px',
};
const inputStyle = {
  width: '100%',
  background: 'var(--w-bg-0)',
  border: '1px solid var(--w-line)',
  borderRadius: 3,
  padding: '8px 10px',
  color: 'var(--w-text-0)',
  font: '13px/1.4 var(--w-mono)',
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, font: '11px/1 var(--w-mono)' }}>
      <span style={{ color: 'var(--w-text-3)' }}>signed in as</span>
      <span style={{ color: 'var(--w-text-0)' }}>{user.email}</span>
      <button
        type="button"
        onClick={signOut}
        style={{
          background: 'transparent', border: '1px solid var(--w-line)',
          color: 'var(--w-text-2)', font: '10.5px/1 var(--w-mono)',
          padding: '4px 10px', borderRadius: 3, cursor: 'pointer',
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}
      >sign out</button>
    </div>
  );
}
