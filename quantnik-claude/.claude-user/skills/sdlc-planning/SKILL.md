---
name: sdlc-planning
description: Generates a Business Requirements Document (BRD) in Agile style from a transcript, requirement doc, or rough idea. Produces all standard BRD sections: executive summary, scope, background, objectives, requirements (functional + non-functional), assumptions, constraints, risks, RACI, and glossary.
---

When this skill is invoked, produce a complete Business Requirements Document (BRD) in markdown format based on whatever input the user provides — a transcript, a requirements document, a rough idea, a conversation summary, or one or more **uploaded files** (see "Input handling" below).

## Input handling

Accept any of these input forms (one or several at once):

- Pasted text (transcript, requirements, idea, email thread)
- One or more **file paths** the user shares, in any of these formats:
  `.txt`, `.md`, `.pdf`, `.doc`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
- A mix of pasted text plus file paths

If the user did not paste anything but referenced an attachment without a path (e.g. "I uploaded a PDF"), ask:

> "Please share the absolute path(s) to the file(s) you'd like me to use as input. Supported types: txt, md, pdf, doc, docx, and images (png/jpg/gif/webp). You can list multiple paths."

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

Ask the user: "Would you like me to refine any section, add more detail, or convert the business requirements into Agile epics and user stories?"
