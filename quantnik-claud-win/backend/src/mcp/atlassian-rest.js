#!/usr/bin/env node
import readline from 'node:readline';

const mode = process.argv[2] === 'confluence' ? 'confluence' : 'jira';
const email = process.env.ATLASSIAN_USER_EMAIL || process.env.MCP_ATLASSIAN_EMAIL;
const token = process.env.ATLASSIAN_API_TOKEN || process.env.MCP_ATLASSIAN_TOKEN;
const siteUrl = normaliseSiteUrl(
  process.env.ATLASSIAN_SITE_URL ||
  process.env.MCP_ATLASSIAN_URL ||
  process.env.ATLASSIAN_SITE_NAME ||
  process.env.MCP_ATLASSIAN_SITE_NAME
);

function normaliseSiteUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) return raw.replace(/\/+$/, '');
  return `https://${raw.replace(/\.atlassian\.net$/i, '')}.atlassian.net`;
}

function authHeaders() {
  if (!email || !token || !siteUrl) {
    throw new Error('Missing Atlassian credentials. Set MCP_ATLASSIAN_EMAIL, MCP_ATLASSIAN_TOKEN, and MCP_ATLASSIAN_URL.');
  }
  return {
    Authorization: `Basic ${Buffer.from(`${email}:${token}`).toString('base64')}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
}

function resolveUrl(inputPath) {
  const p = String(inputPath || '').trim();
  if (!p) throw new Error('path is required');
  if (/^https?:\/\//i.test(p)) return p;
  return `${siteUrl}${p.startsWith('/') ? p : `/${p}`}`;
}

async function rest(method, args = {}) {
  const url = resolveUrl(args.path);
  const init = { method, headers: authHeaders() };
  if (method !== 'GET' && args.body !== undefined) {
    init.body = typeof args.body === 'string' ? args.body : JSON.stringify(args.body);
  }
  const res = await fetch(url, init);
  const text = await res.text();
  let parsed = text;
  try { parsed = text ? JSON.parse(text) : null; } catch {}
  if (!res.ok) {
    const msg = typeof parsed === 'string' ? parsed : JSON.stringify(parsed);
    throw new Error(`${method} ${url} failed: HTTP ${res.status} ${res.statusText}${msg ? ` — ${msg.slice(0, 1200)}` : ''}`);
  }
  return parsed;
}

const pathSchema = {
  type: 'object',
  properties: {
    path: { type: 'string', description: 'REST path, for example /rest/api/3/myself or /wiki/api/v2/spaces?limit=10.' },
  },
  required: ['path'],
};

const bodySchema = {
  type: 'object',
  properties: {
    path: { type: 'string', description: 'REST path to call.' },
    body: { description: 'JSON request body. Objects are serialized automatically.' },
  },
  required: ['path'],
};

function tools() {
  if (mode === 'jira') {
    return [
      { name: 'jira_get', description: 'GET an Atlassian Jira Cloud REST API path.', inputSchema: pathSchema },
      { name: 'jira_post', description: 'POST to an Atlassian Jira Cloud REST API path.', inputSchema: bodySchema },
      { name: 'jira_put', description: 'PUT to an Atlassian Jira Cloud REST API path.', inputSchema: bodySchema },
    ];
  }
  return [
    { name: 'conf_get', description: 'GET an Atlassian Confluence Cloud REST API path.', inputSchema: pathSchema },
    { name: 'conf_post', description: 'POST to an Atlassian Confluence Cloud REST API path.', inputSchema: bodySchema },
    { name: 'conf_put', description: 'PUT to an Atlassian Confluence Cloud REST API path.', inputSchema: bodySchema },
  ];
}

async function callTool(name, args) {
  if (name === 'jira_get' || name === 'conf_get') return rest('GET', args);
  if (name === 'jira_post' || name === 'conf_post') return rest('POST', args);
  if (name === 'jira_put' || name === 'conf_put') return rest('PUT', args);
  throw new Error(`Unknown tool: ${name}`);
}

function write(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

async function handle(message) {
  if (!message || typeof message !== 'object') return;
  const { id, method, params } = message;
  if (id === undefined || id === null) return;
  try {
    if (method === 'initialize') {
      write({
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: params?.protocolVersion || '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: `quantnik-atlassian-${mode}`, version: '0.1.0' },
        },
      });
      return;
    }
    if (method === 'tools/list') {
      write({ jsonrpc: '2.0', id, result: { tools: tools() } });
      return;
    }
    if (method === 'tools/call') {
      const result = await callTool(params?.name, params?.arguments || {});
      write({
        jsonrpc: '2.0',
        id,
        result: {
          content: [{ type: 'text', text: typeof result === 'string' ? result : JSON.stringify(result, null, 2) }],
        },
      });
      return;
    }
    write({ jsonrpc: '2.0', id, error: { code: -32601, message: `Method not found: ${method}` } });
  } catch (err) {
    write({
      jsonrpc: '2.0',
      id,
      error: { code: -32000, message: err?.message || String(err) },
    });
  }
}

const rl = readline.createInterface({ input: process.stdin });
rl.on('line', (line) => {
  try { handle(JSON.parse(line)); }
  catch (err) {
    write({ jsonrpc: '2.0', id: null, error: { code: -32700, message: err?.message || 'Parse error' } });
  }
});
