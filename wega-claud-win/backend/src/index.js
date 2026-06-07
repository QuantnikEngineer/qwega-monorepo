import express from 'express';
import cors from 'cors';
import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { config } from './config.js';
import './db.js';
import { projects } from './routes/projects.js';
import { skills } from './routes/skills.js';
import { settings } from './routes/settings.js';
import { inherited } from './routes/inherited.js';
import { sessionInfo } from './routes/session-info.js';
import { mcp } from './routes/mcp.js';
import { repos } from './routes/repos.js';
import { uploads } from './routes/uploads.js';
import { atlassian } from './routes/atlassian.js';
import { llm } from './routes/llm.js';
import { codeStats } from './routes/code-stats.js';
import { phases } from './routes/phases.js';
import { auth, attachAuth, requireAuth, requireAdmin, requireAuthOrLocal } from './routes/auth.js';
import { admin } from './routes/admin.js';
import { context } from './routes/context.js';
import { deployments, deploymentDispatcher, restartLiveDeployments } from './routes/deployments.js';
import { writeWegaProjectFile } from './routes/atlassian.js';
import { db } from './db.js';
import { seedSkills } from './seed-skills.js';
import { attachWebSocket } from './ws.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '2mb' }));

app.get('/api/health', (_req, res) => res.json({ ok: true }));
// Auth-token decode happens on every /api/* request; routes downstream
// either require auth (requireAuth) or are public (just /api/health and
// /api/auth/{register,login}).
app.use('/api', attachAuth);
app.use('/api/auth', auth);

// ───────────────────────────────────────────────────────────────────────────
// /api/* auth policy
// ───────────────────────────────────────────────────────────────────────────
// The wega2 agent process runs ON the same host as this backend (spawned by
// the Claude Agent SDK as a child of this server). Skills inside that agent
// regularly shell out to `curl http://localhost:6060/api/<route>` for state
// reads, phase tracking, deployment registration, etc. Those curl calls
// have NO Authorization header — the user's bearer token lives in the
// browser's localStorage, never reaches the agent's environment.
//
// Two routes that we caught the hard way (orchestrator stalled at Phase 1's
// /api/phases POST → fix; ran the orchestrator again, stalled at Phase 10's
// /api/deployments POST → fix again) — both were mounted behind requireAuth
// and returned 401 on every internal call. To stop this recurring with the
// next route that's added, the default for every internal-state route is
// now `requireAuthOrLocal` (accepts the bearer-token flow normally AND lets
// loopback callers through with no token).
//
// Anyone with shell access to this host can already touch the SQLite DB,
// spawn deployment processes, write skill files, etc. Loopback bypass does
// not expand their attack surface. Two exceptions get the strict gate:
//
//   /api/auth   — public sub-routes (register/login) anyway; bypass would
//                 only matter for /logout/me, no point.
//   /api/admin  — admin-only endpoints; requireAdmin already runs after
//                 requireAuth so non-admin remote callers 403. Loopback
//                 bypass would let any local process see cross-user usage
//                 and cost data, which the admin gate is explicitly there
//                 to prevent.
//
// If you add a new internal-state route: use `requireAuthOrLocal` unless
// there's a specific reason the agent's skills should NEVER call it.
// Picking bare `requireAuth` is what made Phase 1 + Phase 10 stall.
app.use('/api/projects',     requireAuthOrLocal, projects);
app.use('/api/skills',       requireAuthOrLocal, skills);
app.use('/api/settings',     requireAuthOrLocal, settings);
app.use('/api/inherited',    requireAuthOrLocal, inherited);
app.use('/api/session-info', requireAuthOrLocal, sessionInfo);
app.use('/api/mcp',          requireAuthOrLocal, mcp);
app.use('/api/repos',        requireAuthOrLocal, repos);
app.use('/api/uploads',      requireAuthOrLocal, uploads);
app.use('/api/atlassian',    requireAuthOrLocal, atlassian);
app.use('/api/llm',          requireAuthOrLocal, llm);
app.use('/api/code-stats',   requireAuthOrLocal, codeStats);
app.use('/api/phases',       requireAuthOrLocal, phases);
app.use('/api/deployments',  requireAuthOrLocal, deployments);
app.use('/api/context',      requireAuthOrLocal, context);
app.use('/api/admin',        requireAuth, requireAdmin, admin);

// Dynamic per-deployment dispatcher — matches /<slug>/* against the
// deployments table. Must precede the SPA catch-all so deployed apps win
// over the wega2 SPA fallback. Reserved slugs (api, ws, …) fall through.
app.use(deploymentDispatcher);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '../../frontend/dist');
if (fs.existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get(/^(?!\/api|\/ws).*/, (_req, res) => res.sendFile(path.join(distDir, 'index.html')));
  console.log(`serving frontend from ${distDir}`);
}

// Last-resort error handler — never let a route-level throw crash the
// service or return a raw stack trace to the client.
app.use((err, req, res, _next) => {
  console.error(`[unhandled ${req.method} ${req.path}]`, err);
  if (res.headersSent) return;
  const status = err.status && err.status >= 400 && err.status < 600 ? err.status : 500;
  res.status(status).json({ error: err.message || 'internal error' });
});

// Process-level safety nets so an unhandled rejection in a route handler or
// MCP stdio callback doesn't take the whole service down.
process.on('uncaughtException', (err) => {
  console.error('[uncaughtException]', err);
});
process.on('unhandledRejection', (reason) => {
  console.error('[unhandledRejection]', reason);
});

const server = http.createServer(app);
attachWebSocket(server);

server.listen(config.port, () => {
  console.log(`wega2 backend on http://localhost:${config.port}`);
  console.log(`projects root: ${config.projectsRoot}`);
  // Install bundled skills into ~/.claude/skills/ so the SDK can load them.
  // No-op on this developer box if SKIP_SKILL_SEED=1 in .env.
  try { seedSkills(); } catch (e) {
    console.error('startup skill-seed failed:', e?.message);
  }
  // Refresh every project's <cwd>/.claude/wega.json sidecar so skills running
  // inside the SDK always see current Atlassian + LLM scope, even after a
  // server upgrade or a project DB restore. No-ops if a project's cwd is
  // missing on this host. Single source of truth: the projects table.
  try {
    const rows = db.prepare('SELECT * FROM projects').all();
    let written = 0;
    for (const p of rows) {
      try { writeWegaProjectFile(p); written++; } catch {}
    }
    console.log(`wega.json sidecar refreshed for ${written}/${rows.length} project(s)`);
  } catch (e) {
    console.error('startup sidecar refresh failed:', e?.message);
  }
  // Re-spawn backend processes for deployments that were running before the
  // restart. Frontend deployments need no spawn (static files are served by
  // the dispatcher straight from disk).
  try { restartLiveDeployments(); } catch (e) {
    console.error('startup deployment respawn failed:', e?.message);
  }
});
