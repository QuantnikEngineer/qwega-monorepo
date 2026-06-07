import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { config, getMcpServersFromEnv } from '../config.js';
import { writeWegaProjectFile } from './atlassian.js';

export const projects = Router();

function ensureClaudeDir(projectPath) {
  const claudeDir = path.join(projectPath, '.claude');
  fs.mkdirSync(path.join(claudeDir, 'skills'), { recursive: true });
  const settingsPath = path.join(claudeDir, 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    // Auto-populate MCP servers from environment variables
    const mcpServers = getMcpServersFromEnv();
    const settings = { hooks: {} };
    if (Object.keys(mcpServers).length > 0) {
      settings.mcpServers = mcpServers;
    }
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  }
  return claudeDir;
}

projects.get('/', (req, res) => {
  // Loopback callers (the agent process — see requireAuthOrLocal in
  // auth.js) have no populated req.user; they see all projects since
  // they already have filesystem-level access to the project trees.
  if (!req.user) {
    return res.json(db.prepare(`SELECT * FROM projects ORDER BY id DESC`).all());
  }
  // Show the caller's own projects + every project flagged is_public = 1
  // (shared workspaces — see db.js). Same ordering for both.
  res.json(
    db.prepare(`SELECT * FROM projects
                WHERE owner_user_id = ? OR is_public = 1
                ORDER BY id DESC`).all(req.user.id)
  );
});

projects.post('/', (req, res) => {
  const { name, path: customPath } = req.body || {};
  if (!name || !/^[a-zA-Z0-9_-]+$/.test(name)) {
    return res.status(400).json({ error: 'name must match [a-zA-Z0-9_-]+' });
  }
  const projectPath = customPath
    ? path.resolve(customPath)
    : path.join(config.projectsRoot, name);
  fs.mkdirSync(projectPath, { recursive: true });
  ensureClaudeDir(projectPath);

  try {
    const defaultJira = process.env.DEFAULT_JIRA_PROJECT_KEY?.trim() || null;
    const defaultConfluence = process.env.DEFAULT_CONFLUENCE_SPACE_KEY?.trim() || null;
    // Auto-assign a unique Atlassian label so the dashboard's JQL filter
    // (and Confluence label filter) can scope cleanly to this project. Every
    // skill that writes to Jira/Confluence pulls labels from wega.json and
    // applies them — so artifacts created under this project carry the tag
    // and only those show up in this project's dashboard.
    const slug = name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '');
    const projectLabel = `wega-project-${slug}`;
    // owner_user_id is NULL for loopback creates — the first authenticated
    // user to log in afterward will claim un-owned rows (see auth.js
    // claimOrphanedProjects). Skills that scaffold projects from the agent
    // process therefore don't have to invent a fake owner.
    const ownerId = req.user?.id ?? null;
    const result = db
      .prepare(`INSERT INTO projects
        (name, path, permission_mode, jira_project_key, confluence_space_key, atlassian_labels, owner_user_id)
        VALUES (?, ?, 'acceptEdits', ?, ?, ?, ?)`)
      .run(name, projectPath, defaultJira, defaultConfluence, JSON.stringify([projectLabel]), ownerId);
    const created = db.prepare('SELECT * FROM projects WHERE id = ?').get(result.lastInsertRowid);
    writeWegaProjectFile(created);
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
  // Don't leak existence of other users' projects — return 404, not 403.
  // is_public projects are visible to every authenticated user.
  // Loopback callers bypass the ownership check (see isLocalCaller above).
  if (!isLocalCaller(req) && project.owner_user_id !== req.user.id && !project.is_public) {
    return res.status(404).json({ error: 'not found' });
  }
  res.json(project);
});

// Read-side access gate. Returns the project if the caller is the owner OR
// the project is is_public = 1; else writes 404 and returns null. Use for
// listing, reading, and collaborative ops (chat / messages / file uploads).
function accessibleProjectOr404(req, res) {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
  if (isLocalCaller(req)) return project;
  if (project.owner_user_id !== req.user.id && !project.is_public) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
  return project;
}

// Ownership gate — strict. Used for destructive / configuration-mutating
// operations (PATCH project fields, DELETE, reset-session). Public projects
// can be read & chatted in by anyone, but only the owner can change settings
// or delete them. Loopback callers (the agent process) are treated as the
// owner for these operations — the agent already has filesystem access to
// modify everything these endpoints touch.
function ownProjectOr404(req, res) {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
  if (isLocalCaller(req)) return project;
  if (project.owner_user_id !== req.user.id) {
    res.status(404).json({ error: 'not found' });
    return null;
  }
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
  writeWegaProjectFile(updated);
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
