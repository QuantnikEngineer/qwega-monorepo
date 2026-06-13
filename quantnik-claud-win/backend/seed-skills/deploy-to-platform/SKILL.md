---
name: deploy-to-platform
description: Deploys a generated full-stack application onto the same Quantnik server it was generated on, served under a project-specific subpath like `<PUBLIC_BASE_URL>/<project-name>`. Builds the frontend (`npm run build` or the stack-equivalent), copies the resulting dist into Quantnik's deployments root, and — if a Node-style backend exists — spawns it on an auto-allocated port with reverse-proxy at `/<slug>/api/*`. The deployment is registered in the Quantnik DB so it survives service restarts. The public host is configured on the Quantnik backend via the `PUBLIC_BASE_URL` env var; the skill never has to ask the user which domain to publish under. Use this skill when the user wants to ship the freshly built app for review without setting up separate hosting. The natural counterpart to the orchestrator's Phase 8 (Boot) — that boots dev servers for local testing; this serves the production build behind the same Quantnik domain.
---

When this skill is invoked, follow the steps below in strict order. Do not skip a step or move to the next until the current one is complete.

This skill **calls back to the quantnik backend API on the same host** (`http://localhost:6060/api/deployments/<projectId>`). The skill itself does not serve traffic — it asks the quantnik process to register the deployment, which then handles routing.

---

## Step 0 — Read project context from `quantnik.json`

`Read` `.claude/quantnik.json` at the project cwd. Extract:

- `project.id` → the quantnik project id. **Required** — without it the deployment can't be registered.
- `project.name` → default slug (sanitised: lowercase, hyphen-separated, alphanumeric only, max 48 chars).
- `project.path` → useful as a baseline when locating the generated app folder.

If `quantnik.json` is missing or has no `project.id`, halt with: "Cannot deploy — no quantnik.json with project.id at this cwd. Open the project in quantnik first."

---

## Step 1 — Locate the frontend and backend source folders

The orchestrator and feature-dev skills leave their output paths in the chat history. Find them in this priority order:

1. Look at the most recent assistant `tool_use` blocks calling **Write** — their `file_path` parents reveal the actual generated layout. Walk up to the topmost folder that contains either:
   - `<root>/frontend/package.json` + `<root>/backend/package.json` (orchestrator default layout), OR
   - A single `<root>/package.json` with both frontend (`react`, `next`, `vue`, …) and backend (`express`, `nestjs`, …) deps (fullstack repo).
2. Fall back to lines matching `Path:`, `Output folder:`, or `Application Path:` in the assistant's prior summaries.
3. If still unresolved, ask: "Which folder holds the app to deploy? (absolute path)"

Record:
- `frontendRoot` (the dir containing the frontend `package.json` / framework root)
- `backendRoot` (the dir containing the backend entry point, or `null` if frontend-only)
- `frontendStack` — inspect the frontend `package.json` deps:
  - `react` + `vite` → `react-vite`
  - `next` → `nextjs`
  - `vue` → `vue3-vite`
  - `svelte` → `svelte-kit`
  - `@angular/core` → `angular`
- `backendStack` — inspect the backend manifest:
  - `package.json` with `express` / `fastify` / `koa` → `node-express`
  - `package.json` with `@nestjs/core` → `nestjs`
  - `pyproject.toml` / `requirements.txt` with `fastapi` → `fastapi`
  - `pyproject.toml` / `requirements.txt` with `django` → `django`
  - `pom.xml` / `build.gradle` with `spring-boot` → `spring-boot`
  - `*.csproj` → `dotnet`
  - `go.mod` → `go`

---

## Step 2 — Build the frontend (stack-aware)

The quantnik server can only serve **static** frontend bundles, so the source has to be built into a self-contained folder of files. Pick the build command and resulting dist directory based on `frontendStack`:

| Stack | Build command | Dist directory |
|-------|--------------|----------------|
| `react-vite` / `vue3-vite` / `svelte-kit` | `npm install && npm run build` | `<frontendRoot>/dist` |
| `nextjs` | `npm install && npm run build && npx next export -o out` (only if `next export` is supported; otherwise note that Next requires a Node runtime and fall back to `next start` mode — see Step 3 backend handling) | `<frontendRoot>/out` |
| `angular` | `npm install && npm run build -- --configuration=production` | `<frontendRoot>/dist/<project-name>/browser` (or just `dist` for older Angular) |

For Vite-family projects, **set `base: '/<slug>/'` in `vite.config.js` before building** so all asset URLs in the bundle are prefixed with the deploy slug. Vite hard-codes the base into the bundle.

The skill must also ensure **three** other things are correct before building, or the deployed app will white-screen. Each has caught a real deploy:

**(a) API client honours BASE_URL.** Otherwise the deployed SPA calls `/api/*` on the quantnik origin instead of `/<slug>/api/*` on its own backend. Standard pattern: change any hard-coded `const BASE = '/api'` to ``const BASE = `${import.meta.env.BASE_URL}api`.replace(/\/{2,}/g, '/')`` so it evaluates to `/api` in dev (base=`/`) and `/<slug>/api` in deployed builds. Patch every `/api/...` literal in `src/services/**` the same way before building.

**(b) React Router (or equivalent) has a `basename`.** Otherwise the FIRST internal `<Link>` click navigates the browser out of the slug to `/<route>`, which falls through to quantnik's SPA fallback and renders a white screen. Patch `main.jsx`:

```jsx
<BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
```

For Vue Router: `createRouter({ history: createWebHistory(import.meta.env.BASE_URL) })`. For TanStack Router: `basepath: import.meta.env.BASE_URL.replace(/\/$/, '')`. Apply the framework-equivalent before building.

**(c) Backend mounts under `/api`.** The quantnik dispatcher proxies `/<slug>/api/*` → backend `/api/*` without stripping. If the backend mounts routes at `/` (e.g. `app.use(routes)` where the router has `/v1/members`), then production calls 404 even though dev (which uses Vite's `proxy.rewrite: path => path.replace(/^\/api/, '')`) works. Fix the backend to mount at `/api`:

```js
// before: app.use(routes);
// after:
app.use('/api', routes);
```

And remove the corresponding `rewrite` from `vite.config.js`'s proxy config (so dev forwards `/api/*` unchanged — same shape as production). Apply both edits before building, never just one — a half-applied fix breaks dev OR prod.

Then for the build itself:

```
// before build:
Edit vite.config.js to set `base: '/<slug>/'`
// run build
// after build:
Edit vite.config.js to restore the original base (or unset)
```

For Next.js exports and Angular, do the equivalent (`assetPrefix` for Next, `--base-href=/<slug>/` for Angular).

Run the build as a foreground `Bash` call so failures surface immediately. On failure, halt and print the build output verbatim — never deploy a half-built app.

Verify the dist directory exists and contains `index.html` before proceeding.

---

## Step 3 — Prepare the backend (if present)

If `backendRoot` is `null`, skip this step.

Otherwise, install dependencies and determine the **start command** the quantnik server should use to spawn the backend process. The quantnik server passes `PORT` as an env var; the backend MUST honour `process.env.PORT` (Node) or its stack equivalent.

| `backendStack` | Install | Start command (the value of `backendStartCmd` + `backendStartArgs`) |
|-----------------|---------|----------------------------------------------------------------------|
| `node-express` / `nestjs` | `npm install --omit=dev` | `cmd: "node"`, `args: ["src/server.js"]` (or `nest start` for Nest) |
| `fastapi` | `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt` | `cmd: ".venv/Scripts/uvicorn"`, `args: ["app.main:app", "--host", "127.0.0.1", "--port", "$PORT"]` |
| `django` | same | `cmd: ".venv/Scripts/python"`, `args: ["manage.py", "runserver", "127.0.0.1:$PORT"]` |
| `spring-boot` | `./mvnw -q -DskipTests package` | `cmd: "java"`, `args: ["-jar", "target/<artifact>.jar"]` |
| `dotnet` | `dotnet publish -c Release -o publish` | `cmd: "dotnet"`, `args: ["publish/<assembly>.dll"]` |
| `go` | `go build -o bin/app ./...` | `cmd: "bin/app"`, `args: []` |

The quantnik server only honours `$PORT` as a literal env var (not shell substitution), so for stacks that need the port inline (uvicorn, django), write the args as a placeholder string `"$PORT"` — the deployment route detects the `$PORT` token and substitutes the allocated port number at spawn time.

Actually, simpler: omit the port from args entirely. Configure the backend to read `process.env.PORT` (Node) or `os.getenv("PORT")` (Python) at startup. The quantnik dispatcher always sets `PORT` on the child env. If the user's backend doesn't read PORT, halt with a clear instruction to add that one line.

---

## Step 4 — Register the deployment

`POST` to `http://localhost:6060/api/deployments/<projectId>` with JSON body:

```json
{
  "slug": "<slugified-project-name>",
  "frontendDist": "<absolute-path-to-dist-folder>",
  "backendPath": "<absolute-path-to-backend-root>",   // omit if frontend-only
  "backendStartCmd": "node",                           // omit if frontend-only
  "backendStartArgs": ["src/server.js"],               // omit if frontend-only
  "backendEnv": { "NODE_ENV": "production" }           // optional — merged on top of inherited env
}
```

Use `Bash` with `curl`:

```
curl -s -X POST http://localhost:6060/api/deployments/<projectId> \
  -H "Content-Type: application/json" \
  -d @<temp-json-file>
```

Write the JSON body to a temp file first (the body is too long for inline `-d`).

Always target `http://localhost:6060` even when the public host is `PUBLIC_BASE_URL` — IIS / the reverse proxy fronts the same Quantnik process at both endpoints, and the loopback hop is cheaper. The route reads `PUBLIC_BASE_URL` from the backend's env and stamps the public URL onto the deployment row (no need to send `publicHost` in the body).

Parse the response — on success it returns `{ url, backendPort, deployment, message }`. The `url` field is the publicly browseable URL (for example, `<PUBLIC_BASE_URL>/<slug>`). On failure (4xx/5xx) it returns `{ error }` — surface the error verbatim and halt.

---

## Step 5 — Verify the deployment is live

Run two `curl` probes:

1. `curl -sI http://localhost:6060/<slug>/` — must return 200 with `content-type: text/html`. Confirms the loopback dispatcher is wired.
2. `curl -sI <url>/` against the public URL returned in step 4 (for example, `<PUBLIC_BASE_URL>/<slug>/`) — must also return 200. Confirms IIS / the public proxy is forwarding `/<slug>/*` to the same process. If step 1 passes but step 2 returns the Quantnik SPA, the reverse proxy is eating the slug — flag it and skip step 3 until the proxy is fixed.
3. If a backend was deployed: `curl -sI http://localhost:6060/<slug>/api/health` (or whichever health endpoint the backend exposes — fall back to `/`). Must return 2xx. If it returns 502, the backend process didn't start cleanly — read the backend log at the path printed in the deployment response and surface the first 50 lines as a diagnostic.

If either probe fails, the deployment is registered but not fully live. Print the failure clearly and offer to read the backend log.

---

## Step 6 — Print the final URL and lifecycle hints

On success, print:

```
✅ Deployed.

URL:           <url from response — e.g. http://localhost:6060/myproject/>
Project:       <project name> (id <projectId>)
Slug:          <slug>
Frontend dist: <copied to: ...>
Backend:       <port> (PID <pid>)   |   (frontend-only — no backend)
Logs:          <log path>

Manage from the quantnik host:
  • List all deployments: curl http://localhost:6060/api/deployments
  • Restart this one:     curl -X POST http://localhost:6060/api/deployments/<id>/restart
  • Undeploy:             curl -X DELETE http://localhost:6060/api/deployments/<id>
```

If `publicHost` was overridden (Step 4 takes an optional `publicHost` field — surface it as a question if the project's quantnik.json has a `deployment.publicHost` field), substitute the host accordingly in the printed URL.

---

## Guardrails

- **Reserved slugs.** The quantnik dispatcher refuses these slugs because they collide with API routes or static assets: `api`, `ws`, `auth`, `assets`, `health`, `static`, `public`, `admin`, `login`, `logout`, `callback`, `favicon.ico`, `index.html`, `d`. If the project name sanitises to one of these, append `-app` and retry (e.g. `api` → `api-app`).
- **Never modify the quantnik frontend bundle.** Deployed apps are isolated — they share nothing with quantnik's own UI beyond the Express host.
- **No port range outside 7000–7999.** That range is what the dispatcher allocates from. Don't hard-code a port.
- **Single Phase 9 prompt rule.** This skill is non-interactive — it never pauses for confirmation between steps. The user invoked the skill once; that's the consent. The only exception is when Step 1 can't locate the source folder.
- **No deployment if the source folder is git-dirty in a way the user didn't sign off on.** Run `git status --porcelain` once and surface any modified files in the build log — but do NOT block the deploy unless the user explicitly said to.
- **Re-deploy = clean replace.** If a deployment with the same slug exists, the route kills the existing backend process and overwrites the frontend dist before re-spawning. There's no partial overlap.
