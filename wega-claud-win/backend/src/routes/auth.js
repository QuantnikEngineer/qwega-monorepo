import { Router } from 'express';
import bcrypt from 'bcryptjs';
import crypto from 'node:crypto';
import { db } from '../db.js';

export const auth = Router();

// Session lifetime — long enough to survive a workday without re-auth,
// short enough that a leaked token isn't a forever problem.
const SESSION_TTL_SECONDS = 7 * 24 * 60 * 60; // 7 days

// Registration is open to any valid email. Keep validation deliberately simple:
// trim + lowercase the email, require a conventional email shape and 8+ chars.
const MIN_PASSWORD_LEN = 8;

function normaliseEmail(e) {
  return String(e || '').trim().toLowerCase();
}

function newToken() {
  return crypto.randomBytes(32).toString('hex');
}

function maskUser(u) {
  if (!u) return null;
  return {
    id: u.id,
    email: u.email,
    name: u.name || null,
    createdAt: u.created_at,
    // 0/1 in SQLite; cast to a real boolean so the frontend can `if (user.isAdmin)`.
    isAdmin: !!u.is_admin,
  };
}

// On first successful registration: claim every un-owned project. This is
// the migration handoff for the 5 existing projects (Mobile / Faber / etc.)
// — first user wins them. Subsequent users start with empty lists.
function claimOrphanedProjects(userId) {
  const result = db.prepare(`
    UPDATE projects SET owner_user_id = ? WHERE owner_user_id IS NULL
  `).run(userId);
  return result.changes;
}

// ---- POST /api/auth/register ----------------------------------------------
auth.post('/register', async (req, res) => {
  const email = normaliseEmail(req.body?.email);
  const password = String(req.body?.password || '');
  const name = String(req.body?.name || '').trim() || null;

  if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(email)) {
    return res.status(400).json({ error: 'invalid email format' });
  }
  if (password.length < MIN_PASSWORD_LEN) {
    return res.status(400).json({ error: `password must be at least ${MIN_PASSWORD_LEN} characters` });
  }

  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (existing) {
    return res.status(409).json({ error: 'email already registered — try logging in' });
  }

  const passwordHash = await bcrypt.hash(password, 10);
  const now = Math.floor(Date.now() / 1000);
  const result = db.prepare(`
    INSERT INTO users (email, password_hash, name, created_at, last_login_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(email, passwordHash, name, now, now);
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(result.lastInsertRowid);

  // Migration: if this is the first ever user, claim every un-owned project.
  const userCount = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  const claimed = userCount === 1 ? claimOrphanedProjects(user.id) : 0;

  const token = newToken();
  db.prepare('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)')
    .run(token, user.id, now + SESSION_TTL_SECONDS);

  res.json({
    user: maskUser(user),
    token,
    expiresAt: now + SESSION_TTL_SECONDS,
    claimedProjects: claimed,
  });
});

// ---- POST /api/auth/login -------------------------------------------------
auth.post('/login', async (req, res) => {
  const email = normaliseEmail(req.body?.email);
  const password = String(req.body?.password || '');

  if (!email || !password) {
    return res.status(400).json({ error: 'email and password required' });
  }

  const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  // Same generic error for unknown-email and wrong-password — no account
  // enumeration via the login response.
  if (!user) {
    return res.status(401).json({ error: 'invalid email or password' });
  }
  const ok = await bcrypt.compare(password, user.password_hash);
  if (!ok) {
    return res.status(401).json({ error: 'invalid email or password' });
  }

  const now = Math.floor(Date.now() / 1000);
  db.prepare('UPDATE users SET last_login_at = ? WHERE id = ?').run(now, user.id);
  const token = newToken();
  db.prepare('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)')
    .run(token, user.id, now + SESSION_TTL_SECONDS);

  res.json({
    user: maskUser(user),
    token,
    expiresAt: now + SESSION_TTL_SECONDS,
  });
});

// ---- POST /api/auth/logout ------------------------------------------------
auth.post('/logout', (req, res) => {
  // Pull the token from middleware (req.session.token) OR from the request
  // directly so an unauthenticated logout still cleans up.
  const token = req.session?.token || req.get('authorization')?.replace(/^Bearer\s+/i, '');
  if (token) db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
  res.json({ ok: true });
});

// ---- GET /api/auth/me -----------------------------------------------------
// Returns the current authenticated user. Middleware populates req.user.
auth.get('/me', (req, res) => {
  if (!req.user) return res.status(401).json({ error: 'not authenticated' });
  res.json({ user: maskUser(req.user) });
});

// ---- Express middleware used by /api/* (except /api/auth/login|register) --
// Reads the token from the Authorization header, looks up the session +
// user, and attaches them to req. On miss it sets nothing — route handlers
// decide whether they need auth.
export function attachAuth(req, _res, next) {
  const header = req.get('authorization') || '';
  const m = header.match(/^Bearer\s+(.+)$/i);
  if (!m) return next();
  const token = m[1].trim();
  const now = Math.floor(Date.now() / 1000);
  const row = db.prepare(`
    SELECT s.token, s.expires_at, u.* FROM sessions s
    INNER JOIN users u ON u.id = s.user_id
    WHERE s.token = ? AND s.expires_at > ?
  `).get(token, now);
  if (row) {
    req.session = { token: row.token, expiresAt: row.expires_at };
    req.user = {
      id: row.id,
      email: row.email,
      name: row.name,
      created_at: row.created_at,
      is_admin: !!row.is_admin,
    };
  }
  next();
}

// Stricter middleware — 401 if no req.user. Mount it on every /api/* route
// that should require login (i.e. everything except /api/auth/*).
export function requireAuth(req, res, next) {
  if (!req.user) return res.status(401).json({ error: 'authentication required' });
  next();
}

// Loopback detection — every IPv4/IPv6 form of localhost. Used by routes
// that the local agent process needs to hit without a user-scoped token
// (e.g. phase state tracking from inside a skill's curl call).
const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1']);
function isLoopback(req) {
  const ip = req.ip || req.connection?.remoteAddress || '';
  // express sets req.ip when `trust proxy` is enabled; fall back to the
  // socket remoteAddress otherwise. Strip IPv6-mapped IPv4 prefix.
  const stripped = ip.replace(/^::ffff:/, '');
  return LOOPBACK_HOSTS.has(ip) || LOOPBACK_HOSTS.has(stripped) || stripped === '127.0.0.1';
}

// Loopback OR valid token. For endpoints the local agent process must
// reach without holding a user-scoped bearer token — anyone with shell
// access to the wega2 host has strictly greater privileges than a phase
// transition write, so the bypass is safe. Remote callers still need a
// real session token.
export function requireAuthOrLocal(req, res, next) {
  if (req.user) return next();
  if (isLoopback(req)) return next();
  return res.status(401).json({ error: 'authentication required' });
}

// Admin-only gate. Mount AFTER requireAuth so req.user is present.
// 403 (forbidden) rather than 404 — admin endpoints don't pretend not to
// exist; non-admins know it's there but can't enter.
export function requireAdmin(req, res, next) {
  if (!req.user?.is_admin) return res.status(403).json({ error: 'admin only' });
  next();
}

// Helper used by ws.js for the WS-upgrade auth check.
export function userForToken(token) {
  if (!token) return null;
  const now = Math.floor(Date.now() / 1000);
  const row = db.prepare(`
    SELECT u.* FROM sessions s
    INNER JOIN users u ON u.id = s.user_id
    WHERE s.token = ? AND s.expires_at > ?
  `).get(String(token), now);
  return row ? { id: row.id, email: row.email, name: row.name, is_admin: !!row.is_admin } : null;
}
