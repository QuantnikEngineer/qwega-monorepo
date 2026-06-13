---
name: config-check
description: Diagnoses a quantnik project's external-integration health before a long-running skill (orchestrator, deploy, sanity-check) wastes time hitting a broken dependency. Verifies (a) every registered git repo has a remote URL and that remote is reachable via `git ls-remote`, (b) the Atlassian Jira MCP can fetch `/myself` + the configured Jira project's issue-type metadata, (c) the Atlassian Confluence MCP can resolve the configured space's ID and list at least one page in it. Attempts safe auto-fixes — re-clone a missing local working copy via quantnik's clone API, refresh the Confluence space ID cache, verify the Jira project supports Epic + Story issue types — and prints a clean PASS / DEGRADED / FAIL verdict at the end with a numbered checklist of issues the user still needs to handle. Use this whenever a chat turn fails with a connection / auth / permission error against git, Jira, or Confluence, or pre-flight before kicking off the sdlc-orchestrator on a new project.
---

When invoked, run the checks end-to-end. Mostly autonomous — no prompts under happy path. Halt with a clear error only when `quantnik.json` is missing (we don't know which Jira/Confluence to test against without it).

This skill supports the **two Atlassian MCP shapes** (`mcp__Jira__*` + `mcp__Confluence__*` stdio, or `mcp__claude_ai_Atlassian__*`). Detect which is loaded at session start and use the matching tool calls throughout. If neither is loaded, fail the Atlassian checks loudly — that's exactly the failure mode this skill is here to catch.

---

## Step 0 — Resolve context

Read `.claude/quantnik.json` at the project cwd. Capture:
- `project.id`, `project.name`, `project.path`
- `atlassian.siteName`, `atlassian.siteUrl`
- `atlassian.jiraProjectKey` — what Jira project should be reachable
- `atlassian.confluenceSpaceKey` — what Confluence space should be reachable
- `atlassian.confluenceSpaceId` (if cached)

If `quantnik.json` is absent, halt: "No quantnik.json — can't tell which Jira/Confluence to validate. Open the project in quantnik first so the sidecar gets written."

Initialize a `checks[]` array — every check appends `{ id, category, name, status: 'pass'|'fail'|'fixed'|'skipped', detail, autofix?: { applied, succeeded, note } }`.

---

## Step 1 — Git remote check (per registered repo)

`Bash` `curl -s http://localhost:6060/api/repos/<projectId>` to list every repo registered for the project. For each row:

### 1.1 — Static checks (no network)
- **Has remote_url?** Pass / fail. (`remote_url` is the source-of-truth field; without it the repo isn't deployable, pushable, or shareable.)
- **Local path exists?** `Bash` `[ -d "<path>" ] && echo yes` — pass / fail.
- **Local path is a git repo?** `Bash` `[ -d "<path>/.git" ] && echo yes` — pass / fail.

### 1.2 — Network check
If remote_url is set, run `Bash` `git -C "<path>" ls-remote origin HEAD` with a hard `timeout: 15000`. Three outcomes:
- exit 0 → remote reachable, auth OK → `pass`
- exit 128 + `Could not read from remote repository` → `fail` (auth / network)
- timeout → `fail` with detail "ls-remote timed out — check VPN / proxy / firewall"

### 1.3 — Auto-fix (limited but useful)
- **Local path missing OR not a git repo, but remote_url present** → call `POST /api/repos/<projectId>/<repoId>/clone` and mark the row `fixed` on 2xx. The quantnik API uses its own credentials cache, so clone will succeed wherever the user has Git Credential Manager configured for the remote.
- **No remote_url** → can't auto-fix. Mark `fail` and add to the user-facing checklist as "edit the repo row in the Repos tab to add a remote URL, then re-run `/config-check`."
- **Remote reachable but local missing AND clone fails** → mark `fail` with the stderr from the clone attempt.

Record one check row per repo (`category: 'git'`). If the project has zero repos, that's a `skipped` not a `fail` — some projects don't need a git remote.

---

## Step 2 — Jira MCP check

### 2.1 — MCP availability
Confirm the MCP is loaded by trying the *lightest* possible call:
- **Shape A (stdio):** `mcp__Jira__jira_get` path `/rest/api/3/myself`
- **Shape B (claude.ai-managed):** `mcp__claude_ai_Atlassian__atlassianUserInfo`

On success (returns an account object), record `pass` with the user's email + accountId in the detail.

On failure / tool-not-loaded:
- If the error message is "tool not available" / "unknown tool", record `fail` with detail "Atlassian Jira MCP is not loaded in this session. Re-run quantnik with the Atlassian MCP env vars set: `MCP_ATLASSIAN_EMAIL`, `MCP_ATLASSIAN_TOKEN`, `MCP_ATLASSIAN_SITE_NAME` (see backend/.env)." — there's nothing to auto-fix from inside the skill.
- If the error is HTTP 401 / 403, record `fail` with detail "Jira auth rejected — the API token in `backend/.env` is invalid or revoked. Generate a new one at id.atlassian.com → Security → API tokens, update `MCP_ATLASSIAN_TOKEN`, and restart quantnik."

### 2.2 — Project key check
If 2.1 passed, verify the configured Jira project exists and supports Epic + Story:
- **Shape A:** `mcp__Jira__jira_get` path `/rest/api/3/project/<jiraProjectKey>?expand=issueTypes`
- **Shape B:** `mcp__claude_ai_Atlassian__getJiraProjectIssueTypesMetadata` with the project key

Record:
- HTTP 404 → `fail` ("Jira project `<key>` not found on this site. Either the project was deleted or quantnik.json points at the wrong key.")
- 200 but missing Epic OR Story issue type → `fail` ("Jira project `<key>` does not have Epic / Story issue types — orchestrator's Phase 2 will halt. Add the missing type or switch to a Scrum/Kanban-style project.")
- 200 with both types → `pass` (detail: list the available issue types so the user can spot extras like Test, Sub-task, Bug).

### 2.3 — Auto-fix
Nothing the skill can do from inside the SDK — both failure modes require either env-var changes (auth) or admin actions in Jira (issue types). Mark as `fail` and surface in the final checklist.

---

## Step 3 — Confluence MCP check

### 3.1 — MCP availability
- **Shape A:** `mcp__Confluence__conf_get` path `/wiki/api/v2/spaces?keys=<confluenceSpaceKey>&limit=1`
- **Shape B:** `mcp__claude_ai_Atlassian__getConfluenceSpaces` (filter client-side by key)

On 200 with at least one space matching `confluenceSpaceKey`, record `pass` and capture the spaceId for step 3.3.

On failure, classify:
- Tool not loaded → `fail` ("Atlassian Confluence MCP is not loaded — same env-var issue as Jira above.")
- 401 / 403 → `fail` ("Confluence auth rejected — token issue.")
- 200 but no space matches → `fail` ("Confluence space `<key>` not found in `<site>`. Either the key is wrong in quantnik.json or the user's API token doesn't have access to that space.")

### 3.2 — Page-list smoke test
If 3.1 passed, list the first few pages in the space to confirm read access actually works (some keys resolve but the token can't read them):
- **Shape A:** `mcp__Confluence__conf_get` path `/wiki/api/v2/spaces/<spaceId>/pages?limit=1`
- **Shape B:** `mcp__claude_ai_Atlassian__getPagesInConfluenceSpace` with `spaceId`

200 → `pass`. 403 → `fail` with detail "Token resolved the space but can't list pages — broaden the API token's permissions in Atlassian."

### 3.3 — Auto-fix: refresh cached spaceId
If `quantnik.json` has `confluenceSpaceId: null` but step 3.1 just resolved a real ID, that's a real auto-fix. POST it back to quantnik:
```
curl -s -X PUT http://localhost:6060/api/projects/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"confluence_space_id": "<resolved-id>"}'
```
(If the projects PATCH route doesn't accept that field today, skip this fix and surface it as a non-fatal note — the orchestrator's other skills already re-resolve the ID per-run via `/wiki/api/v2/spaces?keys=`.)

Record as `fixed` if the PUT succeeds.

---

## Step 4 — Quantnik service self-check (cheap)

`Bash` `curl -sf http://localhost:6060/api/health` with `timeout: 5000`. 200 → `pass`. Anything else → `fail` (the quantnik backend itself is down — most user-facing actions in the UI will be broken too).

`curl -sf -I http://localhost:6060/api/deployments` → `pass` on 200. Failing this means the deployments route isn't mounted — either the user is on a very old build, or the backend crashed mid-startup.

These two go in `checks[]` under `category: 'service'`.

---

## Step 5 — Assemble + print the report

Build the verdict:
- `PASS` — every check is `pass` or `fixed`.
- `DEGRADED` — at least one `fail` in `category: 'git'` only (deployable but storage tagging will be off), and Atlassian / service all `pass`.
- `FAIL` — any Atlassian or service check failed (orchestrator-style skills will hit walls).

Print this exact shape (markdown — quantnik renders it cleanly):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIG CHECK COMPLETE — <PASS | DEGRADED | FAIL>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 Project
  Name:   <project.name>  (quantnik id <project.id>)
  Path:   <project.path>

🔗 Git remotes
  <per-repo line — e.g. ✅ quantnik-mobile · https://git.harness.io/…  (cloned, ls-remote 200ms)>
  <❌ frontend-repo · no remote_url set — edit the row in the Repos tab>
  <🔧 docs-repo · was missing locally — auto-cloned (~3 MB)>

🎯 Atlassian
  Site:        <siteName>.atlassian.net
  Jira:        ✅ project <KEY>  (Epic ✓ · Story ✓ · 7 other issue types)
  Confluence:  ✅ space <KEY>  (id <id>, 1+ page readable)

🛠 quantnik service
  /api/health:      ✅ 200
  /api/deployments: ✅ 200

— Auto-fixes applied: <n>
— Items needing user action: <n>
   1. <numbered list of every `fail` row, with its `detail` text>
   2. …
```

If no failures, end with: "All checks passed — safe to invoke `/sdlc-orchestrator` or any other skill that touches git / Atlassian."

If failures, end with: "Fix the items above before re-running heavy skills. Re-run `/config-check` to confirm."

---

## Guardrails

- **No write to Jira / Confluence.** All Jira/Confluence calls in this skill are GETs. Never create an issue, never write a page — diagnostic only.
- **One auto-fix per check.** If clone fails twice or the cached space ID was already correct, record the outcome and move on. Never loop.
- **Hard timeout per network call** — `15s` for `git ls-remote`, `10s` for MCP calls, `5s` for the local quantnik health probe. A flaky remote shouldn't hang the whole skill.
- **Idempotent.** Running `/config-check` ten times in a row produces ten identical reports — no side effects beyond the one-shot clone and spaceId cache refresh.
- **Confluence space key from `quantnik.json` only.** Never call `getConfluenceSpaces` with no filter to find one — that's the bug this skill is designed to catch.
