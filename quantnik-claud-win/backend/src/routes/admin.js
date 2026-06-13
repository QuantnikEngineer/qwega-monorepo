import { Router } from 'express';
import { spawn } from 'node:child_process';
import { auditLog, db } from '../db.js';

export const admin = Router();

// GET /api/admin/overview
// Returns the complete admin view: users + projects + summary + caveat about
// when usage tracking started. One call per page load — kept compact enough
// that the SettingsPanel can re-render the whole table from the response.
admin.get('/overview', (req, res) => {
  // Per-user rollup. LEFT JOIN so users with zero projects / zero turns still
  // appear. COALESCE on the sums so a user with no usage_events shows 0, not
  // NULL — keeps the frontend math simple.
  const users = db.prepare(`
    SELECT
      u.id,
      u.email,
      u.name,
      u.created_at,
      u.last_login_at,
      u.is_admin,
      (SELECT COUNT(*) FROM projects p WHERE p.owner_user_id = u.id) AS project_count,
      (SELECT COUNT(*) FROM usage_events ue WHERE ue.user_id = u.id) AS turn_count,
      COALESCE((SELECT SUM(input_tokens)                FROM usage_events WHERE user_id = u.id), 0) AS input_tokens,
      COALESCE((SELECT SUM(output_tokens)               FROM usage_events WHERE user_id = u.id), 0) AS output_tokens,
      COALESCE((SELECT SUM(cache_creation_input_tokens) FROM usage_events WHERE user_id = u.id), 0) AS cache_creation_input_tokens,
      COALESCE((SELECT SUM(cache_read_input_tokens)     FROM usage_events WHERE user_id = u.id), 0) AS cache_read_input_tokens,
      COALESCE((SELECT SUM(total_cost_usd)              FROM usage_events WHERE user_id = u.id), 0) AS total_cost_usd
    FROM users u
    ORDER BY u.created_at ASC
  `).all().map((r) => ({ ...r, is_admin: !!r.is_admin }));

  // Per-project rollup. JOIN to users for the owner email (LEFT JOIN — if the
  // owner was deleted, owner_user_id is NULL and owner_email becomes null).
  const projects = db.prepare(`
    SELECT
      p.id,
      p.name,
      p.is_public,
      p.created_at,
      p.model,
      p.owner_user_id,
      u.email AS owner_email,
      (SELECT COUNT(*) FROM usage_events ue WHERE ue.project_id = p.id) AS turn_count,
      COALESCE((SELECT SUM(input_tokens)                FROM usage_events WHERE project_id = p.id), 0) AS input_tokens,
      COALESCE((SELECT SUM(output_tokens)               FROM usage_events WHERE project_id = p.id), 0) AS output_tokens,
      COALESCE((SELECT SUM(cache_creation_input_tokens) FROM usage_events WHERE project_id = p.id), 0) AS cache_creation_input_tokens,
      COALESCE((SELECT SUM(cache_read_input_tokens)     FROM usage_events WHERE project_id = p.id), 0) AS cache_read_input_tokens,
      COALESCE((SELECT SUM(total_cost_usd)              FROM usage_events WHERE project_id = p.id), 0) AS total_cost_usd
    FROM projects p
    LEFT JOIN users u ON u.id = p.owner_user_id
    ORDER BY p.created_at ASC
  `).all().map((r) => ({ ...r, is_public: !!r.is_public }));

  // Summary — useful as a top-of-page header in the UI.
  const summary = db.prepare(`
    SELECT
      (SELECT COUNT(*) FROM users)             AS total_users,
      (SELECT COUNT(*) FROM projects)          AS total_projects,
      (SELECT COUNT(*) FROM usage_events)      AS total_turns,
      COALESCE((SELECT SUM(total_cost_usd) FROM usage_events), 0) AS total_cost_usd,
      (SELECT MIN(created_at) FROM usage_events) AS data_tracked_since
  `).get();

  res.json({
    summary,
    users,
    projects,
    generated_at: Math.floor(Date.now() / 1000),
  });
});

// GET /api/admin/audit-logs?level=info,warning,error&search=text&limit=500
// Complete backend audit stream persisted in SQLite. Captures console info,
// warnings, errors, HTTP statuses, process safety-net errors, and explicit
// admin actions from the moment audit logging is installed on startup.
admin.get('/audit-logs', (req, res) => {
  const allowed = new Set(['info', 'warning', 'error']);
  const levels = String(req.query.level || 'info,warning,error')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter((s) => allowed.has(s));
  const selected = levels.length ? levels : ['info', 'warning', 'error'];
  const limit = Math.min(Math.max(Number(req.query.limit || 500), 1), 5000);
  const search = String(req.query.search || '').trim();
  const params = [...selected];
  let where = `level IN (${selected.map(() => '?').join(',')})`;
  if (search) {
    where += ' AND (message LIKE ? OR source LIKE ? OR meta LIKE ?)';
    const q = `%${search}%`;
    params.push(q, q, q);
  }
  params.push(limit);

  const rows = db.prepare(`
    SELECT id, level, source, message, meta, user_id, project_id, request_id, created_at
      FROM audit_logs
     WHERE ${where}
     ORDER BY created_at DESC, id DESC
     LIMIT ?
  `).all(...params).map((r) => {
    let meta = null;
    try { meta = r.meta ? JSON.parse(r.meta) : null; } catch { meta = r.meta; }
    return { ...r, meta };
  });

  const summary = db.prepare(`
    SELECT
      COUNT(*) AS total,
      SUM(CASE WHEN level = 'info' THEN 1 ELSE 0 END) AS info,
      SUM(CASE WHEN level = 'warning' THEN 1 ELSE 0 END) AS warning,
      SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) AS error,
      MIN(created_at) AS oldest,
      MAX(created_at) AS newest
    FROM audit_logs
  `).get();

  res.json({
    rows,
    summary,
    filters: { levels: selected, search, limit },
    generated_at: Math.floor(Date.now() / 1000),
  });
});

// POST /api/admin/restart/backend
// Respond first, then terminate the Node process. In production this should be
// run under a supervisor (pm2/systemd/docker/node --watch) so it comes back up.
admin.post('/restart/backend', (req, res) => {
  auditLog('warning', 'admin requested backend restart', {
    source: 'admin',
    userId: req.user?.id,
    requestId: req.auditRequestId,
  });
  res.json({
    ok: true,
    target: 'backend',
    message: 'Backend restart requested. The process will exit after this response; the supervisor must restart it.',
  });
  setTimeout(() => {
    process.exit(0);
  }, 250);
});

// POST /api/admin/restart/frontend
// Server deployments usually serve frontend/dist from the backend, so there is
// no separate frontend process. Operators that do run one can set
// FRONTEND_RESTART_CMD, for example: "pm2 restart quantnik-frontend".
admin.post('/restart/frontend', (req, res) => {
  const cmd = process.env.FRONTEND_RESTART_CMD?.trim();
  if (!cmd) {
    auditLog('info', 'admin requested frontend restart; no command configured', {
      source: 'admin',
      userId: req.user?.id,
      requestId: req.auditRequestId,
    });
    return res.json({
      ok: true,
      target: 'frontend',
      restarted: false,
      message: 'No FRONTEND_RESTART_CMD is configured. This deployment serves the frontend as static files; reload the browser or restart the backend after a new build.',
    });
  }

  const child = spawn(cmd, {
    shell: true,
    detached: true,
    stdio: 'ignore',
    env: process.env,
  });
  child.unref();
  auditLog('warning', 'admin launched frontend restart command', {
    source: 'admin',
    command: cmd,
    userId: req.user?.id,
    requestId: req.auditRequestId,
  });
  res.json({
    ok: true,
    target: 'frontend',
    restarted: true,
    command: cmd,
    message: 'Frontend restart command launched.',
  });
});

// DELETE /api/admin/users/:id
// Hard-delete a user account. Body:
//   { disposition: 'transfer' | 'delete', transferToUserId?: number }
//
// disposition handles whatever projects the deleted user owns:
//   - 'transfer'  → reassign every project to transferToUserId (must exist
//                   and not be the same user being deleted)
//   - 'delete'    → delete the user's projects (CASCADE wipes their
//                   sessions/messages/phases/repos via FK; on-disk
//                   workspace folders are NOT removed — operator can clean
//                   those separately)
//
// Safety rails (return 400 BEFORE any write):
//   - target user must exist
//   - admin cannot delete THEMSELVES (use the regular sign-out flow instead)
//   - admin cannot delete the LAST admin (would lock out admin access
//     entirely — even from this very route)
//   - disposition is required when the target has ≥1 project
//   - transferToUserId is required when disposition='transfer'; must exist
//     and must not be the target id
admin.delete('/users/:id', (req, res) => {
  const targetId = Number(req.params.id);
  if (!Number.isInteger(targetId) || targetId <= 0) {
    return res.status(400).json({ error: 'invalid user id' });
  }
  if (targetId === req.user.id) {
    return res.status(400).json({ error: 'cannot delete yourself; sign out instead' });
  }

  const target = db.prepare('SELECT id, email, is_admin FROM users WHERE id = ?').get(targetId);
  if (!target) return res.status(404).json({ error: 'user not found' });

  // Last-admin protection. If deleting this user would leave zero admins,
  // refuse — the workbench would be locked out of every admin surface.
  if (target.is_admin) {
    const adminCount = db.prepare('SELECT COUNT(*) AS n FROM users WHERE is_admin = 1').get().n;
    if (adminCount <= 1) {
      return res.status(400).json({ error: 'cannot delete the last admin' });
    }
  }

  const projectCount = db
    .prepare('SELECT COUNT(*) AS n FROM projects WHERE owner_user_id = ?')
    .get(targetId).n;

  const { disposition, transferToUserId } = req.body || {};

  if (projectCount > 0) {
    if (disposition !== 'transfer' && disposition !== 'delete') {
      return res.status(400).json({
        error: `user owns ${projectCount} project(s); body must include disposition: 'transfer' | 'delete'`,
        projectCount,
      });
    }
    if (disposition === 'transfer') {
      const transferId = Number(transferToUserId);
      if (!Number.isInteger(transferId) || transferId <= 0) {
        return res.status(400).json({ error: 'transferToUserId required for disposition=transfer' });
      }
      if (transferId === targetId) {
        return res.status(400).json({ error: 'transferToUserId cannot equal the user being deleted' });
      }
      const transferTarget = db.prepare('SELECT id FROM users WHERE id = ?').get(transferId);
      if (!transferTarget) {
        return res.status(400).json({ error: 'transferToUserId references a user that does not exist' });
      }
    }
  }

  // All gates passed — execute in a single transaction so a mid-flight
  // failure doesn't leave the DB in a half-deleted state.
  const tx = db.transaction(() => {
    if (projectCount > 0) {
      if (disposition === 'transfer') {
        db.prepare('UPDATE projects SET owner_user_id = ? WHERE owner_user_id = ?')
          .run(Number(transferToUserId), targetId);
      } else { // 'delete'
        // Children (sessions, messages, phases, repos, mcp configs,
        // context sources for this project, etc.) cascade via FK.
        db.prepare('DELETE FROM projects WHERE owner_user_id = ?').run(targetId);
      }
    }
    db.prepare('DELETE FROM users WHERE id = ?').run(targetId);
  });
  tx();
  auditLog('warning', `admin deleted user ${target.email}`, {
    source: 'admin',
    userId: req.user?.id,
    deletedUserId: targetId,
    deletedUserEmail: target.email,
    projectsHandled: projectCount,
    disposition: projectCount > 0 ? disposition : 'none',
    requestId: req.auditRequestId,
  });

  res.json({
    ok: true,
    deletedUserId: targetId,
    deletedUserEmail: target.email,
    projectsHandled: projectCount,
    disposition: projectCount > 0 ? disposition : 'none',
    transferredToUserId: disposition === 'transfer' ? Number(transferToUserId) : null,
  });
});
