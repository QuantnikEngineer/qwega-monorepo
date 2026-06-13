import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';

export const skills = Router();

function projectOr404(id, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'project not found' }); return null; }
  return p;
}

function skillsDir(project) {
  const dir = path.join(project.path, '.claude', 'skills');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function safeName(name) {
  return /^[a-zA-Z0-9_-]+$/.test(name);
}

skills.get('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const dir = skillsDir(project);
  const list = fs.readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const skillPath = path.join(dir, d.name, 'SKILL.md');
      const exists = fs.existsSync(skillPath);
      return { name: d.name, hasSkillMd: exists };
    });
  res.json(list);
});

skills.get('/:projectId/:name', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  if (!safeName(req.params.name)) return res.status(400).json({ error: 'invalid name' });
  const filePath = path.join(skillsDir(project), req.params.name, 'SKILL.md');
  if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'not found' });
  res.json({ name: req.params.name, content: fs.readFileSync(filePath, 'utf8') });
});

skills.put('/:projectId/:name', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  if (!safeName(req.params.name)) return res.status(400).json({ error: 'invalid name' });
  const { content } = req.body || {};
  if (typeof content !== 'string') return res.status(400).json({ error: 'content required' });
  const dir = path.join(skillsDir(project), req.params.name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'SKILL.md'), content);
  res.json({ ok: true });
});

skills.delete('/:projectId/:name', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  if (!safeName(req.params.name)) return res.status(400).json({ error: 'invalid name' });
  const dir = path.join(skillsDir(project), req.params.name);
  fs.rmSync(dir, { recursive: true, force: true });
  res.json({ ok: true });
});
