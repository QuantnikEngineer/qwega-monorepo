// Context Engine routes — backs the Context Engine tab. CRUD on sources +
// ingest trigger + retrieval query.
//
// Auth posture matches the rest of /api/* — requireAuthOrLocal is applied at
// the mount in index.js, so loopback callers (the agent process) and bearer-
// token holders (the browser) both work. Org-scoped writes still check
// req.user.is_admin manually.

import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { ingestSource } from '../services/ingest.js';
import { retrieve } from '../services/retrieval.js';
import { isConfigured, authMode, getEmbeddingModel, getEmbeddingDim } from '../services/embedding.js';
import { ask as msQAsk } from '../services/ms-q.js';
import { projectForRead, projectForWrite } from './projectAccess.js';

export const context = Router();

// ---- helpers --------------------------------------------------------------

function parseScope(req) {
  const scope = (req.query.scope || req.body?.scope || 'project').toString();
  const projectId = Number(req.query.projectId ?? req.body?.projectId);
  if (scope === 'org') return { scope: 'org', projectId: null };
  if (scope === 'project') {
    if (!Number.isFinite(projectId)) throw new Error('project scope requires projectId');
    return { scope: 'project', projectId };
  }
  throw new Error(`scope must be 'org' or 'project'`);
}

function adminOnly(req, res) {
  if (req.user?.is_admin) return true;
  // Loopback callers bypass — same policy as everywhere else.
  if (!req.user) return true;
  res.status(403).json({ error: 'org-scoped writes are admin only' });
  return false;
}

function sourceRow(id) {
  const r = db.prepare(`
    SELECT s.*,
      (SELECT COUNT(*) FROM context_documents d WHERE d.source_id = s.id) AS doc_count_live,
      (SELECT COUNT(*) FROM context_chunks ch
        JOIN context_documents d ON d.id = ch.document_id
        WHERE d.source_id = s.id) AS chunk_count_live
    FROM context_sources s
    WHERE s.id = ?
  `).get(id);
  if (!r) return null;
  return {
    id:              r.id,
    scope:           r.scope,
    projectId:       r.project_id,
    type:            r.type,
    config:          safeJson(r.config),
    label:           r.label,
    status:          r.status,
    error:           r.error,
    lastIngestedAt:  r.last_ingested_at,
    documentCount:   r.doc_count_live,
    chunkCount:      r.chunk_count_live,
    totalTokens:     r.total_tokens,
    addedBy:         r.added_by,
    createdAt:       r.created_at,
    updatedAt:       r.updated_at,
  };
}

function safeJson(s) {
  try { return JSON.parse(s); } catch { return {}; }
}

// ---- routes ---------------------------------------------------------------

// GET /api/context/health — surface the embedding backend's state so the
// UI can show whether the first-ingest model download has happened yet.
context.get('/health', (_req, res) => {
  const auth = authMode();
  res.json({
    embeddingModel: getEmbeddingModel(),
    embeddingDim:   getEmbeddingDim(),
    configured:     isConfigured(),
    backend:        'local',           // no remote vendor — runs on the quantnik host
    authMode:       auth.mode,         // always 'local' for now
    authHint:       auth.hint,
    cached:         auth.cached,
    ready:          auth.ready,
    cacheDir:       auth.cacheDir,
  });
});

// GET /api/context/sources?scope=project&projectId=14
context.get('/sources', (req, res) => {
  let scope;
  try { scope = parseScope(req); } catch (e) { return res.status(400).json({ error: e.message }); }

  const rows = scope.scope === 'org'
    ? db.prepare(`SELECT id FROM context_sources WHERE scope='org' ORDER BY id`).all()
    : db.prepare(`
        SELECT id FROM context_sources
        WHERE scope='org' OR (scope='project' AND project_id = ?)
        ORDER BY scope DESC, id
      `).all(scope.projectId);

  res.json({ sources: rows.map((r) => sourceRow(r.id)) });
});

// GET /api/context/sources/:id
context.get('/sources/:id', (req, res) => {
  const r = sourceRow(req.params.id);
  if (!r) return res.status(404).json({ error: 'source not found' });
  res.json(r);
});

// POST /api/context/sources — register a new source
// body: { scope, projectId?, type, config, label? }
context.post('/sources', (req, res) => {
  const { scope, projectId, type, config, label } = req.body || {};
  if (!scope || !['org', 'project'].includes(scope)) return res.status(400).json({ error: `scope must be 'org' or 'project'` });
  if (!type)   return res.status(400).json({ error: 'type required' });
  if (!['repo', 'document', 'website', 'confluence', 'sharepoint', 'agent_output'].includes(type)) {
    return res.status(400).json({ error: `unknown source type: ${type}` });
  }
  if (scope === 'org') {
    if (!adminOnly(req, res)) return;
    if (projectId != null) return res.status(400).json({ error: 'org scope cannot carry a projectId' });
  }
  if (scope === 'project') {
    if (!Number.isFinite(Number(projectId))) return res.status(400).json({ error: 'project scope requires projectId' });
    // Adding a context source to a project is a write — only the owner
    // (or loopback) may do it. Admins do NOT bypass; they can READ
    // someone else's project's context sources via the GET below, but
    // not mutate them.
    if (!projectForWrite(Number(projectId), req, res)) return;
  }

  const cfgStr = JSON.stringify(config || {});
  const r = db.prepare(`
    INSERT INTO context_sources (scope, project_id, type, config, label, added_by)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    scope,
    scope === 'project' ? Number(projectId) : null,
    type,
    cfgStr,
    label || null,
    req.user?.id ?? null,
  );
  res.json(sourceRow(r.lastInsertRowid));
});

// PATCH /api/context/sources/:id — update label / config / disabled
context.patch('/sources/:id', (req, res) => {
  const existing = db.prepare('SELECT * FROM context_sources WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'source not found' });
  if (existing.scope === 'org' && !adminOnly(req, res)) return;

  const sets = [];
  const vals = [];
  if (req.body?.label !== undefined) { sets.push('label = ?');  vals.push(req.body.label); }
  if (req.body?.config !== undefined){ sets.push('config = ?'); vals.push(JSON.stringify(req.body.config)); }
  if (req.body?.status !== undefined){
    if (!['disabled', 'pending'].includes(req.body.status)) {
      return res.status(400).json({ error: 'status PATCH only allows pending|disabled' });
    }
    sets.push('status = ?'); vals.push(req.body.status);
  }
  if (!sets.length) return res.status(400).json({ error: 'nothing to update' });
  sets.push(`updated_at = strftime('%s','now')`);
  vals.push(req.params.id);
  db.prepare(`UPDATE context_sources SET ${sets.join(', ')} WHERE id = ?`).run(...vals);
  res.json(sourceRow(req.params.id));
});

// DELETE /api/context/sources/:id — remove source + documents + chunks
context.delete('/sources/:id', (req, res) => {
  const existing = db.prepare('SELECT * FROM context_sources WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'source not found' });
  if (existing.scope === 'org' && !adminOnly(req, res)) return;
  db.prepare('DELETE FROM context_sources WHERE id = ?').run(req.params.id);
  res.json({ ok: true, removed: existing.id });
});

// POST /api/context/sources/:id/ingest — fire-and-forget ingest
context.post('/sources/:id/ingest', async (req, res) => {
  const existing = db.prepare('SELECT * FROM context_sources WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'source not found' });
  if (existing.scope === 'org' && !adminOnly(req, res)) return;

  // Run async, don't block the HTTP response. Client polls /sources/:id for
  // status updates (pending → ingesting → ready|failed).
  ingestSource(existing.id).catch((err) => {
    console.error(`[context ingest #${existing.id}]`, err?.message || err);
  });
  res.json({ ok: true, started: existing.id, status: 'ingesting' });
});

// POST /api/context/query — body: { scope, projectId?, query, topK? }
context.post('/query', async (req, res) => {
  const { query, topK } = req.body || {};
  if (!query || !String(query).trim()) return res.status(400).json({ error: 'query required' });
  let scope;
  try {
    const s = parseScope(req);
    scope = s.scope === 'org' ? { kind: 'org' } : { kind: 'project', projectId: s.projectId };
  } catch (e) { return res.status(400).json({ error: e.message }); }

  try {
    const r = await retrieve(String(query), scope, { topK: Math.min(50, Math.max(1, Number(topK) || 10)) });
    res.json(r);
  } catch (err) {
    res.status(500).json({ error: err?.message || String(err) });
  }
});

// POST /api/context/sources/bulk
//   { sources: [ { scope, projectId?, type, config, label? }, ... ] }
// Registers many sources in one call. Each result row is returned with its
// new id; ingest is fired in the background for every successful registration.
context.post('/sources/bulk', async (req, res) => {
  const items = Array.isArray(req.body?.sources) ? req.body.sources : null;
  if (!items || !items.length) return res.status(400).json({ error: 'body.sources[] required' });
  const created = [];
  const errors  = [];
  for (let i = 0; i < items.length; i++) {
    const s = items[i];
    try {
      if (!s.scope || !['org', 'project'].includes(s.scope)) throw new Error(`item ${i}: scope must be 'org' | 'project'`);
      if (!s.type) throw new Error(`item ${i}: type required`);
      if (s.scope === 'org' && req.user && !req.user.is_admin) throw new Error(`item ${i}: org scope is admin-only`);
      if (s.scope === 'project' && !Number.isFinite(Number(s.projectId))) throw new Error(`item ${i}: projectId required for project scope`);

      const r = db.prepare(`
        INSERT INTO context_sources (scope, project_id, type, config, label, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run(
        s.scope,
        s.scope === 'project' ? Number(s.projectId) : null,
        s.type,
        JSON.stringify(s.config || {}),
        s.label || null,
        req.user?.id ?? null,
      );
      created.push(sourceRow(r.lastInsertRowid));
      // Fire ingest in background — same pattern as POST /sources/:id/ingest
      ingestSource(r.lastInsertRowid).catch((e) => console.error(`[bulk ingest #${r.lastInsertRowid}]`, e?.message));
    } catch (e) {
      errors.push({ index: i, error: e.message });
    }
  }
  res.json({ created, errors });
});

// POST /api/context/auto-init?projectId=14
// Idempotently ensures a project has:
//   - one `repo` context source per registered project_repos row
//   - one `agent_output` context source
// Both auto-ingest in the background. Existing sources are left untouched.
// Useful as the first call when a Context Engine panel mounts for a project
// the user hasn't touched yet — they should never have to manually wire up
// repos or agent output to get the RAG agent working.
context.post('/auto-init', (req, res) => {
  const projectId = Number(req.query.projectId ?? req.body?.projectId);
  if (!Number.isFinite(projectId)) return res.status(400).json({ error: 'projectId required' });
  // Auto-init mutates context_sources — write gate (owner only).
  const project = projectForWrite(projectId, req, res);
  if (!project) return;

  const created = [];

  // Repos — only auto-register ones whose path actually exists on disk.
  // Otherwise we'd litter the panel with status=failed rows for repos that
  // were registered in the Repos tab but never cloned.
  const repos = db.prepare(`SELECT id, name, path FROM project_repos WHERE project_id = ?`).all(projectId);
  const existingRepoIds = new Set(
    db.prepare(`SELECT config FROM context_sources WHERE type='repo' AND scope='project' AND project_id = ?`)
      .all(projectId)
      .map((r) => { try { return JSON.parse(r.config).repoId; } catch { return null; } })
      .filter(Boolean),
  );
  const skipped = [];
  for (const r of repos) {
    if (existingRepoIds.has(r.id)) continue;
    if (!r.path || !fs.existsSync(r.path)) {
      skipped.push({ repoId: r.id, name: r.name, reason: `path not on disk: ${r.path}` });
      continue;
    }
    const ins = db.prepare(`
      INSERT INTO context_sources (scope, project_id, type, config, label, added_by)
      VALUES ('project', ?, 'repo', ?, ?, ?)
    `).run(projectId, JSON.stringify({ repoId: r.id }), r.name, req.user?.id ?? null);
    created.push({ id: ins.lastInsertRowid, type: 'repo', label: r.name });
    ingestSource(ins.lastInsertRowid).catch((e) => console.error(`[auto-init ingest #${ins.lastInsertRowid}]`, e?.message));
  }

  // Agent output (one per project)
  const hasAgentOut = db.prepare(`
    SELECT 1 FROM context_sources WHERE type='agent_output' AND scope='project' AND project_id = ?
  `).get(projectId);
  if (!hasAgentOut) {
    const ins = db.prepare(`
      INSERT INTO context_sources (scope, project_id, type, config, label, added_by)
      VALUES ('project', ?, 'agent_output', ?, ?, ?)
    `).run(projectId, JSON.stringify({}), 'project chat history', req.user?.id ?? null);
    created.push({ id: ins.lastInsertRowid, type: 'agent_output', label: 'project chat history' });
    ingestSource(ins.lastInsertRowid).catch((e) => console.error(`[auto-init ingest #${ins.lastInsertRowid}]`, e?.message));
  }

  res.json({
    created,
    skipped,
    message: created.length
      ? `Auto-registered ${created.length} source(s)${skipped.length ? ` (skipped ${skipped.length} — repo path missing on disk)` : ''}`
      : 'Nothing new to auto-register',
  });
});

// POST /api/ms-q/ask  (mounted under /api/context for tidiness — keeps
// auth posture + db imports consistent with the other RAG endpoints).
//
// body:
//   { question, scope, projectId?, topK?, model?,
//     history?: [{role:'user'|'assistant', content:string}, ...],
//     userName?: string }
//
// History lets the panel hold a multi-turn conversation client-side and
// replay it on each call — no server-side session state needed. userName
// lets the system prompt address the human by their first name. If the
// caller doesn't pass userName, we derive it from req.user.name / email so
// the chatbot still personalises for authenticated browser users.
context.post('/ask', async (req, res) => {
  const { question, topK, history, userName: userNameFromBody } = req.body || {};
  if (!question || !String(question).trim()) return res.status(400).json({ error: 'question required' });
  let scope;
  try {
    const s = parseScope(req);
    scope = s.scope === 'org' ? { kind: 'org' } : { kind: 'project', projectId: s.projectId };
  } catch (e) { return res.status(400).json({ error: e.message }); }

  // Resolve the human-readable name to address in the chatbot.
  // Order: body override → authenticated user.name → email local-part → null.
  let userName = userNameFromBody || null;
  if (!userName && req.user) {
    userName = req.user.name || (req.user.email ? String(req.user.email).split('@')[0] : null);
  }

  try {
    const out = await msQAsk({
      question:   String(question),
      scope,
      topK:       Math.min(20, Math.max(1, Number(topK) || 6)),
      model:      req.body?.model || undefined,
      userId:     req.user?.id ?? null,
      userName,
      history:    Array.isArray(history) ? history : [],
    });
    res.json(out);
  } catch (err) {
    res.status(500).json({ error: err?.message || String(err) });
  }
});

// GET /api/context/repos-available?projectId=14 — list project_repos rows the
// user could add as a repo source. Excludes ones already registered as a
// source on this project.
context.get('/repos-available', (req, res) => {
  const projectId = Number(req.query.projectId);
  if (!Number.isFinite(projectId)) return res.status(400).json({ error: 'projectId required' });
  // Read gate — admins can see what's available; only the owner can
  // actually wire one up via POST /sources above.
  const project = projectForRead(projectId, req, res);
  if (!project) return;

  const repos = db.prepare(`SELECT id, name, path, remote_url FROM project_repos WHERE project_id = ?`).all(projectId);
  const alreadyRegistered = new Set(
    db.prepare(`SELECT config FROM context_sources WHERE type='repo' AND scope='project' AND project_id = ?`)
      .all(projectId)
      .map((r) => {
        try { return JSON.parse(r.config).repoId; } catch { return null; }
      })
      .filter(Boolean),
  );
  res.json({
    repos: repos.map((r) => ({
      id:         r.id,
      name:       r.name,
      path:       r.path,
      remoteUrl:  r.remote_url,
      registered: alreadyRegistered.has(r.id),
    })),
  });
});
