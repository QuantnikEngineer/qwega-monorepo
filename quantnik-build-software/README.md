# quantnik-build-software

End-to-end software delivery pipeline orchestrator. Give it a description of what you want built and it autonomously runs the full SDLC:

```
Input: "Build a task management app"
         │
         ▼
1. Create BRD ──────────────────────► Confluence
2. Create User Stories ─────────────► Jira (Epics + Stories)
3. Validate User Stories ───────────► Jira (updates) + Confluence (report)
4. Create Test Cases ───────────────► Jira (Xray)
5. Create Test Scripts ─────────────► GitHub (Playwright/TS)
6. Generate React + Node.js code ───► GitHub
7. Deploy ──────────────────────────► Vercel / GitHub Pages
         │
         ▼
Output: deployment URL + all artifact links
```

## Port

`8083`

## Quick start

```bash
cp .env.example .env   # fill in API keys
pip install -r requirements.txt
python run.py
```

## API

### Start a pipeline (streaming)
```bash
curl -N -X POST http://localhost:8083/v1/build \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "task-app",
    "description": "A team task management application with kanban board",
    "confluence_space_key": "QUANTNIK",
    "jira_project_key": "TASK",
    "github_repo": "task-app"
  }'
```

Response is a stream of SSE events:
```
data: {"event_type":"milestone","step":"create_brd","title":"Creating BRD…","progress":0.08}
data: {"event_type":"artifact","step":"create_brd","artifact_key":"brd_url","artifact_url":"https://...","progress":0.15}
data: {"event_type":"milestone","step":"create_user_stories","title":"Generating user stories…","progress":0.20}
...
data: {"event_type":"complete","step":"finalize","title":"Pipeline complete","progress":1.0}
```

### Start async (fire and forget)
```bash
curl -X POST http://localhost:8083/v1/build/async \
  -H "Content-Type: application/json" \
  -d '{ "project_name": "task-app", "description": "...", ... }'
# Returns: { "run_id": "abc-123", "stream_url": "/v1/build/abc-123/stream" }
```

### Poll status
```bash
curl http://localhost:8083/v1/build/{run_id}
```

### List all runs
```bash
curl http://localhost:8083/v1/builds
```

## Skip steps

If you already have a BRD, pass `"skip_steps": ["create_brd"]` and provide `confluence_space_key` for context.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | One of these | LLM for code generation |
| `GOOGLE_API_KEY` | One of these | Gemini fallback |
| `PLANNING_ORCHESTRATOR_URL` | Yes | URL of quantnik-sdlc-orchestrator or planning orch |
| `TEST_ORCHESTRATOR_URL` | Yes | URL of test orchestrator |
| `GITHUB_TOKEN` | Yes (step 5+6) | PAT with repo + write:org |
| `GITHUB_ORG` | Yes | GitHub org/user to create repos under |
| `VERCEL_TOKEN` | No | Enables auto-deploy; without it returns GitHub Pages URL |

## Docker

```bash
docker build -t quantnik-build-software .
docker run -p 8083:8083 --env-file .env quantnik-build-software
```
