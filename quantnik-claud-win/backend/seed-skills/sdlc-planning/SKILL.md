---
name: sdlc-planning
description: Generates a Business Requirements Document (BRD) in Agile style from a transcript, requirement doc, or rough idea. **On invocation the skill first asks the user to either upload a source document (via the Files tab → uploads/) or paste a paragraph/transcript directly into chat** — it never silently makes one up. Produces all standard BRD sections: executive summary, scope, background, objectives, requirements (functional + non-functional), assumptions, constraints, risks, RACI, and glossary.
---

When this skill is invoked, produce a complete Business Requirements Document (BRD) in markdown format based on whatever input the user provides — a transcript, a requirements document, a rough idea, a conversation summary, or one or more **uploaded files**. **Never generate a BRD from thin air** — without explicit source material the document would be pure hallucination. Step 0 enforces this.

## Step 0 — Check for input; if none, request it (mandatory)

Before drafting anything, scan for source material:

1. **Uploads folder** — `Glob` the project's `uploads/` (sibling of cwd if needed): patterns `uploads/*` and `../uploads/*`. Anything present here is auto-eligible source.
2. **Chat-context text** — if the user pasted a paragraph, transcript, requirements doc, or email thread in the same message that invoked the skill, treat that as input.
3. **Prior assistant context** — if a *very recent* (within the same turn) assistant message produced a coherent description to BRD-ify (e.g. user typed `/sdlc-planning` after pasting a summary in the previous turn), include that as candidate input but flag it in the digest.

**If steps 1–3 yield NOTHING**, halt and emit this exact prompt (don't proceed to drafting):

```
📝 sdlc-planning — source material required

I need something to base the BRD on. Pick one:

  ① UPLOAD a document
     Click the 📎 attach button in the chat composer (or drag a file in)
     Supported: .txt · .md · .pdf · .doc · .docx · .png · .jpg · .gif · .webp
     The file will land in this project's uploads/ folder and I'll pick it up.

  ② PASTE a paragraph
     Drop a paragraph, transcript, idea, or email thread directly into chat
     — anything from one sentence to several pages of text is fine.

Re-send `/sdlc-planning` once you've done either (or both — they combine).
```

Do not call any other tool, do not write a placeholder BRD, do not invent content. Wait for the user's next message.

When the user replies with EITHER an upload OR paste OR both, restart this skill and re-enter Step 0; this time uploads/ + chat text will be populated and the skill proceeds to Step 1 (ingest).

## Step 1 — Input handling

Accept any of these input forms (one or several at once):

- Pasted text (transcript, requirements, idea, email thread)
- One or more files in `uploads/` (auto-detected) OR explicit **file paths** the user shares
- A mix of pasted text plus files

If the user referenced an attachment without a path (e.g. "I uploaded a PDF" but `uploads/` is empty), ask:

> "I don't see a file in this project's `uploads/` directory. Did the upload finish? You can also paste the file's absolute path here, or paste the text directly into chat. Supported types: txt, md, pdf, doc, docx, and images (png/jpg/gif/webp)."

When file paths are provided, ingest **every file before** generating the BRD:

| File type | How to ingest |
|-----------|---------------|
| `.txt`, `.md`, any plain text | Use the `Read` tool — content is returned as-is. |
| `.pdf` | Use the `Read` tool. For PDFs longer than 10 pages, paginate with the `pages` parameter (max 20 pages per call) and repeat until the file is fully read. |
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | Use the `Read` tool — the image is presented to you visually. Extract any visible text, wireframes, flow charts, screenshots, sticky notes, and annotations into structured input. |
| `.docx` | Convert first, then read. Try in this order:<br>1. `textutil -convert txt "<path>" -output /tmp/_sdlc_input_<n>.txt` (macOS, built-in)<br>2. `pandoc "<path>" -t plain -o /tmp/_sdlc_input_<n>.txt`<br>Then `Read` the converted file. |
| `.doc` (legacy Word) | Same conversion path as `.docx` — `textutil` handles both. |

If a file path is invalid, unreadable, or conversion fails, stop and report the specific error to the user before generating anything. Do not silently skip files.

Before drafting the BRD, print a one-paragraph **input digest** so the user can spot misreads:

```
Input received:
  • <file1.pdf>     — <one-line summary of what was extracted>
  • <wireframe.png> — <what was visible in the image>
  • <pasted text>   — <topic in one line>
```

Combine all extracted content as the unified input that drives the BRD.

## Behavior rules

- Follow Agile methodology: frame requirements as outcomes, write business requirements in a way that can be decomposed into epics/user stories, and keep success criteria measurable.
- If the user provides input, extract and infer as much as possible from it before generating.
- For any section where insufficient information was provided, still populate it using your best judgment based on the context. Immediately after that section, insert this disclaimer block:

> ⚠️ **AI Generated — Needs Review**
> This section was inferred by AI and has not been validated by a stakeholder. Please review and update before sign-off.

- Never leave a section blank or skip it. Every section must appear in the final document.
- Write in clear, professional business language — avoid jargon unless it is defined in the Glossary.
- Use tables where they add clarity (RACI, risks, glossary).

---

## Output structure

Produce the BRD in this exact order:

---

# Business Requirements Document
**Project:** [infer from input]
**Version:** 1.0 — Draft
**Date:** [today's date]
**Prepared by:** [leave blank or infer if mentioned]
**Status:** Draft

---

### 1. Executive Summary
One to three paragraphs. What is being built, why it matters, and what outcome is expected. Written for a non-technical executive audience.

---

### 2. Background & Current State
Describe the problem or opportunity. What is the current process or system? What pain points, gaps, or market pressures are driving this initiative?

---

### 3. Business Objectives & Success Criteria
List 3–7 measurable business objectives. For each, provide at least one KPI or acceptance criterion that can be tracked in an Agile context (e.g. OKR-style or definition of done).

| # | Objective | Success Criteria |
|---|-----------|-----------------|
| 1 | ... | ... |

---

### 4. Scope

#### 4.1 In Scope
Bulleted list of what is explicitly included in this initiative.

#### 4.2 Out of Scope
Bulleted list of what is explicitly excluded, with a one-line reason for each where possible.

---

### 5. Business Requirements
Numbered list of functional business requirements. Each requirement must:
- Be written from a business perspective (not technical)
- Be testable and traceable
- Follow the format: **BR-[n]: [Requirement statement]**

Group related requirements under sub-headings if helpful.

---

### 6. Non-Functional Requirements
Cover: performance, security, scalability, availability/uptime, compliance/regulatory, accessibility, and usability. Use the format **NFR-[n]: [Requirement]**.

---

### 7. Assumptions
Bulleted list of conditions assumed to be true for this document to hold. Flag assumptions that carry high risk if wrong.

---

### 8. Constraints
Bulleted list of fixed limitations: budget, timeline, technology, regulatory, resource, or organisational constraints.

---

### 9. Risks
| Risk ID | Description | Likelihood (H/M/L) | Impact (H/M/L) | Mitigation |
|---------|-------------|-------------------|----------------|------------|
| R-01 | ... | ... | ... | ... |

List at least 5 risks. Include both business and delivery risks.

---

### 10. RACI Matrix
List the key activities or decision points for this initiative and assign Responsible, Accountable, Consulted, and Informed roles. Infer likely roles (e.g. Product Owner, Business Analyst, Tech Lead, QA, Stakeholder, Delivery Manager) if not specified.

| Activity | Responsible | Accountable | Consulted | Informed |
|----------|-------------|-------------|-----------|----------|
| ... | ... | ... | ... | ... |

---

### 11. Glossary & Definitions
| Term | Definition |
|------|------------|
| ... | ... |

Define all domain-specific terms, acronyms, and abbreviations used in the document.

---

## After producing the document

### Upload to Confluence

**Target space is non-negotiable when `quantnik.json` is present.** Before discovering anything, `Read` `.claude/quantnik.json` at the project cwd. If it exists and has `atlassian.confluenceSpaceKey` or `atlassian.confluenceSpaceId`, use **exactly that** as the target space — do **not** call `getConfluenceSpaces` and pick "first personal space" or anything else. The quantnik project's owner has explicitly chosen this scope; overriding it writes the BRD to the wrong place. If the sidecar is missing or silent on the space, fall back to the user-named space (questionnaire answer) and finally to the personal space.

After the BRD markdown is finalized, upload it to Confluence. **Always print the page URL** when the upload succeeds — that line is mandatory output, not optional. There are two MCP shapes the agent might encounter; use whichever is available in this session:

**Shape A — generic REST passthrough (quantnik stdio servers, current setup):**

Available tools: `mcp__Confluence__conf_get`, `mcp__Confluence__conf_post`. The site URL is `https://<ATLASSIAN_SITE_NAME>.atlassian.net` (look at env var or ask the user once if unclear).

1. Discover the target space:
   - **quantnik.json wins.** Use `atlassian.confluenceSpaceKey` from the sidecar; resolve its `id` via `mcp__Confluence__conf_get` with path `/wiki/api/v2/spaces?keys=<KEY>`.
   - Fallback only if the sidecar is silent.
2. Convert the BRD markdown to Confluence storage HTML (basic mapping: `#`/`##`/`###` → `<h1>`/`<h2>`/`<h3>`, `**bold**` → `<strong>`, tables → `<table>...`, paragraphs → `<p>`, fenced code → `<pre><code>`). Wrap each blockquote callout (the "AI Generated — Needs Review" panels) in `<div data-type="panel-warning"><p>...</p></div>`.
3. **Body-size-aware publish.** Measure the storage-HTML length. The stdio MCPs (`mcp__Confluence__conf_post`) reliably wedge on payloads above ~30 KB because the spawned subprocess buffers the whole JSON request in its own pipe and the host's 180s watchdog (300s if you bumped `MCP_TOOL_TIMEOUT_MS` in `.env`) trips before Atlassian responds. Branch:

   - **Small body (≤ 30 KB):** call `mcp__Confluence__conf_post` with path `/wiki/api/v2/pages` and the standard JSON body.

   - **Large body (> 30 KB):** **bypass the stdio MCP** and POST directly via `Bash` + `curl`. Write the JSON body to a temp file first (avoids shell-quoting issues with large HTML), then:
     ```
     curl -s -X POST "https://<SITE>.atlassian.net/wiki/api/v2/pages" \
       -u "$MCP_ATLASSIAN_EMAIL:$MCP_ATLASSIAN_TOKEN" \
       -H "Content-Type: application/json" \
       -H "Accept: application/json" \
       --data-binary @<temp-body.json>
     ```
     `MCP_ATLASSIAN_EMAIL` + `MCP_ATLASSIAN_TOKEN` are already in the quantnik `.env`. The curl path doesn't traverse the stdio subprocess so it isn't subject to the same buffering wedge.

   Body for both paths:
   ```json
   {
     "spaceId": "<resolved-id>",
     "status": "current",
     "title": "<Project Name> — Business Requirements Document",
     "body": { "representation": "storage", "value": "<the HTML>" }
   }
   ```

4. Build the page URL: `https://<ATLASSIAN_SITE_NAME>.atlassian.net/wiki` + the response's `_links.webui`. If `_links.webui` isn't in the response, fall back to `https://<ATLASSIAN_SITE_NAME>.atlassian.net/wiki/pages/viewpage.action?pageId=<response.id>`.

5. **Apply the project's labels** (mandatory for the dashboard's per-project filtering). Read `atlassian.labels` from `quantnik.json`; for every label, POST to `/wiki/rest/api/content/<pageId>/label` with body `[{"prefix":"global","name":"<label>"}]`. Use the same MCP/curl branch by body size — labels are small, the MCP works fine.

**Shape B — claude.ai-managed Atlassian connector (Claude Code with claude.ai OAuth):**

1. Call `mcp__claude_ai_Atlassian__getAccessibleAtlassianResources` for the `cloudId`.
2. Pick the space (user-named, resolved via `getConfluenceSpaces`; else personal).
3. Call `mcp__claude_ai_Atlassian__createConfluencePage` with `cloudId`, `spaceId`, `title`, `contentFormat: "markdown"`, `body` = the full BRD markdown.
4. URL = `https://<site>.atlassian.net/wiki` + response's `_links.webui` (or `<response._links.base><_links.webui>` if `base` is absolute).

**No-MCP fallback:** if neither shape is available, skip the upload, note "offline mode — BRD saved as local markdown only," and proceed to the closing prompt.

**Final output line (mandatory on success):**

```
✅ BRD published to Confluence: <url>
```

Print it on its own line at the very end of the response, after any summary text. If the upload fails, print the error verbatim plus the local markdown file path so the user has something to fall back to.

### Closing prompt

Ask the user: "Would you like me to refine any section, add more detail, or convert the business requirements into Agile epics and user stories?"
