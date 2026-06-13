"""
api/main.py

FastAPI application — BRD Agent MVP.

Endpoints:
  POST /sessions                  — create session, receive greeting
  POST /sessions/{id}/chat        — send text message
  POST /sessions/{id}/upload-docs — upload .pdf / .docx / .txt (multipart)
  GET  /sessions/{id}             — session status
  GET  /sessions/{id}/download    — download generated BRD .docx
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
import uuid
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

# ── Windows multiprocessing spawn guard ───────────────────────────────────────
# Must be at the top before any other imports that touch asyncio or threading.
# Without this, Windows "spawn" workers re-run the whole module and crash.
import multiprocessing
multiprocessing.freeze_support()

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from agents.conversation_agent import process_turn, process_docs_uploaded
from agents.brd_update_agent import (
    validate_confluence_page,
    process_update_content_from_chat,
    process_update_docs_uploaded,
)
from models.brd_models import (
    ConversationSession, ConversationStep, ChatMessage,
    Stakeholder, StakeholderRole, ROLE_ALIASES,
    MAX_HISTORY_MESSAGES, MAX_DOCUMENTS_TOTAL_BYTES, SESSION_TTL_SECONDS,
)
from utils.file_extractor import extract_text_from_bytes, SUPPORTED_EXTENSIONS
from utils.confluence_exporter import publish_brd_docx_as_page
from utils.validators import dedupe_stakeholders, validate_project_name
from utils.sanitizer import sanitize_filename

# ── Logging setup ─────────────────────────────────────────────────────────────
_log_format = os.environ.get("LOG_FORMAT", "text").strip().lower()
if _log_format == "json":
    import json as _json

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            entry = {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", None),
            }
            if record.exc_info and record.exc_info[1]:
                entry["exception"] = self.formatException(record.exc_info)
            return _json.dumps(entry, default=str)

    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
else:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)

# ── Request ID middleware ─────────────────────────────────────────────────────
_request_id_ctx: dict[int, str] = {}  # task-id → request-id


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        # Store in task-local context for log filter
        task_id = id(asyncio.current_task())
        _request_id_ctx[task_id] = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_ctx.pop(task_id, None)


class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        task_id = id(asyncio.current_task()) if asyncio.current_task() else 0
        record.request_id = _request_id_ctx.get(task_id, "-")
        return True


logging.root.addFilter(_RequestIDFilter())

# ── In-memory session store ───────────────────────────────────────────────────
_sessions: dict[str, ConversationSession] = {}
_session_locks: dict[str, asyncio.Lock] = {}
_session_lock_creation_lock = asyncio.Lock()

MAX_MESSAGE_LENGTH = 50_000  # 50 KB max chat message size

# Generic error message exposed to clients when an internal exception escapes.
_GENERIC_ERROR_MSG = (
    "An internal error occurred. Please try again. If the problem persists, "
    "contact support with this session id."
)


async def _get_lock(session_id: str) -> asyncio.Lock:
    """Return a per-session asyncio.Lock, creating one if needed.

    The creation step itself is guarded so two concurrent first-time callers
    can't end up with two different Lock instances.
    """
    lock = _session_locks.get(session_id)
    if lock is not None:
        return lock
    async with _session_lock_creation_lock:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[session_id] = lock
        return lock


def _truncate_history(session: ConversationSession) -> None:
    """Keep the most recent ``MAX_HISTORY_MESSAGES`` to bound memory usage."""
    if len(session.history) > MAX_HISTORY_MESSAGES:
        overflow = len(session.history) - MAX_HISTORY_MESSAGES
        del session.history[:overflow]
        logger.info(
            "Truncated %d old history message(s) for session %s",
            overflow, session.session_id,
        )


def _persist_session(session_id: str, session: ConversationSession, *, touch: bool = True) -> None:
    _truncate_history(session)
    if touch:
        session.touch()
    _sessions[session_id] = session


async def _evict_expired_sessions() -> None:
    """Background task: drop sessions that have been idle past TTL."""
    from datetime import datetime, timezone, timedelta
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=SESSION_TTL_SECONDS)
            stale: list[str] = []
            for sid, sess in list(_sessions.items()):
                try:
                    updated = datetime.fromisoformat(sess.updated_at)
                except Exception:
                    continue
                if updated < cutoff:
                    stale.append(sid)
            for sid in stale:
                _sessions.pop(sid, None)
                _session_locks.pop(sid, None)
            if stale:
                logger.info("Evicted %d idle session(s).", len(stale))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Session eviction loop error")
        await asyncio.sleep(900)  # check every 15 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BRD Agent API starting...")
    # ── Startup validation ────────────────────────────────────────────────
    warnings: list[str] = []
    if not os.environ.get("GOOGLE_API_KEY"):
        warnings.append("GOOGLE_API_KEY is not set — LLM calls will fail.")
    confluence_url = os.environ.get("CONFLUENCE_PARENT_PAGE_URL") or os.environ.get("CONFLUENCE_URL") or os.environ.get("CONFLUENCE_BASE_URL")
    confluence_email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("CONFLUENCE_USERNAME")
    confluence_token = os.environ.get("CONFLUENCE_API_TOKEN")
    if not all([confluence_url, confluence_email, confluence_token]):
        warnings.append(
            "Confluence env vars incomplete — publish and brownfield update will be unavailable."
        )
    for w in warnings:
        logger.warning("STARTUP: %s", w)
    if not warnings:
        logger.info("All environment variables validated.")
    eviction_task = asyncio.create_task(_evict_expired_sessions())
    try:
        yield
    finally:
        eviction_task.cancel()
        try:
            await eviction_task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("BRD Agent API stopped.")


app = FastAPI(
    title="BRD Agent API",
    description="Conversational AI agent for BRD generation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateSessionResponse(BaseModel):
    session_id: str
    message: str


class CreateSessionRequest(BaseModel):
    mode: str = "new"                    # "new" | "update"
    confluence_link: str | None = None   # For update mode: Confluence page URL or ID


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=MAX_MESSAGE_LENGTH)


class ChatResponse(BaseModel):
    session_id:     str
    reply:          str
    step:           str
    final_brd_path: str | None = None


class UploadDocsResponse(BaseModel):
    session_id:     str
    reply:          str
    step:           str
    files_received: list[str]
    files_rejected: list[str]
    final_brd_path: str | None = None


class SessionStatusResponse(BaseModel):
    session_id:        str
    step:              str
    mode:              str = "new"
    project_name:      str | None
    stakeholder_count: int
    document_count:    int
    final_brd_path:    str | None
    confluence_page_id:  str | None = None
    confluence_page_url: str | None = None
    error:             str | None


class PublishResponse(BaseModel):
    session_id:      str
    uploaded:        bool
    attachment_name: str | None = None
    page_id:         str | None = None
    confluence_url:  str | None = None
    message:         str


class ConfluenceLinkRequest(BaseModel):
    link: str


class ConfluenceLinkResponse(BaseModel):
    session_id:   str
    valid:        bool
    page_id:      str | None = None
    page_title:   str | None = None
    page_version: int | None = None
    page_url:     str | None = None
    step:         str
    message:      str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(session_id: str) -> ConversationSession:
    logger.info("Retrieving session: %s", session_id)
    if session_id not in _sessions:
        logger.warning("Session not found: %s", session_id)
        raise HTTPException(404, detail=f"Session '{session_id}' not found.")
    return _sessions[session_id]


def _normalize_list_field(values: list[str] | None) -> list[str]:
    """Allow either repeated keys or a single JSON/comma list.

    Examples accepted (all as a single text form value):
      - ["Alice Smith", "Bob Jones"]
      - [Alice Smith, Bob Jones]
      - Alice Smith, Bob Jones

    If multiple values are already present (repeated keys), they are returned
    as-is.
    """
    logger.info("Normalizing list field: %s values", len(values) if values else 0)
    if not values:
        return []
    if len(values) > 1:
        return values

    raw = (values[0] or "").strip()
    if not raw:
        return []

    # Try JSON array first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x).strip().strip('"').strip("'") for x in parsed if str(x).strip()]
    except Exception:
        pass

    # Fallback: treat as comma-separated, optionally wrapped in []
    trimmed = raw.strip().lstrip("[").rstrip("]")
    parts = [p.strip().strip('"').strip("'") for p in trimmed.split(",") if p.strip()]
    if parts:
        return parts

    return [raw]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    logger.info("Health check requested")
    return {"status": "ok"}


@app.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest | None = None):
    """Create a new BRD session.

    Modes:
      - ``"new"`` (default): Standard greenfield BRD creation. Agent greets the user.
      - ``"update"``: Brownfield update of an existing BRD on Confluence.
        Pass ``confluence_link`` to validate + fetch the page immediately.
    """
    mode = (req.mode if req else "new").strip().lower()
    confluence_link = req.confluence_link if req else None

    if mode not in ("new", "update"):
        raise HTTPException(400, detail="mode must be 'new' or 'update'.")

    session_id = str(uuid.uuid4())
    session    = ConversationSession(session_id=session_id, mode=mode)

    if mode == "update":
        _sessions[session_id] = session
        if confluence_link:
            # Validate via MCP agent during session creation
            reply, updated = await validate_confluence_page(session, confluence_link)
            _persist_session(session_id, updated)
            logger.info("Update session created: %s, step=%s", session_id, updated.step.value)
            return CreateSessionResponse(session_id=session_id, message=reply)
        else:
            # No link provided — ask for it
            session.step = ConversationStep.UPDATE_COLLECT_LINK
            logger.info("Update session created (awaiting link): %s", session_id)
            msg = (
                "You've chosen to update an existing BRD.\n\n"
                "Please provide the Confluence page URL or page ID for the BRD you want to update."
            )
            return CreateSessionResponse(session_id=session_id, message=msg)

    # Default: new BRD flow
    _sessions[session_id] = session
    reply, updated = await process_turn(session, "__INIT__")
    _persist_session(session_id, updated)

    logger.info("Session created: %s", session_id)
    return CreateSessionResponse(session_id=session_id, message=reply)


@app.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, req: ChatRequest, request: Request):
    """Send a text message. Use for project name, stakeholder details, confirmations.

    Optional ``Idempotency-Key`` header: if a chat call repeats the same key
    that was used for the previous successful call on this session, the prior
    reply is returned without re-running the agent.
    """
    logger.info("Chat message received: session_id=%s, message_preview=%s",
               session_id, req.message[:50])
    idem_key = request.headers.get("Idempotency-Key")
    lock = await _get_lock(session_id)
    async with lock:
        session = _get_session(session_id)
        if idem_key and session.last_idempotency_key == idem_key and session.last_idempotent_reply is not None:
            logger.info("Idempotent replay: session_id=%s key=%s", session_id, idem_key)
            return ChatResponse(
                session_id=session_id,
                reply=session.last_idempotent_reply,
                step=session.step.value,
                final_brd_path=session.final_brd_path,
            )
        try:
            reply, updated = await process_turn(session, req.message)
        except Exception:
            logger.exception("Unhandled error in process_turn: session_id=%s", session_id)
            raise HTTPException(500, detail=_GENERIC_ERROR_MSG)
        if idem_key:
            updated.last_idempotency_key = idem_key
            updated.last_idempotent_reply = reply
        _persist_session(session_id, updated)
    logger.info("Chat response sent: session_id=%s, step=%s", session_id, updated.step.value)
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        step=updated.step.value,
        final_brd_path=updated.final_brd_path,
    )


@app.post("/sessions/{session_id}/confluence-link", response_model=ConfluenceLinkResponse)
async def set_confluence_link(session_id: str, req: ConfluenceLinkRequest):
    """Validate a Confluence page link and attach it to an update session.

    This is an alternative to passing ``confluence_link`` at session creation.
    Can also be used to retry with a different link.
    """
    logger.info("Confluence link request: session_id=%s, link=%s", session_id, req.link[:100])
    lock = await _get_lock(session_id)
    async with lock:
        session = _get_session(session_id)

        if session.mode != "update":
            raise HTTPException(400, detail="This endpoint is only for update-mode sessions.")

        if session.step not in (
            ConversationStep.UPDATE_COLLECT_LINK,
            ConversationStep.UPDATE_COLLECT_CONTENT,
        ):
            raise HTTPException(
                400,
                detail=f"Session is at step '{session.step.value}'. "
                       "Link can only be set during the link-collection or content-collection step.",
            )

        try:
            reply, updated = await validate_confluence_page(session, req.link)
        except Exception:
            logger.exception("Unhandled error in validate_confluence_page: session_id=%s", session_id)
            raise HTTPException(500, detail=_GENERIC_ERROR_MSG)
        _persist_session(session_id, updated)

    is_valid = updated.step == ConversationStep.UPDATE_COLLECT_CONTENT
    return ConfluenceLinkResponse(
        session_id=session_id,
        valid=is_valid,
        page_id=updated.confluence_page_id,
        page_title=updated.existing_page_title,
        page_version=updated.existing_page_version,
        page_url=updated.confluence_page_url,
        step=updated.step.value,
        message=reply,
    )


@app.post("/sessions/{session_id}/upload-docs", response_model=UploadDocsResponse)
async def upload_docs(
    session_id: str,
    files: List[UploadFile] = File(default=[]),
    project_name: str | None = Form(default=None),
    name:         list[str] | None = Form(default=None),
    role:         list[str] | None = Form(default=None),
    email:        list[str] | None = Form(default=None),
):
    """
    Upload source documents (multipart/form-data) with optional one-shot metadata.

        One-shot mode — supply all four fields + files in one request:
            project_name  — name of the project
            name          — stakeholder full name (repeat key for multiple)
            role          — stakeholder role (repeat key; e.g. "Product Owner")
            email         — stakeholder email address (repeat key for multiple)
      files         — one or more .pdf / .docx / .txt files

    When all four fields are provided the session is populated and BRD
    generation starts automatically — no chat turns required.
    Without the extra fields the endpoint behaves as before (requires
    'collect_docs' step).
    """
    logger.info("Upload docs request: session_id=%s, files=%d, project_name=%s",
               session_id, len(files), project_name)

    # ── Resolve stakeholder lists (name/role/email) → Stakeholder objects ───
    # (validation is done before acquiring the lock — no session mutation here)
    stakeholders: list[Stakeholder] = []
    names  = _normalize_list_field(name)
    roles  = _normalize_list_field(role)
    emails = _normalize_list_field(email)

    if names or roles or emails:
        logger.info("Processing stakeholder metadata: names=%d, roles=%d, emails=%d",
                   len(names), len(roles), len(emails))
        if not (len(names) == len(roles) == len(emails)):
            logger.warning("Mismatched stakeholder field counts: names=%d, roles=%d, emails=%d",
                         len(names), len(roles), len(emails))
            raise HTTPException(
                400,
                detail=(
                    "Mismatched stakeholder fields: 'name', 'role', and 'email' "
                    "must have the same number of values."
                ),
            )
        for idx, (n, r_str, e) in enumerate(zip(names, roles, emails), start=1):
            role_key = (r_str or "").strip().lower()
            resolved_role: StakeholderRole | None = None
            if role_key:
                resolved_role = ROLE_ALIASES.get(role_key)
                if resolved_role is None:
                    # Try direct enum value match
                    for r in StakeholderRole:
                        if r.value.lower() == role_key:
                            resolved_role = r
                            break
            if resolved_role is None:
                logger.warning("Unknown role at index %d: %s", idx, r_str)
                raise HTTPException(
                    400,
                    detail=(
                        f"Unknown role at index {idx}: '{r_str}'. Valid roles: "
                        + ", ".join(r.value for r in StakeholderRole)
                    ),
                )
            stakeholders.append(
                Stakeholder(name=(n or "").strip(), email=(e or "").strip(), role=resolved_role)
            )
        # Dedupe one-shot stakeholder list defensively
        stakeholders, removed_dupes = dedupe_stakeholders(stakeholders)
        if removed_dupes:
            logger.info("One-shot dedupe removed %d entries: %s", len(removed_dupes), removed_dupes)
        logger.info("Parsed %d stakeholders from form data", len(stakeholders))

    # ── Validate project name (prevents path traversal, control chars) ────
    cleaned_project_name: str | None = None
    if project_name is not None:
        cleaned_project_name, name_err = validate_project_name(project_name)
        if name_err:
            raise HTTPException(400, detail=f"Invalid project_name: {name_err}")

    # ── Determine if this is a one-shot call (metadata provided) ─────────────
    one_shot = bool(cleaned_project_name and stakeholders)

    # ── Read files before acquiring the lock (I/O heavy) ─────────────────────
    accepted: list[tuple[str, str]] = []
    rejected: list[str] = []

    logger.info("Processing %d uploaded files", len(files))
    for upload in files:
        fname = upload.filename or "unnamed"
        ext   = Path(fname).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            logger.warning("Unsupported file type: %s (%s)", fname, ext)
            rejected.append(f"{fname} — unsupported type '{ext}'")
            continue

        try:
            raw = await upload.read()
            if not raw:
                logger.warning("Empty file uploaded: %s", fname)
                rejected.append(f"{fname} — empty file")
                continue
            if len(raw) > 20 * 1024 * 1024:
                logger.warning("File too large: %s (%d bytes)", fname, len(raw))
                rejected.append(f"{fname} — exceeds 20 MB limit")
                continue
            text = extract_text_from_bytes(fname, raw)
            accepted.append((fname, text))
            logger.info("Extracted %d chars from '%s'", len(text), fname)
        except ValueError as ve:
            logger.warning("Value error extracting text from '%s': %s", fname, ve)
            rejected.append(f"{fname} — {ve}")
        except Exception as exc:
            logger.exception("Error reading '%s'", fname)
            rejected.append(f"{fname} — read error: {exc}")

    logger.info("File processing complete: accepted=%d, rejected=%d", len(accepted), len(rejected))

    # ── Acquire session lock for mutation + handler call ─────────────────────
    lock = await _get_lock(session_id)
    async with lock:
        session = _get_session(session_id)

        # ── Update mode: route to update flow ────────────────────────────────
        is_update_mode = session.mode == "update" and session.step == ConversationStep.UPDATE_COLLECT_CONTENT

        # ── Enforce per-session storage cap on extracted text ────────────────
        new_bytes = sum(len(t.encode("utf-8", errors="ignore")) for _, t in accepted)
        if session.documents_total_bytes + new_bytes > MAX_DOCUMENTS_TOTAL_BYTES:
            logger.warning(
                "Session %s would exceed document storage cap "
                "(have=%d, adding=%d, cap=%d)",
                session_id, session.documents_total_bytes, new_bytes,
                MAX_DOCUMENTS_TOTAL_BYTES,
            )
            raise HTTPException(
                413,
                detail=(
                    f"Total extracted document text would exceed "
                    f"{MAX_DOCUMENTS_TOTAL_BYTES // (1024*1024)} MB for this session."
                ),
            )
        session.documents_total_bytes += new_bytes

        if one_shot:
            session.project_name = cleaned_project_name
            session.stakeholders = stakeholders
            session.step = ConversationStep.CONFIRM_ROLES
            logger.info(
                "One-shot upload: session=%s project='%s' stakeholders=%d",
                session_id, session.project_name, len(session.stakeholders),
            )
        elif not is_update_mode:
            logger.info("Standard upload mode: session_id=%s, step=%s", session_id, session.step.value)
            if session.step not in (ConversationStep.COLLECT_DOCS,):
                logger.warning("Invalid step for upload: session_id=%s, step=%s",
                             session_id, session.step.value)
                raise HTTPException(
                    400,
                    detail=(
                        f"Session is at step '{session.step.value}'. "
                        "File upload is only allowed during the 'collect_docs' step, "
                        "'update_collect_content' step, "
                        "or supply project_name, name, role, email for one-shot mode."
                    ),
                )

        # ── Route to the appropriate handler ─────────────────────────────────
        try:
            if is_update_mode:
                reply, updated = await process_update_docs_uploaded(
                    session=session,
                    accepted_files=accepted,
                    rejected_files=rejected,
                )
            else:
                reply, updated = await process_docs_uploaded(
                    session=session,
                    accepted_files=accepted,
                    rejected_files=rejected,
                    auto_generate=one_shot,
                )
        except Exception:
            logger.exception("Unhandled error in docs handler: session_id=%s", session_id)
            raise HTTPException(500, detail=_GENERIC_ERROR_MSG)
        _persist_session(session_id, updated)

    return UploadDocsResponse(
        session_id=session_id,
        reply=reply,
        step=updated.step.value,
        files_received=[f for f, _ in accepted],
        files_rejected=rejected,
        final_brd_path=updated.final_brd_path,
    )


@app.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    logger.info("Session status request: session_id=%s", session_id)
    s = _get_session(session_id)
    logger.info("Session status: session_id=%s, step=%s, stakeholders=%d, docs=%d",
               session_id, s.step.value, len(s.stakeholders), len(s.documents_text))
    return SessionStatusResponse(
        session_id=s.session_id,
        step=s.step.value,
        mode=s.mode,
        project_name=s.project_name,
        stakeholder_count=len(s.stakeholders),
        document_count=len(s.documents_text),
        final_brd_path=s.final_brd_path,
        confluence_page_id=s.confluence_page_id,
        confluence_page_url=s.confluence_page_url,
        error=s.error,
    )


@app.get("/sessions/{session_id}/download")
async def download_brd(session_id: str):
    logger.info("BRD download request: session_id=%s", session_id)
    s = _get_session(session_id)
    if not s.final_brd_path or not Path(s.final_brd_path).exists():
        logger.warning("BRD not ready for download: session_id=%s, path=%s",
                      session_id, s.final_brd_path)
        raise HTTPException(404, detail="BRD not ready yet.")

    # ── Path traversal defense: ensure file is within the output directory ──
    output_dir = Path(os.environ.get("BRD_OUTPUT_DIR", "./output")).resolve()
    resolved_path = Path(s.final_brd_path).resolve()
    try:
        resolved_path.relative_to(output_dir)
    except ValueError:
        logger.error("Path traversal attempt: session=%s path=%s", session_id, s.final_brd_path)
        raise HTTPException(403, detail="Access denied.")

    logger.info("Sending BRD file: %s", resolved_path)
    return FileResponse(
        path=str(resolved_path),
        filename=resolved_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/sessions/{session_id}/publish", response_model=PublishResponse)
async def publish_brd_to_confluence(session_id: str):
    """Upload the generated BRD .docx to the configured Confluence page.

    Intended to be called only after the user has reviewed the document and
    explicitly confirmed they want it published. The frontend should:
      1) Poll ``/sessions/{id}`` until ``final_brd_path`` is non-null
      2) Ask the user for confirmation ("Publish to Confluence?")
      3) Call this endpoint if they say yes
    """

    logger.info("Publish to Confluence request: session_id=%s", session_id)
    session = _get_session(session_id)
    if not session.final_brd_path:
        logger.warning("Cannot publish - BRD not generated: session_id=%s", session_id)
        raise HTTPException(400, detail="BRD not generated yet for this session.")

    path = Path(session.final_brd_path)
    if not path.exists():
        logger.error("BRD file missing: session_id=%s, path=%s", session_id, session.final_brd_path)
        raise HTTPException(404, detail="Generated BRD file is missing on the server.")

    logger.info("Publishing BRD to Confluence: session_id=%s, project=%s",
               session_id, session.project_name)
    try:
        result = await publish_brd_docx_as_page(
            file_path=path,
            project_name=session.project_name or "Unnamed Project",
        )
    except ValueError as e:
        # Configuration or local file issues
        logger.error("Publish failed (bad configuration or file): %s", e)
        raise HTTPException(500, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive catch
        logger.exception("Publish to Confluence failed: session=%s", session_id)
        raise HTTPException(502, detail=f"Failed to upload to Confluence: {e}")

    logger.info("Successfully published to Confluence: session_id=%s, page_id=%s",
               session_id, result.get("page_id"))
    msg = "BRD uploaded to Confluence successfully."
    return PublishResponse(
        session_id=session_id,
        uploaded=True,
        attachment_name=result.get("attachment_name"),
        page_id=result.get("page_id"),
        confluence_url=result.get("page_url"),
        message=msg,
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )