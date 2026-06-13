import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const ATLASSIAN_MCP = path.join(__dirname, 'mcp', 'atlassian-rest.js');

function loadEnv() {
  const envPath = path.join(ROOT, '.env');
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2];
  }
}
loadEnv();

export const config = {
  port: Number(process.env.PORT || 6060),
  projectsRoot: path.resolve(ROOT, process.env.PROJECTS_ROOT || './data/projects'),
  dbPath: path.resolve(ROOT, process.env.DB_PATH || './data/quantnik.db'),
};

export function resolveProjectPath(projectOrPath) {
  const raw = typeof projectOrPath === 'string'
    ? projectOrPath
    : projectOrPath?.path;
  const name = typeof projectOrPath === 'object' ? projectOrPath?.name : null;
  const value = String(raw || name || '').trim();
  if (!value) return config.projectsRoot;
  if (path.isAbsolute(value)) return value;
  const normalised = value.replace(/[\\/]+/g, '/');
  if (normalised === name || normalised.startsWith('./data/projects/') || normalised.startsWith('data/projects/')) {
    return path.join(config.projectsRoot, path.basename(normalised));
  }
  return path.resolve(ROOT, value.replace(/^\.\//, ''));
}

// MCP server configurations from environment variables
export function getMcpServersFromEnv() {
  const mcpServers = {};

  // Figma MCP (stdio — uses a Figma personal access token directly, no OAuth flow)
  if (process.env.MCP_FIGMA_TOKEN) {
    mcpServers['Figma'] = {
      type: 'stdio',
      command: 'npx',
      args: ['-y', 'figma-developer-mcp', '--stdio'],
      env: { FIGMA_API_KEY: process.env.MCP_FIGMA_TOKEN },
    };
  }

  // Linear MCP
  if (process.env.MCP_LINEAR_TOKEN) {
    mcpServers['Linear'] = {
      type: 'sse',
      url: 'https://mcp.linear.app/sse',
      headers: { 'Authorization': `Bearer ${process.env.MCP_LINEAR_TOKEN}` },
    };
  }

  // Notion MCP
  if (process.env.MCP_NOTION_TOKEN) {
    mcpServers['Notion'] = {
      type: 'sse',
      url: 'https://mcp.notion.so/sse',
      headers: { 'Authorization': `Bearer ${process.env.MCP_NOTION_TOKEN}` },
    };
  }

  // GitHub MCP
  if (process.env.MCP_GITHUB_TOKEN) {
    mcpServers['GitHub'] = {
      type: 'http',
      url: 'https://api.githubcopilot.com/mcp/',
      headers: { 'Authorization': `Bearer ${process.env.MCP_GITHUB_TOKEN}` },
    };
  }

  const atlassianSite = normaliseAtlassianSite(process.env.MCP_ATLASSIAN_URL || process.env.MCP_ATLASSIAN_SITE_NAME);
  const atlassianSiteName = atlassianSite
    ? new URL(atlassianSite).hostname.replace(/\.atlassian\.net$/i, '')
    : '';

  // Atlassian/Jira + Confluence MCP — local stdio wrapper with Jira/Confluence
  // REST tools shaped for the bundled skills: jira_get/post/put and conf_get/post/put.
  if (process.env.MCP_ATLASSIAN_TOKEN && process.env.MCP_ATLASSIAN_EMAIL && atlassianSite) {
    const atlassianEnv = {
      ATLASSIAN_SITE_NAME: atlassianSiteName,
      ATLASSIAN_SITE_URL: atlassianSite,
      ATLASSIAN_USER_EMAIL: process.env.MCP_ATLASSIAN_EMAIL,
      ATLASSIAN_API_TOKEN: process.env.MCP_ATLASSIAN_TOKEN,
    };
    mcpServers['Jira'] = {
      type: 'stdio',
      command: process.execPath,
      args: [ATLASSIAN_MCP, 'jira'],
      env: atlassianEnv,
    };
    mcpServers['Confluence'] = {
      type: 'stdio',
      command: process.execPath,
      args: [ATLASSIAN_MCP, 'confluence'],
      env: atlassianEnv,
    };
  }

  // Slack MCP
  if (process.env.MCP_SLACK_TOKEN) {
    mcpServers['Slack'] = {
      type: 'http',
      url: 'https://mcp.slack.com/mcp',
      headers: { 'Authorization': `Bearer ${process.env.MCP_SLACK_TOKEN}` },
    };
  }

  return mcpServers;
}

function normaliseAtlassianSite(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw.replace(/\.atlassian\.net$/i, '')}.atlassian.net`);
    return `${url.protocol}//${url.hostname}`.replace(/\/+$/, '');
  } catch {
    return '';
  }
}

fs.mkdirSync(config.projectsRoot, { recursive: true });
fs.mkdirSync(path.dirname(config.dbPath), { recursive: true });
