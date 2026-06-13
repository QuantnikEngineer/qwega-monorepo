---
name: sdlc-orchestrator
description: End-to-end autonomous SDLC pipeline. Phase 0 starts with a hard-gate config-check (verifies git remotes, Atlassian Jira + Confluence MCPs, and the Quantnik service itself) — if config-check returns FAIL, the orchestrator aborts before Phase 1 and prints the failure checklist instead of burning minutes against a broken integration. After that gate passes, it executes ELEVEN phases in sequence — BRD generation (sdlc-planning) → INVEST user stories in Jira (user-stories) → full-stack code scaffold (feature-dev) → vulnerability scan + auto-fix + Confluence report (vulnerability-check) → tech-debt scan + auto-fix + Confluence report (tech-debt-check) → Jira/Xray test cases (test-case-generator) → Playwright test scripts committed to git (test-script-generator) → boot (npm install both folders + start frontend & backend dev servers) → execute Playwright suite against the running app, log Jira bugs for failures, ask user which to auto-fix, publish execution report to Confluence (test-script-executor) → publish a production build under `<PUBLIC_BASE_URL>/<project-slug>` (deploy-to-platform) → run a deploy-time sanity check (reachability + API probes + Jira story coverage + performance) and publish the report to Confluence (sanity-check). The eighth phase deliberately runs AFTER the patches from phases 4–5 so the install picks up bumped dep versions; the ninth tests the already-patched + already-running app; the tenth ships the same patched code as a production build; the eleventh runs LAST against the production URL so the published verdict reflects what stakeholders will actually see. Every question the pipeline could need is asked upfront in one consolidated questionnaire (Phase 0); after the user confirms the run config, the orchestrator runs autonomously except for ONE deliberate prompt mid-Phase-9 (which failures to auto-fix).
---

> **Hard rule for every Atlassian write in this pipeline (Phases 1, 2, 4, 5, 6, 7):**
> Before ANY write, `Read` `.claude/quantnik.json` at the project cwd. If it exists, use its values as the **only** allowed targets:
> - Every Confluence page **must** be created in `atlassian.confluenceSpaceKey` (or `confluenceSpaceId`). Never the user's personal space, never the first space returned by `getConfluenceSpaces`.
> - Every Jira issue **must** be created in `atlassian.jiraProjectKey`. Never an inferred key from `getVisibleJiraProjects`, MEMORY.md, or recent chat.
> - If a phase tries to resolve a target some other way and disagrees with quantnik.json, **halt that phase with a clear error** rather than writing to the wrong place.
>
> Cache the resolved space + Jira key into the run-context (`run-context.confluenceSpaceKey`, `run-context.confluenceSpaceId`, `run-context.jiraProjectKey`) at the start of Phase 0 and reuse for every subsequent Atlassian call.

When this skill is invoked, the entire pipeline runs in two acts:

1. **Phase 0 — Intake.** Collect *every* input the eleven downstream phases need, in one consolidated questionnaire. Confirm the resolved run config once. This is the **only** time the orchestrator stops for user input under happy-path execution **except** for the deliberate Phase 9 auto-fix-selection prompt (see below).
2. **Phases 1–11 — Autonomous execution.** Run BRD → User Stories → Feature Dev (scaffold only, no install) → Vulnerability Check → Tech Debt Check → Test Cases → Test Scripts → Boot (install + start servers) → Test Execution (run Playwright suite, log Jira bugs for failures, prompt once for auto-fix selection, publish report) → Deployment (build production bundle, register with Quantnik's deploy route, surface a public URL like `<PUBLIC_BASE_URL>/<slug>`) → Sanity Check (probe the live public URL end-to-end, map probes to Jira stories, publish Confluence report). Print a STATUS block after each phase but **do not wait for confirmation between phases**. The user only sees a prompt again if (a) an external system fails irrecoverably, (b) the Phase 9 auto-fix-selection prompt fires (a deliberately deferred choice — pre-authorized in Phase 0 by virtue of opting into the orchestrator), or (c) the run is complete.

**Status tracking is server-authoritative (mandatory).** The quantnik chat panel reads phase state from `GET /api/phases/<projectId>` — NOT from chat text. Every phase transition must be **POSTed** to the server so the panel stays accurate even when text emissions are missed or malformed. The skill must call:

```bash
# At the START of every phase (right before any phase-specific work):
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":N,"status":"running"}'

# At the END of every phase (success | skipped | failed):
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":N,"status":"done","note":"optional one-line summary"}'

# At the VERY START of the pipeline (right after Phase 0.0 config-check):
curl -s -X DELETE http://localhost:6060/api/phases/<projectId>
# wipes any prior run's state so the panel starts clean
```

`<projectId>` comes from `quantnik.json`'s `project.id`. Treat each curl call as fire-and-forget: if it fails the chat panel will degrade but the orchestrator still runs.

**Live status emission (still required for chat readability).** In *addition* to the POST, print a bare line in chat so users following along see the transition without inspecting the panel:

- Start of phase: bare line `Phase 3 — Feature Dev: running`
- End of phase: bare line `Phase 3 — Feature Dev: done` (or `failed`, `skipped`)
- Print the full STATUS block as a recap at phase boundaries.

The server POST is what makes the panel correct. The chat lines are belt-and-suspenders — the panel will still show server-side state even when the chat lines are skipped.

Maintain a shared run-context object across all phases and print it as a status header after each phase:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SDLC PIPELINE STATUS
  Phase 1  — BRD:               [pending | running | done | skipped | failed]
  Phase 2  — User Stories:      [...]
  Phase 3  — Feature Dev:       [...]
  Phase 4  — Vulnerability:     [...]
  Phase 5  — Tech Debt:         [...]
  Phase 6  — Test Cases:        [...]
  Phase 7  — Test Scripts:      [...]
  Phase 8  — Boot:              [...]
  Phase 9  — Test Execution:    [...]
  Phase 10 — Deployment:        [...]
  Phase 11 — Sanity Checks:      [...]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Phase 0 — Intake (the only interactive phase)

### 0.0 — Pre-flight: run `config-check` FIRST (hard gate)

**Before anything else** — before discovery, before the questionnaire, before reading the BRD — run the `config-check` skill inline. The orchestrator is heavily dependent on the Atlassian MCPs (Phases 1, 2, 4, 5, 6, 9, 11 write to Confluence + Jira), a working git remote (Phases 3 + 7 push branches), and the quantnik backend itself (Phase 10 deployment registers via the local API). Starting the pipeline against a broken integration just burns minutes and ends with a half-published BRD and an angry user.

Procedure:

1. Read `~/.claude/skills/config-check/SKILL.md` and run its full 5-step flow inline (steps 0–5 — quantnik.json read, git ls-remote per repo, Jira `/myself` + project metadata, Confluence space + page-list, quantnik self-check). All checks are read-only.
2. Emit the standard `config-check` final report block (`CONFIG CHECK COMPLETE — <verdict>`) to chat so the user sees exactly what was tested.
3. Branch on the verdict:
   - **`PASS`** — proceed to 0.1 immediately. No prompt, no confirmation.
   - **`DEGRADED`** — git-side failure only (Atlassian + service self-check passed). Emit a one-line warning (`⚠ config-check verdict: DEGRADED — git remotes have issues but Atlassian + service look healthy. Continuing; Phase 3/7 git pushes may fail.`) and proceed. The user pre-authorized this by invoking the orchestrator.
   - **`FAIL`** — **halt the entire pipeline.** Mark every phase as `skipped (config-check failed)` in the STATUS block and print:
     ```
     ❌ Orchestrator aborted — config-check returned FAIL.
     Phases 1–11 will not run. Fix the items above and re-run /sdlc-orchestrator
     when /config-check returns PASS or DEGRADED.
     ```
     Do not move to 0.0a discovery. Do not show the questionnaire. The user must rerun the orchestrator after fixing the underlying issue — there's no auto-retry, because the failure modes (revoked tokens, wrong project key, broken Jira project) all need human intervention outside the SDK.

Record `config_check_verdict` and `config_check_failures` (the numbered checklist) in the run-context so the final summary can cite them later.

### 0.0a — Discover what's already in the project (before asking anything)

Before showing the questionnaire, **silently scan the quantnik project state** so the questionnaire can pre-fill defaults and the user doesn't have to repeat themselves:

1. **Project sidecar config** — **`Read` `.claude/quantnik.json` at the project cwd FIRST.** This file is written by quantnik every time the user updates the project's Atlassian or LLM scope in the dashboard / settings. It is the **authoritative source** for:
   - `atlassian.jiraProjectKey` → default for questionnaire item **C1**.
   - `atlassian.confluenceSpaceKey` / `atlassian.confluenceSpaceId` → default for item **B2**.
   - `atlassian.labels` → use as default labels on every created issue.
   - `atlassian.siteName` / `atlassian.siteUrl` → use when building browse URLs in summaries.
   - `llm.provider` / `llm.model` → already applied by the SDK at session start; surface in the resolved config block.

   **Never override these defaults with values inferred from `getVisibleJiraProjects`, MEMORY.md, or recent chat history.** If `quantnik.json` says `WC`, use `WC` — don't pick `WSKB` just because a recent run mentioned it. If the file is absent, fall back to MEMORY.md / chat-history defaults as before.

2. **Uploaded files** — `Glob` the project's `uploads/` directory (it's a sibling of the cwd; from the agent's cwd, run `Glob` with pattern `uploads/*` and also `../uploads/*` in case of layout variation). Record every match as a candidate BRD input file. **Treat every file in `uploads/` as Phase 1 input by default** — the user already uploaded them via the Files tab; they should not have to repeat the paths.

3. **Configured repos — discover, classify, and propose role assignments.** List `additionalDirectories` from the session-init message. For each, gather:

   - `path` (the absolute directory)
   - `remote` — `Bash` `git -C "<path>" remote get-url origin 2>/dev/null`
   - `branch` — `Bash` `git -C "<path>" rev-parse --abbrev-ref HEAD 2>/dev/null`
   - **Tech inspection** — `Glob` and `Read` the top-level manifests to infer the stack. Cheap, file-existence-based detection (no parsing required for the initial inference):

     | Indicator file at repo root | Inferred tech |
     |-----------------------------|---------------|
     | `package.json` with `react` / `react-dom` in deps | Frontend = React |
     | `package.json` with `next` in deps | Frontend = Next.js |
     | `package.json` with `vue` in deps | Frontend = Vue |
     | `package.json` with `svelte` in deps | Frontend = Svelte |
     | `package.json` with `@angular/core` in deps | Frontend = Angular |
     | `package.json` with `express` / `fastify` / `koa` / `hapi` in deps (no React/Next) | Backend = Node/Express (or detected variant) |
     | `package.json` with `@nestjs/core` | Backend = NestJS |
     | `requirements.txt` / `pyproject.toml` containing `fastapi` | Backend = FastAPI |
     | `requirements.txt` / `pyproject.toml` containing `django` | Backend = Django |
     | `requirements.txt` / `pyproject.toml` containing `flask` | Backend = Flask |
     | `pom.xml` or `build.gradle` with `spring-boot-starter` | Backend = Spring Boot |
     | `*.csproj` / `*.sln` | Backend = .NET |
     | `go.mod` with `gin-gonic/gin` / `labstack/echo` / `gofiber/fiber` | Backend = Go (variant) |
     | Both frontend and backend signals present | `role: fullstack` |

   Read each manifest only once and cache the parsed deps. Tag every repo with:
   ```
   { path, remote, branch, role: "frontend" | "backend" | "fullstack" | "unknown",
     tech: { frontend: [...], backend: [...] } }
   ```

   **Propose role assignments** based on what's detected:
   - If exactly one repo is `frontend` and one is `backend` → suggest that split.
   - If a single repo is `fullstack` → suggest it for both roles.
   - If everything is `unknown` → suggest scaffolding fresh into the default output folder (Phase 0 item D1).
   - If multiple repos compete for the same role → list them all and let the questionnaire's D0 item pick.

4. **Domain detection (for the default brand-style proposal).** Scan the ingested input (uploads + pasted text + any chat-history context the user just typed) for domain keywords. Take the **first match** in this priority list as the inferred domain:

   | Domain | Keyword triggers (case-insensitive substring) |
   |--------|-----------------------------------------------|
   | banking | `bank`, `loan`, `mortgage`, `savings account`, `current account`, `IFSC`, `SWIFT`, `branch banking` |
   | fintech-payments | `payment`, `wallet`, `UPI`, `card issuing`, `merchant`, `payout`, `checkout` |
   | insurance | `insurance`, `policy`, `claim`, `premium`, `underwriting`, `actuarial` |
   | healthcare | `patient`, `clinic`, `hospital`, `EHR`, `EMR`, `prescription`, `appointment` (medical context) |
   | ecommerce | `cart`, `checkout`, `SKU`, `inventory`, `storefront`, `marketplace` |
   | food-delivery | `food delivery`, `restaurant menu`, `rider`, `kitchen`, `dispatch` |
   | travel | `flight`, `hotel booking`, `itinerary`, `PNR`, `boarding pass` |
   | streaming | `stream`, `episode`, `playlist`, `watchlist`, `subscription tier` |
   | education-lms | `course`, `lesson`, `quiz`, `gradebook`, `LMS`, `cohort` |
   | crypto | `wallet address`, `blockchain`, `defi`, `stablecoin`, `swap` |
   | social | `feed`, `follow`, `like`, `comment`, `notifications`, `messaging` |
   | saas-b2b | `dashboard`, `tenant`, `RBAC`, `API key`, `webhook`, `usage-based pricing` |

   Record the inferred domain in the run-context as `inferred_domain` (default to `saas-b2b` if nothing matches). It feeds the **brand-style** default in the questionnaire (see Brand-style catalog at the end of this skill).

Do **not** ask the user about anything from items 1–4 directly. Just pre-fill the defaults — and when `quantnik.json` exists, treat the values inside it as **non-overrideable from inferred sources** (the user can still override them by explicitly typing a different value in the questionnaire).

### 0.1 — Ask everything in one consolidated questionnaire

Present this exact block, pre-filled with the discoveries from 0.0a. Each item below has its discovered default in `<…>` — surface it inline so the user can confirm at a glance. Use the **AskUserQuestion** tool if appropriate; otherwise post the block as plain text and wait for one consolidated answer.

```
SDLC PIPELINE — RUN CONFIG
The pipeline runs end-to-end without further questions after this. Defaults are filled in from
the quantnik project state — confirm or override. Reply ALL-DEFAULTS to accept everything as-is.

A. PROJECT INPUT (for BRD)
   Discovered uploaded files in uploads/:  <list — auto-ingested as input>
   • Paste any extra transcript / call notes / idea below, OR
   • Type SKIP-BRD to reuse an existing Confluence BRD, OR
   • Leave blank to use only the discovered uploads.

B. CONFLUENCE
   B1. Save the generated BRD to Confluence? (default: yes)
   B2. Confluence space (default: <project's confluence_space_id from atlassian config, else first personal space>).

C. JIRA
   C1. Target Jira project key for Epics/Stories (default: <project's jira_project_key, else most-recent-used>).
   C2. Auto-confirm Jira issue creation? (default: yes — required for autonomous mode).

D. FEATURE-DEV (full-stack code)
   Discovered configured repos (from Repos tab + additionalDirectories):
     <table — for each repo: path · remote · branch · role · tech>

   D0. Repo assignment (where the generated code goes).
       D0a. Frontend repo: <suggested = first repo with role ∈ {frontend, fullstack},
                            else SCAFFOLD-NEW at D1/frontend>
       D0b. Backend repo:  <suggested = first repo with role ∈ {backend, fullstack},
                            else SCAFFOLD-NEW at D1/backend>
       (Reply with the repo's path or `SCAFFOLD-NEW` per slot. A single fullstack repo
        can be used for both. If a repo is assigned, the orchestrator works on a fresh
        feature branch off its current HEAD and never force-pushes.)

   D1. Output project folder for SCAFFOLD-NEW slots (default: ~/projects/<project-name>).
       Frontend lives at <folder>/frontend, backend at <folder>/backend.

   D2. Frontend technology (default: <detected-from-assigned-frontend-repo, else React 18 + Vite + Tailwind>).
       Options: react-vite-tailwind | nextjs-tailwind | vue3-vite | svelte-kit | angular
       (Forced to the existing repo's stack when D0a points to an existing repo —
        we never replace a repo's framework.)

   D3. Backend technology (default: <detected-from-assigned-backend-repo, else Node + Express + Prisma>).
       Options: node-express | nestjs | fastapi | django-drf | flask | spring-boot | dotnet-minimal-api | go-gin
       (Same forced-to-existing rule as D2.)

   D4. Frontend port and backend port.
       **Pick two random free ports each run** — do NOT default to the same
       5173/3001 every time. Use `Bash` once before showing the questionnaire:
         `node -e "console.log(JSON.stringify([Math.floor(4000+Math.random()*1999), Math.floor(4000+Math.random()*1999)]))"`
       then verify each is free with
         POSIX: `ss -ltn | grep ':<port> ' || lsof -iTCP:<port> -sTCP:LISTEN`
         Windows: `netstat -ano | findstr :<port>`
       — re-roll on hit. Surface the two confirmed-free numbers
       inline so the user sees them as the proposed defaults; they can still
       override with explicit values. Randomizing avoids collisions when
       multiple orchestrator runs or older `npm run dev` processes are still
       listening, and aligns with how Phase 10's deployment route picks its
       own random port from the 7000–7999 range.

   D5. Brand / style direction (default: <auto from inferred_domain — see Brand-style catalog>).
       Examples surfaced inline based on the detected domain:
         banking      → US Bank · HDFC Bank · Chase · Bank of America
         fintech      → Stripe · Revolut · CRED · Paytm
         healthcare   → Mayo Clinic · Cleveland Clinic · Practo
         ecommerce    → Amazon · Flipkart · Shopify storefronts
         travel       → Booking.com · Airbnb · MakeMyTrip
         saas-b2b     → Linear · Notion · Stripe Dashboard
       Reply with one brand name to copy its visual language, OR `neutral-light` /
       `neutral-dark` for a plain fintech theme, OR paste a hex palette / Figma URL.

   D6. Auto-run install + start both servers after generation? (default: yes).

   D7. Auto-deploy to `<PUBLIC_BASE_URL>/<slug>` after tests? (default: yes).
       Builds a production bundle with base='/<slug>/', writes it into quantnik's
       deployments root, spawns the backend on a quantnik-allocated port, and
       prints the public URL. Slug = sanitised project name. Skip with NO if
       this run shouldn't be exposed publicly.

   D8. Auto-run sanity check after deploy? (default: yes).
       Probes the public URL end-to-end, maps probes to Jira stories,
       publishes a Confluence report. Skipped automatically if D7=no (nothing
       deployed to probe). Set to NO if you don't need the published verdict.

E. TEST CASES
   E1. Which test case types? (default: all — functional, non-functional, boundary-negative, system-architecture, gherkin)
   E2. Auto-confirm Jira Test issue creation, falling back to Sub-task if needed? (default: yes).

F. TEST SCRIPTS (Playwright + git)
   F1. Output folder (default: ~/projects/<project-name>-playwright-tests).
   F2. Base URL (default: http://localhost:<frontend-port from D4>).
   F3. Browsers (default: chromium).
   F4. Git remote URL (default: <first configured repo's origin remote — push the test scripts there>).
   F5. Initial branch (default: <discovered branch or `main`>).
```

Wait for the user's response. Parse it into the run-context object.

**Lenient acceptance rule (critical).** The user does **not** need to type `go` to advance. Accept any of:
- A coherent answer (with or without `go`) → treat as the final config, move directly to 0.2.
- The literal `ALL-DEFAULTS` → take every default as-is, move directly to 0.2.
- An empty reply / `yes` / `proceed` / `ok` / `start` / `go` → take every default, move directly to 0.2.
- Only a list of overrides (e.g. `change Jira project to FOO`) → apply, re-print resolved config, then move on **without** asking again.

The previous behaviour of refusing to advance until the literal token `go` arrived caused the pipeline to hang when users replied with actual answers. **Never block on the `go` token.**

### 0.2 — Ingest file inputs

Re-ingest the uploads discovered in 0.0a plus any extra paths the user pasted in item A. Every file must be ingested **before** advancing to step 0.3.

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
Phase 3 — Feature Dev (scaffold only)
  Frontend repo:    <existing repo path + branch> | SCAFFOLD-NEW at <path>/frontend
  Backend repo:     <existing repo path + branch> | SCAFFOLD-NEW at <path>/backend
  Frontend tech:    <react-vite-tailwind | nextjs-tailwind | vue3-vite | …>  (forced if existing repo)
  Backend tech:     <node-express | nestjs | fastapi | django-drf | …>      (forced if existing repo)
  Ports:            frontend <fp> / backend <bp>
  Brand style:      <brand name from D5> — palette/type/component-language hints applied to scaffold
Phase 4 — Vulnerability Check  (auto-run, pre-authorized)
  Scope:            <Phase 3 output folder>
  Fix-mode:         apply safe automated fixes (Crit→Low) · commit as fix(security)
  Report:           Confluence — same space as BRD
Phase 5 — Tech Debt Check       (auto-run, pre-authorized)
  Scope:            <Phase 3 output folder> · git hotspot ranking
  Fix-mode:         apply safe automated fixes only · commit as refactor
  Report:           Confluence — same space as BRD
Phase 6 — Test Cases
  Types:            functional, non-functional, boundary-negative, system-architecture, gherkin
  Auto-create:      yes
Phase 7 — Test Scripts (Playwright)
  Output folder:    <path>
  Base URL:         http://localhost:<fp>
  Browsers:         chromium
  Git remote:       <first configured repo's origin URL from the Repos tab, e.g. https://git.example.com/foo.git>
                    | (no repos configured — local commit only, push step skipped)
  Initial branch:   <discovered branch or main>
Phase 8 — Boot (install + start dev servers)  (runs AFTER patches from phases 4–5)
  Steps:            install backend deps, then frontend deps (commands depend on D3/D2 stacks)
                    start backend + frontend as background tasks
                    health-check http://localhost:<bp>/health
  Skip if D6=no:    yes | no
Phase 9 — Test Execution (runs Playwright suite)  (auto-run, pre-authorized)
  Project:          <Phase 7 output folder>
  Base URL:         http://localhost:<fp from D4>
  Browsers:         <browsers from F3>
  Bug logging:      mandatory — every failure → Jira bug in <jiraProjectKey> with RCA + corrective action
  Auto-fix:         ONE permitted interactive prompt mid-phase ("which failures to auto-fix?")
                    Reply with `all` / `none` / `1` / `1-5` / `1,3,7` / `skip`
  Report:           Confluence — same space as BRD
  Skip if D6=no:    yes (cannot test what was not started)
Phase 10 — Deployment (publish to PUBLIC_BASE_URL)  (auto-run, pre-authorized)
  Slug:             <sanitised project name — e.g. "you-bank">
  Public URL:       <PUBLIC_BASE_URL>/<slug>
  Frontend build:   vite/next/etc. with base='/<slug>/' and API client patched
                    to use import.meta.env.BASE_URL
  Backend:          spawned by quantnik on auto-allocated port (7000-7999),
                    reverse-proxied at /<slug>/api/*
  Registers via:    POST http://localhost:6060/api/deployments/<projectId>
  Skip if D7=no:    yes
Phase 11 — Sanity Checks (LAST phase — probe the live URL, publish verdict)  (auto-run, pre-authorized)
  Probes:           reachability + API surface + Jira story coverage + perf
  Public URL:       <Phase 10 deployment URL>
  Report:           Confluence — same space as BRD / Phase 9 report
  Verdict:          PASS / DEGRADED / FAIL
  Skip if D7=no:    yes (no deployment to probe)
  Skip if D8=no:    yes
─────────────────────────────────────────────
```

Then print the **input digest** (one-paragraph summary of every ingested file and pasted block) so the user can spot misreads.

**Do not ask for a second `go` confirmation.** The user already answered the questionnaire in 0.1; that answer is the consent to proceed. Move directly to Phase 1 after printing the resolved config + input digest.

The one and only exception: the user explicitly listed changes in their 0.1 reply (`change Jira project to FOO; skip Phase 5`). In that case apply the edits, re-print the resolved config, and proceed — still without asking a "ready?" question.

Never block on a `go` token. The previous version of this skill stalled here when users replied with answers rather than the literal word `go`.

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
- **Target space is `run-context.confluenceSpaceKey` / `confluenceSpaceId` from `quantnik.json`.** Do **not** call `getConfluenceSpaces` to pick a different one. If the sidecar only has a key, resolve its ID with `mcp__Confluence__conf_get` `/wiki/api/v2/spaces?keys=<KEY>` and cache the result. If the sidecar is silent, only then fall back to the user's personal space.
- For quantnik stdio: `mcp__Confluence__conf_post` to `/wiki/api/v2/pages` with the resolved `spaceId` + storage-HTML body.
- For claude.ai-managed: `createConfluencePage` with `contentFormat: "markdown"`. Record the page ID and URL into the run-context.

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

Use the repo assignments (D0a / D0b), tech choices (D2 / D3), ports (D4), and brand style (D5) from the run-context. Do not re-ask.

### 3.2 — Resolve workspace per role

For each role (frontend, backend):

- If D0 assigned an **existing repo**: work inside that repo. Cut a fresh feature branch off the current HEAD first:
  ```
  git -C <repo-path> checkout -b feat/<project-slug>-<YYYYMMDD>
  ```
  Treat the existing structure as the source of truth — read the top-level `package.json` / `requirements.txt` / `pom.xml` / `*.csproj` / `go.mod` to learn the existing conventions (which router lib, which test runner, which state library) and **match them**. Do not introduce a second framework alongside the existing one (e.g. don't add Redux to a Zustand repo). Generated files merge into the repo's existing module layout (`src/features/<name>/…`, `app/<route>/…`, `cmd/<service>/…` — whatever the repo already uses).

- If D0 = `SCAFFOLD-NEW`: scaffold from scratch into `D1/<role>` using the tech in D2 / D3.

### 3.3 — Plan and generate (tech-stack-specific)

Derive UI screens, API endpoints, data models, auth flows, and key interactions from the stories. Print the planned file list for visibility, then generate every file using the **Write** tool.

**Frontend file order, by D2 stack** (only the files relevant to the chosen stack — never mix stacks):

| D2 stack | Generation order |
|----------|------------------|
| `react-vite-tailwind` (default) | `package.json` · `vite.config.js` · `tailwind.config.js` · `index.html` · `src/main.jsx` · `src/App.jsx` · `src/context/*` · `src/services/api.js` · shared components → page-specific components → pages |
| `nextjs-tailwind` | `package.json` · `next.config.mjs` · `tailwind.config.js` · `app/layout.tsx` · `app/page.tsx` · `app/<route>/page.tsx` per screen · `app/api/<resource>/route.ts` per backend slice · `components/*` · `lib/api.ts` |
| `vue3-vite` | `package.json` · `vite.config.js` · `index.html` · `src/main.js` · `src/App.vue` · `src/router/index.js` · `src/stores/*.js` (Pinia) · `src/views/*` · `src/components/*` |
| `svelte-kit` | `package.json` · `svelte.config.js` · `vite.config.js` · `src/app.html` · `src/routes/+layout.svelte` · `src/routes/<route>/+page.svelte` per screen · `src/lib/api.ts` |
| `angular` | `angular.json` · `package.json` · `src/main.ts` · `src/app/app.config.ts` · `src/app/app.routes.ts` · `src/app/features/<name>/<name>.component.ts/.html/.scss` |

**Backend file order, by D3 stack**:

| D3 stack | Generation order |
|----------|------------------|
| `node-express` (default) | `package.json` · `.env.example` · `src/app.js` · `src/server.js` · `src/middleware/*` · per-epic: `src/models/<X>.js` · `src/controllers/<X>.js` · `src/routes/<X>.js` |
| `nestjs` | `package.json` · `nest-cli.json` · `tsconfig.json` · `src/main.ts` · `src/app.module.ts` · per-epic: `src/<feature>/<feature>.module.ts` · `.controller.ts` · `.service.ts` · `.entity.ts` · `.dto.ts` |
| `fastapi` | `pyproject.toml` (or `requirements.txt`) · `.env.example` · `app/main.py` · `app/core/config.py` · `app/api/deps.py` · per-epic: `app/api/v1/<X>.py` · `app/schemas/<X>.py` · `app/models/<X>.py` · `app/crud/<X>.py` |
| `django-drf` | `pyproject.toml` · `manage.py` · `<project>/settings.py` · `<project>/urls.py` · per-epic: `<feature>/models.py` · `serializers.py` · `views.py` · `urls.py` |
| `flask` | `pyproject.toml` · `app/__init__.py` · `app/config.py` · per-epic: `app/blueprints/<X>.py` · `app/models/<X>.py` |
| `spring-boot` | `pom.xml` · `src/main/resources/application.yml` · `src/main/java/.../Application.java` · per-epic: `<feature>/<X>Controller.java` · `<X>Service.java` · `<X>Repository.java` · `<X>Entity.java` · `<X>Dto.java` |
| `dotnet-minimal-api` | `<Project>.csproj` · `Program.cs` · `appsettings.json` · per-epic: `Endpoints/<X>Endpoints.cs` · `Models/<X>.cs` · `Services/<X>Service.cs` |
| `go-gin` | `go.mod` · `main.go` · `internal/config/config.go` · per-epic: `internal/handlers/<x>.go` · `internal/models/<x>.go` · `internal/store/<x>.go` |

**Brand-style application (D5).** Resolve `run-context.brandStyle` against the **Brand-style catalog** at the end of this skill. Apply the matched palette + typography + component-language hints to:

- Frontend design tokens (Tailwind config `theme.extend.colors`, CSS variables, or stack-equivalent — Vue scss vars, Angular styles, Next.js globals).
- Primary / secondary / accent / surface / border / success / warning / error colors.
- Body font family + heading font family (use Google Fonts CDN unless the brand uses a proprietary font, in which case fall back to the closest free equivalent and note it in a `README.md` "Style notes" section).
- Component shape language (rounded vs sharp corners, shadow depth, button density, card treatment).
- Iconography style (line vs filled, weight).

If D5 is a custom palette / Figma URL, use that verbatim instead of a catalog entry. If D5 is `neutral-light` or `neutral-dark`, fall back to the prior fintech defaults (see catalog).

**Code quality rules (apply across all stacks):**
- Match the existing repo's conventions when D0 points to an existing repo — never refactor what's already there to match a different style.
- All magic strings in `constants.{js,ts,py,…}`.
- Every form has client-side validation matching the story's AC.
- Every interactive element gets an `aria-label` (or framework equivalent).
- Functional components + hooks only for React-family stacks — no class components.

### 3.4 — Init git (no install, no servers in this phase)

For **SCAFFOLD-NEW** roles, initialise git so the patches that follow (Phases 4 and 5) can land as their own commits:

```
git init && git add . && git commit -m "feat: <project-name> — generated from Jira <EPIC-KEYS>"
```

For **existing-repo** roles, the feature branch is already in place from §3.2. Commit the generated files to that branch:

```
git -C <repo-path> add -A && git -C <repo-path> commit -m "feat: <project-slug> — scaffold generated from Jira <EPIC-KEYS>"
```

**Do not** run installs or start servers here. That step is deliberately deferred to **Phase 8 (Boot)** — Phases 4 (vulnerability-check) and 5 (tech-debt-check) may bump dependency versions and rewrite source files, so installing now would just be redone after the patches. Installing once at the end picks up the patched dep versions and the patched code on the first run.

Print Phase 3 STATUS — including which slots used existing repos vs scaffolded fresh.

---

## Phase 4 — Vulnerability Check (vulnerability-check)

Runs against the freshly-generated codebase before any test artifacts are produced — so any unsafe primitive the scaffold introduced (e.g. a hard-coded `JWT_SECRET`, `app.use(cors({ origin: '*', credentials: true }))`, `Math.random()` for tokens) is closed before tests are written that would lock in the broken behaviour.

### 4.1 — Scope

Scope is the **Phase 3 output folder** (and every `additionalDirectories` entry). Skip the usual generated/vendored dirs: `node_modules`, `.git`, `dist`, `build`, `coverage`, `__pycache__`, `.venv`, `.next`, `.turbo`.

### 4.2 — Scan + classify

Run every category from `vulnerability-check` Phase 1 verbatim:
- **A.** Hard-coded secrets (CWE-798, OWASP A07).
- **B.** Injection — SQL / command / XSS / path-traversal / SSRF / prototype-pollution / NoSQL / XXE (A03).
- **C.** Crypto — MD5/SHA1 in security contexts, `Math.random` for tokens, hardcoded IVs (CWE-327/326).
- **D.** Auth/session — hardcoded JWT secrets, missing httpOnly/secure, missing CSRF, CORS `*` + credentials.
- **E.** Vulnerable dependencies — shell out to `npm audit --json` (and Python/Go/Rust equivalents if their lockfiles are present). Parse critical/high advisories.
- **F.** Misc — `rejectUnauthorized:false`, `verify=False`, stack-trace leakage to clients, `eval`, open redirect, insecure deserialization.

Build the findings list with the rubric from `vulnerability-check` (Critical/High/Medium/Low/Info; CWE + OWASP refs; `fixable: yes | needs-review`).

### 4.3 — Apply safe fixes

Iterate Critical → Info, applying only the safe automated remedies (Phase 3 of `vulnerability-check`):

- Hard-coded secret → move to env var, also update `.env.example`.
- SQLi → parameterised queries / placeholders.
- Command injection → `execFile`/`spawn`/`subprocess.run([...], shell=False)`.
- XSS via `innerHTML` → `textContent` or DOMPurify.
- Path traversal → normalise + prefix check.
- Weak hash for security → SHA-256 (or bcrypt/argon2 for passwords).
- `Math.random()` for tokens → `crypto.randomBytes` / `secrets.token_hex`.
- CORS `*` + credentials → drop credentials or use explicit allow-list.
- Disabled TLS verify → remove the flag.
- Stack-trace leak → strip from the response, log server-side only.
- Dep CVE → bump to the lowest non-vulnerable version per `npm audit recommendation` and run `npm install`.

After each file edit, run a syntax sanity check (`node --check`, `python -m py_compile`, etc.). On failure, revert that file's last change and re-classify the finding as `needs-review`.

### 4.4 — Verify

Re-run the cheap regex/text scans. Build the resolved-vs-remaining diff. **If any Critical or High remains after this pass**, do **not** halt — record them in the run-context as `vuln_remaining` and continue to Phase 5. They will show up in the published report and in the final pipeline summary so the team can act, without blocking the rest of the pipeline.

### 4.5 — Publish report to Confluence

Title: `<Project> — Security Audit Report — <YYYY-MM-DD HH:mm>`. Body sections per `vulnerability-check` Phase 5: executive summary (with `panel-warning` callout if Critical/High remain) → severity legend → findings table → per-finding card (severity badge, CWE+OWASP, before/after code, status) → remaining risks → recommendations → run metadata.

Use the same Confluence space the BRD went into (from run-context). Reuse the discovery flow from Phase 1.

**Never print a real secret in the report** — show the masked form (`figd_****…JV1Cg`) in the Before block; the After block has the env-var reference (safe to publish).

Record `vuln_report_url` and counts (`vuln_total`, `vuln_critical`, `vuln_high`, `vuln_medium`, `vuln_low`, `vuln_info`, `vuln_fixed`, `vuln_remaining`) into the run-context. Commit the patched files to the Phase 3 git repo as a separate commit:

```
git add -A && git commit -m "fix(security): auto-patch vulnerability-check findings (<n> fixed)"
```

Print Phase 4 STATUS — include the URL of the published report.

---

## Phase 5 — Tech Debt Check (tech-debt-check)

Runs **after** Phase 4 so it scans the patched code, not the original. This way debt findings reflect what the team will actually maintain.

### 5.1 — Scope

Same scope as Phase 4. Detect whether git is available (`git rev-parse --is-inside-work-tree`) — the hotspot ranking uses it. Phase 3 always ran `git init`, so this should be `yes` in autonomous mode.

### 5.2 — Collect signals

Run every category from `tech-debt-check` Phase 1:
- **A.** Hotspot data — `commits_90d`, `authors_90d`, `last_modified` per file.
- **B.** Duplication — block-level (6+ identical normalised lines) + function-level (≤ 3 token diff).
- **C.** Dead code — unused imports, unused exports, unreachable code, large commented-out blocks.
- **D.** Complexity — function LOC > 50/100, cyclomatic > 12/25, nesting > 4/6, params > 5/8, boolean traps.
- **E.** File size — > 500/1000 LOC; "god" files > 30% of dir LOC.
- **F.** TODO/FIXME/HACK backlog with `git blame` for age.
- **G.** Test gaps — files with no sibling `*.test.*` / `*.spec.*` / `tests/test_*.py` / `*_test.go`, weighted by recent changes.
- **H.** Outdated patterns — `var`, `==`, JS/TS/Py/React-specific anti-patterns.
- **I.** Magic literals — numbers > 1 appearing ≥ 4 times, strings ≥ 6 chars appearing ≥ 3 times.
- **J.** Perf smells — `await` in non-dependent loops, sync fs in async handlers, n+1 patterns, deep-clone via JSON parse/stringify.
- **K.** Docs gaps — exported functions/classes without docstrings.
- **L.** Dep hygiene — `depcheck` for unused, `npm outdated --json` for outdated majors. Skip if tooling absent.
- **M.** Architecture drift — circular imports, layer violations, growth drift.

### 5.3 — Rank

Sort by `hotspot_score = severity_weight × (1 + commits_90d) × (1 + authors_90d / 3)`. Hotspot debt floats to the top.

### 5.4 — Apply safe fixes only

Iterate `fixable: yes` findings, highest score first. Apply only:
- Unused imports → remove.
- `var` → `const`/`let`.
- `==`/`!=` → `===`/`!==` (when types match; otherwise mark `needs-refactor`).
- Unreachable code after `return`/`throw` → delete.
- Import sorting (within original group).
- Magic-number → named const (≥ 4 occurrences, derivable name).
- `package.json` deps alphabetised (no version changes).

Everything else stays `needs-refactor`. Skip files with uncommitted edits (`skipped-dirty`).

Run a syntax sanity check after each edit; revert + reclassify on failure.

### 5.5 — Verify

Re-run the cheap regex/text scans. Capture resolved / still-debt / introduced-by-fix counts.

### 5.6 — Publish report to Confluence

Title: `<Project> — Tech-Debt Report — <YYYY-MM-DD HH:mm>`. Body per `tech-debt-check` Phase 5: executive summary → severity & category legend → hotspot heat-map (top 20 by `commits_90d`) → findings table → per-finding cards (before/after/status) → cross-link to Phase 4's vulnerability report → recommendations → run metadata.

Use the same Confluence space as the BRD and vuln report. Record `debt_report_url` and counts (`debt_total`, `debt_critical`, …, `debt_fixed`, `debt_refactor`, `debt_remaining`) into the run-context.

Commit the patched files to the Phase 3 git repo:

```
git add -A && git commit -m "refactor: auto-fix tech-debt-check findings (<n> fixed)"
```

Print Phase 5 STATUS — include the URL of the published report.

---

## Phase 6 — Test Cases (test-case-generator)

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

Record every created test key into the run-context (`test_keys`, grouped by source story). Print Phase 6 STATUS, including a per-story count and a tally of deduplicated skips.

---

## Phase 7 — Test Scripts (test-script-generator)

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
5. **Resolve the remote.** Use whatever F4 was set to in Phase 0. Reminder: the default for F4 is the first configured repo's `origin` remote pulled by Phase 0.0a from the quantnik **Repos** tab. The agent should **not** ask the user to type the remote URL — it's already discovered. Only fall back to "local commit only" when zero repos were configured for this project AND the user didn't explicitly paste a URL.
6. If a remote is resolved: `git remote add origin <url>` then `git push -u origin <branch>`. Never `git push --force`. If the push fails (auth, missing repo, conflict), log the error and continue — the local commit is still safe.
7. If no remote was resolvable, finish at the local commit and print the suggestion to configure a repo in the quantnik Repos tab, or to add a remote later with `git remote add origin <url>`.

If the folder already exists and is already a git repo, do **not** reinitialise it. Detect any existing spec files for the same story and add them as new commits rather than overwriting blindly. If pre-existing untracked files are present in the target folder, list them in the final report — but do not abort.

Print Phase 7 STATUS.

---

## Phase 8 — Boot (install + start dev servers)

Final pre-test phase. Runs **after** the patches from Phases 4 and 5 have landed, so the install picks up bumped dependency versions and the patched source.

Skip this phase entirely if the user set D6 = no in the Phase 0 questionnaire — print `Phase 8 — Boot: skipped (user opted out)` and proceed to the final summary.

### 8.1 — Install dependencies (stack-aware)

For each role, use the path resolved in Phase 3 (`run-context.frontendPath`, `run-context.backendPath`) and run the **install command matching the assigned tech stack**:

| Stack | Install command (run inside the resolved path) |
|-------|-----------------------------------------------|
| `react-vite-tailwind` / `nextjs-tailwind` / `vue3-vite` / `svelte-kit` / `angular` / `node-express` / `nestjs` | `npm install` |
| `fastapi` / `flask` | `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt` (Windows) or `python -m venv .venv && .venv/bin/pip install -r requirements.txt` (POSIX). Prefer `pip install -e .` if `pyproject.toml` exists. |
| `django-drf` | Same as fastapi/flask, then `python manage.py migrate` to bring up the dev SQLite DB. |
| `spring-boot` | `./mvnw -q -DskipTests package` (or `./gradlew build -x test` for Gradle projects). |
| `dotnet-minimal-api` | `dotnet restore` then `dotnet build --no-restore` |
| `go-gin` | `go mod download && go build ./...` |

Run installs **sequentially** as foreground `Bash` calls (no `run_in_background`) so a failure surfaces immediately. Backend first, then frontend, so frontend install can be skipped cleanly on a backend failure. If either install fails, log the error verbatim into `boot_install_error`, print Phase 8 STATUS as `failed`, and proceed to the final summary — do not start servers against a broken install.

### 8.2 — Start dev servers (background, stack-aware)

Once both installs succeed, start each server as a background process so they outlive the pipeline.

| Stack | Start command (run inside the resolved path, with port from D4) |
|-------|------------------------------------------------------------------|
| `react-vite-tailwind` / `vue3-vite` / `svelte-kit` | `npm run dev -- --port <fp>` |
| `nextjs-tailwind` | `npm run dev -- --port <fp>` (Next reads `PORT` env too) |
| `angular` | `npm run start -- --port <fp>` |
| `node-express` | `node src/server.js` (PORT env = `<bp>`) |
| `nestjs` | `npm run start:dev` (PORT env = `<bp>`) |
| `fastapi` | `.venv\Scripts\uvicorn app.main:app --port <bp> --reload` (Windows) / `.venv/bin/uvicorn app.main:app --port <bp> --reload` (POSIX) |
| `django-drf` | `.venv\Scripts\python manage.py runserver <bp>` (Windows) / equivalent on POSIX |
| `flask` | `.venv\Scripts\flask --app app run --port <bp> --debug` |
| `spring-boot` | `./mvnw spring-boot:run -Dspring-boot.run.arguments=--server.port=<bp>` |
| `dotnet-minimal-api` | `dotnet run --urls http://localhost:<bp>` |
| `go-gin` | `go run ./... --port <bp>` (or the project's `cmd/<service>/main.go` entrypoint) |

Each `Bash` call sets `run_in_background: true`. Capture the returned task ids into the run-context as `backend_task_id` and `frontend_task_id` so the final summary can cite them.

Each `Bash` call sets `run_in_background: true`. Capture the returned task ids into the run-context as `backend_task_id` and `frontend_task_id` so the final summary can cite them.

### 8.3 — Health-check the backend

Poll `http://localhost:<bp>/health` (and fall back to the project root `/` if `/health` isn't implemented) once per second for up to 20 seconds, then give up. Use the `Bash` tool with `curl -sf <url>` — the loop exits on the first 2xx.

If the backend never comes up cleanly, log the error into `boot_health_error` and continue to the final summary. **Do not kill the backend process** — the user may still want to inspect its output by reading the background task; leaving the process alive is the right call. The final summary clearly marks the backend as `not responding` so the user can intervene.

### 8.4 — Optional: confirm frontend is serving

After the health-check succeeds (or times out), make one `curl -sf http://localhost:<fp>/` call to confirm the Vite dev server is serving. Record the result; do not block on it.

Print Phase 8 STATUS with one of: `done`, `failed (install: …)`, `failed (backend health: …)`, `skipped (user opted out)`.

---

## Phase 9 — Test Execution (test-script-executor)

**Final phase.** Runs **after** Phase 8 brought the app up, against the already-patched + already-running stack. This is the phase that closes the loop — every spec written in Phase 7 actually runs, every failure produces a Jira bug, and the user gets exactly one chance to pick which failures the orchestrator should auto-fix.

Skip this phase entirely if **any** of the following is true (record the reason in the run-context and print `Phase 9 — Test Execution: skipped (<reason>)`):
- D6 = no (the user opted out of Phase 8, so there is nothing to run against)
- Phase 8 ended in `failed (install: …)` (no working app)
- Phase 8 ended in `failed (backend health: …)` AND the frontend curl in 8.4 also failed (no responding app)
- Phase 7 produced zero spec files

Otherwise proceed.

### 9.1 — Discover the Playwright project

The Phase 7 output folder is already in the run-context (`playwright_output_folder` / equivalent). Use it directly — do not re-scan the disk.

Confirm it exists and contains a `package.json` with `@playwright/test` in `devDependencies` and at least one `.spec.js` (or `.spec.ts`) under `tests/`. If either check fails, halt Phase 9 with a clear error — this is one of the deliberate non-autonomous failure points.

### 9.2 — Preflight (app under test must be alive)

Re-issue the Phase 8.3 health-check (`curl -sf http://localhost:<bp>/health`) and the Phase 8.4 frontend curl. Both must return 2xx before the suite runs. If either is down, do not start the suite — record the failure in `exec_preflight_error`, print Phase 9 STATUS as `failed (preflight: …)`, and proceed to the final summary.

If only one of the two is responding, run anyway but record it as a warning — the user may have specs that only hit one tier.

### 9.3 — Install Playwright + browsers

```
cd <playwright_output_folder> && npm install
npx playwright install --with-deps <browsers from F3, default chromium>
```

Each as a foreground `Bash` call. If either fails, log into `exec_install_error`, print Phase 9 STATUS as `failed (install: …)`, and proceed to the final summary.

### 9.4 — Run the suite

```
cd <playwright_output_folder> && npx playwright test --reporter=json --output=./test-results
```

Capture stdout to a temp file; on completion parse the JSON reporter output to build per-spec, per-test results. Build the failure list:

```
failures: [
  { test_title, spec_file, source_story_key, source_test_key, error_message, stack_trace, screenshot_path? }
]
```

Also count `tests_total`, `tests_passed`, `tests_failed`, `tests_flaky`, `tests_skipped`.

### 9.5 — Log a Jira bug for EVERY failure (mandatory)

This is the **non-negotiable** part — every failure becomes a Jira bug in `run-context.jiraProjectKey` before any auto-fix is even considered. No silent failures.

For each failure, `createJiraIssue`:
- `issueTypeName`: `Bug` (fall back to the highest-severity defect-like type in the project metadata — never silently use a generic `Task`)
- `summary`: `[Test failure] <test title> — <spec file>`
- `description` (markdown):
  ```
  ## Source
  - Spec: <spec file>
  - Test: <test title>
  - Source story: <STORY-KEY>
  - Source test case: <TEST-KEY>

  ## Failure
  <error message>

  ```
  <stack trace, truncated to 50 lines>
  ```

  ## Root cause analysis
  <RCA — derive from stack trace + the source file referenced. Be specific: which assertion failed, which selector wasn't found, which API call returned the wrong status. If the RCA is unclear, say so explicitly — never fabricate.>

  ## Corrective action
  <Concrete fix proposal — file + line + change. If the fix is in the test (selector drift, race condition), say so; if it's in the app (broken endpoint, missing validation), say so.>

  ## Reproduction
  1. Start the app at http://localhost:<fp>/
  2. Run `cd <playwright_output_folder> && npx playwright test <spec-file> -g "<test title>"`
  ```
- `additional_fields`: `{ priority: { name: "<derived from severity — failed assertion=High, missing selector=Medium, flaky=Low>" }, labels: ["test-failure", "auto-logged", "phase-9"] }`
- `createIssueLink` with `type: "Relates"` from the new bug to the source test case (so the test case shows its failures).

Record every bug key into `bug_keys`. If a bug creation fails (Atlassian outage, permissions), capture the failure into `exec_bug_log_errors` and continue — never abandon the rest of the failure list.

### 9.6 — Ask the user which failures to auto-fix (ONE permitted prompt)

This is the **one permitted interactive prompt** in autonomous mode. The user pre-authorized it by virtue of running the orchestrator at all (Phase 9 inherently requires this choice — fixing arbitrary code without confirmation would violate the destructive-write guardrail).

Print the failure list as a numbered table:

```
PHASE 9 — AUTO-FIX SELECTION
The Playwright suite ran. <n> tests failed. Every failure has been logged to Jira:

#   Bug          Test                                              File
1   WC-201       login fails with valid credentials                tests/auth.spec.js
2   WC-202       cart shows wrong total after coupon               tests/checkout.spec.js
3   WC-203       …
...

Which failures should I attempt to auto-fix?

Reply with one of:
  • `all`        — try to auto-fix all failures
  • `none`       — skip auto-fix, finish the pipeline now
  • `1,3,5`      — fix specific failures by number
  • `1-5`        — fix a range
  • `skip`       — same as `none`
```

**Wait for the user's reply.** Accept any of the formats above (lenient parser — see test-script-executor SKILL for the canonical implementation). Do not advance until a reply is received. If the WS reconnects mid-prompt and the reply is lost, re-print the prompt verbatim once.

### 9.7 — Apply selected auto-fixes (verify-or-revert)

For each selected failure (skip if reply was `none` / `skip` / empty selection):

1. Read the file referenced in the bug's Corrective Action.
2. Apply the fix via the **Edit** tool — small, targeted changes only. Never rewrite a whole file.
3. Re-run only the affected spec (`npx playwright test <spec-file> -g "<test title>"`).
4. If the test now passes → mark the bug as `Fixed by auto-fix` via a Jira comment + (if a Resolved/Done transition is available) transition it. Record into `bugs_autofixed`.
5. If the test still fails → revert the edit, add a Jira comment "Auto-fix attempted but reverted (test still failing)" with the new stack trace, and leave the bug open. Record into `bugs_autofix_failed`.

**Never auto-fix anything outside the bug's Corrective Action scope.** No "while I'm here" refactors.

After all selected fixes are processed, re-run the **full** Playwright suite once more to confirm no regressions were introduced by the fixes. Capture the new pass/fail counts as `tests_passed_after_fix` / `tests_failed_after_fix`.

### 9.8 — Publish execution report to Confluence

Title: `<Project> — Test Execution Report — <YYYY-MM-DD HH:mm>`. Body sections:

- **Executive summary** — total / passed / failed / flaky / skipped, with a callout panel if any failures remain
- **Run metadata** — base URL, browsers, duration, Playwright version
- **Per-spec results table** — one row per spec file with pass / fail counts
- **Failures table** — every failure with: # · test title · spec · linked bug (Jira key + URL) · auto-fix status (selected / skipped / fixed / revert)
- **Auto-fix outcomes** — list of bugs auto-fixed + list reverted (with reasons)
- **Re-run delta** — pass/fail counts before vs after auto-fix

Use the same Confluence space as the BRD / vuln / debt reports (from `run-context.confluenceSpaceKey`). Record `exec_report_url` into the run-context.

### 9.9 — Record and emit Phase 9 STATUS

Record into the run-context:
- `tests_total`, `tests_passed`, `tests_failed`, `tests_flaky`, `tests_skipped`
- `tests_passed_after_fix`, `tests_failed_after_fix` (if auto-fix ran)
- `bug_keys` (every logged bug)
- `bugs_autofixed`, `bugs_autofix_failed`
- `exec_report_url`

Print Phase 9 STATUS with one of: `done`, `failed (preflight: …)`, `failed (install: …)`, `skipped (<reason>)`. Include the report URL on `done`.

---

## Phase 10 — Deployment (deploy-to-platform)

**Final phase.** Ships the production build behind the same quantnik domain so the stakeholder can browse the app at a stable URL without setting up separate hosting. Runs **after** Phase 9 so any auto-fix patches applied during test execution are part of what gets deployed.

Skip this phase entirely if **any** of the following is true (record the reason in the run-context and print `Phase 10 — Deployment: skipped (<reason>)`):
- D7 = no (user opted out of deployment)
- Phase 3 produced no frontend code (nothing to build)
- Phase 8 ended in `failed (install: …)` (broken deps would break the production build too)

Phase 9 failures do **not** block Phase 10 — a failing test suite is a signal, not a blocker. The deployment goes out with the bugs visible so reviewers can repro them via the public URL.

### 10.1 — Resolve project context

Read `.claude/quantnik.json` at the project cwd to capture `project.id` (required) and `project.name` (default slug source). Halt with a clear error if either is missing — the deploy API can't be called without a `projectId`.

Derive the slug: lowercase the project name, replace non-`[a-z0-9-]` with `-`, collapse repeats, max 48 chars, default `app` if empty. Reject any slug in the reserved set (`api`, `ws`, `auth`, `assets`, `health`, `static`, `public`, `admin`, `login`, `logout`, `callback`, `favicon.ico`, `index.html`, `d`) by appending `-app`.

Record `slug` into the run-context.

### 10.2 — Patch the frontend for subpath serving

The deployed frontend lives at `<PUBLIC_BASE_URL>/<slug>/`, so all asset URLs and API calls must be prefixed with `/<slug>/`. Apply two edits to the frontend (use the resolved `frontendRoot` from Phase 3):

1. **Vite / Next / Angular base.** For Vite:
   - `Edit` `vite.config.js`: add `base: '/<slug>/'` to the `defineConfig({...})` block.
   - For Next: set `assetPrefix: '/<slug>'` and `basePath: '/<slug>'` in `next.config.{js,mjs}`.
   - For Angular: pass `--base-href=/<slug>/` to the build script.

2. **API client base.** Grep the frontend source for hard-coded `/api`. Replace any literal `const BASE = '/api'` (or equivalent) with ``const BASE = `${import.meta.env.BASE_URL}api`.replace(/\/{2,}/g, '/')`` — works in both dev (base=`/`) and deployed (base=`/<slug>/`) builds. Patch any one-off `fetch('/api/...')` literals similarly.

Cache the original `vite.config.js` (or stack-equivalent) so it can be reverted at step 10.5.

### 10.3 — Build the production bundle

Run the stack-aware build inside `frontendRoot`:

| D2 stack | Build command | Dist dir |
|----------|---------------|----------|
| `react-vite-tailwind` / `vue3-vite` / `svelte-kit` | `npm install && npm run build` | `<frontendRoot>/dist` |
| `nextjs-tailwind` | `npm install && npm run build` (use `next export` only if the user explicitly opted in) | `<frontendRoot>/out` or `.next` (if dynamic, route via Node — see step 10.4) |
| `angular` | `npm install && npm run build -- --configuration=production --base-href=/<slug>/` | `<frontendRoot>/dist/<project>/browser` |

Run as a foreground `Bash` call. If the build fails, record `deploy_build_error`, print Phase 10 STATUS as `failed (build: …)`, revert the base edit, and proceed to the final summary.

Verify the dist directory exists and contains `index.html` before proceeding.

### 10.4 — Register the deployment

`POST http://localhost:6060/api/deployments/<projectId>` with a JSON body:

```json
{
  "slug": "<slug>",
  "frontendDist": "<absolute path to dist dir>",
  "backendPath": "<absolute path to backendRoot, or omit if no backend>",
  "backendStartCmd": "<from D3 stack table — node / npm / .venv/Scripts/uvicorn / …>",
  "backendStartArgs": ["..."],
  "backendEnv": { "NODE_ENV": "production" }
}
```

Use `Bash` with `curl` and write the body to a temp file (`$env:TEMP\quantnik-deploy-<slug>.json` on Windows) before sending.

On 2xx, parse the response `{ url, backendPort, deployment, message }`. Record `deploy_url`, `deploy_backend_port`, `deploy_id` into the run-context. On 4xx/5xx, surface the `error` field and print Phase 10 STATUS as `failed (register: …)`.

### 10.5 — Revert build-time patches

Restore the original `vite.config.js` (or stack-equivalent) by removing the `base` line that was added in 10.2. The `src/services/**` patches that use `import.meta.env.BASE_URL` are **kept** — they work transparently in dev (base=`/`) and in any future deployment.

### 10.6 — Verify

Two `curl` probes:

1. `curl -sI http://localhost:6060/<slug>/` — must return 200 + `content-type: text/html`. Confirms the loopback dispatcher serves the bundle.
2. `curl -sI <deploy_url>/` (the public URL from 10.4) — must return 200 + roughly the same bytes as probe 1. Confirms the public proxy is forwarding `/<slug>/*`. If it returns the Quantnik SPA instead of the deployed app, the public reverse proxy is not forwarding `/<slug>/*` to the Quantnik backend; surface a warning but don't fail if the loopback URL still works.

If a backend was deployed, also `curl -sI http://localhost:6060/<slug>/api/health` (or whichever health endpoint the backend exposes, falling back to `/`). 2xx or 401 = backend alive. 502 = backend didn't start — read the deployment's `log_path` and surface the last 20 lines as a diagnostic.

### 10.7 — Record and emit Phase 10 STATUS

Record into the run-context:
- `deploy_url`, `deploy_id`, `deploy_backend_port`
- `deploy_log_path` (from the deployment response)

Print Phase 10 STATUS with one of: `done`, `failed (build: …)`, `failed (register: …)`, `failed (verify: …)`, `skipped (<reason>)`. Always include the public URL on `done`.

---

## Phase 11 — Sanity Checks (sanity-check)

**Final phase.** Probes the live deployment one last time, maps probes to Jira stories, and publishes a Confluence verdict so stakeholders can read the status in 30 seconds without needing to open the deployed app. Runs **after** Phase 10 so it tests the actual production URL, not a dev server.

Skip this phase entirely if **any** of the following is true (record reason and print `Phase 11 — Sanity Checks: skipped (<reason>)`):
- D7 = no (no deployment to probe)
- D8 = no (user opted out of the sanity check)
- Phase 10 ended in `failed (build: …)` or `failed (register: …)` (nothing live to test)

Phase 10 `failed (verify: …)` is **not** a blocker — that means the proxy was iffy but the row was registered; Phase 11 will surface the same issue with more detail.

### 11.1 — Invoke the sanity-check skill

Read the sanity-check SKILL.md (it's already installed at `~/.claude/skills/sanity-check/`). Run its full flow inline, **reusing values from the run-context** instead of re-discovering:

- `quantnik.json` was already read in Phase 0.0a — reuse `run-context.jiraProjectKey`, `run-context.confluenceSpaceKey`, `run-context.projectId`.
- The deployment record was just created in Phase 10 — reuse `run-context.deploy_id`, `run-context.deploy_url`, `run-context.deploy_backend_port`. No second `GET /api/deployments` is needed.
- The Jira stories from Phase 2 (`run-context.story_keys`) can seed the feature-coverage step — no second JQL search is needed.

### 11.2 — What sanity-check does (recap, not re-derived here)

1. **Reachability** — HEAD public URL, loopback URL, JS bundle, CSS, backend `/health`; slug-isolation check.
2. **API surface discovery** — grep backend routes + frontend api-client call sites, cross-reference.
3. **Smoke-probe each endpoint** with 10s timeout. GETs: 2xx / 401/403 pass. POSTs: any 4xx passes (route alive, body rejected).
4. **Map probes to Jira stories** — each story flagged pass / partial / fail / uncovered via description-keyword match.
5. **Performance baseline** — homepage + bundle TTFB and total. Flag (don't fail) >3s.
6. **Build + publish Confluence report** in the same space as the BRD / Phase 9 report. Sections: Executive Summary · Reachability · API Surface · Feature Coverage · Performance · Run Metadata · Recommendations.
7. **Print final summary** with PASS / DEGRADED / FAIL verdict.

### 11.3 — Record + emit Phase 11 STATUS

Record into the run-context:
- `sanity_report_url` (the Confluence page URL)
- `sanity_verdict` (`pass` / `degraded` / `fail`)
- `sanity_counts` (`{ reach: p/t, probes: p/t, stories: p/t, perf: p/t }`)
- `sanity_critical` (top 3 failing items, if any)

Print Phase 11 STATUS as `done — <verdict>`, `failed (sanity-check: <reason>)`, or `skipped (<reason>)`. Always include the Confluence URL on `done`.

The pipeline's overall outcome is now informed by Phase 11's verdict — surface it in the final summary so users know if anything in the deployment is degraded.

---

## Pipeline complete — final summary

After Phase 10, print:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SDLC PIPELINE COMPLETE ✅
  Phase 1  — BRD:               ✅ done | skipped
  Phase 2  — User Stories:      ✅ done
  Phase 3  — Feature Dev:       ✅ done
  Phase 4  — Vulnerability:     ✅ done
  Phase 5  — Tech Debt:         ✅ done
  Phase 6  — Test Cases:        ✅ done
  Phase 7  — Test Scripts:      ✅ done
  Phase 8  — Boot:              ✅ done | skipped | failed
  Phase 9  — Test Execution:    ✅ done | skipped | failed
  Phase 10 — Deployment:        ✅ done | skipped | failed
  Phase 11 — Sanity Checks:      ✅ pass | ⚠ degraded | ❌ fail | skipped
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
  Frontend: http://localhost:<fp>   [running | not responding | not started]
  Backend:  http://localhost:<bp>   [running | not responding | not started]
  Background tasks: backend=<task-id>, frontend=<task-id>
  Pages:    <n> screens
  Endpoints:
    <list>
  Boot errors (if any): <boot_install_error / boot_health_error>

🔒 Security audit
  Report:   <Confluence URL>
  Findings: <total>  (Crit <c> · High <h> · Med <m> · Low <l> · Info <i>)
  Fixed:    <n>     Still vulnerable: <n>

🧹 Tech debt
  Report:   <Confluence URL>
  Findings: <total>  (Crit <c> · High <h> · Med <m> · Low <l> · Info <i>)
  Fixed:    <n>     Needs refactor: <n>     Still-debt: <n>
  Hotspot top-3: <file> · <file> · <file>

🧪 Playwright tests
  Path:     <absolute path>
  Specs:    <n> spec files / <m> test() blocks
  Skipped:  <list with reasons — e.g. PROJ-510 (non-functional: needs perf harness)>
  Git:      branch <branch> @ <short-sha>
  Remote:   <url> | (none — local only)

🧪 Test execution
  Report:   <Confluence URL>
  Results:  <total> total  (✅ <pass> passed · ❌ <fail> failed · ⚠️ <flaky> flaky · ⏭ <skip> skipped)
  Bugs:     <n> Jira bugs logged · <n> auto-fixed · <n> revert (still failing)
  Re-run:   before <pass>/<total>  →  after auto-fix <pass_after>/<total>
  Preflight/install errors (if any): <exec_preflight_error / exec_install_error>

🔗 Traceability
  tests/proj-123.spec.js  ← PROJ-123  (Tests: PROJ-501, PROJ-502)  →  Bugs: <BUG-KEYS or none>
  ...

🌐 Deployment
  Public URL: <deploy_url>                          ← share this with reviewers
  Slug:       <slug>
  Backend:    port <deploy_backend_port>, log <deploy_log_path>
  Manage:     list    → curl http://localhost:6060/api/deployments
              restart → curl -X POST http://localhost:6060/api/deployments/<deploy_id>/restart
              undeploy→ curl -X DELETE http://localhost:6060/api/deployments/<deploy_id>
  Build/verify errors (if any): <deploy_build_error / deploy_register_error / deploy_verify_warning>

🩺 Sanity check
  Verdict:    <PASS | DEGRADED | FAIL>
  Report:     <sanity_report_url>                   ← stakeholder-facing
  Reach:      <p>/<t>   API: <p>/<t>   Stories: <p>/<t>   Perf: <p>/<t>
  Critical:   <up to 3 top failing items, or "none">
```

**End the response here — do NOT ask a closing question.** The pipeline is complete; nothing is awaiting user input. Print one final line on its own:

```
✅ Orchestrator complete. Pipeline is fully done — no further input required. Send a new message any time if you want to refine a phase, redeploy, re-run sanity, or start another project.
```

That line tells the user the agent is *idle*, not *pending*. The "your turn" banner the quantnik chat UI shows is calibrated against assistant messages that contain a literal question mark or explicit "reply with…" phrasing — keeping the closing message statement-shaped avoids triggering it.

---

## Brand-style catalog

When D5 is a brand name, resolve it against this table and use the listed tokens as Phase 3 design defaults. If a brand isn't listed, derive the equivalent from the brand's public marketing site (read the homepage CSS via WebFetch if available) and add a note in the generated `README.md` "Style notes" section recording where the tokens came from. Never copy proprietary fonts — fall back to the listed Google Fonts equivalent.

| Brand | Domain fit | Primary | Secondary / accent | Surface | Heading font | Body font | Component language |
|-------|-----------|---------|--------------------|---------|--------------|-----------|--------------------|
| **US Bank** | banking | `#0C2074` (deep navy) | `#D4002A` (red) · `#005EB8` (link blue) | `#FFFFFF` / `#F4F6F8` | Source Sans Pro (700) | Source Sans Pro (400) | Conservative rectangles, 4 px radius, low shadow, dense forms, blue button fill with white text. |
| **HDFC Bank** | banking | `#004C8F` (HDFC blue) | `#ED232A` (HDFC red) · `#FFFFFF` | `#FFFFFF` / `#F2F2F2` | Roboto Slab (700) | Open Sans (400) | Strong primary CTAs with red accents, tabbed product cards, sharp 2 px corners. |
| **Chase** | banking | `#117ACA` (Chase blue) | `#0E2C58` (deep blue) · `#FFFFFF` | `#FFFFFF` / `#F2F4F7` | Larsseit (700) → fallback Inter (700) | Inter (400) | Wide, airy spacing, big headers, full-bleed photography, pill-shaped primary buttons. |
| **Bank of America** | banking | `#012169` (BofA navy) | `#E61030` (BofA red) | `#FFFFFF` / `#F0F2F5` | Proxima Nova (700) → fallback Inter (700) | Inter (400) | Square corners (2 px), strong borders, badge-style numeric callouts. |
| **Stripe** | fintech-payments / saas-b2b | `#635BFF` (Stripe purple) | `#0A2540` (ink) · `#00D4FF` | `#FFFFFF` / `#F6F9FC` | Sohne (700) → fallback Inter (700) | Inter (400) | Gradient hero panels, 8 px radius, soft shadows, monospaced numeric data. |
| **Revolut** | fintech-payments | `#0666EB` (Revolut blue) | `#191C1F` (near-black) · `#00D632` (green) | `#FFFFFF` / `#F2F4F7` | Aeonik (700) → fallback Inter (700) | Inter (400) | Bold black headlines, large gradient cards, 16 px radius, sticker-style icons. |
| **CRED** | fintech-payments | `#1A1A1A` (near-black) | `#FFC107` (CRED yellow) · `#E0E0E0` | `#0A0A0A` / `#161616` | DM Sans (700) | DM Sans (400) | Dark glassmorphism cards, gold accents, generous whitespace, micro-animations. |
| **Paytm** | fintech-payments | `#00BAF2` (Paytm blue) | `#002970` (deep blue) · `#FFFFFF` | `#FFFFFF` / `#F4F8FB` | Inter (700) | Inter (400) | Solid color blocks, sharp 4 px radius, prominent QR motifs. |
| **Mayo Clinic** | healthcare | `#0F5E9E` (Mayo blue) | `#8B0000` (deep red — sparingly) · `#FFFFFF` | `#FFFFFF` / `#F4F6F8` | Source Serif Pro (700) | Source Sans Pro (400) | Serif headings, calm whites, 6 px radius, illustrative iconography. |
| **Cleveland Clinic** | healthcare | `#005EB8` (clinic blue) | `#00A19A` (teal) · `#FFFFFF` | `#FFFFFF` / `#F2F6FA` | Lato (700) | Lato (400) | Soft-shadow cards, rounded 8 px, dense info tables, large CTAs. |
| **Practo** | healthcare | `#1AAA5D` (Practo green) | `#0091EA` · `#FFFFFF` | `#FFFFFF` / `#F5F7FA` | Inter (700) | Inter (400) | Green accent CTAs, doctor-card grid, 8 px radius, profile-photo emphasis. |
| **Amazon** | ecommerce | `#FF9900` (Amazon orange) | `#232F3E` (Amazon navy) · `#FFFFFF` | `#FFFFFF` / `#EAEDED` | Amazon Ember (700) → fallback Inter (700) | Inter (400) | Dense product grid, yellow/orange CTAs, 4 px radius, persistent search bar. |
| **Flipkart** | ecommerce | `#2874F0` (Flipkart blue) | `#FB641B` (orange CTA) · `#FFE500` (yellow) | `#FFFFFF` / `#F1F3F6` | Roboto (700) | Roboto (400) | Blue header band, vivid orange "buy" CTAs, card-based product tiles. |
| **Shopify (Polaris)** | ecommerce / saas-b2b | `#008060` (Shopify green) | `#202223` (ink) · `#FFFFFF` | `#FFFFFF` / `#F6F6F7` | Inter (700) | Inter (400) | Strict Polaris design system: 8 px radius, hairline borders, structured admin layout. |
| **Booking.com** | travel | `#003580` (Booking blue) | `#FEBB02` (yellow CTA) · `#FFFFFF` | `#FFFFFF` / `#F2F6FA` | Inter (700) | Inter (400) | Yellow primary CTA on blue header, search-bar dominance, listing-card density. |
| **Airbnb** | travel | `#FF385C` (Rausch) | `#222222` · `#FFFFFF` | `#FFFFFF` / `#F7F7F7` | Cereal (700) → fallback Inter (700) | Inter (400) | Edge-to-edge photography, 12 px radius cards, soft shadows, generous whitespace. |
| **MakeMyTrip** | travel | `#EB2026` (MMT red) | `#053C75` (deep blue) · `#FFB400` | `#FFFFFF` / `#F1F5F9` | Open Sans (700) | Open Sans (400) | Tab-style search, red CTAs, deal-banner pattern, dense itinerary cards. |
| **Linear** | saas-b2b | `#5E6AD2` (Linear purple) | `#0A0A0A` (ink) · `#FFFFFF` | `#FFFFFF` / `#F9FAFB` (light) or `#08090A` / `#101113` (dark) | Inter (700) | Inter (400) | Keyboard-first density, 6 px radius, monochrome ink palette, subtle dividers. |
| **Notion** | saas-b2b | `#000000` (ink) | `#37352F` · `#2EAADC` (accent blue) | `#FFFFFF` / `#F7F6F3` | Inter (700) | Inter (400) | Document-style spacing, 4 px radius, emoji-as-icon, slash-command affordances. |
| **Netflix** | streaming | `#E50914` (Netflix red) | `#141414` (near-black) · `#FFFFFF` | `#000000` / `#141414` | Netflix Sans (700) → fallback Inter (700) | Inter (400) | Full-bleed dark hero, horizontal scrolling tile rows, 4 px radius, red CTAs. |
| **Spotify** | streaming | `#1DB954` (Spotify green) | `#191414` · `#FFFFFF` | `#121212` / `#1A1A1A` (dark default) | Circular (700) → fallback Inter (700) | Inter (400) | Dark surfaces, green accent CTAs, 50% rounded buttons, album-grid layout. |
| **Coinbase** | crypto | `#0052FF` (Coinbase blue) | `#0A0E27` · `#FFFFFF` | `#FFFFFF` / `#F8FAFC` (light) or `#0A0E27` / `#0F1426` (dark) | Inter (700) | Inter (400) | Blue/black duotone, 8 px radius, big numeric typography, gradient asset pills. |
| **Binance** | crypto | `#F0B90B` (Binance yellow) | `#1E2329` (ink) · `#FFFFFF` | `#FFFFFF` / `#F5F5F5` (light) or `#0B0E11` / `#181A20` (dark) | Inter (700) | Inter (400) | Yellow/black dominance, 4 px radius, monospaced tickers, dense data tables. |
| **neutral-light** | fallback | `#1D4ED8` | `#4F46E5` · `#10B981` | `#FFFFFF` / `#F1F5F9` | Inter (700) | Inter (400) | Plain fintech: 6 px radius, light shadows, 1 px borders. |
| **neutral-dark** | fallback | `#3B82F6` | `#10B981` · `#F59E0B` (warn) · `#F43F5E` (error) | `#0A0F1E` / `#111827` | Inter (700) | Inter (400) | CRED-style glass cards on dark, gradient accents, 8 px radius. |

Apply the matched row's tokens to Tailwind's `theme.extend.colors` (or the stack-equivalent), bring in the fonts via Google Fonts in `index.html` / `app/layout.tsx`, and set the component-language hints (radius, shadow, density) globally so every generated screen inherits them without per-component overrides.

---

## Guardrails (apply across all phases)

- **Autonomous after Phase 0.1.** Once the user has answered the questionnaire — with or without the literal word `go` — no further prompts. Status prints are one-way; they never wait for input. The pipeline only halts for (a) an external system failure the orchestrator can't resolve, (b) a destructive operation that was not pre-authorised in 0.1, (c) the **one deliberate Phase 9 auto-fix-selection prompt** (§9.6), or (d) pipeline completion. The Phase 9 prompt is not optional — auto-fixing arbitrary source files without user confirmation would violate the destructive-write guardrail, so this single mid-pipeline pause is intentional and pre-authorized by the act of invoking the orchestrator. Phase 10 (Deployment) is fully autonomous — `D7=yes` in the questionnaire pre-authorizes the publish, no per-deploy prompt fires.
- **Front-loaded confirmation only.** Destructive / external operations (Confluence writes, Jira creates, git pushes) are pre-authorized in Phase 0. Do not bypass that authorization — if Phase 0 did not cover a particular operation (e.g. force-push), do not perform it autonomously; raise it instead.
- **Hard stops, not silent skips.** Halt with a clear error for: missing Epic/Story issue type, missing Test issue type with no acceptable fallback, invalid file path in Phase 0.2, BRD source not found when Phase 1 was skipped. Print what failed and what state was already persisted.
- **Idempotency across re-runs.** Skip Jira issues whose `summary` already exists for the same parent/story. Skip git init if the target folder is already a repo. Record skips in the final report.
- **Traceability is mandatory.** Every Phase 4 TC carries `Linked story: <KEY>`; every Phase 5 `test()` block carries a header comment with the source story key + Test issue key; the Playwright README's traceability table lists every spec.
- **Identity respect for git.** Use existing `git config user.email` if set; only fall back to the user's `MEMORY.md` email (`abhinav.krishna@wipro.com`) and only scoped to the repo, never global.
- **No fabricated test logic.** If a Test issue has neither Gherkin nor numbered steps, emit `test.fixme()` with the source key — never invent flows.
- **No remote without consent.** Phase 5 pushes only when the user supplied a remote URL in Phase 0 (F4). Empty remote = local commit only, full stop.
- **No `--force` anywhere.** No `git push --force`, no `git reset --hard`, no `rm -rf` of the user's output folders.
