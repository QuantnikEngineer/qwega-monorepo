# WEGA

A local web wrapper around Claude Code. Run a Node backend that uses the
**Claude Agent SDK** to drive Claude Code sessions, and a React frontend that
gives you a chat UI plus panels to manage projects, skills, MCP servers,
hooks, and settings — the same primitives Claude Code understands natively.

```
claude-web/
├── backend/        Express + WebSocket + Claude Agent SDK
└── frontend/       React (Vite) UI: chat / skills / mcp / settings
```

The placeholder logo lives at `frontend/src/components/Logo.jsx`; swap the
SVG for your official mark when you have it.

## Prerequisites

- Node 20+
- `claude` CLI authenticated on your machine, **or** an `ANTHROPIC_API_KEY`
  available to the backend process. The Claude Agent SDK uses whichever it
  finds (CLI session token takes precedence in most setups).

## Setup

```bash
# 1. backend
cd backend
cp .env.example .env             # tweak PORT / paths if needed
npm install
# If the SDK version in package.json fails to resolve, pin to latest:
#   npm install @anthropic-ai/claude-agent-sdk@latest
npm run dev                      # http://localhost:4000

# 2. frontend (in a second terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Open <http://localhost:5173>.

## Tabs

- **chat** — streaming conversation with Claude. Tool-use blocks render inline.
- **skills** — CRUD for `<project>/.claude/skills/<name>/SKILL.md`. Also shows
  read-only your user-level skills and plugin skills (`~/.claude/skills`,
  `~/.claude/plugins`) — they're already available because the backend passes
  `settingSources: ['user', 'project', 'local']` to the Agent SDK.
- **mcp** — view live MCP connections reported by the SDK (status: connected /
  needs-auth / failed), plus add/delete project-local MCP servers (stdio, http,
  sse). Local entries are written to `<project>/.claude/settings.json` under
  `mcpServers`.
- **settings** — model, permission mode, hooks JSON, raw `settings.json`, and
  the agents + tools the SDK reported on the last turn.

## What lives where

- **Project metadata + chat history**: SQLite at `backend/data/claude-web.db`.
- **Project working directories**: by default under `backend/data/projects/<name>/`.
  You can also point a project at any absolute path (e.g. an existing repo)
  when you create it from the UI.
- **Per-project Claude config**: `<project-path>/.claude/`
  - `settings.json` — model, hooks, etc. Claude Code reads this when invoked
    with that directory as `cwd`.
  - `skills/<name>/SKILL.md` — skills available to that project.

The frontend just edits these files on disk; the Agent SDK picks them up the
next time you send a message.

## How chat works

1. You select (or create) a project in the sidebar.
2. The Chat tab opens a WebSocket to `/ws`.
3. Each user message becomes a `query()` call against the Agent SDK with
   `cwd` = project path, `model` / `permissionMode` from the project row in
   SQLite, and `resume` = the last `session_id` so turns chain together.
4. Streamed events (assistant text, tool use, tool result, run summary) are
   forwarded to the UI and persisted to `messages`.
5. **Reset** clears stored messages and forgets the session id so the next
   message starts a fresh Claude conversation.

## Permission modes

Set per project in the Settings tab:

- `default` — Claude pauses for permission on sensitive tools. This wrapper
  does not yet surface those prompts in the UI, so the turn will hang. Use
  one of the modes below for now.
- `acceptEdits` *(default)* — auto-approves edits, still prompts for shell.
- `plan` — read-only planning mode, no edits or shell.
- `bypassPermissions` — auto-approves everything. Use with care.

A future iteration should hook `canUseTool` and surface approval prompts
inline in the chat.

## Roadmap toward multi-user

This scaffold is intentionally single-user / local. Before exposing it to
multiple developers you'll want, at minimum:

- Auth (session cookies or OIDC) and per-user project ownership.
- Sandboxed working directories per session (Docker container or Firecracker
  VM per chat), not bare host paths.
- A separate Anthropic API key per user (or per workspace) so usage is
  attributable and rate-limited individually.
- A `canUseTool` permission UI surfaced in the chat pane.
- Audit logging of tool use beyond the local SQLite table.
