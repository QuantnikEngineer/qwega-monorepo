import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { spawn } from 'node:child_process';
import { db } from '../db.js';
import { config } from '../config.js';
import { projectForRead, projectForWrite } from './projectAccess.js';

export const repos = Router();

const REPOS_ROOT = path.join(path.dirname(config.dbPath), 'repos');
fs.mkdirSync(REPOS_ROOT, { recursive: true });

function inspect(repoPath) {
  const exists = fs.existsSync(repoPath);
  const isGit = exists && fs.existsSync(path.join(repoPath, '.git'));
  return { exists, isGit };
}

function withStatus(repo) {
  return { ...repo, ...inspect(repo.path) };
}

// Derive a filesystem-safe leaf name from a git remote URL.
// `https://example.com/foo/my-svc.git` → `my-svc`
// `git@github.com:foo/my-svc.git`      → `my-svc`
function slugFromRemoteUrl(remoteUrl) {
  if (!remoteUrl) return null;
  const stripped = remoteUrl.trim().replace(/\.git$/, '').replace(/\/$/, '');
  const lastSlash = Math.max(stripped.lastIndexOf('/'), stripped.lastIndexOf(':'));
  const leaf = lastSlash >= 0 ? stripped.slice(lastSlash + 1) : stripped;
  return leaf.replace(/[^a-zA-Z0-9._-]+/g, '-').toLowerCase() || 'repo';
}

function defaultLocalPath(projectName, remoteUrl, name) {
  const projectSlug = String(projectName || 'project').replace(/[^a-zA-Z0-9._-]+/g, '-').toLowerCase();
  const repoSlug = slugFromRemoteUrl(remoteUrl) || String(name || 'repo').replace(/[^a-zA-Z0-9._-]+/g, '-').toLowerCase();
  return path.join(REPOS_ROOT, projectSlug, repoSlug);
}

// Promise-wrapped `git clone`. Resolves on success, rejects with { code, stderr }
// on failure. Caller is responsible for deleting the row / handling cleanup.
function gitClone(remoteUrl, targetPath) {
  return new Promise((resolve, reject) => {
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    const proc = spawn('git', ['clone', remoteUrl, targetPath], { timeout: 180_000 });
    let stderr = '';
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(Object.assign(new Error(`git clone exited ${code}`), { code, stdout, stderr }));
    });
    proc.on('error', reject);
  });
}

repos.get('/:projectId', (req, res) => {
  const project = projectForRead(req.params.projectId, req, res);
  if (!project) return;
  const rows = db
    .prepare('SELECT * FROM project_repos WHERE project_id = ? ORDER BY id ASC')
    .all(project.id);
  res.json(rows.map(withStatus));
});

repos.post('/:projectId', async (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  let { name, remoteUrl } = req.body || {};
  name = (name || '').trim();
  remoteUrl = (remoteUrl || '').trim();

  if (!name) return res.status(400).json({ error: 'name required' });
  if (!remoteUrl) return res.status(400).json({ error: 'remote URL is required — wega2 stores repos by remote and clones a local working copy automatically' });

  // Local path is auto-derived under wega2's repos root. Users no longer
  // type it — the repo's identity is the remote URL; the local path is
  // wega2's clone target.
  const rPath = defaultLocalPath(project.name, remoteUrl, name);

  // Clone immediately so the orchestrator (and every other skill that
  // reads additionalDirectories) sees a populated working tree on the
  // next chat turn. If the target already exists and is a git repo,
  // reuse it; if it exists and isn't, refuse (avoid clobbering arbitrary
  // files at the auto-derived path — unlikely but possible if the user
  // pre-created the dir).
  let cloneNote = null;
  const targetExists = fs.existsSync(rPath);
  const targetIsGit = targetExists && fs.existsSync(path.join(rPath, '.git'));
  if (!targetExists) {
    try { await gitClone(remoteUrl, rPath); cloneNote = 'cloned'; }
    catch (e) {
      return res.status(500).json({
        error: 'git clone failed',
        message: e.message,
        stderr: e.stderr || null,
        path: rPath,
        hint: 'check that the remote URL is reachable and credentials are configured (git credential manager / token in URL).',
      });
    }
  } else if (targetIsGit) {
    cloneNote = 'already-cloned';
  } else {
    return res.status(409).json({
      error: 'auto-derived path exists and is not a git repo',
      path: rPath,
      hint: 'remove or rename that folder, then retry.',
    });
  }

  const result = db
    .prepare('INSERT INTO project_repos (project_id, name, path, remote_url) VALUES (?, ?, ?, ?)')
    .run(project.id, name, rPath, remoteUrl);
  const row = db.prepare('SELECT * FROM project_repos WHERE id = ?').get(result.lastInsertRowid);
  res.json({ ...withStatus(row), cloneNote });
});

repos.get('/:projectId/:repoId/tree', (req, res) => {
  const project = projectForRead(req.params.projectId, req, res);
  if (!project) return;
  const repo = db
    .prepare('SELECT * FROM project_repos WHERE id = ? AND project_id = ?')
    .get(req.params.repoId, project.id);
  if (!repo) return res.status(404).json({ error: 'repo not found' });
  if (!fs.existsSync(repo.path)) return res.json({ entries: [], stats: null });

  const skip = new Set(['.git', 'node_modules', 'dist', 'build', '.next', '.turbo', '.cache', 'coverage', '.venv', '__pycache__']);
  const maxEntries = 12;
  const entries = [];
  let files = 0;
  let dirs = 0;

  function walk(dir, depth, prefix) {
    if (entries.length >= maxEntries || depth > 2) return;
    let items;
    try { items = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    items.sort((a, b) => {
      if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    const filtered = items.filter((i) => !skip.has(i.name) && !i.name.startsWith('.'));
    filtered.forEach((item) => {
      if (entries.length >= maxEntries) return;
      if (item.isDirectory()) {
        dirs++;
        entries.push({ depth, name: item.name, kind: 'dir' });
        if (depth < 1) walk(path.join(dir, item.name), depth + 1, prefix);
      } else {
        files++;
        let size = null;
        try { size = fs.statSync(path.join(dir, item.name)).size; } catch {}
        entries.push({ depth, name: item.name, kind: 'file', size });
      }
    });
  }

  walk(repo.path, 0, '');

  // Get git status / branch info
  let branch = null;
  let ahead = 0, behind = 0;
  try {
    if (fs.existsSync(path.join(repo.path, '.git'))) {
      const head = fs.readFileSync(path.join(repo.path, '.git', 'HEAD'), 'utf8').trim();
      if (head.startsWith('ref: refs/heads/')) branch = head.slice('ref: refs/heads/'.length);
    }
  } catch {}

  res.json({ entries, stats: { files, dirs }, branch, ahead, behind });
});

repos.delete('/:projectId/:repoId', (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  db.prepare('DELETE FROM project_repos WHERE id = ? AND project_id = ?')
    .run(req.params.repoId, project.id);
  res.json({ ok: true });
});

repos.post('/:projectId/:repoId/clone', async (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  const repo = db
    .prepare('SELECT * FROM project_repos WHERE id = ? AND project_id = ?')
    .get(req.params.repoId, project.id);
  if (!repo) return res.status(404).json({ error: 'repo not found' });
  if (!repo.remote_url) return res.status(400).json({ error: 'no remote_url to clone' });
  if (fs.existsSync(repo.path)) return res.status(400).json({ error: 'path already exists' });

  try {
    const { stdout, stderr } = await gitClone(repo.remote_url, repo.path);
    res.json({ ok: true, stdout, stderr });
  } catch (e) {
    res.status(500).json({ error: 'git clone failed', code: e.code, stderr: e.stderr, message: e.message });
  }
});
