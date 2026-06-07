---
name: container-deploy
description: Containerises a generated full-stack app (frontend + backend from feature-dev / sdlc-orchestrator), builds Docker images, runs them via docker compose locally, health-checks the result, and optionally pushes the images to a configured registry. Auto-generates Dockerfiles / .dockerignore / docker-compose.yml when they're missing, never overwrites them when they're already in the repo. Logs a Jira bug on hard failures (image build, container crash on boot) with RCA + corrective action, and publishes a structured deployment report to Confluence with the running URLs. Discovers the app folder the same way test-script-executor does (project cwd → configured repos → chat-history-derived paths). The natural counterpart to the feature-dev + Phase-8 boot — that boots dev servers; this wraps the same app in containers for parity with non-dev environments.
---

When invoked, run end-to-end. **Autonomous after a single Phase 0 confirmation** when a destructive operation is in play (overwriting an existing image tag in a remote registry, or starting containers on ports already in use by other processes). Every other step proceeds without prompts.

**Scope rule (read this first).** `Read` `.claude/wega.json` at the project cwd. If present:
- `atlassian.jiraProjectKey` → the **only** allowed Jira project for failure tickets (Phase 5 fallback).
- `atlassian.confluenceSpaceKey` / `confluenceSpaceId` → the **only** allowed Confluence space for the deployment report.
- `atlassian.labels` → propagate to every created bug.

If the sidecar is silent or missing, fall back to MEMORY.md / chat-history defaults; never to "first personal space" / "first visible Jira project" for the published report.

This skill supports the same two Atlassian MCP shapes used by the other SDLC skills (`mcp__Confluence__conf_*` / `mcp__Jira__jira_*` for wega2 stdio; `mcp__claude_ai_Atlassian__*` for claude.ai-managed). **Jira logging is mandatory only on hard failures** (not on every successful run). Confluence publish is best-effort — if neither MCP shape is available, the report falls back to a local markdown file at `<app-folder>/deploy/report-<timestamp>.md` and the deployment is still considered successful.

---

## Phase 0 — Preflight

### 0.1 — Verify Docker is available

`Bash` `docker --version` then `docker compose version` (or `docker-compose --version` as a v1 fallback). If either fails, halt with:

> "Docker (or `docker compose`) is not on the PATH for the wega2 service. Install Docker Desktop, ensure it's running, and retry. Alternatively, point me at a remote Docker host via DOCKER_HOST."

Probe the daemon: `docker info --format "{{.ServerVersion}}"`. If the daemon isn't reachable, halt with the same hint.

### 0.2 — Discover the app folder

In order:
1. User-supplied path in the invocation message.
2. Run-context `output_folder` from a prior `/sdlc-orchestrator` Phase 3.
3. Configured wega2 repos (`additionalDirectories`) that contain both a `frontend/` and a `backend/` subfolder at the root.
4. Chat-history scan for `Application Path:` / `Output folder:` / `Path:` lines (same approach as the dashboard's code-stats endpoint), require `frontend/` + `backend/` siblings to count.
5. `~/projects/*` directories with both subfolders.

Pick the most-recently-modified candidate. Print:

```
Selected app: <absolute path>
  Frontend: <path>/frontend  (Node, package.json detected)
  Backend:  <path>/backend   (Node, package.json detected)
```

If neither folder exists or neither has a `package.json`, halt with a clear error pointing the user to run `/sdlc-orchestrator` first.

### 0.3 — Resolve ports

Read `<app>/backend/.env` and `<app>/frontend/.env` (if present) for `PORT`. Default backend `3001`, default frontend `5173`. Cache as `run-context.backendPort`, `run-context.frontendPort`.

### 0.4 — Detect port conflicts

`Bash` `netstat -ano -p TCP | findstr LISTENING | findstr ":<frontendPort> :<backendPort>"` (or `ss -tln | grep ...` on Linux). If either port is already taken **by a non-Docker process**, ask the user once (only permitted prompt in this skill):

```
Port <frontendPort> is already in use by PID <pid> (<process name>).
Reply: bump   — pick a free port (frontend ≥ 5180, backend ≥ 3010), update compose
        kill   — stop that PID and reuse the original port
        cancel — abort the deploy
```

If both ports are clear or are held by an existing container of this same app (compose project name match), proceed silently.

### 0.5 — Detect registry config

Read `<app>/.env` and `~/.docker/config.json` (best-effort) for:
- `DOCKER_REGISTRY` (e.g. `ghcr.io/wipro`, `<account>.dkr.ecr.us-east-1.amazonaws.com`, `wegabuildiq.azurecr.io`).
- A logged-in registry from `~/.docker/config.json`'s `auths` keys.

If neither is found, push step is skipped — local images only. Record `run-context.registry` (or `null`).

---

## Phase 1 — Generate Dockerfiles + compose (only when missing)

Never overwrite files that already exist. For each missing artifact, write it; for each present one, log "kept existing" and continue.

### 1.1 — `<app>/backend/Dockerfile`

```dockerfile
# Multi-stage build keeps the runtime image lean.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
USER node
EXPOSE <backendPort>
CMD ["node", "server.js"]
```

If the backend's entry isn't `server.js`, infer it from `package.json#main` or `package.json#scripts.start` and patch the `CMD` accordingly. If a `Dockerfile` is already at `<app>/backend/`, **keep it** — don't merge or rewrite.

### 1.2 — `<app>/frontend/Dockerfile`

Vite static-build via multi-stage; serve with nginx-alpine.

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=http://backend:<backendPort>
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf 2>/dev/null || true
EXPOSE 80
```

Drop in a minimal `<app>/frontend/nginx.conf` if one isn't present:

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;
  location /api/ {
    proxy_pass http://backend:<backendPort>;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

### 1.3 — `<app>/.dockerignore` (both folders)

```
node_modules
dist
build
.next
.turbo
.cache
coverage
.git
.env.local
.env.*.local
*.log
.DS_Store
```

### 1.4 — `<app>/docker-compose.yml`

```yaml
name: <project-slug>
services:
  backend:
    build:
      context: ./backend
    container_name: <project-slug>-backend
    ports:
      - "<backendPort>:<backendPort>"
    env_file:
      - ./backend/.env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:<backendPort>/health"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    networks: [appnet]

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: http://localhost:<backendPort>
    container_name: <project-slug>-frontend
    ports:
      - "<frontendPort>:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    networks: [appnet]

networks:
  appnet:
    driver: bridge
```

`<project-slug>` is the app folder's basename, lowercased, with non-`[a-z0-9_-]` stripped. If a `docker-compose.yml` already exists, keep it — record both the existing path and "kept" in run-context.

---

## Phase 2 — Build images

`cd <app> && docker compose build --pull` — foreground, captures stdout/stderr verbatim. Long-running but bounded; cap the bash timeout at 15 minutes.

On non-zero exit:
- Capture last 80 lines of stderr.
- Try to classify: `npm ci` failure, missing native build tool (`gyp`, `python`), file not found in COPY, etc.
- Log a Jira bug per the **Phase 5 — Failure ticket** template (mandatory) and halt before Phase 3. Do not start partial deployments.

On success: record per-image size from `docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}"` filtered to the two image refs (`<project-slug>-backend`, `<project-slug>-frontend`).

---

## Phase 3 — Run the containers

`cd <app> && docker compose up -d --remove-orphans`. Should return within ~15 seconds. Foreground bash with 60s timeout.

Then `docker compose ps --format json` to list services and their state. Cache the container ids and states into `run-context.containers`.

If any service exits during the up command (state `exited` immediately), grab its logs (`docker compose logs --tail 100 <service>`), classify the cause, log a Jira bug, and continue to print the partial summary — don't halt mid-cleanup, but flag the failed service prominently.

---

## Phase 4 — Health-check

Poll once per second for up to 60 seconds (most cold starts finish in ~10–20):

- Backend: `curl -sf -m 3 http://localhost:<backendPort>/health` — first 2xx wins. If `/health` isn't implemented (404), retry against `/` once before giving up.
- Frontend: `curl -sf -m 3 http://localhost:<frontendPort>/` — accept any 2xx or 3xx (single-page apps often 304 on revalidation, or 200 on first hit).

Record `healthcheck.backend` and `healthcheck.frontend` as `passed | failed (<reason>)`.

If both pass → Phase 5 is skipped (no failure ticket). If either fails → Phase 5 logs the failure and the report is still published but flagged red.

---

## Phase 5 — Failure ticket (mandatory on hard failures)

Only when Phase 2 (build), Phase 3 (start), or Phase 4 (health) failed.

Use the same RCA + corrective-action playbook style as `test-script-executor` Phase 4. Issuetype: `Bug` → `Defect` → `Task` fallback. Project key from `wega.json` `jiraProjectKey` (hard-fail if neither sidecar nor MEMORY.md resolves a key).

Bug summary: `Container deploy failed: <stage> [<short reason>]`. Description sections:
- **Stage** — build / start / healthcheck.
- **App path / project slug**.
- **Error** — last ~600 chars of the offending command's stderr, fenced.
- **Root cause analysis** — classification (image missing base, npm ci network error, port conflict, container exited code N, healthcheck 500, etc.).
- **Corrective action** — concrete next step (`bump base image to node:20-alpine`, `add native build deps`, `fix /health route`, `set CORS_ORIGIN`, etc.).
- **Reproduce locally** — exact commands.
- **Container logs** — `docker compose logs --tail 80 <service>` output, fenced.

Idempotency: search the project for an existing open bug with the same summary; if found, add a "↻ Reproduced in run <timestamp>" comment instead of creating a duplicate.

---

## Phase 6 — Publish report to Confluence

Use **`wega.json.atlassian.confluenceSpaceKey`** as the target — non-negotiable when present. Never fall back to "first personal space" when the sidecar has a value.

Title: `<Project slug> — Container Deployment Report — <YYYY-MM-DD HH:mm>`.

Body sections:

1. **Executive summary** — green panel if both services healthy; amber if one is degraded; red if any failed. Show `frontend → http://localhost:<fp>`, `backend → http://localhost:<bp>`, image sizes, build time.
2. **Run metadata** — app path, docker engine version, compose version, host (`hostname`), commit SHA (`git -C <app> rev-parse HEAD`), invoking user, deploy timestamp.
3. **Service table** — service | image | size | port | container id | status | uptime | restart policy.
4. **Generated artifacts** — list each Dockerfile / compose / nginx.conf produced or kept (`generated` vs `kept existing`).
5. **Healthcheck** — backend + frontend probe results with the first 2xx URL / final retry response.
6. **Failures (if any)** — bug key + RCA + container log excerpt.
7. **Push to registry (if performed)** — registry host, image refs pushed, digests.
8. **Stop / clean commands** — copy-paste recipes:
   ```
   cd <app> && docker compose down            # stop containers, keep volumes
   docker compose down -v --rmi all           # stop + remove volumes + images
   ```

Record `deploy_report_url` in the run-context.

---

## Phase 7 — Optional registry push

Skip if `run-context.registry` is null.

For each image (backend + frontend):
1. Tag: `docker tag <project-slug>-<service>:latest <registry>/<project-slug>-<service>:<tag>` where `<tag>` is the short git SHA (`git -C <app> rev-parse --short HEAD`) or `latest` when not in a repo.
2. Push: `docker push <registry>/<project-slug>-<service>:<tag>`.
3. Capture digest from push output.

If a push fails (auth, network), log the error verbatim into the run-context as `push_errors[]` and continue. Pushes are best-effort — local containers are still running and the deploy report still publishes.

Never `docker tag` over an existing tag at a remote registry without the user's go-ahead (the Phase 0 prompt covers this case).

---

## Phase 8 — Final output (mandatory shape)

Print, in this order, exactly:

```
✅ Container deploy complete.

App:         <absolute path>
Slug:        <project-slug>
Engine:      Docker <version> · Compose <version>
Build:       <build duration>s
Images:
  • <slug>-backend:latest   <size>   (built | kept)
  • <slug>-frontend:latest  <size>   (built | kept)

Containers:
  • <slug>-backend   id <short>   state running   health passed   <uptime>
  • <slug>-frontend  id <short>   state running                   <uptime>

Reachable at:
  Frontend: http://localhost:<frontendPort>
  Backend:  http://localhost:<backendPort>  (health: ✅)

Generated artifacts (kept existing not re-written):
  • backend/Dockerfile   (generated | kept)
  • frontend/Dockerfile  (generated | kept)
  • frontend/nginx.conf  (generated | kept)
  • docker-compose.yml   (generated | kept)
  • .dockerignore        (generated | kept)

Registry push:    <pushed n / skipped / errors m>
Report:           <confluence-url>   (or local path on fallback)
Failure ticket:   <bug-key>   (omitted on success)

Stop with:        cd <app> && docker compose down
```

If any stage failed (build / start / healthcheck), the leading line becomes `🔴 Container deploy completed with errors.` and the Failure ticket row lists the bug key for follow-up.

If no Atlassian MCP was loaded at all, the report line shows the local markdown path; the deploy is still successful as long as build + start + health all passed.

---

## Behavior rules

- **Be autonomous.** Single permitted interactive moment: Phase 0.4 port conflict (bump / kill / cancel). Otherwise no prompts.
- **Never overwrite existing Dockerfiles / compose / nginx config.** If they're there, the team has reasons; respect them, log "kept existing", continue.
- **No silent registry pushes.** Phase 7 only fires when a registry is explicitly resolvable. No magic guessing at default Docker Hub.
- **Never delete volumes or images without user consent.** The stop recipe in the report mentions `-v --rmi all` but the skill never runs that variant itself.
- **Treat the wega.json scope as authoritative** for Jira project key and Confluence space — never fall back to personal-space or first-visible-project when the sidecar has a value.
- **Don't leak secrets.** When echoing `<app>/.env` content into the report or into a Jira bug, mask any value whose key matches `(?:_KEY|_TOKEN|_SECRET|_PASSWORD|API_KEY)\b` to `••••<last4>`.
- **Idempotent.** Re-running over a healthy deploy returns within seconds (compose ps confirms running, healthcheck reconfirms, nothing rebuilt unless source changed).
