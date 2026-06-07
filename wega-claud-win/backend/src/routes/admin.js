import { Router } from 'express';
import { db } from '../db.js';

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
