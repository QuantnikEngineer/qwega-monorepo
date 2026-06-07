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

  // Atlassian/Jira + Confluence MCP — stdio servers with full CRUD via Basic auth.
  // The official mcp.atlassian.com endpoint only exposes Teamwork Graph (read-only)
  // tools over Basic auth; these stdio servers expose the full REST surface.
  if (process.env.MCP_ATLASSIAN_TOKEN && process.env.MCP_ATLASSIAN_EMAIL && process.env.MCP_ATLASSIAN_SITE_NAME) {
    const atlassianEnv = {
      ATLASSIAN_SITE_NAME: process.env.MCP_ATLASSIAN_SITE_NAME,
      ATLASSIAN_USER_EMAIL: process.env.MCP_ATLASSIAN_EMAIL,
      ATLASSIAN_API_TOKEN: process.env.MCP_ATLASSIAN_TOKEN,
    };
    // Use absolute paths so the LocalSystem-running service can find the
    // user-installed npm globals (which aren't on the service PATH).
    const userNpmDir = process.env.USERPROFILE
      ? `${process.env.USERPROFILE}\\AppData\\Roaming\\npm`
      : 'C:\\Users\\abhinav.krishna\\AppData\\Roaming\\npm';
    mcpServers['Jira'] = {
      type: 'stdio',
      command: `${userNpmDir}\\mcp-atlassian-jira.cmd`,
      args: [],
      env: atlassianEnv,
    };
    mcpServers['Confluence'] = {
      type: 'stdio',
      command: `${userNpmDir}\\mcp-atlassian-confluence.cmd`,
      args: [],
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

fs.mkdirSync(config.projectsRoot, { recursive: true });
fs.mkdirSync(path.dirname(config.dbPath), { recursive: true });
