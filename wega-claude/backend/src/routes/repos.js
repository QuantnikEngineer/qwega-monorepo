import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { spawn } from 'node:child_process';
import { db } from '../db.js';

export const repos = Router();

function projectOr404(id, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'project not found' }); return null; }
  return p;
}

function inspect(repoPath) {
  const exists = fs.existsSync(repoPath);
  const isGit = exists && fs.existsSync(path.join(repoPath, '.git'));
  return { exists, isGit };
}

function withStatus(repo) {
  return { ...repo, ...inspect(repo.path) };
}

repos.get('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const rows = db
    .prepare('SELECT * FROM project_repos WHERE project_id = ? ORDER BY id ASC')
    .all(project.id);
  res.json(rows.map(withStatus));
});

repos.post('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const { name, path: rPath, remoteUrl } = req.body || {};
  if (!name || typeof name !== 'string') return res.status(400).json({ error: 'name required' });
  if (!rPath || !path.isAbsolute(rPath)) return res.status(400).json({ error: 'path must be absolute' });
  if (rPath === project.path || rPath.startsWith(project.path + path.sep)) {
    return res.status(400).json({ error: 'repo path cannot be inside the project workspace' });
  }
  const result = db
    .prepare('INSERT INTO project_repos (project_id, name, path, remote_url) VALUES (?, ?, ?, ?)')
    .run(project.id, name.trim(), rPath, remoteUrl?.trim() || null);
  const row = db.prepare('SELECT * FROM project_repos WHERE id = ?').get(result.lastInsertRowid);
  res.json(withStatus(row));
});

repos.delete('/:projectId/:repoId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  db.prepare('DELETE FROM project_repos WHERE id = ? AND project_id = ?')
    .run(req.params.repoId, project.id);
  res.json({ ok: true });
});

repos.post('/:projectId/:repoId/clone', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const repo = db
    .prepare('SELECT * FROM project_repos WHERE id = ? AND project_id = ?')
    .get(req.params.repoId, project.id);
  if (!repo) return res.status(404).json({ error: 'repo not found' });
  if (!repo.remote_url) return res.status(400).json({ error: 'no remote_url to clone' });
  if (fs.existsSync(repo.path)) return res.status(400).json({ error: 'path already exists' });

  fs.mkdirSync(path.dirname(repo.path), { recursive: true });

  const proc = spawn('git', ['clone', repo.remote_url, repo.path], {
    timeout: 120_000,
  });

  let stderr = '';
  let stdout = '';
  proc.stdout.on('data', (d) => { stdout += d.toString(); });
  proc.stderr.on('data', (d) => { stderr += d.toString(); });

  proc.on('close', (code) => {
    if (code === 0) return res.json({ ok: true, stdout, stderr });
    res.status(500).json({ error: 'git clone failed', code, stdout, stderr });
  });
  proc.on('error', (err) => res.status(500).json({ error: err.message }));
});
