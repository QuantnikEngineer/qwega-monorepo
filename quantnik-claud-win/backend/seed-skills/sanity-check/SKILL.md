---
name: sanity-check
description: Runs an end-to-end sanity / smoke check against a deployed application — verifies the public URL serves the SPA, the deployed backend's health endpoint responds, every API route the frontend actually calls returns a healthy status, and each main user-story feature visible in Jira maps to a live endpoint. Publishes a structured pass/fail report to Confluence with the URL printed at the end. Use this after a deploy-to-platform (or orchestrator Phase 10) run to confirm the deployment is actually healthy, not just "running". The counterpart to test-script-executor — that runs scripted Playwright tests against the UI; this runs a lightweight HTTP/SPA probe suite for fast deploy-time confidence and produces a single Confluence-published report stakeholders can read in 30 seconds.
---

When invoked, run the sanity checks end-to-end. **Mostly autonomous** — no interactive prompts under happy path. Halt with a clear error only when (a) `quantnik.json` is missing, (b) no deployment exists for this project, or (c) the Confluence MCP isn't loaded.

This skill supports the **two Atlassian MCP shapes** described in other quantnik skills (`mcp__Jira__*` + `mcp__Confluence__*` stdio, or `mcp__claude_ai_Atlassian__*`). Detect which is loaded at session start and use the matching tool calls throughout. If neither is available, still run the checks but skip the Confluence-publish step — print the report to chat instead so the user can paste it elsewhere.

---

## Step 0 — Resolve context

### 0.1 — Read `.claude/quantnik.json` at the project cwd

Pull from the sidecar:
- `project.id` → required for the deployments API.
- `project.name` → default slug seed.
- `atlassian.jiraProjectKey` → scope Jira queries (the project key for user-story discovery).
- `atlassian.confluenceSpaceKey` → target space for the report (do **not** publish elsewhere).
- `atlassian.siteName` / `siteUrl` → for browse URLs.

Halt with a clear error if `quantnik.json` is absent — without `project.id` we can't find the deployment to probe.

### 0.2 — Fetch the deployment record

`GET http://localhost:6060/api/deployments` and find the row where `project_id === quantnik.json's project.id`. Capture:
- `slug`
- `url` (e.g. `https://claude.quantnik.com/<slug>`) — the **canonical public URL** under test
- `backend_port` (loopback port — used for direct probes that bypass IIS / quantnik proxy)
- `frontend_path` (the served dist directory — for static-asset checks)
- `backend_path` + `backend_start_args` (for backend source inspection)
- `status` — if `stopped`, the deployment isn't running; halt with an error pointing the user at `POST /api/deployments/<id>/restart`.

Record into `run-context.deployment`.

### 0.3 — Confirm Atlassian MCP availability

Try `mcp__Jira__jira_get` `/rest/api/3/myself` (Shape A) or `atlassianUserInfo` (Shape B). If both fail, continue but mark `run-context.atlassian = null` — the Jira-story-mapping step (3) and Confluence publish step (6) will degrade gracefully.

---

## Step 1 — Reachability checks

Run each as a single `Bash` call (use `curl -sI` for HEAD, `curl -s -o /dev/null -w '%{http_code}'` for body-less status, `curl -s -o NUL -w '%{http_code}'` on Windows). Build a `checks[]` array with `{ name, target, expected, actual, status, latencyMs }` entries.

| Check | Probe | Pass criteria |
|-------|-------|---------------|
| Public SPA | `HEAD <deployment.url>/` | 200 + `content-type: text/html` + body bytes > 500 (not a 389-byte quantnik SPA fallback) |
| Loopback SPA | `HEAD http://localhost:6060/<slug>/` | 200 + `content-type: text/html` |
| Main JS bundle | Parse `<script src=...>` from the public SPA's index.html, then `HEAD` it | 200 + `content-type: text/javascript` or `application/javascript` + size > 10 KB |
| Stylesheet | Parse `<link rel=stylesheet>` similarly | 200 + `text/css` |
| Backend health | Try in order: `<deployment.url>/api/health` → `<deployment.url>/health` → `http://127.0.0.1:<backend_port>/health`. First 2xx wins. | 2xx response (any body) |
| Slug isolation | `HEAD <deployment.url>/<random-string>/` | If this returns the same 1100+ byte SPA as the slug root, **fail** — the proxy is forwarding paths it shouldn't. If it returns quantnik's 389-byte fallback, that's actually correct here. |

If the public SPA check returns a body that matches quantnik's own index.html (`<title>Quantnik</title>`, ~389 bytes), mark as **critical fail** — the reverse proxy is eating the slug. Skip downstream checks that need the SPA to be live and jump to step 6.

---

## Step 2 — Discover the API surface

The goal here is to enumerate every API route the frontend actually calls in production, then probe each. Two complementary signals — use both:

### 2.1 — Backend route inspection

`Grep` the backend source for route definitions:

```
backend_path = run-context.deployment.backend_path
grep -rn "router\.\(get\|post\|put\|patch\|delete\)\|app\.\(get\|post\|put\|patch\|delete\)" <backend_path>/src
```

Parse each match into `{ method, path, file, line }`. Skip routes mounted under non-`/api` prefixes if the frontend's BASE constant only resolves to `/api` (typical Vite scaffold). Record into `run-context.backendRoutes`.

### 2.2 — Frontend API client inspection

`Grep` the frontend source for fetch calls:

```
grep -rn "fetch(\|api\.\(get\|post\|put\|delete\)\|request(" <frontend_path's source mirror>/src
```

Frontend source is the original repo dir (find it in `quantnik.json` repos list or the orchestrator's Phase 3 output folder, NOT the deployed `dist/` — that's minified). Record `{ method, path, file, line }` per call site.

If you can't find the original frontend source on disk, fall back to **string-scanning the minified `dist/<bundle>.js`** for `/api/` substrings — this catches at least the paths if not the methods. Mark these as "method:?" so the probe step uses `GET` by default.

### 2.3 — Cross-reference

Match the frontend call sites against the backend routes. Build the final probe list:

```
probes: [
  { method, path, calledFromFrontend: bool, definedInBackend: bool, mappedStory?: <STORY-KEY> },
  ...
]
```

---

## Step 3 — Smoke-probe each endpoint

For each probe in the list:

1. **GET routes:** `curl -s -o <tmp> -w '%{http_code} %{time_total}'` against `<deployment.url><path>`. Pass criteria: HTTP 200 with a non-empty body, OR HTTP 401/403 (endpoint exists but requires auth). Fail criteria: 404 (route missing), 502 (backend down), 500 (server error — capture first 200 chars of body for the report).
2. **POST/PUT/PATCH routes:** `curl -s -o <tmp> -w '%{http_code}' -X POST -H 'content-type: application/json' -d '{}'` — pass on **any** 4xx (400/401/422 all mean the route exists; the empty payload was rejected). Fail on 404/5xx.
3. **DELETE routes:** treat like POST but never send the request body. Probe with `-X DELETE` against the collection path (`/api/items` not `/api/items/123`); a 4xx is expected and fine.

Each probe runs with a 10-second hard timeout (`Bash` `timeout: 10000`). If it times out, mark `{ result: 'timeout', latencyMs: 10000 }` and continue to the next probe — never block the suite on one stuck endpoint.

Record results into `run-context.probeResults[]`.

---

## Step 4 — Map probes to Jira user stories (feature coverage)

Skip if `run-context.atlassian` is null.

For each story in the Jira project (`searchJiraIssuesUsingJql`: `project = <jiraProjectKey> AND issuetype in (Story, Task) ORDER BY created DESC`, limit ~50):

- Parse the story's description for `/api/<path>` mentions, route names, or feature keywords (e.g. "members", "insights", "dismiss"). Use a simple substring match — if the story description contains a substring that also appears in any probe's path, mark the story as **covered** by that probe.
- Record `{ storyKey, storyTitle, coveredBy: [<paths>], aliveCount: <how many of those probes passed>, status: 'pass' | 'partial' | 'fail' | 'uncovered' }`.

Threshold:
- `pass` — every covering probe returned 2xx / expected 4xx.
- `partial` — at least one covering probe passed, at least one failed.
- `fail` — every covering probe failed.
- `uncovered` — no matching probes (often means the story is purely UI, or the heuristic missed it; surface in the report but don't fail the whole suite).

Record into `run-context.featureCoverage`.

---

## Step 5 — Performance baseline

One `Bash` call per metric, all timeouts at 15s.

```
curl -o /dev/null -s -w 'connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}' <deployment.url>/
```

Record `homepage_ttfb_ms`, `homepage_total_ms`. Repeat for the JS bundle (often the long pole). Flag any over 3 seconds as a yellow warning in the report (not a fail — these are deploys, not load tests).

---

## Step 6 — Assemble + publish the Confluence report

### 6.1 — Build the report body

Title: `<Project> — Sanity Check Report — <YYYY-MM-DD HH:mm>`

Storage-format (Shape A) or markdown (Shape B) body, sections in this exact order:

```
## Executive Summary

Status: ✅ PASS  |  ⚠ DEGRADED  |  ❌ FAIL
Public URL: <deployment.url>
Probed at: <ISO timestamp>
Deployment id: <deployment.id>  ·  Backend port: <backend_port>

| Category | Pass | Fail | Total |
| Reachability | 5 | 0 | 5 |
| API probes   | 12 | 1 | 13 |
| Feature stories covered | 8 | 1 | 11 (2 uncovered) |
| Performance under 3s    | 2 | 0 | 2 |

## Reachability

<one row per Step 1 check — name, target, expected, actual, latency, ✅/❌>

## API Surface

<one row per probe from Step 3 — method, path, status code, latency, called-from-frontend?, defined-in-backend?, pass/fail>

For each fail, include a code block with the first 200 chars of the response body so the user can see the actual error.

## Feature Coverage

<one row per Jira story from Step 4 — key, title, status, covering paths>
For uncovered stories, add a "Likely UI-only" or "Needs manual check" note.

## Performance

| Metric | Value | Threshold | Status |
| home_ttfb_ms | 280 | <3000 | ✅ |
| home_total_ms | 540 | <3000 | ✅ |
| bundle_total_ms | 1820 | <3000 | ✅ |

## Run Metadata

- Project: <name> (quantnik id <id>)
- Slug: <slug>
- Deployment URL: <url>
- Backend path: <backend_path>
- Frontend dist: <frontend_path>
- Jira project: <jiraProjectKey>
- Confluence space: <confluenceSpaceKey>
- Probes ran: <count>; Probes timed out: <n>

## Recommendations

<if any check failed, list the top 3 next actions tied to specific findings — e.g. "Endpoint /api/v1/foo returned 500; check controller error handling at <file>:<line>">
<if all passed: "Deployment looks healthy. Consider running test-script-executor for deeper coverage.">
```

Use real tables (Confluence storage `<table>` / `<tr>` / `<td>`, or markdown tables in Shape B). Color the Status pill in the Executive Summary using a Confluence `info`/`warning`/`error` panel macro (Shape A) or just emoji (Shape B).

### 6.2 — Publish

- **Shape A:** `mcp__Confluence__conf_post` to `/wiki/api/v2/pages` with `spaceId` resolved from `run-context.confluenceSpaceKey` via `/wiki/api/v2/spaces?keys=<KEY>`. Cache the resolved spaceId.
- **Shape B:** `createConfluencePage` with `cloudId`, `spaceId`, `title`, `contentFormat: "markdown"`, `body`.

Record `run-context.reportUrl` from the response.

If publishing fails (Atlassian outage, permission issue), still print the full report to chat so the user can grab it manually. Don't silently swallow.

---

## Step 7 — Final output (mandatory shape)

Print **exactly** this format at the end:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SANITY CHECK COMPLETE — <PASS | DEGRADED | FAIL>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 Deployment
  URL:        <deployment.url>
  Slug:       <slug>
  Backend:    port <backend_port>

✅ Reachability:  <p>/<t>
🔌 API probes:    <p>/<t>  (<n> timeouts)
📋 Stories:       <p>/<t>  (<u> uncovered)
⚡ Performance:   <p>/<t>

📄 Report:    <confluence URL>

🚨 Critical findings:
  • <up to 3 most-important fails — endpoint, status, suggested action>
```

Overall verdict rules:
- `PASS` — every Reachability check passes AND ≥ 80% of API probes pass AND zero timeouts AND no story marked `fail`.
- `DEGRADED` — Reachability all-pass, but one of: <80% API probes, any timeouts, any partial/uncovered stories.
- `FAIL` — any Reachability check failed, OR the public URL served quantnik's fallback SPA, OR Confluence publish failed AND every other check failed too.

Ask: "Report published. Anything to drill into — re-run a specific endpoint, expand a failing story into a Playwright test, or re-deploy?"

---

## Guardrails

- **Never mutate the deployed app** — every probe is a read-only HEAD/GET or a deliberately-malformed POST that the backend should reject before doing any work. Never run `delete`, `clear`, or anything that creates real records.
- **No interactive prompts under happy path.** The user invoked the skill; that's the consent. Final summary is the only output that waits for engagement.
- **Confluence space is `run-context.confluenceSpaceKey` ONLY.** Same rule as every other quantnik skill — read from `quantnik.json`, never `getConfluenceSpaces` to pick a different one.
- **Hard timeout per probe = 10 s.** Whole-suite budget should land under 2 minutes even on a 30-endpoint API.
- **Never re-roll the deployment row.** If `status === 'stopped'`, halt with the exact restart command — don't try to start it from this skill.
