import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema for the extraction stage output
# ---------------------------------------------------------------------------

class _RoleSchema(BaseModel):
    name: str = ""
    responsibility: str = ""
    keywords: List[str] = Field(default_factory=list)


class _StepProcedure(BaseModel):
    name: str = ""
    steps: List[str] = Field(default_factory=list)


class _FieldDescription(BaseModel):
    field: str = ""
    description: str = ""


class _ExtractionResult(BaseModel):
    document_title: str = ""  # always required; never null
    product_name: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    roles: List[_RoleSchema] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    domain_terms: List[str] = Field(default_factory=list)
    key_features: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    step_by_step_procedures: List[_StepProcedure] = Field(default_factory=list)
    notifications: List[str] = Field(default_factory=list)
    business_rules: List[str] = Field(default_factory=list)
    field_descriptions: List[_FieldDescription] = Field(default_factory=list)


def _extract_first_json_object(text: str) -> Optional[str]:
    """Return the first balanced ``{...}`` substring inside ``text``."""
    if not text:
        return None
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i + 1]
    return None


def _coerce_to_extraction(raw: Any) -> Dict[str, Any]:
    """Best-effort parse + validate. Always returns a normalized dict that
    satisfies _ExtractionResult, even if the input is broken.
    """
    if isinstance(raw, dict):
        try:
            return _ExtractionResult(**raw).model_dump()
        except ValidationError:
            pass

    if isinstance(raw, str):
        text = raw.strip()
        # Try direct JSON parse
        try:
            parsed = json.loads(text)
            return _ExtractionResult(**parsed).model_dump()
        except (json.JSONDecodeError, ValidationError):
            pass
        # Fallback: find the first balanced {...} block (handles cases
        # where the LLM wrapped JSON in ``` fences or prose).
        block = _extract_first_json_object(text)
        if block:
            try:
                parsed = json.loads(block)
                return _ExtractionResult(**parsed).model_dump()
            except (json.JSONDecodeError, ValidationError):
                pass

    logger.warning(
        "extraction_json could not be parsed; falling back to empty schema. "
        "raw type=%s", type(raw).__name__,
    )
    return _ExtractionResult().model_dump()


def _validate_extraction_callback(callback_context: Any) -> None:
    """ADK after_agent_callback that hardens ``extraction_json`` in state.

    Without this hook a malformed LLM JSON output would silently corrupt
    every downstream stage. We always coerce the value to a normalized
    dict that downstream agents can rely on, and re-serialize as JSON
    string so prompt placeholders embed predictably.
    """
    state = getattr(callback_context, "state", None)
    if state is None:
        return None
    raw = state.get("extraction_json")
    normalized = _coerce_to_extraction(raw)
    # Enforce non-empty document_title. If the LLM omitted it, derive one
    # from project_name (seeded into state before the pipeline runs).
    title = (normalized.get("document_title") or "").strip()
    if not title:
        project_name = (state.get("project_name") or "").strip()
        fallback = re.sub(r"[_\-]+", " ", project_name).strip() if project_name else "User Manual"
        normalized["document_title"] = fallback
        logger.warning(
            "extraction_agent returned no document_title; using fallback=%r", fallback,
        )
        title = fallback

    state["extraction_json"] = json.dumps(normalized, ensure_ascii=False)
    state["extraction_data"] = normalized  # convenience for tools
    role_count = len(normalized.get("roles") or [])
    logger.info(
        "extraction validated: title=%r roles=%d workflows=%d terms=%d",
        title, role_count,
        len(normalized.get("workflows") or []),
        len(normalized.get("domain_terms") or []),
    )
    return None


INFORMATION_EXTRACTION_INSTRUCTION = """
PERSONA: You are the Analyst stage of a USER MANUAL WRITER pipeline. Your
sole job is to read the unified source corpus and extract a faithful,
structured representation that downstream User Manual Writer stages will
use to author the manual.

ANTI-HALLUCINATION RULES (NON-NEGOTIABLE):
- Use ONLY information present in `{raw_corpus?}`. Never invent product
  names, roles, workflows, or capabilities that are not stated or
  unmistakably implied by the corpus.
- If something is not in the corpus, return null or an empty list. NEVER
  guess.
- Do NOT use general world knowledge to fill gaps.
- Do NOT mention file names or document titles from the corpus.

INPUTS YOU CAN READ (from session state, may be empty):
- `{raw_corpus?}` – aggregated text from all source documents.
- `{has_figma_designs?}` – bool, true if any UI/Figma/screenshot images exist.
- `{has_architecture_diagrams?}` – bool, true if any architecture diagrams exist.
- `{project_name?}` – the user-supplied project name. Treat this ONLY as
  a workspace label / filing identifier supplied by the requester. It is
  NOT the title of the user manual. DO NOT copy it verbatim into
  `document_title`. DO NOT use it as a seed, anchor, prefix, or suffix
  for the title. Ignore it entirely when inferring `document_title`
  unless the corpus is completely empty (see fallback rule below).

TASKS:
1. Infer the DOCUMENT TITLE for the user manual. The title:
   - Is MANDATORY. NEVER return null, empty string, or omit this field.
   - Must be 3 to 9 words.
   - Must be derived STRICTLY from the corpus content – the actual
     product name, feature name, capability, or subject the corpus
     describes. Read the corpus and name what the product DOES for the
     end user.
   - Concise – no filler such as "Documentation", "Overview", "Manual",
     "System Documentation", "User Guide for", "Details".
   - Meaningful – capability- or outcome-driven (e.g.
     "Auto-pay-CC Automated Credit Card Payments",
     "PESP: Petroleum Engineering Workflow Platform",
     "Wegaum: AI-Driven User Manual Generator").
   - Unique-feeling – avoid generic placeholders.
   - NEVER use `project_name` as the title or include it in the title.
     `project_name` is a filing label only; it must NOT appear in
     `document_title`.
   - If a product name / feature name appears in the corpus, use it.
   - FALLBACK ONLY: if and only if the corpus has zero usable content
     from which a title can be inferred, AND `project_name` is supplied,
     you may return `project_name` verbatim as a last-resort fallback.
     In every other situation prefer a corpus-derived title.
2. Infer the overall PURPOSE / OBJECTIVE.
3. Identify the explicit PRODUCT / SYSTEM name if present (else null).
4. Identify the SCOPE / KEY CAPABILITIES.
5. Identify USER ROLES and their responsibilities. For each role, generate
   3 to 6 lower-case role-specific keywords drawn from the corpus that will
   help match this role to UI/screenshot images later (e.g. for an
   "Approver" role you might emit ["approval", "review", "decision",
   "status", "dashboard"]). If `has_figma_designs` is false, emit an empty
   keyword list.
6. Identify KEY WORKFLOWS / ACTIONS (high-level workflow names only, not
   individual steps — steps go in step_by_step_procedures below).
7. Identify CONSTRAINTS / ASSUMPTIONS.
8. Extract DOMAIN TERMS suitable for a glossary (abbreviations, technical
   terms, product-specific vocabulary).
9. Extract KEY FEATURES – a list of distinct capability statements
   (e.g. "Schedule automatic payments on a chosen day each month",
   "Supports Visa, Mastercard, and Amex credit cards"). Each feature must
   be a complete, end-user-friendly sentence drawn directly from the corpus.
   Target 5–12 items; return [] if none are grounded.
10. Extract PREREQUISITES – everything a user needs before they can use the
    system: access requirements, eligibility criteria, account setup, browser
    requirements, required permissions, linked accounts. Each item is a
    plain-text sentence. Return [] if nothing is stated.
11. Extract STEP-BY-STEP PROCEDURES – for every distinct workflow or task
    named in the corpus, produce an entry with a short `name` and an ordered
    `steps` list. Each step is a short imperative sentence (e.g. "Click Save").
    Capture ALL procedures mentioned, even if steps are implied rather than
    numbered. Return [] if the corpus contains no procedural content.
12. Extract NOTIFICATIONS – every system notification, email alert, SMS
    message, in-app confirmation, or status update mentioned in the corpus.
    Describe each as an end-user-visible message or trigger (e.g. "Confirmation
    email sent when auto-pay is set up", "Payment failure alert sent if card
    is declined"). Return [] if none are mentioned.
13. Extract BUSINESS RULES – validation rules, payment limits, thresholds,
    conditions, eligibility rules, cutoff times, and any "if … then …" logic
    stated in the corpus. Each rule is a plain-text sentence. Return [] if
    none are grounded.
14. Extract FIELD DESCRIPTIONS – every named UI field, form input, or
    configuration option mentioned in the corpus. For each, provide its
    `field` name and a short `description` of what it controls or means
    (e.g. {"field": "Payment Amount", "description": "The amount to be paid
    automatically; options include full balance, minimum due, or a fixed
    amount"}). Return [] if no field-level details exist in the corpus.

STRICT OUTPUT (JSON ONLY, NO PROSE, NO CODE FENCES):

{
  "document_title": "<REQUIRED – always a non-empty string, never null>",
  "product_name": "... or null",
  "purpose": "... or null",
  "scope": "... or null",
  "roles": [
    {"name": "...", "responsibility": "...", "keywords": ["..."]}
  ],
  "workflows": ["..."],
  "constraints": ["..."],
  "domain_terms": ["..."],
  "key_features": ["..."],
  "prerequisites": ["..."],
  "step_by_step_procedures": [
    {"name": "...", "steps": ["Step 1 ...", "Step 2 ..."]}
  ],
  "notifications": ["..."],
  "business_rules": ["..."],
  "field_descriptions": [
    {"field": "...", "description": "..."}
  ]
}

If a field has no grounding, return null or [] — EXCEPT document_title
which MUST always be a non-empty string.
Return ONLY valid JSON.
"""

extraction_agent = LlmAgent(
    name="information_extraction_agent",
    model=os.getenv("GEMINI_MODEL"),
    description="Extracts grounded structured information from the aggregated corpus.",
    instruction=INFORMATION_EXTRACTION_INSTRUCTION,
    output_key="extraction_json",
    after_agent_callback=_validate_extraction_callback,
)
