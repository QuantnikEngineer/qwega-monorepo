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
// Two access tiers:
//
//   projectForRead   — owner OR is_public OR admin OR loopback
//                      Use for GETs and non-mutating reads.
//   projectForWrite  — owner OR loopback ONLY (NOT admin, NOT public)
//                      Use for PATCH/PUT/POST that mutate config or state.
//                      Per the documented contract in db.js: admins can
//                      SEE everyone's projects but can't MUTATE them.
//
// Both helpers write the 404 response body themselves and return null on
// denial so callers reduce to:
//
//     const project = projectForRead(req.params.projectId, req, res);
//     if (!project) return;
//
// 404 (not 403) on every denial — keeps the "don't leak existence"
// property for non-admins probing for projects they can't see.

import { db } from '../db.js';

const isLoopback = (req) => !req.user;

/** Read-side gate. Returns the project row or null (404 already sent). */
export function projectForRead(id, req, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'not found' }); return null; }
  if (isLoopback(req))                       return p;
  if (p.owner_user_id === req.user.id)       return p;
  if (p.is_public)                            return p;
  if (req.user.is_admin)                     return p;
  res.status(404).json({ error: 'not found' });
  return null;
}

/** Write-side gate. Strict — owner OR loopback only. */
export function projectForWrite(id, req, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'not found' }); return null; }
  if (isLoopback(req))                       return p;
  if (p.owner_user_id === req.user.id)       return p;
  res.status(404).json({ error: 'not found' });
  return null;
}
