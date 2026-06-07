---
name: user-stories
description: Generates INVEST-compliant Agile user stories from a BRD stored in Confluence, then creates the Epics and Stories directly in Jira. Detects when a backlog for the initiative already exists and switches to **Update mode** — computing a diff against the new BRD, then applying updates, re-parents, closures, and additions instead of duplicating issues. Every story carries a MoSCoW label (`moscow-must` / `should` / `could` / `would`) so MVP scope is queryable.
---

When this skill is invoked, follow the steps below in strict order. Do not skip a step or move to the next until the current one is complete.

This skill supports **two Atlassian MCP shapes** — detect which one is loaded at session start and use the matching tool calls throughout:

- **Shape A (wega2 stdio):** generic REST verbs `mcp__Jira__jira_get/post/put/patch/delete` and `mcp__Confluence__conf_get/post/...`. The site URL is `https://<ATLASSIAN_SITE_NAME>.atlassian.net`; read it from env or ask once if unknown.
- **Shape B (claude.ai-managed):** discrete tools `mcp__claude_ai_Atlassian__atlassianUserInfo`, `getAccessibleAtlassianResources`, `getVisibleJiraProjects`, `getJiraProjectIssueTypesMetadata`, `createJiraIssue`, `searchConfluenceUsingCql`, `getConfluencePage`, etc.

If **neither** shape is loaded, stop and tell the user: "No Atlassian MCP is available in this session. Configure one (or run in a context that has it) before retrying."

---

## Step 0 — Resolve scope from `wega.json` (do this first)

`Read` `.claude/wega.json` at the project cwd. If present, treat as authoritative:
- `atlassian.jiraProjectKey` → the Jira project for all Epics/Stories created in this run. Do **not** prompt the user to pick from `getVisibleJiraProjects` if this is set.
- `atlassian.confluenceSpaceKey` / `confluenceSpaceId` → if Step 2 needs to read an existing BRD, scope the search to this space.
- `atlassian.siteName` / `siteUrl` → use when building browse URLs.
- `atlassian.labels` → the **initiative label** (e.g. `wega-project-faber`). Add this to every issue created or updated. It is also the predicate used in Step 4.5 to find an existing backlog.

If `wega.json` is absent, fall back to the previous flow (ask the user for project + initiative slug).

---

## Step 1 — Authenticate & discover the workspace

- **Shape A:** call `mcp__Jira__jira_get` with path `/rest/api/3/myself`. If it returns 200 with an account, you're in. The "site" is `ATLASSIAN_SITE_NAME` from env; the browse base is `https://<ATLASSIAN_SITE_NAME>.atlassian.net`. No `cloudId` needed for subsequent calls.
- **Shape B:** call `atlassianUserInfo`, then `getAccessibleAtlassianResources`. Extract `cloudId` — you'll pass it to every subsequent call.

---

## Step 2 — Find the BRD via the project's Confluence label

**The BRD is labelled.** The `sdlc-planning` skill tags every BRD it publishes with the project's `atlassian.labels` (e.g. `wega-project-faber`). That label — read from `wega.json` in Step 0 — is the authoritative selector. Do NOT do a generic CQL `title ~ "BRD"` search; that leaks across projects.

### 2.1 — Primary lookup (label-scoped CQL)

Build the CQL from the wega.json values:

```
space = "<atlassian.confluenceSpaceKey>"
  AND label in (<initiative-label-list, comma-separated quoted>)
  AND type = page
  AND (title ~ "BRD" OR title ~ "Business Requirements")
ORDER BY lastmodified DESC
```

- **Shape A:** `mcp__Confluence__conf_get` with path `/wiki/rest/api/content/search?cql=<encoded-cql>&limit=10&expand=version`.
- **Shape B:** `searchConfluenceUsingCql` with `cloudId` + the CQL.

Outcomes:
- **Exactly one match** → pick it. Tell the user *which* page (id + title + version) you chose so they can override if wrong.
- **Multiple matches** (e.g. several BRD revisions exist as separate pages) → pick the most-recently-modified, tell the user, and let them override.
- **Zero matches** → proceed to 2.2 (CQL label index has a known lag).

### 2.2 — Fallback (label-metadata scan)

Confluence's CQL search index can lag by minutes to ~an hour after a label is applied. If 2.1 returned nothing, list recent pages in the configured space and read each page's labels directly — this hits the page's metadata rather than the search index, so freshly-labelled BRDs land here:

1. `mcp__Confluence__conf_get` `/wiki/api/v2/spaces/<spaceId>/pages?limit=50&sort=-modified-date`
2. For each result, `mcp__Confluence__conf_get` `/wiki/api/v2/pages/<id>/labels?limit=50`
3. Keep pages whose label set intersects `wega.json.atlassian.labels`
4. Of those, prefer pages whose title matches `/BRD/i` or `/Business Requirements/i`
5. Pick the most-recent. Tell the user *which* page you chose and let them override.

### 2.3 — Hard stop

If neither 2.1 nor 2.2 finds anything labelled for this project, do NOT fall back to an unscoped search. Stop and tell the user:

> *"No BRD found for project `<initiative-label>` in Confluence space `<spaceKey>`. Either (a) run `/sdlc-planning` first to produce the BRD, or (b) manually tag the existing BRD with the `<initiative-label>` label in Confluence."*

Reasons this matters: cross-project BRD selection is the single biggest source of stories landing in the wrong Jira project, which corrupts the dashboard's per-project filtering and is painful to unwind. The label is the trust boundary.

---

## Step 3 — Fetch and parse the BRD

- **Shape A:** `mcp__Confluence__conf_get` with path `/wiki/api/v2/pages/<page-id>?body-format=storage`. Read the storage HTML body — its headings and tables map cleanly to BRD sections. Capture `version.number` and `version.createdAt` so Step 4.5 can detect "BRD has changed since last run".
- **Shape B:** `getConfluencePage` with `contentFormat: "markdown"`.

Extract:

- **Initiative / feature name** (from the page title or executive summary)
- **Personas / roles** (from stakeholder, user, or actor sections)
- **Functional requirements** (BR-n items or equivalent)
- **Non-functional requirements**
- **Scope** (in-scope / out-of-scope) — pay attention to "interim tooling" or "future release" callouts; those usually imply integration-handshake stories
- **Constraints and assumptions**
- **Change log** — if the BRD has one, the version-to-version notes are the strongest signal of what's changed and why. In Update mode, those notes drive the diff narrative.
- **MoSCoW / RTM table** — if the BRD has one, treat it as the authoritative MoSCoW classification per BR. Otherwise derive from BR criticality in Step 5.

Summarise what you extracted in 3–4 bullet points so the user can spot misreadings early.

---

## Step 4 — Select the Jira project

If `wega.json.atlassian.jiraProjectKey` is set, use it without prompting. Confirm Epic + Story issue types are supported:

- **Shape A:** `mcp__Jira__jira_get` with path `/rest/api/3/project/<KEY>?expand=issueTypes`.
- **Shape B:** `getJiraProjectIssueTypesMetadata` with `cloudId` and `projectIdOrKey`.

If `wega.json` does not set the project, list available projects and ask the user to pick.

If the project does not have Epic, use the highest-level available type as the grouping container and note this to the user.

---

## Step 4.5 — Detect existing backlog → choose **Create mode** vs **Update mode**

This is the gate between "first run" and "BRD has been updated" behaviour. Run a JQL query for the initiative label:

- **Shape A:** `mcp__Jira__jira_get` with path `/rest/api/3/search/jql`, query params `{"jql": "project = <KEY> AND labels = \"<initiative-slug>\" AND statusCategory != Done", "maxResults": "200", "fields": "summary,issuetype,parent,labels,status"}`.
- **Shape B:** the equivalent issue search call.

Use `jq` to project just key / summary / type / parent / labels / status to keep tokens cheap.

- **Zero results** → **Create mode**. Skip Step 6's diff section; you're writing a fresh backlog.
- **Non-zero results** → **Update mode**. Hold the existing-issue list in memory; Step 6 will compute the diff against it.

Also capture the transition IDs for the project (you'll need the "Done" transition in Update mode):
- `mcp__Jira__jira_get` `/rest/api/3/issue/<any-existing-key>/transitions` and find the `Done` transition's `id`.

Tell the user explicitly which mode you're entering before going further.

---

## Step 5 — Generate Epics and Stories (INVEST + MoSCoW)

Derive all Epics and User Stories from the BRD content. Every story **must** pass all six INVEST checks before being included:

| Principle | Check |
|-----------|-------|
| **I**ndependent | Can the story be developed and delivered without depending on another unfinished story? If not, restructure or split. |
| **N**egotiable | Is the story focused on *what* is needed (not *how*)? Remove implementation details from the story statement. |
| **V**aluable | Does the story deliver direct value to a named user or stakeholder? If not, merge it into a story that does. |
| **E**stimable | Is the story clear enough that the team can size it? If not, add detail or flag as needs-clarification. |
| **S**mall | Can the story be completed in a single sprint (≤ 8 story points)? If not, split into per-flow / per-state chunks; each split chunk should be independently shippable. |
| **T**estable | Does it have acceptance criteria that can be verified as pass/fail? Every story must have at least 3 AC items. |

### Story metadata (every story carries these)

- **User story statement:** `As a <persona>, I want <goal>, so that <measurable benefit>.`
- **≥ 3 Acceptance criteria** (Given/When/Then preferred)
- **Story points:** 1 / 2 / 3 / 5 / 8 — with a one-line rationale
- **Priority:** P1 Highest / P2 High / P3 Medium / P4 Low
- **MoSCoW label:** exactly one of `moscow-must` / `moscow-should` / `moscow-could` / `moscow-would`
- **Initiative label:** the project label from `wega.json.atlassian.labels` (e.g. `wega-project-faber`)
- **Domain labels:** category-specific tags (e.g. `mdm`, `integration`, `accessibility`, `migration`)
- **Source citation:** at the bottom of the description, cite the BR-n or NFR-n that drove the story. In Update mode, also cite the BRD version (e.g. "Source: BR-7 (BRD v1.1, SDD §2.9)").

### MoSCoW mapping rule

1. If the BRD has an explicit MoSCoW or RTM table, use it verbatim.
2. Otherwise derive:
   - Critical-path / regulatory / data-integrity / cutover-blocking BRs → **must**
   - Important but workaround-able BRs → **should**
   - "Nice to have" BRs the BRD itself flags as deferable → **could**
   - Aspirational scope explicitly out of MVP → **would**
3. MVP scope = `must` + `should` only. `could` + `would` defer to continuous improvement.

If the BRD calls out interim tooling that bridges MVP → future state (e.g. "uses L2 + Transporeon for MVP transport"), create integration-handshake stories for each interim system. They typically tag `moscow-must` because MVP cutover depends on them.

### Story-size guard

If a draft story exceeds **8 points**, split it before previewing. Common split axes:
- **Per-flow** (create / edit / publish / close / realise)
- **Per-channel** (web / portal / EDI / email)
- **Per-state-transition** (allocate / fulfil / settle / reverse)
- **Per-region** (when each region has its own e-invoicing / tax / compliance work)

Each split chunk should be ≤ 5 pts and independently shippable.

### Quantitative ACs for NFR stories

NFR stories (availability, throughput, latency, observability, accessibility) need **numbers**, not qualitative goals. Default targets if the BRD is silent:
- Latency p95: ≤ 2 s for interactive APIs
- Bulk throughput: explicit messages/min or records/min
- Queue depth + oldest-message-age alerts on async pipelines
- Availability: at least one digit of precision (e.g. 99.5 %) tied to a documented SLA baseline
- DR drill cadence + measured RTO / RPO

Flag these as "subject to platform-architect ratification" in the description so the team knows they're defensible defaults, not contractual commitments.

### Preview format

Show the user a readable markdown summary of every Epic and every Story. Use a compact table per Epic with columns: `#` · `Story` · `Pts` · `Pri` · `MoSCoW`. Flag INVEST violations only when not met (⚠️ with a one-line reason).

For stories that are ambiguous or inferred, append:
> ⚠️ **Needs clarification:** [specific question]
> ℹ️ **Inferred from context** (if not explicitly stated in BRD)

---

## Step 6 — Compute the diff (**Update mode**) or full preview (**Create mode**)

### Create mode
Display the full proposed Epic + Story list. Move to Step 7.

### Update mode
For every existing issue from Step 4.5 and every newly-derived story from Step 5, categorise the operation needed:

| Existing-vs-new comparison | Operation |
|--------------------------|-----------|
| BR already covered by an existing story, story wording still accurate | **No-op** |
| BR covered but story wording / ACs are stale | **Update**: PUT new summary / description / labels |
| BR expanded — existing story OK, but new aspect needs another story | **Add story** under the existing Epic |
| Existing story is under the wrong Epic in the new structure | **Re-parent**: PUT `parent` |
| Existing story doesn't map to any current BR or NFR | **Close as obsolete** with a clear comment |
| Existing Epic has no still-relevant children after re-parents | **Close Epic** (after children handled) |
| Entirely new BR with no existing coverage | **New Epic + stories** |

Then present the diff as a single numbered table the user can scan in one pass:

| # | Op | Target | What changes |
|---|----|--------|--------------|
| 1 | Update | WC-137 | Add customer-hierarchy AC |
| 2 | Re-parent | WC-150 | WC-132 → WC-129 |
| 3 | Close | WC-152 | Pool-deposit removed in BRD v1.1 |
| 4 | New Epic | — | Credit Control & Collections (BR-7) |
| 5 | New Story | (under new Credit Control epic) | Credit-limit setup per customer |
| ... | | | |

Then a one-line totals row: *N updates · M re-parents · K closes · X new epics · Y new stories*.

---

## Step 7 — Confirm with the user before writing

### Create mode
Display the compact table and ask: *"Shall I create these N epic(s) and M story/stories in Jira project [KEY]? Reply 'yes' to proceed, or tell me what to change first."*

### Update mode
Display the diff table and ask three sub-questions (use `AskUserQuestion` so the answers are structured):

1. **Obsolete handling**: close-with-comment / keep open with `deferred-by-brd-v<N>` label / leave alone
2. **MoSCoW tagging**: tag every new story / no tags
3. **Execution scope**: full plan / additions only / updates+closes only

If the user replies in free text, parse generously. A single "yes" or "go with recommended" means **close obsolete + MoSCoW-tag + full plan**.

Wait for confirmation. Do not write to Jira until the user confirms.

---

## Step 8 — Execute writes

### Operation ordering (matters!)

1. **Updates** (parallel) — change summary, description, labels, priority, points on existing issues.
2. **New Epic creations** (parallel) — capture every returned key.
3. **Re-parents** (parallel within constraints) — stories that point to an existing Epic can move first; stories that point to a newly-created Epic must wait for its key.
4. **New Story creations** (parallel within each Epic — Jira Cloud accepts parallel siblings under one parent).
5. **Closes** (last) — children must be re-parented or closed before their parent Epic; the parent Epic close should be the very last operation.

### Operation primitives

**Create (Epic or Story)** — Shape A:
```json
POST /rest/api/3/issue
{
  "fields": {
    "project": { "key": "<KEY>" },
    "issuetype": { "name": "Epic" | "Story" },
    "summary": "<title>",
    "description": <ADF document>,
    "priority": { "name": "<Highest|High|Medium|Low|Lowest>" },
    "labels": ["<initiative-slug>", "<domain-tag>", "moscow-must|should|could|would"],
    "parent": { "key": "<epic-key>" },          // Story only
    "customfield_10016": <story-points>          // Story only
  }
}
```

Shape B: `createJiraIssue` with `contentFormat: "markdown"`, `additional_fields: { priority, labels, customfield_10016 }`, and `parent: "<epic-key>"`.

**Update existing issue** — Shape A:
```json
PUT /rest/api/3/issue/<KEY>
{
  "fields": {
    "summary": "<new summary>",
    "description": <full new ADF document>,     // description is replaced atomically
    "priority": { "name": "..." },
    "customfield_10016": <new points>
  }
}
```
Only include fields you're changing. PUT is partial-update for the `fields` object on Jira issues.

**Update labels atomically** — Shape A:
```json
PUT /rest/api/3/issue/<KEY>
{ "update": { "labels": [ {"add": "moscow-must"}, {"remove": "moscow-should"} ] } }
```
Use `update.labels` (not `fields.labels`) when you want to add/remove a single tag without knowing the full label set. You can combine `update` and `fields` in one PUT.

**Re-parent** — Shape A:
```json
PUT /rest/api/3/issue/<KEY>
{ "fields": { "parent": { "key": "<new-epic-key>" } } }
```

**Close obsolete (with mandatory comment)** — Shape A:
```json
POST /rest/api/3/issue/<KEY>/transitions
{
  "transition": { "id": "<done-transition-id>" },
  "update": { "comment": [ { "add": { "body": <ADF doc with WHY> } } ] }
}
```
The comment is **mandatory** — say WHY the story is being closed (cite the BRD version, the change-log entry, or the removed-BR ID). Never silently close without an audit trail.

### ADF helper (Shape A only)

Shape A's `jira_post` requires the `description` field as an ADF document, not a markdown string. Build it like this for a story:

```json
{
  "type": "doc",
  "version": 1,
  "content": [
    { "type": "paragraph",
      "content": [
        { "type": "text", "text": "As a ", "marks": [] },
        { "type": "text", "text": "<persona>", "marks": [{ "type": "strong" }] },
        { "type": "text", "text": ", I want ", "marks": [] },
        { "type": "text", "text": "<goal>", "marks": [{ "type": "strong" }] },
        { "type": "text", "text": ", so that ", "marks": [] },
        { "type": "text", "text": "<benefit>", "marks": [{ "type": "strong" }] },
        { "type": "text", "text": "." }
      ]
    },
    { "type": "heading", "attrs": { "level": 3 }, "content": [{ "type": "text", "text": "Acceptance Criteria" }] },
    { "type": "bulletList", "content": [
      { "type": "listItem", "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Given <context>, when <action>, then <outcome>." }] }] }
    ]},
    { "type": "paragraph",
      "content": [{ "type": "text", "text": "Source: BR-<n> (BRD v<x.y>).", "marks": [{ "type": "em" }] }]
    }
  ]
}
```

If there are clarification flags, append another paragraph node starting with `⚠️ Needs clarification:`.

For Shape B (`contentFormat: "markdown"`) keep it simple markdown — let the SDK handle ADF conversion.

### Priority mapping

P1 → "Highest" • P2 → "High" • P3 → "Medium" • P4 → "Low"

---

## Step 9 — Report results (URLs are mandatory)

After every write, **print every affected issue with its full browse URL.** This is required output, not optional. The base URL is `https://<ATLASSIAN_SITE_NAME>.atlassian.net` (Shape A — read from env) or from `getAccessibleAtlassianResources` (Shape B).

### Create mode report
```
✅ Done. Created in Jira project <KEY>:

Epics:
  • [WC-129] Epic name → https://<site>.atlassian.net/browse/WC-129
  ...

Stories:
  • [WC-137] Story title (Epic: WC-129, P2, 3 pts, moscow-must) → https://<site>.atlassian.net/browse/WC-137
  ...

MoSCoW totals: <X> must / <Y> should / <Z> could / <W> would
```

### Update mode report
Group by operation, every line with the browse URL:

```
✅ Done. Updated in Jira project <KEY>:

🔄 Updated (N):
  • [WC-137] What changed → URL

🔀 Re-parented (M):
  • [WC-150] WC-132 → WC-129 → URL

❌ Closed as obsolete (K):
  • [WC-152] Why → URL

➕ New Epics (X):
  • [WC-173] Title → URL

➕ New Stories (Y):
  • [WC-184] Title (Epic: WC-173, P1, 3 pts, moscow-must) → URL

MoSCoW totals after this run: <X> must / <Y> should / <Z> could / <W> would
Operations: N updates · M re-parents · K closes · X new epics · Y new stories · 0 failures
```

If any operation failed, list the failures explicitly (issue key/summary + error message). Don't silently skip.

---

## Step 10 — Offer a refinement turn

After the report, offer specific refinements that frequently follow a first pass:
1. **Split oversized stories** (any > 8 pts) into per-flow chunks
2. **Promote MoSCoW** (`should → must` or `could → should`) for items the user wants in MVP
3. **Add quantitative targets** to qualitative NFR ACs (throughput, latency, queue depth, drill cadence)
4. **Add interim-tooling integration stories** (if the BRD names interim systems for MVP — those handshakes are real backlog)
5. **Retro-tag** older stories with MoSCoW labels if they were created before MoSCoW classification existed

When the user accepts a refinement, execute it as additional Update-mode operations (no need to re-run the full skill).
