// Install the WEGA Claude backend as a Windows service using node-windows.
// Run as Administrator from the repo root:  node scripts\install-windows-service.cjs
//
// The service inherits the environment of the installing shell, so set
// CLAUDE_CODE_OAUTH_TOKEN and any MCP_*_TOKEN values (Windows env vars or
// the elevated PowerShell session) before running this script.

const path = require('node:path');
const fs = require('node:fs');
const { Service } = require('node-windows');

const repoRoot = path.resolve(__dirname, '..');
const backendDir = path.join(repoRoot, 'backend');
const entryScript = path.join(backendDir, 'src', 'index.js');

if (!fs.existsSync(entryScript)) {
  console.error(`Backend entry not found at ${entryScript}. Did you clone the full repo?`);
  process.exit(1);
}

const passthrough = [
  'PORT',
  'PROJECTS_ROOT',
  'DB_PATH',
  'ANTHROPIC_API_KEY',
  'CLAUDE_CODE_OAUTH_TOKEN',
  'MCP_FIGMA_TOKEN',
  'MCP_LINEAR_TOKEN',
  'MCP_NOTION_TOKEN',
  'MCP_GITHUB_TOKEN',
  'MCP_ATLASSIAN_EMAIL',
  'MCP_ATLASSIAN_TOKEN',
  'MCP_ATLASSIAN_URL',
  'MCP_SLACK_TOKEN',
];

const env = passthrough
  .filter((name) => process.env[name] !== undefined && process.env[name] !== '')
  .map((name) => ({ name, value: process.env[name] }));

env.push({ name: 'NODE_ENV', value: 'production' });

const svc = new Service({
  name: 'WegaClaude',
  description: 'WEGA Claude — Node backend (Express + WebSocket + Claude Agent SDK).',
  script: entryScript,
  workingDirectory: backendDir,
  nodeOptions: [],
  env,
});

svc.on('install', () => {
  console.log('Service installed. Starting…');
  svc.start();
});
svc.on('alreadyinstalled', () => {
  console.log('Service is already installed. Run uninstall-windows-service.cjs first to re-install.');
});
svc.on('start', () => {
  console.log('Service WegaClaude started.');
  console.log('Backend should now be reachable at http://127.0.0.1:' + (process.env.PORT || 6060));
});
svc.on('error', (err) => {
  console.error('Service error:', err);
  process.exitCode = 1;
});

svc.install();
