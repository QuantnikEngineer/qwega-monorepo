---
name: build-software
description: End-to-end autonomous software delivery pipeline. Takes a plain-English description of what to build and runs the full SDLC automatically: creates a BRD and publishes it to Confluence → generates user stories and pushes them to Jira → validates user stories against the BRD, updates Jira, and publishes a validation report to Confluence → generates test cases and uploads them to Jira → generates Playwright test scripts and pushes them to GitHub → generates a full React + Node.js application, pushes the code to GitHub, deploys it, and returns the live URL. Use this skill when the user says anything like "build me an app", "create software for", "build software", "develop an application", or invokes /build-software.
---

When this skill is invoked, execute the following phases in strict order. Do not skip a phase or move to the next until the current one is complete. After each phase print a STATUS block.

---

## Phase 0 — Intake (the only interactive phase)

### 0.1 — Read project config

`Read` `.claude/quantnik.json` at the project cwd. If the file exists, extract and cache into **run-context**:
- `run-context.projectId` ← `project.id`
- `run-context.jiraProjectKey` ← `atlassian.jiraProjectKey`
- `run-context.confluenceSpaceKey` ← `atlassian.confluenceSpaceKey`
- `run-context.confluenceSpaceId` ← `atlassian.confluenceSpaceId`
- `run-context.githubRepo` ← `git.repo` (if present)

These are the **only** allowed Jira / Confluence targets. Never infer different targets from chat history or MCP calls.

### 0.2 — Collect inputs

Ask the user ONE consolidated questionnaire. Pre-fill anything already known from run-context or from the user's invocation message:

```
BUILD-SOFTWARE — Setup

A1. What is the project name? (short slug, e.g. "task-app")
    → [pre-fill if mentioned in invocation]

A2. Describe what you want built:
    → [pre-fill if mentioned in invocation]

A3. Confluence space key for BRD + reports:
    → [pre-fill: run-context.confluenceSpaceKey or ask]

A4. Jira project key for stories + test cases:
    → [pre-fill: run-context.jiraProjectKey or ask]

A5. GitHub repo name (created automatically if it doesn't exist):
    → [default: <project-name>]

A6. Skip any steps? (leave blank to run all)
    Options: create_brd, create_user_stories, validate_user_stories,
             create_test_cases, create_test_scripts, generate_code
    → [default: none — run everything]
```

Wait for the user's response. If the user's original message already contained the description and project name, pre-fill those fields and only ask for the ones that are still unknown.

### 0.3 — Confirm run config

Print the resolved config and ask for confirmation:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUILD-SOFTWARE — Run Config
  Project name:        <value>
  Description:         <value>
  Confluence space:    <value>
  Jira project:        <value>
  GitHub repo:         <value>
  Skip steps:          <value or "none">
  Build service URL:   ${BUILD_SOFTWARE_URL:-${BUILD_SOFTWARE_URL:-http://localhost:8083}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Proceed? (yes / no / edit)
```

If the user says yes, proceed immediately. If no, abort. If edit, re-show 0.2.

---

## Phase 1 — Start the pipeline

Reset the phases panel and mark Phase 1 as running:

```bash
curl -s -X DELETE http://localhost:6060/api/phases/<projectId>
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":1,"status":"running","name":"Pipeline Start"}'
```

Start the build-software pipeline in async mode:

```bash
curl -s -X POST ${BUILD_SOFTWARE_URL:-http://localhost:8083}/v1/build/async \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "<project_name>",
    "description": "<description>",
    "confluence_space_key": "<confluenceSpaceKey>",
    "jira_project_key": "<jiraProjectKey>",
    "github_repo": "<githubRepo>",
    "skip_steps": [<skip_steps_array>]
  }'
```

Extract `run_id` from the response. Store as `run-context.runId`.

Print:
```
Phase 1 — Pipeline: running
🚀 Build pipeline started (run_id: <runId>)
Monitoring progress...
```

---

## Phase 2 — Monitor and relay progress

Poll `GET ${BUILD_SOFTWARE_URL:-http://localhost:8083}/v1/build/<runId>` every 15 seconds until `status` is `completed` or `failed`.

For each poll, read the `artifacts` field. For each new artifact key that appears since the last poll, print it immediately and update the phases panel:

### Artifact → phase mapping

| Artifact key | Phase | Name (pass exactly as shown) | Label |
|---|---|---|---|
| `brd_url` | 2 | `BRD → Confluence` | BRD published to Confluence |
| `jira_epic_url` | 3 | `User Stories → Jira` | User stories pushed to Jira |
| `validation_url` | 4 | `Validation → Confluence` | Validation report published |
| `test_cases_url` | 5 | `Test Cases → Jira` | Test cases uploaded to Jira |
| `test_scripts_url` | 6 | `Test Scripts → GitHub` | Test scripts pushed to GitHub |
| `repo_url` | 7 | `Code → GitHub` | Code pushed to GitHub |
| `deployment_url` | 8 | `Deploy → Live URL` | Application deployed |

When an artifact appears, immediately:

1. Print in chat:
   ```
   Phase <N> — <Label>: done
   → <artifact_url>
   ```

2. POST phase update (always include the `name` field so the dashboard shows "Software Build"):
   ```bash
   curl -s -X POST http://localhost:6060/api/phases/<projectId> \
     -H "Content-Type: application/json" \
     -d '{"phase":<N>,"status":"done","name":"<Name>","note":"<artifact_url>"}'
   ```

3. Mark the NEXT phase as running (include its name too):
   ```bash
   curl -s -X POST http://localhost:6060/api/phases/<projectId> \
     -H "Content-Type: application/json" \
     -d '{"phase":<N+1>,"status":"running","name":"<NextName>"}'
   ```

Print a STATUS block after each new artifact.

### STATUS block format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUILD-SOFTWARE STATUS  (run: <runId>)
  Phase 1 — Pipeline start:          [done]
  Phase 2 — BRD → Confluence:        [done | running | pending | skipped | failed]
  Phase 3 — User Stories → Jira:     [...]
  Phase 4 — Validation → Confluence: [...]
  Phase 5 — Test Cases → Jira:       [...]
  Phase 6 — Test Scripts → GitHub:   [...]
  Phase 7 — Code → GitHub:           [...]
  Phase 8 — Deploy → Live URL:       [...]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If `status` becomes `failed`, print the error from `run.error`, mark the failed phase as `failed` in the panel, mark all remaining phases as `skipped`, and stop polling.

---

## Phase 3 — Final summary

When `status` is `completed`, print:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUILD-SOFTWARE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ BRD                → <brd_url>
  ✅ User Stories       → <jira_epic_url>
  ✅ Validation Report  → <validation_url>
  ✅ Test Cases         → <test_cases_url>
  ✅ Test Scripts       → <test_scripts_url>
  ✅ Code Repository    → <repo_url>
  ✅ Live Application   → <deployment_url>

Your application is live at: <deployment_url>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

POST the final phase as done:

```bash
curl -s -X POST http://localhost:6060/api/phases/<projectId> \
  -H "Content-Type: application/json" \
  -d '{"phase":8,"status":"done","note":"<deployment_url>"}'
```

---

## Error handling

- If `${BUILD_SOFTWARE_URL:-http://localhost:8083}/health` returns non-200 at any point, print: `❌ Build-software service is not running. Start it with: cd quantnik-build-software && python3 run.py` and abort.
- If a phase fails, print the error clearly, mark remaining phases as `skipped` in the panel, and suggest re-running with `skip_steps` to resume from the failed step.
- If polling times out after 30 minutes with no `completed` / `failed` status, print the last known status and tell the user to check `GET ${BUILD_SOFTWARE_URL:-http://localhost:8083}/v1/build/<runId>` manually.

---

## Pre-flight check

Before Phase 0.2, verify the build-software service is reachable:

```bash
curl -s ${BUILD_SOFTWARE_URL:-http://localhost:8083}/health
```

If it returns non-200 or times out, print:

```
❌ Build-software service is not running on port 8083.
Start it first:
  cd /Users/akk/qwega-monorepo/quantnik-build-software
  python3 run.py
Then re-run /build-software.
```

And abort. Do not proceed to the questionnaire.
