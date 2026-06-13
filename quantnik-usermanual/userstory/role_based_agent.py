"""Role-based section writer.

The previous version of this agent re-scanned the local /data folder and used
a hardcoded Rocket.Chat keyword map. That broke for any deployment where
images come from SharePoint or Confluence, and biased relevance scoring for
non-chat products. This version:

1. Reads the already-extracted, classified images from session state.
2. Uses dynamic role keywords supplied by the extraction stage.
3. Selects at most one image per role using a pure relevance score.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext


GENERIC_TERMS = ["workflow", "screenshot", "ui", "screen", "page"]
SCORE_THRESHOLD = float(os.getenv("ROLE_IMAGE_SCORE_THRESHOLD", "1.5"))
MAX_IMAGES_PER_ROLE = int(os.getenv("ROLE_IMAGES_MAX", "1"))


def _tok(s: str) -> str:
    return (s or "").strip().lower()


def _hits(text: str, terms: List[str]) -> int:
    t = _tok(text)
    if not t:
        return 0
    n = 0
    for k in terms:
        k = _tok(k)
        if not k:
            continue
        if re.search(rf"\b{re.escape(k)}\b", t) or k in t:
            n += 1
    return n


def _build_role_terms(role_name: str, provided_keywords: str) -> List[str]:
    seeds: List[str] = [_tok(role_name)]
    if provided_keywords:
        seeds.extend([_tok(x) for x in re.split(r"[,;]", provided_keywords) if x.strip()])
    seeds.extend(GENERIC_TERMS)
    seen = set()
    out: List[str] = []
    for w in seeds:
        if w and w not in seen:
            out.append(w)
            seen.add(w)
    return out


def get_role_images(role_name: str, keywords: str, tool_context: ToolContext) -> str:
    """Pick up to MAX_IMAGES_PER_ROLE images that best match the given role.

    Reads the pre-classified image list from session state. Considers only
    images of category 'figma' or 'screenshot' so role sections never end up
    with an architecture diagram.
    """
    state = tool_context.state if tool_context is not None else {}
    all_images: List[Dict[str, Any]] = list(state.get("images") or [])
    candidate_images = [i for i in all_images if i.get("category") in {"figma", "screenshot"}]

    role_terms = _build_role_terms(role_name, keywords)

    scored: List[Dict[str, Any]] = []
    for img in candidate_images:
        src_doc = _tok(img.get("source_document"))
        fname = _tok(img.get("filename") or Path(img.get("path", "")).name)
        caption = _tok(img.get("caption"))
        description = _tok(img.get("description"))

        # The Vision-generated `description` (when present) is the strongest
        # semantic signal because filenames like "abc_p3_i2.png" carry none.
        score = 0.0
        score += 1.2 * _hits(fname, role_terms)
        score += 1.0 * _hits(src_doc, role_terms)
        score += 0.7 * _hits(caption, role_terms)
        score += 1.4 * _hits(description, role_terms)
        if img.get("category") == "figma":
            score += 0.25

        if score >= SCORE_THRESHOLD:
            scored.append({
                "path": img.get("path"),
                "filename": Path(img.get("path", "")).name,
                "source_document": img.get("source_document"),
                "caption": img.get("caption"),
                "description": img.get("description"),
                "category": img.get("category"),
                "score": round(score, 2),
            })

    scored.sort(key=lambda x: (x.get("score", 0.0), x.get("category") == "figma"), reverse=True)
    topk = scored[:MAX_IMAGES_PER_ROLE]

    if "role_images" not in state:
        state["role_images"] = {}
    state["role_images"][role_name] = topk

    return json.dumps({
        "status": "success",
        "role": role_name,
        "images_found": len(topk),
        "candidates_considered": len(candidate_images),
        "threshold": SCORE_THRESHOLD,
        "images": topk,
    })


ROLE_BASED_AGENT_INSTRUCTION = """
PERSONA: You are a USER MANUAL WRITER. You write the role-specific
sections of the user manual. Stay grounded in the extracted facts; never
invent responsibilities, steps, or screens.

INPUTS (FROM SESSION STATE):
- `{extraction_json?}` – contains:
  - `roles`: array with `name`, `responsibility`, and `keywords`.
  - `step_by_step_procedures`: array of {name, steps[]} for each workflow.
  - `business_rules`: list of rules/constraints applicable to users.
  - `notifications`: list of system notifications/alerts.
  - `field_descriptions`: list of {field, description} form field details.

PROCESS:
For EACH role in `extraction_json.roles`:
1. Call `get_role_images(role_name, keywords)` exactly once. Pass the
   role's keywords as a comma-separated string. The tool returns the
   most-relevant image (if any) for this role.
2. Identify which `step_by_step_procedures` are relevant to this role
   (use the role's `responsibility` and `keywords` as a guide). Include
   ALL matching procedures in the "How to Use" section.
3. Identify which `notifications` are relevant to this role and include
   them in the "Notifications & Alerts" sub-section.
4. Identify which `field_descriptions` are relevant to this role and
   include them in the "Key Fields" sub-section if any exist.
5. Identify which `business_rules` apply to this role and include them
   in the "Important Rules & Limits" sub-section if any exist.
6. Compose the role's section using ONLY information present in the
   extraction.

OUTPUT FORMAT (MARKDOWN — repeat for every role, separated by a blank
line followed by `---` followed by a blank line):

### <Role Name>

#### Key Responsibilities
- Responsibility 1
- Responsibility 2

#### How to Use (Step by Step)
[For each relevant step_by_step_procedure, write:]
**<Procedure Name>**
1. Step one
2. Step two
3. Step three

[If no procedures are available for this role, write 3–5 general steps
derived from the role's responsibility and extraction workflows.]

[IF the tool reported images_found > 0]
![<Role Name> screen](<absolute path returned by the tool>)

#### Key Fields
[Only include this sub-section if field_descriptions has items relevant to this role.]
| Field | Description |
| --- | --- |
| <Field Name> | <Description> |

#### Notifications & Alerts
[Only include this sub-section if notifications has items relevant to this role.]
- Notification 1
- Notification 2

#### Important Rules & Limits
[Only include this sub-section if business_rules has items relevant to this role.]
- Rule 1
- Rule 2

#### System Workflow
Brief description of how this role fits into the overall system workflow,
grounded in the extraction.

---

STRICT RULES:
- Use proper Markdown headings: `###` for the role name and `####` for
  all sub-sections. Do NOT use bold labels as headings.
- Insert the image AFTER the "How to Use" section ONLY when images_found > 0.
- Use the EXACT `path` returned by the tool.
- OMIT the "Key Fields", "Notifications & Alerts", and "Important Rules &
  Limits" sub-sections entirely if no relevant content exists for that role.
- Do NOT invent or include any image other than the one returned by the tool.
- Do NOT add extra sections, summaries, or commentary outside this template.
- Render every role from the extraction. Skip a role only if its
  responsibility text is empty/null.
"""

role_based_agent = LlmAgent(
    name="role_based_section_agent",
    model=os.getenv("GEMINI_MODEL"),
    description="Writes role-specific user manual sections, embedding one relevant UI image per role when available.",
    instruction=ROLE_BASED_AGENT_INSTRUCTION,
    tools=[get_role_images],
    output_key="role_sections",
)
