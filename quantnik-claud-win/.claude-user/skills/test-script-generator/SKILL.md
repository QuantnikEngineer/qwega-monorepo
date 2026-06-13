---
name: test-script-generator
description: Reads Xray / Jira Test issues (typically the ones produced by the test-case-generator skill) and generates Playwright JavaScript test scripts. Maps Gherkin scenarios to Playwright `test.describe` / `test()` blocks, builds a runnable Playwright project with Page Object Model layout, and stores everything in a git repository that is initialized, committed, and (optionally) pushed automatically. Use when the user asks for "Playwright tests", "test scripts", "automate the test cases", or "convert the Xray tests into code".
---

When this skill is invoked, follow the steps below in strict order. Do not skip a step or move to the next until the current one is complete. Always prefer the **Atlassian MCP** for Jira reads and dedicated **Write** / **Bash** tools for filesystem and git work.

---

## Step 1 — Authenticate & discover the Atlassian workspace

Call `mcp__claude_ai_Atlassian__atlassianUserInfo` to confirm the user is authenticated. If it fails, call `getAccessibleAtlassianResources` and follow the auth flow. Extract the `cloudId` from the accessible resources — you need it for every subsequent Jira call.

If the user's `MEMORY.md` already records a cloudId / default project for this workspace, surface that as the suggested default rather than re-asking from scratch.

---

## Step 2 — Resolve the source of the test cases

Ask the user **how** they want to scope the test issues. Present these options:

1. **By project + JQL** — e.g. `project = PROJ AND issuetype = Test AND labels = test-case` (the default labels written by the `test-case-generator` skill).
2. **By source story** — supply one or more story keys (e.g. `PROJ-123`); the skill will follow the `Tests` issue link / `Sub-task` parent relationship and pull every linked test.
3. **By Xray Test Set / Test Plan** — supply a Test Set or Test Plan key (Xray issue types). The skill will read its linked Tests.
4. **By explicit test keys** — a comma-separated list of test issue keys.

Wait for the user's selection before running any JQL.

---

## Step 3 — Fetch the test issues

Depending on the choice in Step 2:

- **JQL** → `searchJiraIssuesUsingJql` (paginate when results exceed 50).
- **By source story** → for each story key, `getJiraIssue` to read its issue links, then `getJiraIssue` again for each linked Test, plus `searchJiraIssuesUsingJql` with `parent = <STORY-KEY> AND issuetype = Sub-task` to catch sub-task style tests.
- **Test Set / Test Plan** → `getJiraIssue` on the Set/Plan, walk the linked Tests.
- **Explicit keys** → `getJiraIssue` per key.

For every Test issue, capture:

- `key`, `summary`, `priority`, `labels`, `components`
- `description` — this is where the `test-case-generator` skill writes the TC body (functional steps, Gherkin block, boundary tables, etc.)
- Linked source story key (follow the `Tests` outward link, or `parent` for Sub-task tests)
- Xray-specific custom fields **if present** — common field IDs:
  - Cucumber / Gherkin script: `customfield_10200` (varies by tenant — fall back to scraping a ```gherkin fenced block from the description)
  - Manual test steps: `customfield_10201`
  - Test Type: `customfield_10202`

Never invent a custom field ID. If a field isn't returned by `getJiraIssue`, do not synthesize it — parse the `description` instead.

Print a compact summary table to the user:

```
Test issues found: [n]

KEY          | Source story | Type            | Has Gherkin? | Title
PROJ-501     | PROJ-123     | functional      | yes          | Login with valid OTP
PROJ-502     | PROJ-123     | boundary-neg.   | no           | Login OTP — 5 invalid attempts
...
```

Ask: "Generate Playwright scripts for all of these? Reply `yes`, or list the keys to include."

Wait for confirmation.

---

## Step 4 — Classify and group the tests

For each test issue, infer the **mapping strategy**:

- If a ```gherkin fenced block is present in the description (or in the Xray Cucumber field) → map each `Scenario` / `Scenario Outline` to a `test()` block; `Background` → `test.beforeEach`; `Examples` table → `for…of` data-driven loop.
- Else if numbered "Test steps:" are present → map each step to a Playwright action with a leading `// Step n:` comment so traceability is preserved.
- Else if it's a `non-functional` category (performance, accessibility, security) → emit a placeholder spec that calls the appropriate Playwright integration (`@axe-core/playwright` for a11y, a `request` fixture probing for response timing for perf, etc.) with a TODO referencing the source TC ID. **Do not silently skip these** — surface them in the report.

Group by **source story key** — one spec file per story, named `tests/<story-key-lowercased>.spec.js`. This keeps git diffs aligned with story-level work.

---

## Step 5 — Collect output preferences

Ask the user for:

1. **Output directory** — absolute path. Default: `~/projects/<PROJECT-KEY>-playwright-tests`.
2. **Base URL** — the application under test (e.g. `http://localhost:5173`). Default: read from the linked story's description if it mentions a URL; otherwise `http://localhost:3000`.
3. **Browsers to run** — multi-select among `chromium`, `firefox`, `webkit`. Default: `chromium` only.
4. **Git remote (optional)** — if provided, the skill will set it as `origin` and push after committing. If empty, the skill creates a local repo and stops at the commit step. Never invent a remote URL.
5. **Initial branch name** — default `main`.

Print the resolved settings back to the user as a confirmation block before writing files.

---

## Step 6 — Plan the Playwright project layout

Print this structure to the user before writing any file:

```
<output-dir>/
├── package.json
├── playwright.config.js
├── .gitignore
├── README.md
├── tests/
│   ├── <story-key>.spec.js        # one per source story
│   └── ...
├── pages/                          # Page Object Model — one file per UI surface
│   ├── BasePage.js
│   └── <Surface>Page.js
├── fixtures/
│   └── test-fixtures.js            # custom fixtures (authenticated context, test data)
├── data/
│   └── <story-key>.data.js         # data-driven test inputs (from Gherkin Examples tables)
└── utils/
    ├── selectors.js                # central selectors map
    └── api.js                      # API helpers for setup/teardown via request fixture
```

If the test issue body references specific selectors, screens, or domain entities, fold those into the page object names — do not emit placeholder `LoginPage` if the story is about cards.

---

## Step 7 — Generate the Playwright project files

Write every file using the **Write** tool. Required contents:

### `package.json`

```json
{
  "name": "<project-key>-playwright-tests",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "test:ui": "playwright test --ui",
    "report": "playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.0",
    "@axe-core/playwright": "^4.10.0"
  }
}
```

### `playwright.config.js`

- `testDir: './tests'`
- `fullyParallel: true`
- `retries: process.env.CI ? 2 : 0`
- `reporter: [['list'], ['html', { open: 'never' }]]`
- `use`: `baseURL` from Step 5, `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`
- `projects`: one entry per selected browser, each with `use: { ...devices['Desktop <Browser>'] }`

### `.gitignore`

```
node_modules/
playwright-report/
test-results/
.env
.env.local
```

### `tests/<story-key>.spec.js`

For every test in the group:

- Add a header comment block with the source Jira keys: `// Source story: PROJ-123 / Test: PROJ-501`.
- Use `test.describe(<story summary>, () => { ... })` to wrap all tests from the same story.
- For Gherkin scenarios:
  - `Scenario` → `test('<scenario title>', async ({ page }) => { ... })`
  - `Background` → `test.beforeEach(...)`
  - `Scenario Outline` + `Examples` → wrap in a `for (const row of examples)` loop with `test(\`<title> [\${row.input}]\`, ...)`.
  - Translate `Given` to setup actions (navigation, fixture seeding), `When` to user actions, `Then` to `expect(...)` assertions. Preserve the original Gherkin lines as comments above each Playwright statement so the trace back to the TC is obvious.
- For numbered manual steps: emit one Playwright action per step with `// Step <n>: <original step text>` above each.
- Every `test()` ends with at least one `expect(...)` — never an empty assertion. If the TC's expected outcome is vague, emit a `test.fixme()` marker with a comment explaining what's missing, instead of asserting `true`.

### Page Object Model

For each unique UI surface referenced by the tests, generate `pages/<Surface>Page.js`:

```js
import { expect } from '@playwright/test';

export class <Surface>Page {
  constructor(page) {
    this.page = page;
    // selectors here — prefer role / label / test-id locators
    this.heading = page.getByRole('heading', { name: '<Surface>' });
  }

  async goto() {
    await this.page.goto('<path>');
    await expect(this.heading).toBeVisible();
  }

  // one method per user action referenced in the tests
}
```

Always prefer `page.getByRole`, `getByLabel`, `getByTestId` over CSS / XPath. Add a TODO comment if the source TC does not give enough detail to pick a reliable selector — do not invent specific class names.

### `fixtures/test-fixtures.js`

Export an extended `test` with reusable fixtures: `authenticatedPage` (logs in once per worker), `apiContext` (`request.newContext` for API setup/teardown). Spec files import `test` from here, not from `@playwright/test`.

### `data/<story-key>.data.js`

For each `Scenario Outline`, export the `Examples` rows as a JS array of objects. Spec files import and iterate over these — keeps test bodies clean.

### `README.md`

- One-paragraph overview noting the source Jira project and the test-case-generator origin.
- Setup: `npm install && npx playwright install`.
- How to run: `npm test`, `npm run test:ui`, `npm run report`.
- Traceability section: a markdown table mapping every spec file → source story → list of Test issue keys it implements.

---

## Step 8 — Initialize git automatically

Run these via the **Bash** tool, in order. Use the resolved output directory as the working directory for each command (`-C <output-dir>` or `cd` once).

1. `git init -b <branch-name>` — `git init` if the user's git is older than 2.28.
2. `git add .`
3. `git -c user.name=... -c user.email=...` — only if `git config user.email` returns empty. Use the user's email from `MEMORY.md` / their environment context; do not invent identities.
4. `git commit -m "Initial Playwright test scaffold from <PROJECT-KEY> test cases"` — include a multi-line body listing the source story keys and Test issue keys covered, via a HEREDOC.
5. If the user supplied a remote in Step 5:
   - `git remote add origin <url>`
   - `git push -u origin <branch-name>` — and **only** if the user explicitly opted into pushing. Do not push otherwise.
6. If no remote was supplied, print the local repo path and the suggestion: "Add a remote later with `git remote add origin <url> && git push -u origin <branch>`."

Report progress one line at a time:

```
✓ git initialized at <path>
✓ committed 14 files (<short sha>)
✓ pushed to origin/<branch>            # only if remote was configured
```

---

## Step 9 — Report and next steps

Print a final summary:

```
Done. Playwright project generated at <path>:

Spec files:   [n] (one per source story)
Test blocks:  [m] (mapped from [k] Jira Test issues)
Skipped:      [list with reason — e.g. PROJ-510 (non-functional: needs perf harness)]
Page objects: [n]
Browsers:     chromium [, firefox, webkit]

Git:
  Repo:       <path>
  Branch:     <branch-name>
  Commit:     <sha> "<message>"
  Remote:     <url> | (none — local only)

Traceability table:
  tests/proj-123.spec.js  ← PROJ-123  (Tests: PROJ-501, PROJ-502)
  tests/proj-124.spec.js  ← PROJ-124  (Tests: PROJ-503)
  ...

Run locally:
  cd <path>
  npm install
  npx playwright install
  npm test
```

Ask: "Want me to (a) execute the suite now via `npm test`, (b) add CI workflow (GitHub Actions) for these tests, (c) generate additional scripts from new Test issues, or (d) wire these results back to Xray as Test Executions?"

---

## Guardrails

- **No fabricated test logic.** If a Test issue's description has neither Gherkin nor numbered steps, do not invent a flow. Emit a `test.fixme()` marker with a comment pointing to the Jira key and ask the user to enrich the source TC.
- **Selectors are honest.** Never invent CSS classes or `data-testid` values that aren't in the source TC. Use semantic locators (role/label) and add a TODO when uncertain. The user should always be able to grep a selector back to either the TC or the linked story.
- **One spec per story.** Do not collapse multiple stories into a single spec file — it breaks git blame and review flow.
- **Traceability is mandatory.** Every `test()` block must carry a header comment with the source story key AND the Test issue key. The README's traceability table must list every spec.
- **Idempotency.** If the output directory already exists and is a git repo, do not blow it away. Detect existing spec files for the same story; ask whether to overwrite, append, or skip per file.
- **Git safety.** Never `git push --force`. Never commit `.env` or anything matching the `.gitignore` patterns. If `git status` shows pre-existing untracked files in the target directory, list them and ask before `git add .`.
- **No remote without consent.** Adding a remote and pushing requires the user to have supplied a remote URL in Step 5 *and* confirmed the push. Default is local-only.
- **Identity respect.** Use `git config user.email` if already set on the machine; only fall back to the email recorded in `MEMORY.md` (`abhinav.krishna@wipro.com`) when nothing is configured — and surface the choice to the user before committing.
- **Stop on Jira failure.** If any `getJiraIssue` / `searchJiraIssuesUsingJql` call returns an error, halt and report — do not generate placeholder specs from imagined data.
