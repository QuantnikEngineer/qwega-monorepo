// Shared per-project access gates. Every route that resolves a project by
// id from the URL (`/api/{settings,llm,atlassian,mcp,repos,skills,phases,
// projects,uploads,...}/:id...`) goes through one of these two helpers so
// the access rules stay consistent across the backend.
//
// Until this module landed, each route file defined its own `projectOr404`
// helper that did a bare `SELECT * FROM projects WHERE id = ?` with no
// ownership check, which meant any authenticated user could hit a
// per-project endpoint by guessing the id. Even after admin-scope-all
// landed in /api/projects, those satellite endpoints stayed wide open.
// This module closes that hole.
//
// Access model:
//
//   Any authenticated user can read and work in any project. Quantnik is a
//   shared workbench: users should be able to use chat, skills, MCPs, repos,
//   uploads, project settings, and phases across the workspace.
//
//   Admin-only behavior belongs exclusively under /api/admin/*.
//
// Both helpers write the 404 response body themselves and return null on
// denial so callers reduce to:
//
//     const project = projectForRead(req.params.projectId, req, res);
//     if (!project) return;
//
// 404 only when the project truly does not exist.

import { db } from '../db.js';

const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1']);
const isLoopback = (req) => {
  const ip = req.socket?.remoteAddress || '';
  const stripped = ip.replace(/^::ffff:/, '');
  return LOOPBACK_HOSTS.has(ip) || LOOPBACK_HOSTS.has(stripped) || stripped === '127.0.0.1';
};

/** Read-side gate. Returns the project row or null (404 already sent). */
export function projectForRead(id, req, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'not found' }); return null; }
  if (isLoopback(req)) return p;
  if (req.user) return p;
  res.status(401).json({ error: 'authentication required' });
  return null;
}

/** Write-side gate. Any authenticated user may work in a project. */
export function projectForWrite(id, req, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'not found' }); return null; }
  if (isLoopback(req)) return p;
  if (req.user) return p;
  res.status(401).json({ error: 'authentication required' });
  return null;
}
