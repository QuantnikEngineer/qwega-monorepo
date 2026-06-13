---
name: test-case-generator
description: Generates test cases from Jira Epics and User Stories and writes them back to the same Jira project. Supports five types — functional, non-functional, boundary-negative, system-architecture, and Gherkin (positive + boundary). Pulls source issues via the Atlassian MCP, creates a Test issue (or Sub-task fallback) per generated test case, and links it to the source story via a "Tests" link. Use when the user asks for "test cases", "TCs", "test scenarios", or "gherkin tests" against existing Jira stories.
---

# test-case-generator

Generates test cases for existing Jira Epics and User Stories — typically the ones produced by the `user-stories` skill.

## Inputs you must collect before generating

Ask the user for any of these that are missing — do not assume.

1. **Source issues** — one of:
   - A single Jira issue key (e.g. `PROJ-123`)
   - A JQL query (e.g. `project = PROJ AND type in (Epic, Story) AND created >= -7d`)
   - A Jira project key + scope phrase ("all open stories in PROJ")
2. **Test case type** — one or more of:
   - `functional` — happy-path verifications, one or more TCs per acceptance criterion
   - `non-functional` — performance, security, usability, accessibility, scalability, reliability — with measurable thresholds
   - `boundary-negative` — boundary values (min, max, just below/above) plus invalid inputs / error paths
   - `system-architecture` — integration and contract tests across components/services, including failure modes
   - `gherkin` — Given/When/Then scenarios covering positive paths and boundary edges
   - `all` — generate every type above

Present the test-case-type menu when the user hasn't specified — don't make them guess option names.

**Output is always Jira.** Every generated test case is created as a Jira issue in the same project as the source story and linked back to it. The skill picks the issue type automatically:

1. Prefer `Test` (or `Test Case`) if the project's issue type metadata includes it.
2. Otherwise fall back to `Sub-task` parented to the source story.
3. If neither is available, ask the user which existing issue type to use — never silently create a generic `Task`.

## Steps

1. **Resolve the project**
   - `mcp__claude_ai_Atlassian__getAccessibleAtlassianResources` → pick the cloud id
   - If the user gave only a project name, `getVisibleJiraProjects` to confirm the key

2. **Fetch source issues**
   - Single key → `getJiraIssue`
   - JQL or batch → `searchJiraIssuesUsingJql` (paginate if `>50`)
   - For each story, capture: summary, description, acceptance criteria (often in the description or a custom field), priority, components, labels, linked issues

3. **Resolve the target issue type** — call `getJiraProjectIssueTypesMetadata` for the project once. Pick `Test` / `Test Case` if present; else `Sub-task`; else stop and ask. Cache the choice for the whole run.

4. **Confirm scope** — print a short table of the stories that will be processed, the chosen test type(s), the resolved Jira issue type, and the projected new-issue count. Wait for explicit "go". For large batches (`>20 stories`) make the total count especially obvious.

5. **Generate test cases** using the templates below — one section per type per source story. Always include `Linked story: <KEY>` and reference the acceptance criterion text or number for traceability.

6. **Write output to Jira** for every generated TC:
   - `createJiraIssue` with:
     - `summary` = the TC `Title`
     - `description` = the full TC body in Atlassian Document Format (or wiki markup if ADF unavailable), preserving steps / examples / Gherkin formatting
     - `issuetype` = the resolved type from step 3 (if `Sub-task`, set `parent` to the source story key)
     - `priority` copied from source story when unset
     - `components` and `labels` copied from the source story; additionally tag with `label: test-case` and `label: tc-<type>` (e.g. `tc-functional`)
   - `createIssueLink` with `type=Tests` from the new TC to the source story (skip this for sub-tasks since the parent relationship already implies it)

7. **Report** — emit a final summary table: `Source story | Type | Count | New issue keys`. Include any failures with their error message and the TC that failed.

## Templates

### functional

For each acceptance criterion, emit one or more cases:

```
ID: TC-<KEY>-F<n>
Title: <one-line, ties to the AC>
Priority: High | Medium | Low
Preconditions:
  - <state required before the test>
Test steps:
  1. <action>
  2. <action>
Expected result: <observable outcome tied to the AC>
Linked story: <KEY>  (AC #<n> / "<short AC text>")
```

### non-functional

Cover applicable categories from: performance, security, usability, accessibility, scalability, reliability. Each TC must include a measurable target.

```
ID: TC-<KEY>-NF<n>
Category: performance | security | usability | accessibility | scalability | reliability
Title: <what is being measured>
Target: <quantitative threshold, e.g. "p95 latency < 500ms at 100 RPS for 5 min sustained">
Test approach: <method — load test, fuzz, audit, etc.>
Suggested tools: <k6, OWASP ZAP, axe, Lighthouse, Locust, etc.>
Linked story: <KEY>
```

### boundary-negative

For each input field / numeric or temporal parameter in the story:

```
ID: TC-<KEY>-B<n>
Input under test: <field name and type>
Boundary cases:
  - min valid: <value> → <expected>
  - max valid: <value> → <expected>
  - just below min: <value> → <expected error>
  - just above max: <value> → <expected error>
Negative cases:
  - invalid format: <value> → <expected error>
  - empty / null: → <expected error>
  - injection-style payload: <value> → <expected sanitisation or error>
Linked story: <KEY>
```

### system-architecture

```
ID: TC-<KEY>-SA<n>
Components: <serviceA> ↔ <serviceB> [↔ <serviceC>]
Scenario: <integration flow being verified>
Preconditions: <dependencies and state>
Steps:
  1. <cross-component action>
  2. <cross-component action>
Expected: <successful contract / interaction outcome>
Failure modes covered:
  - <e.g. serviceB returns 5xx>
  - <e.g. timeout / slow response>
  - <e.g. malformed payload from upstream>
Linked story: <KEY>
```

### gherkin

At minimum one positive scenario and one boundary scenario per AC. Use `Scenario Outline` + `Examples` for repeated input spaces. When writing to Markdown, fence the block with three backticks and the `gherkin` language tag.

```
Feature: <story title>
  As a <user role>
  I want <capability>
  So that <benefit>

  Background:
    Given <common precondition>

  Scenario: <positive case>
    Given <state>
    When <action>
    Then <observable outcome>

  Scenario Outline: <boundary case>
    Given <state with <input>>
    When <action>
    Then <expected for <result>>

    Examples:
      | input   | result      |
      | <min>   | <accepted>  |
      | <max>   | <accepted>  |
      | <min-1> | <rejected>  |
      | <max+1> | <rejected>  |
```

## Guardrails

- **No fabricated acceptance criteria.** If a source story has none, stop and ask the user whether to (a) skip it, (b) infer ACs from the description and confirm, or (c) abort.
- **Traceability is mandatory.** Every TC must reference the source story key and the AC text or number it covers.
- **Batch confirmation.** If the run will create more than 20 Jira issues, surface the total count and wait for "yes" before the first `createJiraIssue` call.
- **Idempotency.** Before creating a Jira TC, search for an existing issue with the same `summary` already linked to (or parented under) that story; if it exists, skip and note it in the report instead of duplicating.
- **Linking.** For `Test` / `Test Case` issue type, always `createIssueLink` with `type=Tests` from the TC to the source story. For `Sub-task`, the `parent` field is the link — do not add a redundant "Tests" link.
- **Component / label propagation.** Copy `components` and `labels` from the source story to the new TC so test filters and saved JQL queries continue to work. Always add `label: test-case` plus `label: tc-<type>`.
- **No local files.** Do not write a `.md` file as a fallback — if Jira creation fails, report the failure and the unsaved TC content in the chat so the user can decide. Local files defeat the point of having tests in the tracker.
