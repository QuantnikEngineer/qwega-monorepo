---
name: test-script-executor
description: Executes a Playwright test project against a running application, captures the results, MANDATORILY logs a Jira bug ticket (with RCA + corrective action) for every failure, then pauses to ask the user which failures to auto-fix and applies only those fixes. Publishes an execution report to Confluence and links every failure to its bug. Discovers the Playwright project from disk (defaults to the sdlc-orchestrator's output folder), preflights the app under test, installs missing dependencies and browsers, runs the suite, parses the JSON reporter output, and prints a structured summary with the report URL and per-spec breakdowns. The natural counterpart to `test-script-generator` — that skill writes the scripts; this one runs them.
---

When invoked, run the executor end-to-end. The skill is **mostly autonomous** with **one mandatory interactive pause** — after Jira bug tickets are logged for every failure, it asks the user to pick which to auto-fix and applies only those fixes. No other prompts under happy-path execution.

This skill supports the same two Atlassian MCP shapes used by the other SDLC skills:
- **Shape A — wega2 stdio:** `mcp__Confluence__conf_get/post/...`, `mcp__Jira__jira_get/post/...`. Site URL is `https://<ATLASSIAN_SITE_NAME>.atlassian.net`.
- **Shape B — claude.ai-managed:** `mcp__claude_ai_Atlassian__createConfluencePage`, `getJiraIssue`, `createJiraIssue`, `addCommentToJiraIssue`, etc.

**Jira logging is mandatory.** If neither shape is loaded, halt with:

> "Jira ticket logging is mandatory and no Atlassian MCP is loaded. Configure one (or run in a context that has it) before retrying `/test-script-executor`."

Tests are not run when Jira logging isn't available — the run is meaningless without the audit trail.

---

## Phase 0 — Discovery and preflight

### 0.1 — Locate the Playwright project

In order:

1. If the user named a path in the invocation message, use it.
2. Else look at the orchestrator's run-context (if running inside sdlc-orchestrator); use its `playwright_output_folder`.
3. Else check the wega2 project's configured repos (`additionalDirectories`): scan each for a `playwright.config.{js,ts,mjs,cjs}` at the root.
4. Else check siblings of the project cwd matching `*-playwright-tests` or `playwright-tests`.
5. Else search `~/projects/*-playwright-tests/` for a `playwright.config.*`.

If multiple candidates match, pick the **most recently modified**. Print:

```
Selected Playwright project: <absolute path>
  Config: playwright.config.js  ·  Last modified: <relative time>
```

If none are found, halt with the message:

> "No Playwright project found. Either pass an absolute path, configure the test repo in the Repos tab, or run `/test-script-generator` first."

### 0.2 — Read the config

Read `playwright.config.{js,ts,mjs,cjs}` at the project root. Extract (best-effort regex if it's not statically analysable):

- `baseURL` (under `use.baseURL`)
- `projects[].name` and `projects[].use.devices` (browser list)
- `testDir` (default: `tests`)
- `reporter` shape — note whether HTML reporter and/or `json`/`junit` are wired

If `baseURL` is missing, fall back to whatever the user passed in the invocation, then to `http://localhost:5173`. Record into `run-context.baseUrl`.

### 0.3 — Preflight the app under test

`curl -sf -m 5 <baseUrl>/` once. If it returns 2xx-3xx, the app is up.

If it's not up, look for the matching wega2 frontend / backend in `additionalDirectories` (or the orchestrator's `output_folder`). If found AND a `package.json` exists there:

- Start the backend (`node server.js` or `npm run start`) and the frontend (`npm run dev`) as **background** tasks via the `Bash` tool with `run_in_background: true`. Capture task ids.
- Re-poll `<baseUrl>/` once per second for up to 30 seconds. First 2xx-3xx wins.
- Record `boot_by_executor: true` so the final summary can flag that the servers were started by this skill (and remind the user to stop them later via the wega2 chat or `taskkill /F /PID`).

If the app still isn't reachable after the boot attempt (or there's nothing to start), halt with a clear error:

> "App under test is not reachable at <baseUrl>. Either start the dev servers (Phase 8 of /sdlc-orchestrator does this), point me at the right baseUrl, or pass `--no-preflight` to run the suite anyway."

### 0.4 — Read the traceability table

Open the Playwright project's `README.md` and look for the **traceability table** that `test-script-generator` writes. Parse `spec file → source story key → list of Test issue keys`. Store in `run-context.traceability` as `{ specFile: { storyKey, testKeys: [] } }`. This is what links the run results back to Jira.

If the table isn't present, run without traceability — the per-Jira-issue update step (Phase 4) will be skipped.

---

## Phase 1 — Install dependencies + browsers

### 1.1 — `npm install`

If `<playwright-folder>/node_modules` doesn't exist OR its mtime is older than `<playwright-folder>/package.json`:

```
cd <playwright-folder> && npm install
```

Foreground. If it fails, halt with the install error verbatim.

### 1.2 — Install browser binaries

Playwright keeps browser binaries in a user-level cache. If they're missing, the test run will fail with a clear error. Pre-empt by running:

```
cd <playwright-folder> && npx playwright install <browser-list>
```

Where `<browser-list>` defaults to whatever's in `playwright.config.js` `projects[].use.devices` (e.g. `chromium firefox webkit`), or just `chromium` if the config doesn't say. Skip if `~/.cache/ms-playwright/<browser>` already exists.

Foreground. If a browser fails to install, log the error and continue — the run will skip that browser project.

---

## Phase 2 — Run the suite

### 2.1 — Construct the command

Base form:

```
cd <playwright-folder> && npx playwright test --reporter=list,json,html
```

- Default reporter set: `list` (terminal-friendly progress), `json` (machine-readable for parsing), `html` (browse-able report on disk). The `json` reporter writes to `<playwright-folder>/test-results.json` by default; `html` writes to `<playwright-folder>/playwright-report/`.
- Add `--workers=<n>` if the user specified a worker count; otherwise let Playwright's default decide.
- Add `--project=<browser>` if the user filtered to a specific browser.
- Add `--grep=<pattern>` if the user filtered to specific spec names; otherwise run everything.
- Honour `PWDEBUG=1` if the user explicitly asked for the inspector — but never set it implicitly.

### 2.2 — Execute

Use the `Bash` tool **foreground** with a generous timeout (default 10 minutes — most suites finish well inside that). Capture stdout/stderr verbatim.

If the run is expected to take longer (the suite has > 200 tests, or the user said so), spawn it `run_in_background: true` and `Monitor` for completion.

### 2.3 — On crash vs failure

Distinguish:
- **Exit 0** — everything passed (or there were `test.skip`/`test.fixme` but no actual failures).
- **Exit 1** — one or more tests failed. This is **expected** — record the failures and continue, do not halt.
- **Other non-zero** — the runner itself crashed (e.g. config parse error, baseURL unreachable mid-run). Capture the error message and halt with a clear note. Do not pretend the suite ran.

---

## Phase 3 — Parse results

### 3.1 — Read the JSON reporter output

Read `<playwright-folder>/test-results.json`. The shape is:

```
{
  config: { ... },
  suites: [
    { title: "spec-name.spec.js", file: "tests/spec.js", specs: [
      { title, ok, tests: [
        { projectName: "chromium", results: [
          { status: "passed" | "failed" | "skipped" | "timedOut" | "interrupted",
            duration: <ms>,
            error: { message, stack } | null,
            attachments: [ { name, path, contentType } ],
            retry: <n>
          }
        ]}
      ]}
    ]}
  ],
  stats: { startTime, duration, expected, unexpected, flaky, skipped }
}
```

Flatten into a list of `TestResult` records:

```
{
  id: "<spec-path>::<test-title>::<browser>",
  spec: "tests/foo.spec.js",
  title: "should sign in with valid credentials",
  browser: "chromium",
  status: "passed" | "failed" | "skipped" | "flaky" | "timedOut",
  duration_ms: 1234,
  retries: 0,
  error: { message, location } | null,
  attachments: [ { name, path } ],
  jiraStoryKey: "<from traceability lookup by spec file>",
  jiraTestKeys: [ "<from traceability table>" ],
}
```

A test counts as **flaky** if `retries > 0` AND the final result was `passed`.

### 3.2 — Compute summary

```
total:    <n>
passed:   <p>
failed:   <f>
flaky:    <flaky>     # passed-after-retry
skipped:  <s>
duration: <d.dd>s
pass_rate: <p / (p+f)> %
```

Per-spec sub-summaries too — the report will use both.

---

**Scope rule before Phase 4 + Phase 6.** `Read` `.claude/wega.json` at the project cwd. If present:
- `atlassian.jiraProjectKey` → the **only** allowed Jira project for bug logging (Phase 4). Do not infer from traceability or `getVisibleJiraProjects`.
- `atlassian.confluenceSpaceKey` / `confluenceSpaceId` → the **only** allowed Confluence space for the execution report (Phase 6). Never the personal space when this is set.
- `atlassian.labels` → propagate to every created bug.

If the sidecar is silent on either, fall back to the existing discovery chain (traceability → wega2 project → halt).

## Phase 4 — Log a Jira ticket for every failure (mandatory)

This phase is **non-negotiable**. Every failed or timed-out test produces a Jira bug ticket containing RCA, corrective action, and reproduction details. If the Jira project doesn't expose a writable `Bug` (or `Task` as a fallback) issuetype, halt with a clear error — the run is not "complete" without the audit trail.

### 4.1 — Resolve the target Jira project

In order:

1. If `run-context.traceability` exists, take the project key from the first Test issue listed (e.g. `WC-123` → `WC`).
2. Else use the wega2 project's configured `jira_project_key` (read from `/api/llm/<projectId>` or from the project row).
3. Else halt with: "No Jira project resolvable for ticket logging. Configure `jira_project_key` on the wega2 project or run `/test-script-generator` first so the traceability table exists."

Probe the project for issuetypes:
- **Shape A:** `mcp__Jira__jira_get` with `/rest/api/3/project/<KEY>?expand=issueTypes`.
- **Shape B:** `getJiraProjectIssueTypesMetadata`.

Resolved issuetype is the first match of: `Bug` → `Defect` → `Task`. Record the resolved name in `run-context.bugIssueType`. Halt if none of those exist.

### 4.2 — Generate RCA + corrective action for each failure

For each `TestResult` with status `failed` or `timedOut`, classify by the error message:

| Error signature | RCA template | Corrective-action template |
|---|---|---|
| `locator.click: Timeout` / `waiting for selector` | Element matching selector did not appear within the wait budget. Likely causes: element renamed, removed, or rendered async after data load; selector too generic and matches a different element; race with navigation. | (Code) Add `data-testid` to the target element and switch the selector. (Test) Replace `getByText` with `getByRole(..., { name: ... })` or `getByTestId(...)`. Increase wait only as a last resort. |
| `expect(received).toBe(expected)` / `toEqual` mismatch | Assertion drift. Actual vs expected diverged — either business logic changed and the test is stale, or the source code regressed. | (Test if intentional behaviour change) Update expected value. (Code if regression) Fix the source so the assertion holds. |
| HTTP `4xx` from `page.request` / `fetch` failure | API endpoint returned client-error status. Possible causes: missing auth header, wrong path, validation broke, dependency change. | Inspect the request body/headers in the trace, replicate via `curl`, fix the failing handler or the test setup. |
| HTTP `5xx` from API | Backend threw a server error. Trace + server logs show the stack. | Open server logs (`<task-id>` from Phase 0.3 boot), fix the throwing path; do not paper over with `try/catch` that swallows. |
| `net::ERR_CONNECTION_REFUSED` / `ECONNREFUSED` | Backend or frontend dev server not running mid-test. | (Infra) Ensure Phase 0 preflight booted the servers OR start them manually; if the suite started them, check whether one crashed mid-run. |
| `Timeout exceeded while waiting for event` | An awaited event (response, page load, request) never fired. | (Test) Verify the event name and conditions; (Code) check that the event is actually emitted under the test's conditions. |
| `page.goto: net::ERR_*` | Navigation to the target URL failed. | Confirm baseURL and route exist; check the network tab in the trace. |
| Anything else | Untyped failure — capture the raw error message verbatim as the RCA seed. | "Review the attached trace and screenshot; reproduce locally with `npx playwright test <spec> --headed --debug`." |

Augment each RCA with the failing-line snippet pulled from the spec file (3 lines of context around the `error.location.line`).

Severity → Priority mapping:
- **timedOut on a non-flaky test that previously passed:** `High`.
- **Assertion failure:** `High` (likely regression).
- **5xx from API:** `Highest` (backend is broken).
- **Selector / timeout failure on a recently-touched spec:** `Medium`.
- **Skipped-but-marked-failing edge case:** `Low`.
- Default when uncertain: `Medium`.

### 4.3 — Create the bug

For each failure (sequentially, never in parallel — keeps the key sequence sensible):

**Shape A:** `mcp__Jira__jira_post` to `/rest/api/3/issue` with body:

```json
{
  "fields": {
    "project":   { "key": "<resolved key>" },
    "issuetype": { "name": "<bugIssueType>" },
    "summary":   "Test failure: <test title> [<browser>]",
    "priority":  { "name": "<resolved priority>" },
    "labels":    ["test-failure", "playwright", "<initiative-slug if known>"],
    "description": <ADF doc — see structure below>
  }
}
```

**Shape B:** `mcp__claude_ai_Atlassian__createJiraIssue` with `cloudId`, `projectKey`, `issueTypeName: <bugIssueType>`, `summary`, `contentFormat: "markdown"`, `description` (markdown), `additional_fields: { priority, labels }`.

**Description body** (markdown for Shape B; ADF doc with the same content for Shape A):

```
**Source spec:** `tests/<spec>.spec.js`
**Test:** "<full test title>"
**Browser:** chromium
**Run:** <ISO timestamp>
**Linked Story:** <STORY-KEY>
**Linked Test issues:** <TEST-KEY-1>, <TEST-KEY-2>

---

### Error

```
<error.message — first 600 chars>
   at <error.location.file>:<line>:<col>
```

### Failing line (with context)

```js
<3 lines above>
> <failing line>
<3 lines below>
```

### Root Cause Analysis

<the RCA template, expanded with the specifics from this failure>

### Corrective Action

<the corrective-action template, expanded with the specifics from this failure>

### Reproduce locally

```
cd <playwright-folder>
npx playwright test "<spec>" -g "<test-title>" --project=<browser> --headed --debug
```

### Attachments (on disk in the Playwright project)

- Trace: `test-results/<spec>-<title>/trace.zip`
- Screenshot: `test-results/<spec>-<title>/test-failed-1.png`
- Video: `test-results/<spec>-<title>/video.webm`
```

After creation, capture the returned `key` (and `id`) into the `TestResult` as `bugKey`.

### 4.4 — Link the bug to the source Test / Story

For each created bug:

- If the failing test has linked `jiraTestKeys` from the traceability table, create a "Relates to" link from the bug to each Test issue (and from the bug to the parent Story, if available).
  - **Shape A:** `mcp__Jira__jira_post` to `/rest/api/3/issueLink` with `{ type: { name: "Relates" }, inwardIssue: { key: <bugKey> }, outwardIssue: { key: <testKey> } }`.
  - **Shape B:** `createIssueLink`.
- Also comment on each linked Test issue: `❌ Failed in run <timestamp>. Logged as <bugKey>. <see bug for RCA + corrective action>.`

### 4.5 — Idempotency

Before creating a bug, search the project for an existing **open** bug with the same `summary`:

- **Shape A:** `mcp__Jira__jira_get` with `/rest/api/3/search/jql?jql=project=<KEY> AND summary~"\"<test title>\"" AND statusCategory!=Done&maxResults=5`.
- **Shape B:** `searchJiraIssuesUsingJql` with the same JQL.

If a match is found, **don't** create a duplicate — instead, add a comment to the existing bug:

```
↻ Reproduced in run <timestamp>. Error unchanged.
```

Update `TestResult.bugKey` to point to the existing bug. Count this as `dedupedBugs` in the run summary.

Record every bug into `run-context.bugs` as:

```
{ bugKey, testResultId, summary, priority, rca, correctiveAction, deduped: bool }
```

---

## Phase 5 — Interactive auto-fix selection (one prompt, then autonomous)

Only run if `run-context.bugs` is non-empty.

### 5.1 — Present the bug list

Print a numbered list of every bug logged in Phase 4. Each entry shows the bug key, the test title, the browser, the one-line RCA summary, and the suggested fix scope (`code` / `test` / `infra`):

```
The following <n> bug ticket(s) were logged for failures in this run.
Reply with the numbers to auto-fix (comma- or space-separated, ranges like 1-3 OK, "all" or "none" also accepted).
Auto-fix touches the source code or the spec file directly; everything not selected stays as a Jira ticket only.

 1. [WC-241] login.spec.js > "should reject empty password" (chromium)  ▸ fix scope: test
    RCA: Selector `input[name="password"]` matched the username field after the form was restructured.
    Suggested: switch to `getByRole('textbox', { name: 'Password' })`.

 2. [WC-242] feed.spec.js > "should paginate 20 chirps" (chromium)  ▸ fix scope: code
    RCA: Backend `/chirps?page=2` returned HTTP 500 — controller doesn't handle non-integer page.
    Suggested: parse `page` with Number(); reject NaN with 400.

 3. [WC-243] thread.spec.js > "should reply within 140 chars" (chromium)  ▸ fix scope: test
    RCA: Assertion expected reply count 1 but found 2; previous test seeded a reply.
    Suggested: add `test.beforeEach` to reset replies for the parent chirp.

> _
```

### 5.2 — Wait for selection

This is the **single permitted interactive pause** in the skill. Use the `AskUserQuestion` tool only if there are 2–4 bugs; for more, use a plain prompt so the user can type a list. Accept any of:

- A list/ranges (`1,3`, `1-3 5`, `2`).
- `all` → every bug.
- `none` / empty / `skip` → no auto-fix, move on.
- `n` (just the number) → only that one.

Parse into `run-context.autoFixSelection: number[]` (1-indexed into the bug list). Reject empty selections silently by treating them as `none`.

### 5.3 — Apply the selected fixes

**Hard rules for this loop — non-negotiable:**

- **One attempt per bug.** No retry loops. If the first patch + verify cycle doesn't succeed, mark it `auto-fix-failed`, revert any edit, and move to the next bug. Never loop trying alternate patches.
- **Per-bug budget: 90 seconds end-to-end.** If you can't finish a fix (read → patch → syntax check → verify → Jira update) in 90s, abandon it as `auto-fix-timeout`, revert any edit, and move on.
- **Re-run uses a bounded `Bash` call.** The Phase-5 verify (`npx playwright test ...`) must be called with the `Bash` tool's `timeout` parameter set to **60000 ms** AND with `--timeout=30000` passed to the playwright CLI. Playwright otherwise happily waits the default 30s × retries × browsers per failing test, easily blowing past five minutes on a single stuck spec.
- **Print progress before AND after every bug.** Before: `[fix M/N] <bug-key> — applying (scope=<test|code>)…`. After: `[fix M/N] <bug-key> — verified ✅` / `failed ❌` / `timeout ⏱` / `skipped (infra) ➖`. The user needs to see motion or they'll think the run is hung.
- **Skip-anytime escape.** If the user sends `skip` or `stop` at any point during the loop, abandon all remaining selected bugs, mark them `skipped-by-user`, and jump to §5.4. This is the second sanctioned interactive pause after §5.1 — accept the input via WS just like the auto-fix-selection prompt.

For each selected bug (sequentially, never in parallel, never more than one at a time):

1. **Read the failing artifact**: the spec file when `fix scope: test`, the source file(s) when `fix scope: code`. For `infra`, mark `skipped-infra` and move on — auto-restarting servers or editing CI is out of scope.
2. **Construct ONE patch** using the corrective-action template, specialised to the actual code:
   - **Selector fix:** replace the broken selector with the suggested role/testid one. If the target element doesn't have a `data-testid`, add one to the source component AND update the spec.
   - **Backend 500 fix:** add the missing `parseInt`/validation guard in the controller; emit the right status code; update tests if behaviour changes.
   - **Assertion drift fix:** when the RCA classification is "test stale", update the expected value in the spec; when it's "code regression", patch the source so the original assertion holds. The default is "treat as test stale" only when the spec was modified more recently than the source file under test — otherwise treat it as code regression.
   - **Race / event fix:** add an explicit `await page.waitForResponse(...)` or `await expect(locator).toBeVisible()` before the action; never just bump a timeout.
3. **Apply via `Edit`** (preferred — minimal diff) or `Write` (only if rewriting the whole spec is genuinely simpler).
4. **Syntax sanity check** with `Bash` and `timeout: 10000`: `node --check <file>` for JS, `tsc --noEmit` if a `tsconfig.json` exists. On non-zero exit, revert the edit and mark `auto-fix-failed`. Move on.
5. **Re-run that single test** with a bounded `Bash` call (`timeout: 60000`):
   ```
   cd <playwright-folder> && npx playwright test "<spec>" -g "<test-title>" --project=<browser> --reporter=line --timeout=30000
   ```
   - Exit 0 → mark `auto-fix-verified`.
   - Non-zero exit → revert the edit, mark `auto-fix-failed`.
   - Bash returns a timeout error → revert the edit, mark `auto-fix-timeout`. Do NOT re-run; do NOT investigate; move on.
6. **Update the Jira bug** with a comment (one `Bash`/MCP call, no retries):
   - Success: `🔧 Auto-fix applied + verified. Diff:` followed by a code block of the applied diff.
   - Failure / timeout: `🟡 Auto-fix attempted, verification failed (<reason>). Reverted. Manual investigation required.`
   If the Jira update itself fails (network, MCP error), log to console and continue — the outcome is already recorded in run-context.

Record each outcome into the bug record in `run-context.bugs`:

```
{ ...bug, autoFix: 'verified' | 'failed' | 'timeout' | 'skipped-by-user' | 'skipped-infra' }
```

### 5.4 — Re-run summary (optional but printed)

If at least one fix was verified, print:

```
Auto-fixes applied & verified: <k> of <selected>
Now-passing tests:
  • [WC-241] login.spec.js > "should reject empty password"
  ...

Remaining failures (not selected or fix unverified): <n>
  • [WC-242] feed.spec.js > "should paginate 20 chirps"  (auto-fix not attempted)
  • [WC-243] thread.spec.js > "should reply within 140 chars"  (auto-fix failed, see Jira for diff)
```

---

## Phase 6 — Publish the execution report to Confluence

Page title: `<Project> — Playwright Execution Report — <YYYY-MM-DD HH:mm>`.

Discover the Confluence space the same way `vulnerability-check` does — wega2 project's configured `confluence_space_key`/`confluence_space_id` first; else first personal space. Use the same dual-shape support.

Body sections:

1. **Executive summary** — pass rate (big number); `panel-success` callout if 100%, `panel-warning` if 80–99%, `panel-error` if < 80%. Total tests / duration / browser matrix / app URL.
2. **Run metadata** — playwright project path, baseURL, browser projects exercised, Node version (`process.version` captured at run time), Playwright version (`npx playwright --version`), commit SHA from the playwright project's git HEAD (`git -C <path> rev-parse HEAD`), executor `boot_by_executor` flag.
3. **Failures table** — every `failed` or `timedOut` test: spec | title | browser | duration | retries | linked Jira Test keys (clickable) | one-line error. Failures float to the top of the report.
4. **Flaky table** — tests that passed only on retry. Useful for the team's flakiness budget; smaller font.
5. **Pass table (collapsible)** — every `passed`. Inside a `<details><summary>` block.
6. **Per-spec breakdown** — one heading per spec file, with the spec's pass/fail counts and the list of contained tests with their statuses. This is what stakeholders look at when they want "did the login flow pass?".
7. **Traceability** — exact copy of the table from the test-script-generator README, but each row now has a Status column derived from the latest test result for that spec.
8. **Attachments index** — list every screenshot / trace / video attachment with its path inside the Playwright project. Don't try to inline them on the Confluence page (size); list the relative path so the team can fetch from disk.

Record `exec_report_url` into the run-context.

---

## Phase 7 — Final output (mandatory shape)

Print, in this order, exactly:

```
✅ Playwright execution complete.

Suite:       <playwright-folder>
Base URL:    <baseUrl>
Browsers:    <list>
Duration:    <d.dd>s

Tests:       <total>  (passed <p>, failed <f>, flaky <flaky>, skipped <s>)
Pass rate:   <pct>%

Bugs logged (<bugs_total>, <deduped> dedup'd against existing tickets):
  • [WC-241] spec/login.spec.js > "should reject empty password" (chromium) · Medium · auto-fix: verified ✅
    → RCA: selector matched the wrong field after form restructure.
  • [WC-242] spec/feed.spec.js > "should paginate 20 chirps" (chromium) · Highest · auto-fix: not-selected 🟡
    → RCA: backend /chirps?page=2 returns 500 on non-integer page.
  • [WC-243] spec/thread.spec.js > "should reply within 140 chars" (chromium) · High · auto-fix: failed 🔴
    → RCA: assertion drift — replies not reset between tests. Auto-fix reverted; manual investigation required.
  ...

Auto-fix summary: <verified>/<selected> verified, <failed> reverted, <not-selected> kept as ticket only.
Now-passing after auto-fix: [WC-241], ...

Flaky (<flaky>):
  • [WC-260] spec/bar.spec.js > "should load dashboard" — passed on retry #1
  ...

Reports:
  HTML:        <file:// path to playwright-report/index.html>
  JSON:        <file:// path to test-results.json>
  Confluence:  <url>

Jira: <bugs_created> bug ticket(s) created, <deduped> dedup'd; <test-comments> Test issues commented.
```

If Confluence publish failed (network / auth), replace the `Confluence:` line with `Confluence: ⚠ publish failed (<error>). Report saved locally: <path>`. The skill still succeeded — Jira bugs are the canonical record.

If no Atlassian MCP was loaded at all, Phase 4 already halted the run — this output is never reached in that case.

---

## Behavior rules

- **Mostly autonomous.** The skill has exactly **one** permitted interactive pause (Phase 5.2 — auto-fix selection). Every other step runs without confirmation. Acceptable halts: Playwright project not found at all; app under test unreachable AND no boot path available; runner-level crash (exit code other than 0 or 1); **no Atlassian MCP loaded** (Phase 4 mandatory — halt before running the suite); no writable Bug/Defect/Task issuetype on the resolved Jira project.
- **Jira logging is mandatory.** Every failed or timed-out test produces a Jira ticket with RCA + corrective action before Phase 5 begins. No "skip Jira" override exists — if the user wants to inspect failures locally without filing, they're using the wrong tool (use `npx playwright test` directly).
- **Auto-fix only what the user selected.** Skill must never silently patch a failure the user didn't pick. The bug-list prompt is the gate; an empty / `none` reply is respected and no edits happen.
- **Auto-fix is verified or reverted, never half-landed.** Every applied fix is re-run against the same test; on failure, the edit reverts and the bug is marked `auto-fix-failed`. The user never ends up with a "fix" that didn't actually fix anything but already mutated the codebase.
- **Idempotent.** Re-runs of the executor dedup against existing open Jira bugs by `summary` match. Comments on linked Test issues throttle to one per 5 minutes per (issue, status) pair so re-runs don't spam.
- **Never commit the report or generated artifacts.** Screenshots, traces, and the HTML report are write-only outputs in the Playwright project folder. Don't `git add` them; `.gitignore` should already exclude `playwright-report/` and `test-results.json` (test-script-generator handles this).
- **Never push test code changes from the auto-fix loop.** Edits land in the working tree only. Committing/pushing is a deliberate human step after the user reviews the diffs.
- **Honor user filters.** If the user said "run only the login spec", `--grep` accordingly; if they said "only chromium", `--project chromium`.
- **Don't leak secrets in the report or in Jira tickets.** When echoing test bodies, mask any `process.env.<NAME>` references with `[env:<NAME>]` rather than the resolved value. Same for any string that looks like an API key (`sk-...`, `figd_...`, `ATATT...`, `AKIA...`).
