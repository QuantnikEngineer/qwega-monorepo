---
name: sdlc-orchestrator
description: End-to-end autonomous SDLC pipeline. Takes raw input (transcript, idea, or requirements doc) and executes FIVE skills in sequence — BRD generation (sdlc-planning) → INVEST user stories in Jira (user-stories) → full-stack code (feature-dev) → Jira/Xray test cases (test-case-generator) → Playwright test scripts committed to git (test-script-generator). Every question the pipeline could need is asked upfront in one consolidated questionnaire; after the user confirms the run config, the orchestrator runs the remaining four phases autonomously without intermediate checkpoints.
---

When this skill is invoked, the entire pipeline runs in two acts:

1. **Phase 0 — Intake.** Collect *every* input the five downstream phases need, in one consolidated questionnaire. Confirm the resolved run config once. This is the **only** time the orchestrator stops for user input under happy-path execution.
2. **Phases 1–5 — Autonomous execution.** Run BRD → User Stories → Feature Dev → Test Cases → Test Scripts back-to-back. Print a STATUS block after each phase but **do not wait for confirmation**. The user only sees a prompt again if (a) an external system fails irrecoverably, (b) a destructive choice was deliberately deferred to runtime (e.g. a Jira issue type fallback the user did not pre-authorize), or (c) the run is complete.

Maintain a shared run-context object across all phases and print it as a status header after each phase:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SDLC PIPELINE STATUS
  Phase 1 — BRD:           [pending | running | done | skipped | failed]
  Phase 2 — User Stories:  [...]
  Phase 3 — Feature Dev:   [...]
  Phase 4 — Test Cases:    [...]
  Phase 5 — Test Scripts:  [...]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Phase 0 — Intake (the only interactive phase)

### 0.1 — Ask everything in one consolidated questionnaire

Present this exact block (substitute the user's known defaults from `MEMORY.md` where applicable — cloudId, default Jira project, email). Use the **AskUserQuestion** tool if appropriate; otherwise post the block as plain text and wait for one consolidated answer.

```
SDLC PIPELINE — RUN CONFIG
The pipeline runs end-to-end without further questions after this. Please answer all items:

A. PROJECT INPUT (for BRD)
   Paste any combination of:
   • Transcript / call notes
   • Rough idea / problem statement
   • Existing requirements doc or email thread
   • File paths to uploaded files: .txt, .md, .pdf, .doc, .docx, .png, .jpg, .jpeg, .gif, .webp
   Or type SKIP-BRD to reuse an existing Confluence BRD (you will be asked which one in step 0.2 — pre-emptively give the page title or ID here if known).

B. CONFLUENCE
   B1. Save the generated BRD to Confluence? (yes / no, default: yes)
   B2. If yes — Confluence space name or key (default: first space returned by getConfluenceSpaces — name it explicitly if you have a preference).

C. JIRA
   C1. Target Jira project key for Epics/Stories (default: <PROJECT-KEY from MEMORY if known>).
   C2. Auto-confirm Jira issue creation? (yes / no, default: yes — required for autonomous mode).

D. FEATURE-DEV (full-stack code)
   D1. Output project folder (absolute path, default: ~/projects/<project-name>).
   D2. Frontend port (default 5173) and backend port (default 3001).
   D3. Theme (light fintech / dark fintech, default: light).
   D4. Auto-run npm install + start both servers after generation? (yes / no, default: yes).

E. TEST CASES (test-case-generator → Jira/Xray)
   E1. Which test case types? Comma-separated subset of:
       functional, non-functional, boundary-negative, system-architecture, gherkin
       Or `all` (default: all).
   E2. Auto-confirm Jira Test issue creation, even if the project requires a Sub-task fallback? (yes / no, default: yes).

F. TEST SCRIPTS (test-script-generator → Playwright + git)
   F1. Output folder for the Playwright project (default: ~/projects/<project-name>-playwright-tests).
   F2. Base URL for the Playwright tests (default: http://localhost:<frontend-port> from D2).
   F3. Browsers (subset of chromium, firefox, webkit — default: chromium).
   F4. Git remote URL to push the test scripts to (default: none — local commit only).
   F5. Initial branch name (default: main).

Type ALL-DEFAULTS to accept every default for items where you have not given a value.
```

Wait for the user's response. Parse it into the run-context object.

### 0.2 — Ingest file inputs

If item A includes any **file paths**, ingest every file **before** advancing to step 0.3. If the user references an attachment but no path was given (e.g. "I uploaded the PDF"), ask once for the absolute path and wait — this is a permitted second prompt within Phase 0.

| File type | How to ingest |
|-----------|---------------|
| `.txt`, `.md`, any plain text | `Read` tool — content returned as-is. |
| `.pdf` | `Read` tool. For PDFs > 10 pages, paginate via the `pages` parameter (max 20 pages per call) until fully read. |
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | `Read` tool — image is presented visually. Extract visible text, wireframes, flow charts, screenshots, sticky notes, and annotations into structured input. |
| `.docx` | Convert first, then `Read` the converted file. Try in order:<br>1. `textutil -convert txt "<path>" -output /tmp/_sdlc_input_<n>.txt` (macOS, built-in)<br>2. `pandoc "<path>" -t plain -o /tmp/_sdlc_input_<n>.txt` |
| `.doc` (legacy Word) | Same conversion path as `.docx`. |

If a file path is invalid, unreadable, or conversion fails, stop and report the specific error to the user before continuing. Do not silently skip files.

If the user typed **SKIP-BRD**, mark Phase 1 as skipped in the run-context and locate the BRD in Confluence now (still within Phase 0):
- Call `atlassianUserInfo` → `getAccessibleAtlassianResources` → `getConfluenceSpaces`.
- Search via `searchConfluenceUsingCql`: `title ~ "BRD" AND type = page ORDER BY lastmodified DESC`.
- If exactly one BRD page is found, take it. If multiple are found, pick the one whose title contains the project name extracted from item C1; if still ambiguous, fall back to most-recently-modified. Record the selection in the run-context — do *not* re-prompt during Phase 2.

### 0.3 — Resolve and confirm the run config

Print a fully-resolved run-config block to the user, defaults filled in:

```
RESOLVED RUN CONFIG
─────────────────────────────────────────────
Project name:       <inferred from input>
Phase 1 — BRD
  Source:           <pasted text + N files> | <skip — reuse Confluence page X>
  Confluence save:  yes → space "<name>" | no
Phase 2 — User Stories
  Jira project:     <KEY>
  Auto-create:      yes
Phase 3 — Feature Dev
  Output folder:    <path>
  Ports:            frontend <fp> / backend <bp>
  Theme:            light fintech | dark fintech
  Auto-run servers: yes | no
Phase 4 — Test Cases
  Types:            functional, non-functional, boundary-negative, system-architecture, gherkin
  Auto-create:      yes
Phase 5 — Test Scripts (Playwright)
  Output folder:    <path>
  Base URL:         http://localhost:<fp>
  Browsers:         chromium
  Git remote:       <url> | (none — local commit only)
  Initial branch:   main
─────────────────────────────────────────────
```

Then print the **input digest** (one-paragraph summary of every ingested file and pasted block) so the user can spot misreads.

Ask exactly one final question:

> "I will run all five phases autonomously with the config above. Reply `go` to start, or list any changes (e.g. `change Jira project to FOO; skip Phase 5`)."

Apply any user edits, re-print the resolved config, and wait again — but only if the user requested changes. Once the user replies `go`, do **not** prompt again until the entire pipeline is complete or an unrecoverable error occurs.

---

## Phase 1 — BRD Generation (sdlc-planning)

If the run-context marks Phase 1 as **skipped**, fetch the chosen Confluence BRD (`getConfluencePage` with `contentFormat: "markdown"`), store the markdown body in the run-context as `brd_markdown`, print the STATUS block, and continue to Phase 2 without any further prompt.

Otherwise generate the BRD now. Combine every ingested input (pasted text + file contents) into the unified driver.

Produce a complete Business Requirements Document in markdown, following these rules:

- Frame requirements as outcomes traceable to epics/stories (Agile).
- Extract and infer as much as possible from the user's input.
- For any section where the input is thin, still populate it using best judgement, then append immediately below:

  > ⚠️ **AI Generated — Needs Review**
  > This section was inferred by AI and has not been validated by a stakeholder. Please review and update before sign-off.

- Never skip a section. Every section must appear.
- Write in clear, professional business language.
- Use tables where they add clarity (RACI, risks, glossary).

Produce the BRD in this exact section order:

```
# Business Requirements Document
**Project:** [name]
**Version:** 1.0 — Draft
**Date:** [today]
**Prepared by:** [blank or inferred]
**Status:** Draft

### 1. Executive Summary
### 2. Background & Current State
### 3. Business Objectives & Success Criteria   (table: # | Objective | Success Criteria)
### 4. Scope
  #### 4.1 In Scope
  #### 4.2 Out of Scope
### 5. Business Requirements    (BR-1, BR-2 … numbered, testable)
### 6. Non-Functional Requirements    (NFR-1, NFR-2 …)
### 7. Assumptions
### 8. Constraints
### 9. Risks    (table: Risk ID | Description | Likelihood | Impact | Mitigation — min 5 rows)
### 10. RACI Matrix    (table)
### 11. Glossary & Definitions    (table)
```

If the user opted into Confluence save (item B1 = yes):
- `atlassianUserInfo` → `getAccessibleAtlassianResources` → `getConfluenceSpaces` to resolve the chosen space.
- `createConfluencePage` with `contentFormat: "markdown"`. Record the page ID and URL into the run-context.

Store the BRD markdown in the run-context as `brd_markdown` for Phase 2. Print Phase 1 STATUS (`done`). **Do not** ask for confirmation — move directly into Phase 2.

---

## Phase 2 — User Stories (user-stories)

### 2.1 — Extract from the BRD

Parse `brd_markdown` to pull out:
- Initiative / feature name
- Personas / roles
- Functional requirements (BR-n items)
- Non-functional requirements
- Scope and constraints

### 2.2 — Confirm the Jira project metadata

The Jira project key was supplied in Phase 0 (C1). Verify with `getJiraProjectIssueTypesMetadata` that it supports both **Epic** and **Story** issue types. If either is missing, halt with a clear error — do not silently substitute. (This is one of the deliberate non-autonomous failure points.)

### 2.3 — Generate INVEST user stories

Derive all Epics and User Stories from the BRD. Every story must pass all six INVEST checks:

| Principle | Check |
|-----------|-------|
| **I**ndependent | Can be developed without depending on another unfinished story? |
| **N**egotiable | Focused on *what*, not *how*? |
| **V**aluable | Delivers direct value to a named user or stakeholder? |
| **E**stimable | Clear enough to size? |
| **S**mall | Completable in one sprint (≤ 8 pts)? |
| **T**estable | Has ≥ 3 Given/When/Then acceptance criteria? |

Story format used internally and in Jira description:

> **Story statement:**
> As a **[persona]**, I want **[goal]**, so that **[measurable benefit]**.
>
> **Acceptance Criteria**
> - Given [context], when [action], then [outcome]
> - Given [context], when [action], then [outcome]
> - Given [context], when [action], then [outcome]
>
> **Story point estimate:** [1/2/3/5/8] — one-line rationale
> **Priority:** P1 / P2 / P3 / P4

Only flag INVEST violations (⚠️) when a principle is not met.

### 2.4 — Create in Jira (no checkpoint)

The user pre-authorized creation in Phase 0 (C2 = yes). Print the compact table for visibility, then proceed immediately.

| # | Type | Summary | Epic | Points | Priority |
|---|------|---------|------|--------|----------|

For each Epic call `createJiraIssue` with `issueTypeName: "Epic"`.
For each Story call `createJiraIssue` with:
- `issueTypeName: "Story"`
- `parent`: the Epic issue key
- `additional_fields`: `{"priority": {"name": "..."}, "customfield_10016": [n]}` (use `customfield_10016` for story points on Jira Cloud — recorded in `MEMORY.md`).

Description as clean markdown with blank lines between AC items.

Create stories sequentially within each epic to preserve the parent reference. Record every created issue key into the run-context (`epic_keys`, `story_keys`). Print Phase 2 STATUS.

---

## Phase 3 — Feature Development (feature-dev)

### 3.1 — Fetch story details

For each epic in `epic_keys`, `searchJiraIssuesUsingJql`:
```
project = [KEY] AND issuetype = Story AND parent = [EPIC-KEY] ORDER BY created ASC
```

For each story, `getJiraIssue` to fetch full description and acceptance criteria.

Use the output folder, ports, and theme from the run-context (Phase 0 D1–D3). Do not re-ask.

### 3.2 — Plan and generate

Derive UI screens, API endpoints, data models, auth flows, and key interactions from the stories. Print the planned directory structure for visibility, then generate every file using the **Write** tool in the order specified in the `feature-dev` SKILL:

1. Both `package.json` files
2. Config files (`vite.config.js`, `tailwind.config.js`, `.env.example`)
3. Backend entry (`app.js`, `server.js`)
4. Backend middleware (error handler, validate, auth)
5. Backend models → controllers → routes (one epic domain at a time)
6. Frontend entry (`main.jsx`, `App.jsx`, `tailwind.config.js`)
7. Frontend context and services
8. Frontend components (shared first, then page-specific)
9. Frontend pages
10. Root `README.md`

Design tokens follow the theme chosen in D3:
- **Light fintech:** bg `#F1F5F9`, surfaces `#FFFFFF`, borders `#E2E8F0`, primary `#1D4ED8`, accent `#4F46E5`, success `#10B981`.
- **Dark fintech:** bg `#0A0F1E`, accent `#3B82F6`, success `#10B981`, warning `#F59E0B`, error `#F43F5E`; CRED-style glass-morphism cards.

Code quality rules (apply uniformly):
- Functional components + hooks only — no class components
- All gradients via inline `style={}` — never dynamic Tailwind class strings
- All magic strings in `constants.js`
- Tailwind for static styling; no inline styles elsewhere
- Every form has client-side validation matching the story's AC
- `aria-label` on every interactive element

### 3.3 — Init git and (optionally) start servers

Always initialise git in the output folder:
```
git init && git add . && git commit -m "feat: <project-name> — generated from Jira <EPIC-KEYS>"
```

If D4 = yes, run `npm install` in both `frontend/` and `backend/` (sequentially per folder), then start:
- Backend: `node server.js` in the backend folder, **background**.
- Frontend: `npm run dev` in the frontend folder, **background**.

Verify the backend responds (poll `http://localhost:<bp>/health` or `/` once with a short timeout) before continuing. If the backend doesn't come up cleanly, log the error and continue to Phase 4 — do not block the pipeline on a dev-server hiccup. The user can restart later from the README instructions.

Print Phase 3 STATUS.

---

## Phase 4 — Test Cases (test-case-generator)

The user pre-selected test case types in Phase 0 (E1) and pre-authorized creation (E2).

### 4.1 — Resolve target issue type

Call `getJiraProjectIssueTypesMetadata` for the Jira project (cache the result for the whole phase). Pick in order:
1. `Test` or `Test Case` (the Xray Test type if installed).
2. Else `Sub-task`, with `parent` set to the source story key on every issue.
3. Else halt with a clear error — this is a deliberate non-autonomous failure point because falling back to a generic `Task` would pollute the project.

### 4.2 — Generate test cases per story

For every story in `story_keys`, generate test cases of every type selected in E1. Use the templates defined in the `test-case-generator` SKILL verbatim:

- `functional` — one or more TCs per AC, IDs `TC-<KEY>-F<n>`
- `non-functional` — performance / security / usability / accessibility / scalability / reliability, with measurable targets, IDs `TC-<KEY>-NF<n>`
- `boundary-negative` — boundary + invalid + injection cases, IDs `TC-<KEY>-B<n>`
- `system-architecture` — cross-component flows and failure modes, IDs `TC-<KEY>-SA<n>`
- `gherkin` — at minimum one positive and one boundary `Scenario` per AC, wrapped in a ```gherkin fenced block so Phase 5 can parse it back out

Every TC body must include `Linked story: <KEY>` and reference the AC text or number.

### 4.3 — Write to Jira

For every generated TC:
- `createJiraIssue` with the resolved issue type, the TC `Title` as `summary`, the full TC body as `description` (markdown / ADF preserving Gherkin and tables), priority copied from the source story, and `components` + `labels` propagated. Always add `label: test-case` and `label: tc-<type>` (e.g. `tc-functional`, `tc-gherkin`).
- For `Sub-task` mode, set the `parent` field to the source story key and skip the redundant link.
- For `Test` / `Test Case` mode, also `createIssueLink` with `type=Tests` from the new TC to the source story.

Idempotency check: before each `createJiraIssue`, `searchJiraIssuesUsingJql` for an existing issue with the same `summary` already linked to (or parented under) the source story; if found, skip that TC and record it as "deduplicated" in the run-context. This keeps re-runs of the pipeline safe.

Record every created test key into the run-context (`test_keys`, grouped by source story). Print Phase 4 STATUS, including a per-story count and a tally of deduplicated skips.

---

## Phase 5 — Test Scripts (test-script-generator)

The user pre-supplied output folder, base URL, browsers, remote, and branch in Phase 0 (F1–F5).

### 5.1 — Pull test issue bodies back from Jira

For every story key in the run-context, look up every linked Test issue (whether stored as a `Tests` link or as a `Sub-task` parent) using `getJiraIssue` for each `test_keys` entry. Capture for each: `key`, `summary`, `priority`, `labels`, `description`, plus any Xray Cucumber custom field if it is returned by the API. Do not invent field IDs.

### 5.2 — Classify each test

For each test:
- If a ```gherkin block is present in the description (or in the Xray Cucumber field) → map each `Scenario` to a Playwright `test()` block, `Background` → `test.beforeEach`, `Scenario Outline` + `Examples` → `for…of` data-driven loop (with the rows exported to `data/<story-key>.data.js`).
- Else if numbered "Test steps:" are present → emit one Playwright action per step with a `// Step <n>: <original text>` comment.
- Else if it is `non-functional` (label `tc-non-functional`) → emit a stub spec that wires `@axe-core/playwright` (accessibility), `page.request` timing (performance), or a security-probe TODO, marked `test.fixme()` and tagged with the source TC key. Surface in the final report.
- Else → emit `test.fixme()` with a comment pointing back to the Jira key and a note that the source TC lacked actionable steps.

### 5.3 — Generate the Playwright project

Output folder layout (write every file via the **Write** tool):

```
<output-folder>/
├── package.json
├── playwright.config.js
├── .gitignore
├── README.md
├── tests/
│   └── <story-key>.spec.js          # one spec per source story
├── pages/                            # POM — one file per UI surface referenced
│   ├── BasePage.js
│   └── <Surface>Page.js
├── fixtures/
│   └── test-fixtures.js
├── data/
│   └── <story-key>.data.js
└── utils/
    ├── selectors.js
    └── api.js
```

`package.json` declares `@playwright/test` and `@axe-core/playwright` as `devDependencies`, with scripts `test`, `test:headed`, `test:ui`, `report`.

`playwright.config.js`: `testDir: './tests'`, `fullyParallel: true`, `retries: process.env.CI ? 2 : 0`, `reporter: [['list'], ['html', { open: 'never' }]]`, `use.baseURL` from F2, `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, one `projects` entry per browser from F3 using `devices['Desktop <Browser>']`.

Every spec file starts with a header comment block listing source story key + Test issue keys. Every `test()` ends with at least one `expect(...)` (or is `test.fixme()`). Selectors prefer `getByRole` / `getByLabel` / `getByTestId`; only emit a CSS / `data-testid` value if it is grounded in the source TC, otherwise add a TODO comment.

`README.md` includes a **traceability table** mapping every spec file → source story → list of Test issue keys it implements.

### 5.4 — Initialise git automatically

In the Playwright output folder:
1. If the folder is not already a git repo: `git init -b <branch>` (fall back to `git init` then `git checkout -b <branch>` on older git).
2. `git add .`
3. If `git config user.email` is empty, configure it for this repo only with the user's email from `MEMORY.md` (`abhinav.krishna@wipro.com`) — never globally.
4. `git commit -m "test: initial Playwright scaffold from <PROJECT-KEY> test cases"` with a HEREDOC body listing source story keys and Test issue keys covered.
5. If F4 supplied a remote URL: `git remote add origin <url>` then `git push -u origin <branch>`. Never `git push --force`. If the push fails (auth, missing repo, conflict), log the error and continue — the local commit is still safe.
6. If F4 was empty, finish at the local commit and print the suggestion for adding a remote later.

If the folder already exists and is already a git repo, do **not** reinitialise it. Detect any existing spec files for the same story and add them as new commits rather than overwriting blindly. If pre-existing untracked files are present in the target folder, list them in the final report — but do not abort.

Print Phase 5 STATUS.

---

## Pipeline complete — final summary

After Phase 5, print:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SDLC PIPELINE COMPLETE ✅
  Phase 1 — BRD:           ✅ done | skipped
  Phase 2 — User Stories:  ✅ done
  Phase 3 — Feature Dev:   ✅ done
  Phase 4 — Test Cases:    ✅ done
  Phase 5 — Test Scripts:  ✅ done
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 BRD
  Title:    <title>
  Location: <Confluence URL | "held in session">

📋 Jira (<KEY>)
  Epics:    <EPIC-KEYS>
  Stories:  <STORY-KEYS>
  Tests:    <TEST-KEYS>  (deduplicated: <n>)

💻 Application
  Path:     <absolute path>
  Frontend: http://localhost:<fp>   [running | not started]
  Backend:  http://localhost:<bp>   [running | not started]
  Pages:    <n> screens
  Endpoints:
    <list>

🧪 Playwright tests
  Path:     <absolute path>
  Specs:    <n> spec files / <m> test() blocks
  Skipped:  <list with reasons — e.g. PROJ-510 (non-functional: needs perf harness)>
  Git:      branch <branch> @ <short-sha>
  Remote:   <url> | (none — local only)

🔗 Traceability
  tests/proj-123.spec.js  ← PROJ-123  (Tests: PROJ-501, PROJ-502)
  ...
```

Ask: "All five phases done. Anything to refine — story tweaks, more screens, additional test types, or another project?"

---

## Guardrails (apply across all phases)

- **Autonomous after `go`.** Once the user replies `go` in Phase 0, no further prompts unless an external system fails in a way the orchestrator cannot resolve. Status prints are one-way — they never wait for input.
- **Front-loaded confirmation only.** Destructive / external operations (Confluence writes, Jira creates, git pushes) are pre-authorized in Phase 0. Do not bypass that authorization — if Phase 0 did not cover a particular operation (e.g. force-push), do not perform it autonomously; raise it instead.
- **Hard stops, not silent skips.** Halt with a clear error for: missing Epic/Story issue type, missing Test issue type with no acceptable fallback, invalid file path in Phase 0.2, BRD source not found when Phase 1 was skipped. Print what failed and what state was already persisted.
- **Idempotency across re-runs.** Skip Jira issues whose `summary` already exists for the same parent/story. Skip git init if the target folder is already a repo. Record skips in the final report.
- **Traceability is mandatory.** Every Phase 4 TC carries `Linked story: <KEY>`; every Phase 5 `test()` block carries a header comment with the source story key + Test issue key; the Playwright README's traceability table lists every spec.
- **Identity respect for git.** Use existing `git config user.email` if set; only fall back to the user's `MEMORY.md` email (`abhinav.krishna@wipro.com`) and only scoped to the repo, never global.
- **No fabricated test logic.** If a Test issue has neither Gherkin nor numbered steps, emit `test.fixme()` with the source key — never invent flows.
- **No remote without consent.** Phase 5 pushes only when the user supplied a remote URL in Phase 0 (F4). Empty remote = local commit only, full stop.
- **No `--force` anywhere.** No `git push --force`, no `git reset --hard`, no `rm -rf` of the user's output folders.
