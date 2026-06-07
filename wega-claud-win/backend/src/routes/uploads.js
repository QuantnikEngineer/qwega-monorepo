import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import multer from 'multer';
import { db } from '../db.js';

export const uploads = Router();

const UPLOAD_SUBDIR = 'uploads';

function safeBase(name) {
  return name
    .replace(/[^\w.\-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120) || 'file';
}

const storage = multer.diskStorage({
  destination(req, _file, cb) {
    const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.projectId);
    if (!project) return cb(new Error('project not found'));
    const dir = path.join(project.path, UPLOAD_SUBDIR);
    fs.mkdirSync(dir, { recursive: true });
    req._project = project;
    cb(null, dir);
  },
  filename(_req, file, cb) {
    const ts = Date.now();
    cb(null, `${ts}-${safeBase(file.originalname)}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 50 * 1024 * 1024 },
});

// Pre-flight check so we 404 cleanly before multer touches multipart state —
// this prevents the busboy / stream error chain from spitting a 500 + stack
// trace when the frontend has a stale project id cached.
uploads.post('/:projectId',
  (req, res, next) => {
    const project = db.prepare('SELECT id FROM projects WHERE id = ?').get(req.params.projectId);
    if (!project) return res.status(404).json({ error: 'project not found — refresh the project list and retry' });
    next();
  },
  (req, res, next) => {
    upload.single('file')(req, res, (err) => {
      if (!err) return next();
      if (err.message === 'project not found') {
        return res.status(404).json({ error: err.message });
      }
      if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(413).json({ error: 'file exceeds 50 MB limit' });
      }
      return res.status(400).json({ error: `upload failed: ${err.message}` });
    });
  },
  (req, res) => {
    if (!req.file) return res.status(400).json({ error: 'no file' });
    const relPath = path.posix.join(UPLOAD_SUBDIR, req.file.filename);
    res.json({
      ok: true,
      originalName: req.file.originalname,
      storedName: req.file.filename,
      relativePath: relPath,
      absolutePath: req.file.path,
      size: req.file.size,
      mimeType: req.file.mimetype,
    });
  },
);

uploads.get('/:projectId', (req, res) => {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.projectId);
  if (!project) return res.status(404).json({ error: 'project not found' });
  const dir = path.join(project.path, UPLOAD_SUBDIR);
  if (!fs.existsSync(dir)) return res.json([]);
  const files = fs.readdirSync(dir).map((name) => {
    const stat = fs.statSync(path.join(dir, name));
    return { name, size: stat.size, mtime: stat.mtimeMs, relativePath: path.posix.join(UPLOAD_SUBDIR, name) };
  });
  files.sort((a, b) => b.mtime - a.mtime);
  res.json(files);
});

uploads.delete('/:projectId/:filename', (req, res) => {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.projectId);
  if (!project) return res.status(404).json({ error: 'project not found' });
  const name = req.params.filename;
  if (name.includes('/') || name.includes('\\') || name === '..' || name === '.') {
    return res.status(400).json({ error: 'invalid filename' });
  }
  const file = path.join(project.path, UPLOAD_SUBDIR, name);
  if (fs.existsSync(file)) fs.unlinkSync(file);
  res.json({ ok: true });
});

uploads.get('/:projectId/:filename/raw', (req, res) => {
  const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(req.params.projectId);
  if (!project) return res.status(404).json({ error: 'project not found' });
  const name = req.params.filename;
  if (name.includes('/') || name.includes('\\') || name === '..' || name === '.') {
    return res.status(400).json({ error: 'invalid filename' });
  }
  const file = path.join(project.path, UPLOAD_SUBDIR, name);
  if (!fs.existsSync(file)) return res.status(404).json({ error: 'not found' });
  res.download(file);
});
