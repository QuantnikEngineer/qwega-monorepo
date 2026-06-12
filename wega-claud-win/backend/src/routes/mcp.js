import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { projectForRead, projectForWrite } from './projectAccess.js';
import { getMcpServersFromEnv } from '../config.js';

export const mcp = Router();

function settingsPath(project) {
  const dir = path.join(project.path, '.claude');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'settings.json');
  if (!fs.existsSync(file)) fs.writeFileSync(file, JSON.stringify({}, null, 2));
  return file;
}

function readSettings(project) {
  return JSON.parse(fs.readFileSync(settingsPath(project), 'utf8'));
}

function writeSettings(project, data) {
  fs.writeFileSync(settingsPath(project), JSON.stringify(data, null, 2));
}

function lastInit(projectId) {
  const row = db
    .prepare(
      `SELECT payload FROM messages
       WHERE project_id = ? AND payload LIKE '%"type":"session"%'
       ORDER BY id DESC LIMIT 1`
    )
    .get(projectId);
  if (!row) return null;
  try { return JSON.parse(row.payload); } catch { return null; }
}

function maskedEnvServers() {
  const servers = getMcpServersFromEnv();
  return Object.fromEntries(Object.entries(servers).map(([name, cfg]) => [name, {
    type: cfg.type || (cfg.command ? 'stdio' : cfg.url ? 'http' : 'unknown'),
    command: cfg.command,
    args: cfg.args || [],
    url: cfg.url,
    hasAuth: !!(cfg.headers || cfg.env),
  }]));
}

function validateConfig(cfg) {
  if (!cfg || typeof cfg !== 'object') return 'config must be an object';
  if (cfg.type === 'stdio' || cfg.command) {
    if (!cfg.command || typeof cfg.command !== 'string') return 'stdio servers need a command string';
    if (cfg.args && !Array.isArray(cfg.args)) return 'args must be an array';
    if (cfg.env && (typeof cfg.env !== 'object' || Array.isArray(cfg.env))) return 'env must be an object';
    return null;
  }
  if (cfg.type === 'http' || cfg.type === 'sse') {
    if (!cfg.url || typeof cfg.url !== 'string') return 'http/sse servers need a url';
    if (cfg.headers && typeof cfg.headers !== 'object') return 'headers must be an object';
    return null;
  }
  return "type must be 'stdio', 'http', or 'sse' (or supply a command for stdio)";
}

mcp.get('/:projectId', (req, res) => {
  const project = projectForRead(req.params.projectId, req, res);
  if (!project) return;
  const s = readSettings(project);
  const runtime = lastInit(req.params.projectId);
  res.json({
    local: s.mcpServers || {},
    env: maskedEnvServers(),
    runtime: runtime?.mcpServers || [],
  });
});

mcp.post('/:projectId', (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  const { name, config } = req.body || {};
  if (!name || !/^[a-zA-Z0-9_-]+$/.test(name)) return res.status(400).json({ error: 'invalid name' });
  const err = validateConfig(config);
  if (err) return res.status(400).json({ error: err });
  const s = readSettings(project);
  s.mcpServers = s.mcpServers || {};
  if (s.mcpServers[name]) return res.status(409).json({ error: 'already exists; delete first to replace' });
  s.mcpServers[name] = config;
  writeSettings(project, s);
  res.json({ ok: true, server: { name, config } });
});

mcp.put('/:projectId/:name', (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  const { name } = req.params;
  if (!/^[a-zA-Z0-9_-]+$/.test(name)) return res.status(400).json({ error: 'invalid name' });
  const err = validateConfig(req.body);
  if (err) return res.status(400).json({ error: err });
  const s = readSettings(project);
  s.mcpServers = s.mcpServers || {};
  s.mcpServers[name] = req.body;
  writeSettings(project, s);
  res.json({ ok: true });
});

mcp.delete('/:projectId/:name', (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  const s = readSettings(project);
  if (s.mcpServers) {
    delete s.mcpServers[req.params.name];
    writeSettings(project, s);
  }
  res.json({ ok: true });
});
