import { Router } from 'express';
import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import net from 'node:net';
import http from 'node:http';
import { db } from '../db.js';
import { projectForWrite } from './projectAccess.js';

export const deployments = Router();

const DEPLOY_ROOT = path.resolve(process.cwd(), 'data', 'deployments');
fs.mkdirSync(DEPLOY_ROOT, { recursive: true });

// Reserved at the first path segment — must never become a deployment slug.
export const RESERVED_SLUGS = new Set([
  'api', 'ws', 'auth', 'assets', 'health', 'static', 'public', 'admin',
  'login', 'logout', 'callback', 'favicon.ico', 'index.html', 'd',
  // SPA route prefixes — must fall through to the SPA catch-all instead of
  // matching a deployed app whose slug happens to clash with a wega2 URL.
  'projects',
]);

const PORT_RANGE_START = 7000;
const PORT_RANGE_END = 7999;

// Track spawned child processes per slug so DELETE / restart can SIGTERM them.
const liveProcesses = new Map(); // slug -> { child, port }

function slugify(name) {
  return String(name || '').toLowerCase().trim()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'app';
}

async function isPortFree(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, '127.0.0.1');
  });
}

async function allocatePort() {
  // Skip ports already claimed by recorded deployments.
  const taken = new Set(
    db.prepare(`SELECT backend_port FROM deployments WHERE backend_port IS NOT NULL`).all()
      .map((r) => r.backend_port),
  );
  // Build the candidate list then Fisher-Yates shuffle so each new deployment
  // gets a random free port instead of always landing on PORT_RANGE_START.
  // Predictable port numbers make collisions with manually-started processes
  // and scrape scripts more likely; randomization spreads them out.
  const candidates = [];
  for (let p = PORT_RANGE_START; p <= PORT_RANGE_END; p++) {
    if (!taken.has(p)) candidates.push(p);
  }
  for (let i = candidates.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [candidates[i], candidates[j]] = [candidates[j], candidates[i]];
  }
  for (const p of candidates) {
    if (await isPortFree(p)) return p;
  }
  throw new Error(`no free port in range ${PORT_RANGE_START}-${PORT_RANGE_END}`);
}

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else if (entry.isFile()) fs.copyFileSync(s, d);
  }
}

function deploymentRoot(slug) { return path.join(DEPLOY_ROOT, slug); }
function deploymentFrontendDir(slug) { return path.join(deploymentRoot(slug), 'frontend'); }
function deploymentLogPath(slug) { return path.join(deploymentRoot(slug), 'backend.log'); }

function killProcess(slug) {
  const live = liveProcesses.get(slug);
  if (!live) return;
  try { live.child.kill('SIGTERM'); } catch {}
  liveProcesses.delete(slug);
}

function spawnBackend(dep) {
  if (!dep.backend_path || !dep.backend_start_cmd) return null;
  const args = dep.backend_start_args ? JSON.parse(dep.backend_start_args) : [];
  const env = { ...process.env, PORT: String(dep.backend_port) };
  // Inject CORS_ORIGIN so the deployed backend accepts requests originating
  // from the public host. Browsers send Origin even on same-origin POSTs
  // (anti-CSRF), so a generated app that defaults CORS to http://localhost:5173
  // will otherwise reject every dispatcher-proxied write. PUBLIC_BASE_URL is
  // wega2's authoritative public host; default the dev port for localhost runs.
  if (process.env.PUBLIC_BASE_URL) {
    env.CORS_ORIGIN = `${process.env.PUBLIC_BASE_URL},http://localhost:${process.env.PORT || 6060},http://localhost:5173`;
  }
  if (dep.backend_env) {
    try { Object.assign(env, JSON.parse(dep.backend_env)); } catch {}
  }
  // Ensure PORT is the wega2-allocated one even if backend_env specified a different one.
  env.PORT = String(dep.backend_port);

  const logFd = fs.openSync(dep.log_path || deploymentLogPath(dep.slug), 'a');
  const child = spawn(dep.backend_start_cmd, args, {
    cwd: dep.backend_path,
    env,
    stdio: ['ignore', logFd, logFd],
    shell: true,
    detached: false,
  });
  child.on('exit', (code) => {
    console.log(`[deploy:${dep.slug}] backend exited (code=${code})`);
    liveProcesses.delete(dep.slug);
    db.prepare(`UPDATE deployments SET status='stopped', pid=NULL WHERE slug=?`).run(dep.slug);
  });
  liveProcesses.set(dep.slug, { child, port: dep.backend_port });
  db.prepare(`UPDATE deployments SET status='running', pid=?, last_started_at=strftime('%s','now') WHERE slug=?`)
    .run(child.pid, dep.slug);
  return child;
}

// Express middleware — match the FIRST path segment as a deployment slug. If
// the slug is registered, serve from the deployment's frontend dir, OR
// reverse-proxy /<slug>/api/* to the backend's allocated port.
export function deploymentDispatcher(req, res, next) {
  const m = req.path.match(/^\/([^/]+)(\/.*)?$/);
  if (!m) return next();
  const slug = m[1];
  if (RESERVED_SLUGS.has(slug)) return next();

  const dep = db.prepare(`SELECT * FROM deployments WHERE slug=?`).get(slug);
  if (!dep) return next();

  // Canonicalize the slug root: a bare-slug URL like /globalexer (no
  // trailing slash) gets 308'd to /globalexer/. Without this, every
  // deployed SPA whose React Router uses basename "/<slug>/" (the build
  // default the orchestrator emits) fails to match any route, renders
  // nothing, and looks like a black screen against the typical dark body
  // background. Caught when the Globalexer credit-card app went dark on
  // a direct typed URL — bundle was fine, basename just didn't match.
  // 308 (vs 301) preserves the request method on GET and is permanently
  // cacheable, so browsers won't keep hitting this redirect path.
  if (!m[2]) {
    const qsIdx = req.url.indexOf('?');
    const qs = qsIdx >= 0 ? req.url.slice(qsIdx) : '';
    return res.redirect(308, `/${slug}/${qs}`);
  }

  const subPath = m[2];

  // Reverse-proxy /<slug>/api/* to the spawned backend.
  if (subPath.startsWith('/api/') || subPath === '/api') {
    if (!dep.backend_port) {
      return res.status(503).json({ error: `deployment ${slug} has no backend` });
    }
    const upstreamPath = subPath; // backend mounts its routes at /api, so pass-through
    const headers = { ...req.headers, host: `127.0.0.1:${dep.backend_port}` };

    // express.json() upstream has already consumed the request stream for any
    // body-bearing method (POST/PUT/PATCH). If we just pipe(req), the upstream
    // sees no body and hangs until the socket times out. So if req.body looks
    // parsed, reserialize it and ship as a fresh buffer with a corrected
    // content-length. GET/DELETE/HEAD have no body and fall through to pipe.
    const methodHasBody = !['GET', 'HEAD', 'DELETE', 'OPTIONS'].includes(req.method.toUpperCase());
    let bodyBuf = null;
    if (methodHasBody && req.body !== undefined && typeof req.body === 'object') {
      // ALWAYS reserialize the parsed body for body-bearing methods, even when
      // it's an empty {} — falling back to req.pipe() would send a drained
      // stream and the upstream would hang waiting for the body. Empty {}
      // becomes the literal 2-byte string "{}" so backend validation can fire.
      bodyBuf = Buffer.from(JSON.stringify(req.body));
      headers['content-length'] = String(bodyBuf.length);
      if (!headers['content-type']) headers['content-type'] = 'application/json';
      delete headers['transfer-encoding'];
    }

    const opts = {
      hostname: '127.0.0.1',
      port: dep.backend_port,
      method: req.method,
      path: upstreamPath + (req._parsedUrl?.search || ''),
      headers,
    };
    const upstream = http.request(opts, (upRes) => {
      res.writeHead(upRes.statusCode || 502, upRes.headers);
      upRes.pipe(res);
    });
    upstream.on('error', (e) => {
      if (!res.headersSent) res.status(502).json({ error: `proxy error: ${e.message}` });
    });
    if (bodyBuf) { upstream.end(bodyBuf); }
    else { req.pipe(upstream); }
    return;
  }

  // Static frontend — try exact file, else fall back to index.html (SPA).
  const root = deploymentFrontendDir(slug);
  if (!fs.existsSync(root)) {
    return res.status(503).type('text').send(`deployment ${slug} has no frontend bundle yet`);
  }
  const candidate = subPath === '/' || subPath === ''
    ? path.join(root, 'index.html')
    : path.join(root, subPath);
  const safe = path.normalize(candidate);
  if (!safe.startsWith(root)) return res.status(400).end();
  if (fs.existsSync(safe) && fs.statSync(safe).isFile()) {
    return res.sendFile(safe);
  }
  // SPA fallback
  const indexPath = path.join(root, 'index.html');
  if (fs.existsSync(indexPath)) return res.sendFile(indexPath);
  return res.status(404).type('text').send('not found');
}

// On wega2 startup: re-spawn every deployment that was running before the
// restart, so the user's deployed apps survive a service bounce.
export function restartLiveDeployments() {
  const rows = db.prepare(`SELECT * FROM deployments WHERE status IN ('running', 'pending') AND backend_path IS NOT NULL`).all();
  let started = 0;
  for (const dep of rows) {
    try { spawnBackend(dep); started++; }
    catch (e) { console.error(`[deploy:${dep.slug}] respawn failed:`, e.message); }
  }
  if (rows.length > 0) console.log(`re-spawned ${started}/${rows.length} backend deployment(s)`);
}

// ---- routes ----

deployments.post('/:projectId', async (req, res) => {
  // Deploying mutates the deployments root + spawns processes — write gate
  // (owner only). Admins do NOT bypass; only the owner (or loopback for
  // the deploy-to-platform skill) may deploy.
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;

  const {
    slug: requestedSlug,
    frontendDist,           // ABSOLUTE path to a built static dir (e.g. <project>/frontend/dist)
    backendPath,            // ABSOLUTE path to the backend source dir (optional)
    backendStartCmd,        // e.g. 'node' or 'npm' or 'python'
    backendStartArgs,       // string[]
    backendEnv,             // object — merged on top of inherited env
    publicHost,             // override the printed URL host; default = req host
  } = req.body || {};

  const slug = slugify(requestedSlug || project.name);
  if (RESERVED_SLUGS.has(slug)) {
    return res.status(400).json({ error: `slug "${slug}" is reserved` });
  }

  if (!frontendDist || !fs.existsSync(frontendDist) || !fs.statSync(frontendDist).isDirectory()) {
    return res.status(400).json({ error: `frontendDist not found or not a directory: ${frontendDist}` });
  }
  const indexHtml = path.join(frontendDist, 'index.html');
  if (!fs.existsSync(indexHtml)) {
    return res.status(400).json({ error: `frontendDist has no index.html: ${frontendDist}` });
  }

  if (backendPath && (!fs.existsSync(backendPath) || !fs.statSync(backendPath).isDirectory())) {
    return res.status(400).json({ error: `backendPath not found or not a directory: ${backendPath}` });
  }

  try {
    // 1. Kill any prior process for this slug before re-deploying
    killProcess(slug);
    db.prepare(`DELETE FROM deployments WHERE slug=?`).run(slug);

    // 2. Copy frontend dist into the deploy root
    const targetFrontend = deploymentFrontendDir(slug);
    if (fs.existsSync(targetFrontend)) {
      fs.rmSync(targetFrontend, { recursive: true, force: true });
    }
    copyDir(frontendDist, targetFrontend);

    // 3. Allocate backend port (only if backend was supplied)
    let backendPort = null;
    if (backendPath && backendStartCmd) {
      backendPort = await allocatePort();
    }

    // 4. Build the public URL.
    // Priority: explicit publicHost in request body > PUBLIC_BASE_URL env >
    // X-Forwarded-Host (IIS forwards original host) > Host header > localhost.
    let url;
    if (publicHost) {
      const base = /^https?:\/\//.test(publicHost) ? publicHost : `http://${publicHost}`;
      url = `${base.replace(/\/+$/, '')}/${slug}`;
    } else if (process.env.PUBLIC_BASE_URL) {
      url = `${process.env.PUBLIC_BASE_URL.replace(/\/+$/, '')}/${slug}`;
    } else {
      const host = req.get('x-forwarded-host') || req.get('host') || `localhost:${process.env.PORT || 6060}`;
      const proto = req.get('x-forwarded-proto') || req.protocol || 'http';
      url = `${proto}://${host}/${slug}`;
    }

    // 5. Insert row
    const logPath = deploymentLogPath(slug);
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    const insert = db.prepare(`
      INSERT INTO deployments
        (project_id, slug, frontend_path, backend_path, backend_port,
         backend_start_cmd, backend_start_args, backend_env, status, url, log_path)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    `);
    const info = insert.run(
      project.id,
      slug,
      targetFrontend,
      backendPath || null,
      backendPort,
      backendStartCmd || null,
      backendStartArgs ? JSON.stringify(backendStartArgs) : null,
      backendEnv ? JSON.stringify(backendEnv) : null,
      url,
      logPath,
    );

    // 6. Spawn backend if requested
    const row = db.prepare(`SELECT * FROM deployments WHERE id=?`).get(info.lastInsertRowid);
    if (backendPath && backendStartCmd) {
      spawnBackend(row);
    } else {
      db.prepare(`UPDATE deployments SET status='running' WHERE id=?`).run(row.id);
    }

    const finalRow = db.prepare(`SELECT * FROM deployments WHERE id=?`).get(row.id);
    return res.json({
      deployment: finalRow,
      url,
      backendPort,
      message: `Deployed at ${url}${backendPort ? ` (backend on port ${backendPort})` : ' (frontend-only)'}`,
    });
  } catch (e) {
    console.error('[deploy] failed:', e);
    return res.status(500).json({ error: e.message });
  }
});

deployments.get('/', (_req, res) => {
  const rows = db.prepare(`
    SELECT d.*, p.name AS project_name
    FROM deployments d
    LEFT JOIN projects p ON p.id = d.project_id
    ORDER BY d.deployed_at DESC
  `).all();
  res.json(rows);
});

deployments.get('/:id', (req, res) => {
  const row = db.prepare(`SELECT * FROM deployments WHERE id=?`).get(req.params.id);
  if (!row) return res.status(404).json({ error: 'deployment not found' });
  res.json(row);
});

deployments.delete('/:id', (req, res) => {
  const row = db.prepare(`SELECT * FROM deployments WHERE id=?`).get(req.params.id);
  if (!row) return res.status(404).json({ error: 'deployment not found' });
  killProcess(row.slug);
  // Remove the deployment root (frontend bundle + logs)
  try { fs.rmSync(deploymentRoot(row.slug), { recursive: true, force: true }); } catch {}
  db.prepare(`DELETE FROM deployments WHERE id=?`).run(row.id);
  res.json({ ok: true, undeployed: row.slug });
});

deployments.post('/:id/restart', (req, res) => {
  const row = db.prepare(`SELECT * FROM deployments WHERE id=?`).get(req.params.id);
  if (!row) return res.status(404).json({ error: 'deployment not found' });
  killProcess(row.slug);
  if (row.backend_path && row.backend_start_cmd) {
    spawnBackend(row);
  }
  res.json({ ok: true, restarted: row.slug, pid: liveProcesses.get(row.slug)?.child.pid || null });
});
