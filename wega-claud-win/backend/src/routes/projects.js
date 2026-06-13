import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db, reconcileProjectSidecars } from '../db.js';
import { config } from '../config.js';
import { writeQuantnikProjectFile } from './atlassian.js';

export const projects = Router();

function ensureClaudeDir(projectPath) {
  const claudeDir = path.join(projectPath, '.claude');
  fs.mkdirSync(path.join(claudeDir, 'skills'), { recursive: true });
  const settingsPath = path.join(claudeDir, 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    // Service-wide MCP servers are injected at runtime from backend env.
    // Do not copy env-backed credentials into project-local files.
    fs.writeFileSync(settingsPath, JSON.stringify({ hooks: {} }, null, 2));
  }
  return claudeDir;
}

projects.get('/', (req, res) => {
  try { reconcileProjectSidecars(); } catch (e) { console.warn('[projects] sidecar reconcile failed:', e?.message); }
  // Loopback callers (the agent process — see requireAuthOrLocal in
  // auth.js) have no populated req.user; they see all projects since
  // they already have filesystem-level access to the project trees.
  if (!req.user) {
    return res.json(db.prepare(`SELECT * FROM projects ORDER BY id DESC`).all());
  }
  // Quantnik is a shared workbench: every authenticated user can see every
  // project and use all project-level tools. Admin-only behavior lives under
  // /api/admin/*, not in project visibility.
  res.json(db.prepare(`SELECT * FROM projects ORDER BY id DESC`).all());
});

projects.post('/', (req, res) => {
  const { name, path: customPath } = req.body || {};
  if (!name || !/^[a-zA-Z0-9_-]+$/.test(name)) {
    return res.status(400).json({ error: 'name must match [a-zA-Z0-9_-]+' });
  }
  const projectFsPath = customPath
    ? path.resolve(customPath)
    : path.join(config.projectsRoot, name);
  const projectPath = customPath ? projectFsPath : `./data/projects/${name}`;
  fs.mkdirSync(projectFsPath, { recursive: true });
  ensureClaudeDir(projectFsPath);

  try {
    const defaultJira = process.env.DEFAULT_JIRA_PROJECT_KEY?.trim() || null;
    const defaultConfluence = process.env.DEFAULT_CONFLUENCE_SPACE_KEY?.trim() || null;
    // Auto-assign a unique Atlassian label so the dashboard's JQL filter
    // (and Confluence label filter) can scope cleanly to this project. Every
    // skill that writes to Jira/Confluence pulls labels from quantnik.json and
    // applies them — so artifacts created under this project carry the tag
    // and only those show up in this project's dashboard.
    const slug = name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '');
    const projectLabel = `quantnik-project-${slug}`;
    // owner_user_id is NULL for loopback creates — the first authenticated
    // user to log in afterward will claim un-owned rows (see auth.js
    // claimOrphanedProjects). Skills that scaffold projects from the agent
    // process therefore don't have to invent a fake owner.
    const ownerId = req.user?.id ?? null;
    // Chat runs through Anthropic direct. Do not default new projects to AWS
    // provider state just because old AWS env vars happen to exist.
    const defaultProvider = 'anthropic';
    const defaultModel = process.env.QUANTNIK_CHAT_ANTHROPIC_MODEL || 'claude-sonnet-4-6';
    const created = db.transaction(() => {
      const result = db
        .prepare(`INSERT INTO projects
          (name, path, permission_mode, jira_project_key, confluence_space_key, atlassian_labels, owner_user_id,
           llm_provider, llm_model, model)
          VALUES (?, ?, 'acceptEdits', ?, ?, ?, ?, ?, ?, ?)`)
        .run(name, projectPath, defaultJira, defaultConfluence, JSON.stringify([projectLabel]), ownerId,
             defaultProvider, defaultModel, defaultModel);
      const row = db.prepare('SELECT * FROM projects WHERE id = ?').get(result.lastInsertRowid);
      writeQuantnikProjectFile(row);
      return row;
    })();
    res.json(created);
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// Loopback callers (no req.user) act as a superuser-equivalent for project
// access — they can already touch the filesystem and DB directly, so the
// HTTP layer offering them the same view is the consistent choice. Routes
// the agent calls from inside its skills (PATCH config, DELETE, etc.)
// therefore work without needing a real session.
const isLocalCaller = (req) => !req.user;

projects.get('/:id', (req, res) => {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) return res.status(404).json({ error: 'not found' });
  // Every authenticated user can read every project. The mount middleware
  // already guarantees auth or loopback.
  res.json(project);
});

// Read-side access gate. Every authenticated user can access every project;
// admin-only behavior belongs under /api/admin/*.
function accessibleProjectOr404(req, res) {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
  if (isLocalCaller(req)) return project;
  if (req.user) return project;
  return project;
}

// Workbench write gate. Every authenticated user can mutate project-level
// state. Only /api/admin/* requires admin.
function ownProjectOr404(req, res) {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
  if (isLocalCaller(req)) return project;
  if (req.user) return project;
  return project;
}

projects.patch('/:id', (req, res) => {
  if (!ownProjectOr404(req, res)) return;
  const { model, permission_mode } = req.body || {};
  const fields = [];
  const values = [];
  if (model !== undefined) { fields.push('model = ?'); values.push(model); }
  if (permission_mode !== undefined) { fields.push('permission_mode = ?'); values.push(permission_mode); }
  if (!fields.length) return res.status(400).json({ error: 'nothing to update' });
  values.push(req.params.id);
  db.prepare(`UPDATE projects SET ${fields.join(', ')} WHERE id = ?`).run(...values);
  const updated = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  writeQuantnikProjectFile(updated);
  res.json(updated);
});

projects.delete('/:id', (req, res) => {
  if (!ownProjectOr404(req, res)) return;
  db.prepare('DELETE FROM projects WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

projects.get('/:id/messages', (req, res) => {
  // Messages are part of the collaborative surface — readable by anyone with
  // access (owner or public). Posting goes through the WS, which has its
  // own access check.
  if (!accessibleProjectOr404(req, res)) return;
  const rows = db
    .prepare('SELECT * FROM messages WHERE project_id = ? ORDER BY id ASC')
    .all(req.params.id);
  res.json(rows.map((r) => ({ ...r, payload: JSON.parse(r.payload) })));
});

projects.post('/:id/reset-session', (req, res) => {
  if (!ownProjectOr404(req, res)) return;
  db.prepare('UPDATE projects SET last_session_id = NULL WHERE id = ?').run(req.params.id);
  db.prepare('DELETE FROM messages WHERE project_id = ?').run(req.params.id);
  res.json({ ok: true });
});
