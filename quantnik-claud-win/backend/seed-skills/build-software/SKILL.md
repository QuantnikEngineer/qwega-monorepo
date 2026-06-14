---
name: build-software
description: End-to-end autonomous software delivery pipeline. Takes a plain-English description or an uploaded requirements file and runs the full SDLC automatically using MCP tools: creates a BRD and publishes it to Confluence → generates user stories and pushes them to Jira → validates user stories against the BRD, updates Jira stories, and publishes a validation report to Confluence → generates test cases and uploads them to Jira → generates Playwright test scripts and commits them to GitHub → generates a full React + Node.js application, commits the code to GitHub, and returns the repository URL. Use when the user says "build me an app", "build software", "create an application", "develop", or invokes /build-software.
---

When this skill is invoked, execute the following phases in strict order. Print a STATUS block after each phase. Do not stop for user input after Phase 0 unless a tool call fails.

---

## Pre-flight

Read `.claude/quantnik.json` at the project cwd. Cache:
- `run-context.projectId` ← `project.id`
- `run-context.jiraProjectKey` ← `atlassian.jiraProjectKey`
- `run-context.confluenceSpaceKey` ← `atlassian.confluenceSpaceKey`
- `run-context.confluenceSpaceId` ← `atlassian.confluenceSpaceId`

These are the **only** allowed Jira/Confluence targets.

Then check for uploaded files: `Glob` the pattern `uploads/*` at the project cwd and also `../uploads/*`. Record every file found — treat them as source input for the BRD.

---

## Phase 0 — Intake

Ask ONE consolidated questionnaire. Pre-fill everything you already know:

```
BUILD-SOFTWARE — Setup

A1. Project name (short slug, e.g. "task-app"):
    → [pre-fill if mentioned in invocation]

A2. What to build (or confirm you'll use the uploaded file):
    → [pre-fill if mentioned, or "will use uploaded file at <path>"]

A3. Confluence space key for BRD + reports:
    → [pre-fill from quantnik.json or ask]

A4. Jira project key for stories + test cases:
    → [pre-fill from quantnik.json or ask]

A5. GitHub repo name (will be created under QuantnikEngineer if it doesn't exist):
    → [default: <project-name>]

A6. Skip any steps? (leave blank to run all)
    Options: brd, user_stories, validation, test_cases, test_scripts, code
```

Wait for response. Then confirm the run config and ask "Proceed? (yes / no)". After yes, run all phases autonomously.

---

## Phase 1 — Create BRD → Confluence

**Update phases panel:**
```bash
curl -s -X DELETE http://localhost:6060/api/phases/<projectId>
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":1,"status":"running","name":"BRD → Confluence"}'
```

**If there is an uploaded file:** Read it with the `Read` tool. Use its contents as the source material for the BRD.

**Generate the BRD:** Using your own knowledge and the source material, write a complete Business Requirements Document covering:
- Executive Summary
- Problem Statement
- Goals & Objectives
- Functional Requirements (FR-01, FR-02, …)
- Non-Functional Requirements (NFR-01, NFR-02, …)
- Out of Scope
- Success Metrics

**Publish to Confluence** using the `createConfluencePage` MCP tool:
- Space: `run-context.confluenceSpaceKey`
- Title: `BRD — <project-name>`
- Body: the BRD content in Confluence storage format (HTML)

Save the returned page URL as `run-context.brdUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":1,"status":"done","name":"BRD → Confluence","note":"<brdUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":2,"status":"running","name":"User Stories → Jira"}'
```

Print: `Phase 1 — BRD → Confluence: done → <brdUrl>`

---

## Phase 2 — Create User Stories → Jira

**Generate epics and user stories** from the BRD. Follow INVEST principles. Produce 2–3 epics with 3–5 stories each in the format:

```
Epic: <title>
  Story: As a <user>, I want <feature> so that <benefit>
    Acceptance Criteria:
    - Given... When... Then...
```

**Create in Jira:**
1. For each epic: use `createJiraIssue` MCP tool with `issuetype: Epic`
2. For each story under the epic: use `createJiraIssue` with `issuetype: Story` and `parent: <epic-key>`

Save the first epic's browse URL as `run-context.jiraEpicUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":2,"status":"done","name":"User Stories → Jira","note":"<jiraEpicUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":3,"status":"running","name":"Validation → Confluence"}'
```

Print: `Phase 2 — User Stories → Jira: done → <jiraEpicUrl>`

---

## Phase 3 — Validate User Stories → Jira + Confluence

**Validate** each user story against the BRD requirements. Check:
- Every FR has at least one story covering it
- Stories are testable and unambiguous
- Acceptance criteria are specific

**For each gap found:** Update the relevant Jira story using `updateJiraIssue` to add a comment or update the description with the improved acceptance criteria.

**Write a validation report** covering:
- Coverage summary (X of Y requirements covered)
- Gaps found and how they were addressed
- Updated stories list
- Sign-off recommendation

**Publish to Confluence:**
- Title: `User Story Validation Report — <project-name>`
- Body: the validation report in Confluence storage format

Save the URL as `run-context.validationUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":3,"status":"done","name":"Validation → Confluence","note":"<validationUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":4,"status":"running","name":"Test Cases → Jira"}'
```

Print: `Phase 3 — Validation → Confluence: done → <validationUrl>`

---

## Phase 4 — Create Test Cases → Jira

**Generate test cases** for each user story. For each story produce 2–4 test cases covering:
- Happy path
- Edge cases
- Negative / error scenarios

**Create in Jira** using `createJiraIssue` with `issuetype: Task` and label `test-case`, linked to the parent story via `parent: <story-key>`.

Format each test case summary as: `TC-<N>: <description>`

Save the first test case's browse URL as `run-context.testCasesUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":4,"status":"done","name":"Test Cases → Jira","note":"<testCasesUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":5,"status":"running","name":"Test Scripts → GitHub"}'
```

Print: `Phase 4 — Test Cases → Jira: done → <testCasesUrl>`

---

## Phase 5 — Generate Test Scripts → GitHub

**Generate Playwright TypeScript test scripts** covering the test cases from Phase 4. Produce at minimum:
- `tests/smoke.spec.ts` — basic load and navigation tests
- `tests/core.spec.ts` — core functionality tests
- `playwright.config.ts` — config pointing at `http://localhost:3000`
- `package.json` — with `@playwright/test` dependency

**Push to GitHub** using Bash:
```bash
# Create repo via GitHub API
curl -s -X POST https://api.github.com/orgs/QuantnikEngineer/repos \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"<project-name>-tests","private":true,"auto_init":true}'

# Clone, write files, commit, push
cd /tmp
git clone https://x-access-token:$GITHUB_TOKEN@github.com/QuantnikEngineer/<project-name>-tests.git
cd <project-name>-tests
# Write each file using the Write tool, then:
git config user.email "engineerquantnik@gmail.com"
git config user.name "Quantnik"
git add -A
git commit -m "feat: add generated Playwright test scripts"
git push
```

Save `https://github.com/QuantnikEngineer/<project-name>-tests` as `run-context.testScriptsUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":5,"status":"done","name":"Test Scripts → GitHub","note":"<testScriptsUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":6,"status":"running","name":"Code → GitHub"}'
```

Print: `Phase 5 — Test Scripts → GitHub: done → <testScriptsUrl>`

---

## Phase 6 — Generate Application Code → GitHub

**Generate a complete React + Node.js application** based on the user stories. The app must be functional and runnable. Produce at minimum:

**Frontend (React + Vite + TypeScript + Tailwind):**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- Key feature components based on the user stories

**Backend (Node.js + Express):**
- `backend/package.json`
- `backend/src/index.js` — REST API with routes matching the user stories
- Data storage using better-sqlite3 or in-memory store

**Infrastructure:**
- `docker-compose.yml`
- `README.md` with setup instructions

**Push to GitHub:**
```bash
cd /tmp
curl -s -X POST https://api.github.com/orgs/QuantnikEngineer/repos \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"<project-name>","private":true,"auto_init":true}'

git clone https://x-access-token:$GITHUB_TOKEN@github.com/QuantnikEngineer/<project-name>.git
cd <project-name>
# Write all files using the Write tool, then:
git config user.email "engineerquantnik@gmail.com"
git config user.name "Quantnik"
git add -A
git commit -m "feat: initial generated application for <project-name>"
git push
```

Save `https://github.com/QuantnikEngineer/<project-name>` as `run-context.repoUrl`.

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":6,"status":"done","name":"Code → GitHub","note":"<repoUrl>"}'
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":7,"status":"running","name":"Deploy → Live URL"}'
```

Print: `Phase 6 — Code → GitHub: done → <repoUrl>`

---

## Phase 7 — Deploy

**Enable GitHub Pages** on the test scripts repo OR provide a `docker compose up` deployment guide as a Confluence page.

If no automated deployment is configured, publish a **Deployment Guide** to Confluence:
- Title: `Deployment Guide — <project-name>`
- Contents: step-by-step instructions to run the app locally and deploy to Cloud Run / Vercel

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":7,"status":"done","name":"Deploy → Live URL","note":"<deployUrl>"}'
```

Print: `Phase 7 — Deploy: done → <deployUrl>`

---

## Final Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUILD-SOFTWARE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ BRD                → <brdUrl>
  ✅ User Stories       → <jiraEpicUrl>
  ✅ Validation Report  → <validationUrl>
  ✅ Test Cases         → <testCasesUrl>
  ✅ Test Scripts       → <testScriptsUrl>
  ✅ Code Repository    → <repoUrl>
  ✅ Deployment         → <deployUrl>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## STATUS block format (print after every phase)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUILD-SOFTWARE STATUS
  Phase 1 — BRD → Confluence:        [done | running | pending | failed]
  Phase 2 — User Stories → Jira:     [...]
  Phase 3 — Validation → Confluence: [...]
  Phase 4 — Test Cases → Jira:       [...]
  Phase 5 — Test Scripts → GitHub:   [...]
  Phase 6 — Code → GitHub:           [...]
  Phase 7 — Deploy:                  [...]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Error handling

- If a Jira/Confluence MCP call fails: retry once, then log the error and continue to the next phase.
- If GitHub push fails: check `$GITHUB_TOKEN` is set in the environment. If not set, write the generated files to the project cwd instead and tell the user.
- Never stop the pipeline for a non-critical failure — complete as many phases as possible and summarise what succeeded and what failed in the final summary.
