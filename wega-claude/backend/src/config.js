import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

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
  dbPath: path.resolve(ROOT, process.env.DB_PATH || './data/wega2.db'),
};

// MCP server configurations from environment variables
export function getMcpServersFromEnv() {
  const mcpServers = {};

  // Figma MCP
  if (process.env.MCP_FIGMA_TOKEN) {
    mcpServers['Figma'] = {
      type: 'http',
      url: 'https://mcp.figma.com/mcp',
      headers: { 'X-Figma-Token': process.env.MCP_FIGMA_TOKEN },
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

  // Atlassian/Jira MCP
  if (process.env.MCP_ATLASSIAN_TOKEN && process.env.MCP_ATLASSIAN_EMAIL) {
    mcpServers['Atlassian'] = {
      type: 'http',
      url: process.env.MCP_ATLASSIAN_URL || 'https://mcp.atlassian.com/mcp',
      headers: {
        'Authorization': `Basic ${Buffer.from(`${process.env.MCP_ATLASSIAN_EMAIL}:${process.env.MCP_ATLASSIAN_TOKEN}`).toString('base64')}`,
      },
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

fs.mkdirSync(config.projectsRoot, { recursive: true });
fs.mkdirSync(path.dirname(config.dbPath), { recursive: true });
