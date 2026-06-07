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
import { attachWebSocket } from './ws.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '2mb' }));

app.get('/api/health', (_req, res) => res.json({ ok: true }));
app.use('/api/projects', projects);
app.use('/api/skills', skills);
app.use('/api/settings', settings);
app.use('/api/inherited', inherited);
app.use('/api/session-info', sessionInfo);
app.use('/api/mcp', mcp);
app.use('/api/repos', repos);
app.use('/api/uploads', uploads);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '../../frontend/dist');
if (fs.existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get(/^(?!\/api|\/ws).*/, (_req, res) => res.sendFile(path.join(distDir, 'index.html')));
  console.log(`serving frontend from ${distDir}`);
}

const server = http.createServer(app);
attachWebSocket(server);

server.listen(config.port, () => {
  console.log(`wega2 backend on http://localhost:${config.port}`);
  console.log(`projects root: ${config.projectsRoot}`);
});
