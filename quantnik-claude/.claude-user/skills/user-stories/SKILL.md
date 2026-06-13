---
name: user-stories
description: Generates INVEST-compliant Agile user stories from a BRD stored in Confluence, then creates the Epics and Stories directly in Jira. Guides the user to pick a BRD and a Jira project before generating anything.
---

When this skill is invoked, follow the steps below in strict order. Do not skip a step or move to the next until the current one is complete.

---

## Step 1 — Authenticate & discover the Atlassian workspace

Call `atlassianUserInfo` to confirm the user is authenticated. If it fails, call `getAccessibleAtlassianResources` and follow the auth flow. Extract the `cloudId` from the accessible resources — you will need it for every subsequent call.

---

## Step 2 — List available BRDs from Confluence

Search Confluence for BRD pages using `searchConfluenceUsingCql` with the query:

```
title ~ "BRD" AND type = page ORDER BY lastmodified DESC
```

If zero results are returned, try:

```
title ~ "Business Requirements" AND type = page ORDER BY lastmodified DESC
```

Display the results as a numbered list:

```
Found [n] BRD(s) in Confluence:

1. [Page title] — Space: [space name] — Last modified: [date]
2. [Page title] — Space: [space name] — Last modified: [date]
...
```

Ask: "Which BRD should I use? Enter the number, or paste a Confluence page URL/ID directly."

Wait for the user's response before continuing.

---

## Step 3 — Fetch and parse the BRD

Call `getConfluencePage` with `contentFormat: "markdown"` for the selected page. Read the full content. Extract:

- **Initiative / feature name** (from the page title or executive summary)
- **Personas / roles** (from stakeholder, user, or actor sections)
- **Functional requirements** (BR-n items or equivalent)
- **Non-functional requirements**
- **Scope** (in-scope / out-of-scope)
- **Constraints and assumptions**

Summarise what you extracted in 3–4 bullet points so the user can spot misreadings early.

---

## Step 4 — Select the Jira project

Call `getVisibleJiraProjects` to list available projects. Display them as a numbered list:

```
Available Jira projects:

1. [Project name] ([KEY])
2. [Project name] ([KEY])
...
```

Ask: "Which Jira project should the Epics and Stories be created in? Enter the number or the project key."

Wait for the user's response. Then call `getJiraProjectIssueTypesMetadata` for the chosen project to confirm it supports **Epic** and **Story** issue types. If it does not have Epic, use the highest-level available type as the grouping container and note this to the user.

---

## Step 5 — Generate user stories using INVEST principles

Derive all Epics and User Stories from the BRD content. Every story **must** pass all six INVEST checks before being included:

| Principle | Check |
|-----------|-------|
| **I**ndependent | Can the story be developed and delivered without depending on another unfinished story? If not, restructure or split. |
| **N**egotiable | Is the story focused on *what* is needed (not *how*)? Remove implementation details from the story statement. |
| **V**aluable | Does the story deliver direct value to a named user or stakeholder? If not, merge it into a story that does. |
| **E**stimable | Is the story clear enough that the team can size it? If not, add detail or flag as needs-clarification. |
| **S**mall | Can the story be completed in a single sprint (≤ 8 story points)? If not, split it. |
| **T**estable | Does it have acceptance criteria that can be verified as pass/fail? Every story must have at least 3 AC items. |

### Story format

Write every story using this structure in the pre-Jira preview shown to the user:

**Story statement:**
> As a **[persona]**, I want **[goal]**, so that **[measurable benefit]**.

**Acceptance criteria** (Given/When/Then preferred):
- [ ] Given [context], when [action], then [outcome]
- [ ] ...

**Story point estimate:** [1 / 2 / 3 / 5 / 8] — with a one-line rationale
**Priority:** P1 Critical / P2 High / P3 Medium / P4 Low

Only flag INVEST violations in the preview, and only when a principle is **not** met (⚠️ with a one-line reason). Do not list all six INVEST ticks on every story.

For stories that are ambiguous or inferred, append:
> ⚠️ **Needs clarification:** [specific question]
> ℹ️ **Inferred from context** (if not explicitly stated in BRD)

Show the full generated set to the user in a readable markdown summary before writing anything to Jira.

---

## Step 6 — Confirm before writing to Jira

Display a compact table of everything that will be created:

| # | Type | Summary | Epic | Points | Priority |
|---|------|---------|------|--------|----------|
| 1 | Epic | [name] | — | — | — |
| 2 | Story | [title] | [epic name] | 3 | P2 |
...

Ask: "Shall I create these [n epic(s)] and [m story/stories] in Jira project **[KEY]**? Reply 'yes' to proceed, or tell me what to change first."

Wait for confirmation. Do not write to Jira until the user confirms.

---

## Step 7 — Create Epics and Stories in Jira

For each Epic, call `createJiraIssue` with:
- `issueTypeName`: "Epic"
- `summary`: epic name
- `description`: epic goal statement in markdown
- `additional_fields`: `{"priority": {"name": "[P1→Critical / P2→High / P3→Medium / P4→Low]"}}`

Capture the returned Epic issue key (e.g. `PROJ-12`).

For each Story under that Epic, call `createJiraIssue` with:
- `issueTypeName`: "Story"
- `summary`: short story title
- `description`: structured story description — see Jira description format below
- `parent`: the Epic issue key from above
- `additional_fields`: `{"priority": {"name": "..."}, "customfield_10016": [n]}` — `customfield_10016` is the standard Jira Cloud story points field

Create stories sequentially within each epic (not in parallel) to preserve the parent reference.

### Jira description format

Write the description as clean markdown with explicit blank lines between every section. Do NOT include INVEST flags or story point values in the description body — those go in dedicated fields. Structure:

```
As a **[persona]**, I want **[goal]**, so that **[measurable benefit]**.

**Acceptance Criteria**

- Given [context], when [action], then [outcome]

- Given [context], when [action], then [outcome]

- Given [context], when [action], then [outcome]
```

If there are clarification flags, add them after the AC block:

```
⚠️ Needs clarification: [specific question]
```

Each acceptance criterion must be on its own line with a blank line separating it from the next item, so Jira renders each as a distinct paragraph rather than a run-on list.

---

## Step 8 — Report results

Print a final summary:

```
Done. Created in Jira project [KEY]:

Epics:
  • [PROJ-12] Epic name

Stories:
  • [PROJ-13] Story title (Epic: PROJ-12, P2, 3 pts)
  • [PROJ-14] Story title (Epic: PROJ-12, P1, 5 pts)
  ...

Open questions logged as story comments:
  • [list any ⚠️ clarification flags]
```

Ask: "Would you like to refine any stories, add edge-case stories, or re-run this for another BRD?"
