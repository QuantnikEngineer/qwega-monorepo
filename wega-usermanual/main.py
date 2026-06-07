from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.errors.already_exists_error import AlreadyExistsError
from google.auth.exceptions import TransportError
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field, field_validator

from userstory.agent import root_agent
from userstory.confluence_tools import (
    confluence_page_exists,
    publish_manual_to_confluence,
)

# Configure structured logging for production observability. Each request
# correlates by ADK session_id which is included on most log lines.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger(__name__)

APP_TITLE = "Wegaum – User Manual Generator API"
APP_VERSION = "1.0.0"

APP_DESCRIPTION = """
AI-powered API that generates a comprehensive user manual from source documents and publishes it directly to **Confluence** as a native page.

## How It Works

1. Call **POST `/generate-manual`** with a source URL and a project name.
2. The pipeline reads all documents from the source.
3. A 3-stage AI agent pipeline (powered by **Google Gemini**) extracts, structures, and writes the manual in parallel; sections are assembled in Python.
4. The finished manual is published as a Confluence child page under the configured parent.
5. You get back the **Confluence page URL** in the response.

## Accepted Source URL Types

| Source | Example URL |
|--------|-------------|
| **SharePoint folder** | `https://tenant.sharepoint.com/sites/MySite/Shared Documents/MyFolder` |
| **SharePoint folder (browser view)** | `https://tenant.sharepoint.com/...AllItems.aspx?id=%2Fsites%2F...%2FMyFolder` |
| **Confluence page** | `https://tenant.atlassian.net/wiki/spaces/KEY/pages/12345678/Page+Title` |

> When a **SharePoint URL** is provided, all supported documents inside that folder are read.  
> When a **Confluence URL** is provided, that page and its direct children are read.

## Supported Document Types
| Type | Extensions |
|------|------------|
| Documents | `.pdf`, `.docx`, `.txt` |
| Spreadsheets | `.xls`, `.xlsx`, `.csv` |
| Presentations | `.pptx` |
| Data | `.json` |

## Project Name
The `project_name` field is **required**. It becomes the title of the published Confluence page and must be unique under the configured parent page. If a page with the same name already exists, the API returns **HTTP 409**.

## Prerequisites
The following must be configured as **environment variables** on the server:
- **SharePoint:** `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_TENANT_ID`
- **Confluence (output):** `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_PARENT_PAGE_ID`
- **Google AI:** `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL`
"""

tags_metadata = [
    {
        "name": "manuals",
        "description": "Generate and publish user manuals from SharePoint folders or Confluence pages.",
    },
    {
        "name": "health",
        "description": "Service health and readiness checks.",
    },
]

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================
# ADK Runner / Session Helpers
# =============================

APP_NAME = "wegaum"
DEFAULT_PROMPT = "generate user manual"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/outputs")).resolve()

# Serialize requests that mutate env vars for source config.
_pipeline_env_lock = asyncio.Lock()

# ── Concurrency / timeout admission control ─────────────────────────────────
# MAX_CONCURRENT_PIPELINES caps how many pipelines may be in flight at once.
# MAX_QUEUED_PIPELINES caps how many waiters may queue beyond that. Any
# request beyond (in-flight + queued) is rejected immediately with HTTP 429
# so callers fail fast instead of timing out at the load balancer.
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "3"))
MAX_QUEUED_PIPELINES = int(os.getenv("MAX_QUEUED_PIPELINES", "5"))
PIPELINE_TIMEOUT_SECS = int(os.getenv("PIPELINE_TIMEOUT_SECS", "900"))  # 15 min

_pipeline_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)
_inflight_count = 0
_queued_count = 0
_admission_lock = asyncio.Lock()


async def _acquire_admission() -> None:
    """Reserve a slot or raise HTTP 429 if too many requests are queued."""
    global _queued_count
    async with _admission_lock:
        if _queued_count >= MAX_QUEUED_PIPELINES and _pipeline_semaphore.locked():
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many concurrent manual-generation requests "
                    f"(max in-flight={MAX_CONCURRENT_PIPELINES}, "
                    f"max queued={MAX_QUEUED_PIPELINES}). "
                    "Please retry shortly."
                ),
            )
        _queued_count += 1


async def _release_queue() -> None:
    global _queued_count
    async with _admission_lock:
        if _queued_count > 0:
            _queued_count -= 1


def _is_confluence_url(url: str) -> bool:
    """Return True if the URL points to a Confluence page."""
    u = url.lower()
    return "atlassian.net/wiki" in u or "/wiki/spaces/" in u


# ── Markdown post-processing safeguards ────────────────────────────────────

_GENERIC_TITLES = {
    "user manual", "documentation", "system documentation", "user guide",
    "overview", "manual", "untitled", "user manual writer",
}

_MD_IMG_RE = re.compile(r"^[ \t]*!\[[^\]]*\]\(([^)]+)\)[ \t]*$", flags=re.MULTILINE)


def _strip_orphan_images(markdown_text: str) -> str:
    """Remove `![alt](path)` lines whose path is neither an http(s) URL nor
    an existing local file. This is a defensive net against any LLM drift
    that might emit fabricated image references when no images were
    actually extracted from the source.
    """
    if not markdown_text:
        return markdown_text

    def _check(match: re.Match[str]) -> str:
        src = (match.group(1) or "").strip()
        if not src:
            return ""
        low = src.lower()
        if low.startswith(("http://", "https://", "data:")):
            return match.group(0)
        candidate = Path(src)
        if candidate.is_absolute() and candidate.exists():
            return match.group(0)
        rel = (Path.cwd() / candidate).resolve()
        if rel.exists():
            return match.group(0)
        project_root = Path(__file__).resolve().parent
        proj_rel = (project_root / candidate).resolve()
        if proj_rel.exists():
            return match.group(0)
        logger.warning("Stripping orphan image reference (path not found): %s", src)
        return ""

    return _MD_IMG_RE.sub(_check, markdown_text)


def _add_section_numbers(markdown_text: str) -> str:
    """Add outline numbering to section headings in the rendered manual.

    Rules
    -----
    * `## Heading`  →  `## 1. Heading`, `## 2. Heading`, …
    * `### SubHeading` *inside the Roles & Workflows section* only
      →  `### 3.1. Customer`, `### 3.2. Admin`, … (numeric suffix)
    * `### SubHeading` inside the FAQs section
      →  `### 4.1. How do I...`, `### 4.2. ...`, … (numeric suffix)
    * `### SubHeading` in any other section → left unchanged.
    * `####` headings → always left unchanged.

    The Roles section is detected heuristically: any `##` heading whose
    text (lowercased, stripped) contains "role".
    """
    if not markdown_text:
        return markdown_text

    lines = markdown_text.splitlines()
    out: list[str] = []
    section_idx = 0          # counter for ## headings (1-based when printed)
    roles_section_num = None  # which section number is the Roles section
    role_sub_idx = 0          # counter for ### within Roles (1-based)
    in_roles = False

    faq_section_num = None
    faq_sub_idx = 0           # counter for ### within FAQs (1-based)
    in_faq = False

    for line in lines:
        stripped = line.rstrip()

        if stripped.startswith("## "):
            section_idx += 1
            heading_text = stripped[3:].strip()
            # Remove any pre-existing numbering so we never double-number.
            heading_text = re.sub(r"^\d+\.\s*", "", heading_text)
            new_line = f"## {section_idx}. {heading_text}"
            out.append(new_line)
            lower = heading_text.lower()
            if "role" in lower:
                roles_section_num = section_idx
                in_roles = True
                role_sub_idx = 0
                in_faq = False
            elif "faq" in lower or "troubleshoot" in lower or "frequently" in lower:
                faq_section_num = section_idx
                in_faq = True
                faq_sub_idx = 0
                in_roles = False
            else:
                in_roles = False
                in_faq = False
            continue

        if stripped.startswith("### "):
            heading_text = stripped[4:].strip()
            # Strip any pre-existing sub-number (e.g. "3.1. " or "3.a. ").
            heading_text = re.sub(r"^\d+\.\d+\.\s*", "", heading_text)
            heading_text = re.sub(r"^\d+\.[a-z]\.\s*", "", heading_text)
            if in_roles:
                role_sub_idx += 1
                out.append(f"### {roles_section_num}.{role_sub_idx}. {heading_text}")
            elif in_faq:
                faq_sub_idx += 1
                out.append(f"### {faq_section_num}.{faq_sub_idx}. {heading_text}")
            else:
                out.append(f"### {heading_text}")
            continue

        # #### headings (role sub-sections) — never numbered, kept verbatim.
        out.append(stripped if not line.rstrip() else line)

    return "\n".join(out)


def _build_confluence_title(project_name: str, state: Dict[str, Any]) -> str:
    """Build the Confluence page title as '<project_name> - <document_title>'.

    Reads document_title directly from extraction_json in session state so
    it is always the content-derived title regardless of what fallback the
    H1 resolved to.  Combining both makes the Confluence page title unique
    per document set — the same project_name can be reused for different
    source documents without hitting 409 conflicts.

    Example:
        project_name     = "WEGA"
        extraction title = "Auto-pay-CC Automated Credit Card Payments"
        →  "WEGA - Auto-pay-CC Automated Credit Card Payments"

    If extraction produced no usable title, returns just project_name.
    """
    import json as _json

    manual_title = ""
    extraction_raw = state.get("extraction_json") or ""
    if extraction_raw:
        try:
            ext = _json.loads(extraction_raw) if isinstance(extraction_raw, str) else extraction_raw
            candidate = (ext.get("document_title") or "").strip()
            if candidate and candidate.lower() not in _GENERIC_TITLES:
                manual_title = candidate
        except Exception:
            pass

    project = (project_name or "").strip()

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip().lower())

    # Treat the extracted title as a duplicate (and skip the concat) when
    # it is empty, equals the project name, or is the project name with
    # only whitespace / case differences — prevents the awkward
    # "<project> - <project>" Confluence page title when the extractor
    # falls back to / echoes the project_name.
    norm_title = _norm(manual_title)
    norm_project = _norm(project)
    is_duplicate = not norm_title or norm_title == norm_project
    if manual_title and not is_duplicate:
        return f"{project} - {manual_title}" if project else manual_title
    # Extraction title missing or duplicate of project_name — return project only.
    return project or "User Manual"


def _assemble_manual_from_state(state: Dict[str, Any], project_name: str) -> str:
    """Assemble the final Markdown manual purely in Python.

    Replaces the former ``markdown_renderer_agent`` LLM call (saves ~30-60 s
    per run). Reads the four output_key values written by the parallel content
    agents and stitches them together in the canonical section order.

    Title priority:
      1. extraction_json.document_title  (if non-empty and not a generic placeholder)
      2. project_name
      3. "User Manual"
    """
    import json as _json

    # ── Resolve title ────────────────────────────────────────────────────────
    title = ""
    extraction_raw = state.get("extraction_json") or ""
    if extraction_raw:
        try:
            ext = _json.loads(extraction_raw) if isinstance(extraction_raw, str) else extraction_raw
            candidate = (ext.get("document_title") or "").strip()
            if candidate and candidate.lower() not in _GENERIC_TITLES:
                title = candidate
        except Exception:
            pass
    if not title:
        # Clean the project_name: underscores/hyphens → spaces so the H1
        # reads "My Page Manual" not "My_Page_Manual".
        raw = (project_name or "").strip()
        title = re.sub(r"[_\-]+", " ", raw).strip() or "User Manual"

    parts: list[str] = [f"# {title}"]

    # ── Common sections (Overview + Getting Started) ─────────────────────────
    # The common_sections_agent emits its output with plain-text labels:
    #     Overview:
    #     <text>
    #
    #     Getting Started:
    #     <text>
    # Convert those labels into proper markdown H2 headings so they render
    # as sections in Confluence (and appear in the TOC). Also tolerate
    # variants where the agent may have already used "## Overview" / a
    # bold label / a trailing colon.
    common = (state.get("common_sections") or "").strip()
    if common:
        def _promote_label(text: str, label: str) -> str:
            # Match a line that is exactly the label (optionally with a
            # leading "##", "**", trailing colon) and replace it with
            # `## <label>`. Case-insensitive, anchored to start of line.
            pattern = re.compile(
                rf"^[ \t]*(?:#+\s*)?\**\s*{re.escape(label)}\s*\**\s*:?\s*$",
                flags=re.IGNORECASE | re.MULTILINE,
            )
            return pattern.sub(f"## {label}", text)

        common = _promote_label(common, "Overview")
        common = _promote_label(common, "Getting Started")
        # If the agent omitted the Overview label entirely but content
        # exists before "Getting Started", prepend an Overview heading so
        # the section is not orphaned at the top of the document.
        if "## Overview" not in common and "## Getting Started" in common:
            common = "## Overview\n\n" + common
        parts.append(common)

    # ── Roles & Workflows ────────────────────────────────────────────────────
    roles = (state.get("role_sections") or "").strip()
    if roles:
        parts.append("## Roles & Workflows\n\n" + roles)

    # ── FAQs & Troubleshooting ───────────────────────────────────────────────
    faq = (state.get("faq_section") or "").strip()
    if faq:
        # Strip a leading "FAQs & Troubleshooting" / "FAQs" title line the
        # agent may have added at the top of its output.
        faq = re.sub(r"^(?:FAQs?[^\n]*)\n+", "", faq, count=1, flags=re.IGNORECASE).strip()
        if faq:
            parts.append("## FAQs & Troubleshooting\n\n" + faq)

    # ── Glossary ─────────────────────────────────────────────────────────────
    glossary = (state.get("glossary_section") or "").strip()
    if glossary:
        # Strip a leading "Glossary" title line the agent may have added.
        glossary = re.sub(r"^Glossary[^\n]*\n+", "", glossary, count=1, flags=re.IGNORECASE).strip()
        if glossary:
            parts.append("## Glossary\n\n" + glossary)

    return "\n\n".join(parts)


def _ensure_meaningful_title(markdown_text: str, project_name: str) -> str:
    """Replace the H1 with `project_name` if it is empty or a generic
    placeholder ("User Manual", "Documentation", ...).
    """
    if not markdown_text:
        return f"# {project_name}\n"
    lines = markdown_text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            current = stripped[2:].strip()
            if not current or current.lower() in _GENERIC_TITLES:
                lines[idx] = f"# {project_name}"
            return "\n".join(lines)
        if stripped:
            # First non-empty line isn't an H1 → prepend one.
            lines.insert(idx, f"# {project_name}")
            lines.insert(idx + 1, "")
            return "\n".join(lines)
    return f"# {project_name}\n"

session_service = InMemorySessionService()

runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)


@contextmanager
def _override_env(**overrides: str):
    """Temporarily set environment variables, restoring originals on exit."""
    previous = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, orig in previous.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig


def _new_session_id(prefix: str = "manual") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _normalize_path(p: str) -> str:
    """Resolve a path string to an absolute POSIX path."""
    if not p:
        return p
    p = p.replace("\\", "/")
    pp = Path(p)
    if pp.is_absolute() and pp.exists():
        return pp.resolve().as_posix()
    cwd_candidate = (Path.cwd() / pp).resolve()
    if cwd_candidate.exists():
        return cwd_candidate.as_posix()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate = (OUTPUT_DIR / pp.name).resolve()
    return candidate.as_posix()


def _enrich_and_normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    s = dict(state or {})
    raw_path = s.get("file_path") or s.get("pdf_path")
    file_name = s.get("file_name")

    if raw_path:
        normalized = _normalize_path(raw_path)
        s["file_path"] = normalized
        s["pdf_path"] = normalized
        s.setdefault("file_name", Path(normalized).name)
        s.setdefault("output_dir", str(Path(normalized).parent.as_posix()))
        return s

    if file_name:
        normalized = _normalize_path(file_name)
        s["file_path"] = normalized
        s["pdf_path"] = normalized
        s.setdefault("output_dir", str(Path(normalized).parent.as_posix()))
        return s

    s.setdefault("output_dir", OUTPUT_DIR.as_posix())
    return s


async def run_wegaum_pipeline(
    prompt: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new unique session, run the Wegaum pipeline, and return state.

    The user-supplied `project_name` is seeded into session state so the
    title-generation stage can use it as a canonical anchor.
    """

    user_id = "api-user"
    app_name = APP_NAME
    session_id = _new_session_id()
    initial_state: Dict[str, Any] = {}
    if project_name:
        initial_state["project_name"] = project_name

    for _ in range(2):
        try:
            await session_service.create_session(
                user_id=user_id,
                session_id=session_id,
                app_name=app_name,
                state=initial_state,
            )
            break
        except AlreadyExistsError:
            session_id = _new_session_id()
    else:
        raise RuntimeError("Unable to create unique session after retries.")

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=prompt or DEFAULT_PROMPT)],
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        author = getattr(event, "author", None)
        if author:
            logger.info("[session=%s] stage=%s event received", session_id, author)

    session = await session_service.get_session(
        user_id=user_id,
        session_id=session_id,
        app_name=app_name,
    )
    state = _enrich_and_normalize_state(session.state or {})
    state["session_id"] = session_id

    logger.info("Pipeline finished (session_id=%s)", session_id)
    return state


# ---------------------
# Request / Response Models
# ---------------------

class GenerateManualRequest(BaseModel):
    """Request body for manual generation."""

    url: str = Field(
        ...,
        title="Source URL",
        description=(
            "URL of the source content. Accepts:\n"
            "- **SharePoint folder/file URL** – reads all supported documents from that location.\n"
            "- **Confluence page URL** – reads that page and its direct children."
        ),
        json_schema_extra={
            "example": "https://wipro365.sharepoint.com/sites/BuildIQ/Shared Documents/WEGA"
        },
    )

    project_name: str = Field(
        ...,
        title="Project Name",
        description=(
            "Name to use for the published Confluence page. "
            "Must be unique under the configured parent page."
        ),
        json_schema_extra={"example": "WEGA User Manual"},
    )

    @field_validator("url")
    @classmethod
    def _strip_url(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @field_validator("project_name")
    @classmethod
    def _strip_project_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("project_name must not be blank.")
        return v

    model_config = {"json_schema_extra": {"examples": [
        {"url": "https://wipro365.sharepoint.com/sites/BuildIQ/Shared Documents/WEGA", "project_name": "WEGA User Manual"},
        {"url": "https://wegabuildiq.atlassian.net/wiki/spaces/WAAD/pages/81330177/My+Page", "project_name": "My Page Manual"},
    ]}}


class GenerateManualResponse(BaseModel):
    """Successful response after manual generation and Confluence publish."""

    status: str = Field(
        ...,
        description="Result status. Always `success` on a 200 response.",
        json_schema_extra={"example": "success"},
    )
    session_id: str = Field(
        ...,
        description="Unique session ID for this pipeline run. Useful for debugging.",
        json_schema_extra={"example": "manual-a1b2c3d4e5f6"},
    )
    confluence_url: Optional[str] = Field(
        None,
        description="Direct URL to the published Confluence page.",
        json_schema_extra={"example": "https://wegabuildiq.atlassian.net/wiki/spaces/WAAD/pages/12345678/WEGA+User+Manual"},
    )


class ErrorResponse(BaseModel):
    """Error response returned on failure."""

    detail: str = Field(
        ...,
        description="Human-readable error message describing what went wrong.",
        json_schema_extra={"example": "Pipeline execution failed: <reason>"},
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., json_schema_extra={"example": "healthy"})
    version: str = Field(..., json_schema_extra={"example": APP_VERSION})


# ---------------------
# Endpoints
# ---------------------

@app.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health status and version. Use this to verify the API is running.",
)
async def health_check():
    return HealthResponse(status="healthy", version=APP_VERSION)


@app.post(
    "/generate-manual",
    tags=["manuals"],
    response_model=GenerateManualResponse,
    summary="Generate & publish a user manual",
    description=(
        "Accepts a **SharePoint folder URL** or a **Confluence page URL** as the source.\n\n"
        "- **SharePoint:** reads all supported documents (PDF, DOCX, PPTX, XLSX, TXT, CSV, JSON) from the folder.\n"
        "- **Confluence:** reads the specified page and its direct children.\n\n"
        "Runs a 3-stage AI pipeline (ingest → extract → parallel write) powered by Google Gemini, then assembles sections in Python, "
        "then publishes the finished manual to Confluence as a native child page under the configured parent.\n\n"
        "The `project_name` field sets the Confluence page title and **must be unique** — "
        "if a page with that name already exists, HTTP 409 is returned without running the pipeline.\n\n"
        "**Typical response time:** 2–5 minutes depending on document volume.\n\n"
        "**Returns:** Direct Confluence page URL on success."
    ),
    responses={
        200: {"description": "Manual generated and published successfully.", "model": GenerateManualResponse},
        409: {"description": "A Confluence page with the given project name already exists.", "model": ErrorResponse},
        429: {"description": "Service is at capacity. Retry shortly.", "model": ErrorResponse},
        500: {"description": "Pipeline or Confluence publish failed.", "model": ErrorResponse},
        502: {"description": "Could not reach Google Gemini / Vertex AI.", "model": ErrorResponse},
        504: {"description": "Pipeline exceeded its time budget.", "model": ErrorResponse},
    },
)
async def generate_manual(body: GenerateManualRequest):
    logger.info(
        "Manual generation requested: project_name=%r url=%r",
        body.project_name, body.url,
    )
    if _is_confluence_url(body.url):
        env_overrides = {"CONFLUENCE_SOURCE_URL": body.url, "SHAREPOINT_URL": ""}
    else:
        env_overrides = {"SHAREPOINT_URL": body.url, "CONFLUENCE_SOURCE_URL": ""}

    # ── Admission control ──────────────────────────────────────────────────
    # _acquire_admission() raises HTTP 429 if the queue is saturated.
    await _acquire_admission()

    global _inflight_count
    session_id: Optional[str] = None
    confluence_result: Dict[str, Any] = {}

    try:
        async with _pipeline_semaphore:
            _inflight_count += 1
            logger.info(
                "Pipeline admitted (in_flight=%d, queued=%d)",
                _inflight_count, _queued_count,
            )
            try:
                async with _pipeline_env_lock:
                    with _override_env(**env_overrides):
                        # ── Run the pipeline with a hard wall-clock timeout ─
                        try:
                            state = await asyncio.wait_for(
                                run_wegaum_pipeline(project_name=body.project_name),
                                timeout=PIPELINE_TIMEOUT_SECS,
                            )
                        except asyncio.TimeoutError as exc:
                            logger.error(
                                "Pipeline timed out after %ss for project_name=%r",
                                PIPELINE_TIMEOUT_SECS, body.project_name,
                            )
                            raise HTTPException(
                                status_code=504,
                                detail=(
                                    f"Pipeline exceeded the {PIPELINE_TIMEOUT_SECS}s "
                                    "timeout. The source documents may be too large, "
                                    "or upstream LLM/API calls are unresponsive."
                                ),
                            ) from exc
                        except TransportError as exc:
                            logger.exception("Gemini/Vertex authentication or network failure")
                            raise HTTPException(
                                status_code=502,
                                detail=(
                                    "Failed to reach Gemini/Vertex AI. Check Google "
                                    "authentication, Vertex configuration, and outbound "
                                    "network access."
                                ),
                            ) from exc
                        except HTTPException:
                            raise
                        except Exception as exc:
                            logger.exception("Pipeline execution failed")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Pipeline execution failed: {exc}",
                            ) from exc

                        session_id = state.get("session_id")

                        if not session_id:
                            raise HTTPException(
                                status_code=500,
                                detail="Failed to allocate session id",
                            )

                        project_name = body.project_name

                        # ── Python assembly (replaces renderer_agent LLM call) ──
                        # Reads the four output_key values written by the parallel
                        # content agents and assembles them in order. ~30-60 s faster
                        # than asking an LLM to do the same concatenation.
                        rendered_markdown = _assemble_manual_from_state(state, project_name)

                        if not rendered_markdown or not rendered_markdown.strip():
                            raise HTTPException(
                                status_code=500,
                                detail="Pipeline did not produce any content",
                            )

                        # Defensive post-processing:
                        # 1. Strip image refs whose local path doesn't exist.
                        # 2. Ensure the H1 title is meaningful.
                        # 3. Add outline section numbering.
                        rendered_markdown = _strip_orphan_images(rendered_markdown)
                        rendered_markdown = _ensure_meaningful_title(
                            rendered_markdown, project_name,
                        )
                        rendered_markdown = _add_section_numbers(rendered_markdown)

                        # Build the Confluence page title:
                        # "<project_name> - <manual_title>" so that the same
                        # project_name can be reused for different source
                        # documents without hitting 409 conflicts.
                        confluence_title = _build_confluence_title(
                            project_name, state,
                        )
                        logger.info(
                            "[session=%s] Confluence page title: %r",
                            session_id, confluence_title,
                        )

                        # ── Confluence: existence check + publish ───────────
                        try:
                            if confluence_page_exists(confluence_title):
                                raise HTTPException(
                                    status_code=409,
                                    detail=(
                                        f"A Confluence page named '{confluence_title}' "
                                        "already exists. Please choose a different "
                                        "project name or use a different source document."
                                    ),
                                )
                        except HTTPException:
                            raise
                        except Exception as exc:
                            logger.error(
                                "Failed to check Confluence page existence: %s", exc,
                            )
                            raise HTTPException(
                                status_code=500,
                                detail=f"Could not verify project name availability: {exc}",
                            )

                        try:
                            confluence_result = publish_manual_to_confluence(
                                markdown_text=rendered_markdown,
                                project_name=confluence_title,
                            )
                        except Exception as exc:
                            logger.error(
                                "Failed to publish manual to Confluence: %s", exc,
                            )
                            raise HTTPException(
                                status_code=500,
                                detail=f"Manual generated but Confluence publish failed: {exc}",
                            )
            finally:
                _inflight_count -= 1
    finally:
        await _release_queue()

    logger.info(
        "[session=%s] Manual published to Confluence: %s (images_uploaded=%s)",
        session_id, confluence_result.get("confluence_url"),
        confluence_result.get("images_uploaded"),
    )
    return GenerateManualResponse(
        status="success",
        session_id=session_id,
        confluence_url=confluence_result.get("confluence_url"),
    )
