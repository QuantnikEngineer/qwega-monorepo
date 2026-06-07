import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';

export const settings = Router();

function projectOr404(id, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'project not found' }); return null; }
  return p;
}

function settingsPath(project) {
  const dir = path.join(project.path, '.claude');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'settings.json');
  if (!fs.existsSync(file)) fs.writeFileSync(file, JSON.stringify({ hooks: {} }, null, 2));
  return file;
}

function readSettings(project) {
  return JSON.parse(fs.readFileSync(settingsPath(project), 'utf8'));
}

function writeSettings(project, data) {
  fs.writeFileSync(settingsPath(project), JSON.stringify(data, null, 2));
}

settings.get('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  res.json(readSettings(project));
});

settings.put('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const body = req.body;
  if (!body || typeof body !== 'object') return res.status(400).json({ error: 'body must be JSON object' });
  writeSettings(project, body);
  res.json({ ok: true });
});

settings.get('/:projectId/hooks', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  res.json(readSettings(project).hooks || {});
});

settings.put('/:projectId/hooks', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const hooks = req.body;
  if (!hooks || typeof hooks !== 'object') return res.status(400).json({ error: 'body must be object' });
  const data = readSettings(project);
  data.hooks = hooks;
  writeSettings(project, data);
  res.json({ ok: true });
});
