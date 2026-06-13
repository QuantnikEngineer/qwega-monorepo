import { Router } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

export const inherited = Router();

const USER_HOME = os.homedir();
const USER_SKILLS_DIR = path.join(USER_HOME, '.claude', 'skills');
const USER_CLAUDE_JSON = path.join(USER_HOME, '.claude.json');
const USER_SETTINGS_JSON = path.join(USER_HOME, '.claude', 'settings.json');
const USER_PLUGINS_DIR = path.join(USER_HOME, '.claude', 'plugins');

function readJsonSafe(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

function listSkillsIn(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const skillMd = path.join(dir, d.name, 'SKILL.md');
      let description = null;
      if (fs.existsSync(skillMd)) {
        const head = fs.readFileSync(skillMd, 'utf8').slice(0, 2000);
        const m = head.match(/^description:\s*(.+)$/m);
        if (m) description = m[1].trim();
      }
      return { name: d.name, description };
    });
}

inherited.get('/skills', (_req, res) => {
  const user = listSkillsIn(USER_SKILLS_DIR);

  const plugins = [];
  if (fs.existsSync(USER_PLUGINS_DIR)) {
    const walk = (root) => {
      for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const child = path.join(root, entry.name);
        const skillsDir = path.join(child, 'skills');
        if (fs.existsSync(skillsDir)) {
          for (const s of listSkillsIn(skillsDir)) {
            plugins.push({ ...s, plugin: path.relative(USER_PLUGINS_DIR, child) });
          }
        }
        walk(child);
      }
    };
    walk(USER_PLUGINS_DIR);
  }

  res.json({ user, plugins });
});

inherited.get('/mcp', (_req, res) => {
  const userSettings = readJsonSafe(USER_SETTINGS_JSON) || {};
  const claudeJson = readJsonSafe(USER_CLAUDE_JSON) || {};

  const collect = (obj) => {
    const out = {};
    if (obj && typeof obj === 'object' && obj.mcpServers && typeof obj.mcpServers === 'object') {
      for (const [name, cfg] of Object.entries(obj.mcpServers)) {
        out[name] = {
          type: cfg?.type || (cfg?.command ? 'stdio' : cfg?.url ? 'http' : 'unknown'),
          hasAuth: !!(cfg?.headers || cfg?.env),
        };
      }
    }
    return out;
  };

  res.json({
    fromSettings: collect(userSettings),
    fromClaudeJson: collect(claudeJson),
  });
});
