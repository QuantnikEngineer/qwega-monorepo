import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { config, getMcpServersFromEnv } from '../config.js';

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

projects.get('/', (_req, res) => {
  res.json(db.prepare('SELECT * FROM projects ORDER BY id DESC').all());
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
    const result = db
      .prepare("INSERT INTO projects (name, path, permission_mode) VALUES (?, ?, 'bypassPermissions')")
      .run(name, projectPath);
    res.json(db.prepare('SELECT * FROM projects WHERE id = ?').get(result.lastInsertRowid));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

projects.get('/:id', (req, res) => {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id);
  if (!project) return res.status(404).json({ error: 'not found' });
  res.json(project);
});

projects.patch('/:id', (req, res) => {
  const { model, permission_mode } = req.body || {};
  const fields = [];
  const values = [];
  if (model !== undefined) { fields.push('model = ?'); values.push(model); }
  if (permission_mode !== undefined) { fields.push('permission_mode = ?'); values.push(permission_mode); }
  if (!fields.length) return res.status(400).json({ error: 'nothing to update' });
  values.push(req.params.id);
  db.prepare(`UPDATE projects SET ${fields.join(', ')} WHERE id = ?`).run(...values);
  res.json(db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.id));
});

projects.delete('/:id', (req, res) => {
  db.prepare('DELETE FROM projects WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

projects.get('/:id/messages', (req, res) => {
  const rows = db
    .prepare('SELECT * FROM messages WHERE project_id = ? ORDER BY id ASC')
    .all(req.params.id);
  res.json(rows.map((r) => ({ ...r, payload: JSON.parse(r.payload) })));
});

projects.post('/:id/reset-session', (req, res) => {
  db.prepare('UPDATE projects SET last_session_id = NULL WHERE id = ?').run(req.params.id);
  db.prepare('DELETE FROM messages WHERE project_id = ?').run(req.params.id);
  res.json({ ok: true });
});
