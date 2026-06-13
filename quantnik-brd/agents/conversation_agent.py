"""
agents/conversation_agent.py

Google ADK LlmAgent: GREETING → COLLECT_ROLES → CONFIRM_ROLES → COLLECT_DOCS → GENERATING → COMPLETE

Fixes:
- ADK Runner/SessionService created lazily (not at module level) — Windows spawn safe
- Always create_session upfront, never rely on get_session raising for missing session
- subprocess replaced with asyncio.create_subprocess_exec
"""
from __future__ import annotations
import asyncio
import logging
import os
import re
import threading

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from models.brd_models import (
    BRDSection, ConversationSession, ConversationStep,
    ChatMessage, Stakeholder, StakeholderRole, BRDDocument,
    MAX_CORRECTION_ATTEMPTS,
)
from utils.prompts import (
    CONVERSATION_SYSTEM_PROMPT,
    BRD_GENERATION_SYSTEM_PROMPT,
    BRD_GENERATION_USER_PROMPT,
)
from utils.validators import (
    parse_stakeholder_block, format_validation_errors, all_valid,
    dedupe_stakeholders, validate_project_name,
)
from utils.docx_generator import generate_brd_docx, _SECTION_KEY_TO_TITLE
from utils.adk_helpers import ensure_session, make_tool_list, run_runner_to_text
from utils.json_parser import parse_llm_json
from utils.sanitizer import sanitize_for_prompt
from utils.mcp_confluence import get_confluence_toolset
from agents.brd_update_agent import (
    validate_confluence_page,
    process_update_content_from_chat,
    process_update_docs_uploaded,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

# Hard ceiling on a single LLM call; raised in env for slow models.
LLM_CALL_TIMEOUT_SECONDS = float(os.environ.get("LLM_CALL_TIMEOUT_SECONDS", "180"))

# Generic message exposed to users when an internal exception occurs.  The
# real exception is logged with full traceback for operators.
_GENERIC_ERROR_MSG = (
    "Sorry, something went wrong on our side. Please try again in a moment. "
    "If the issue persists, contact support with this session id."
)


# ── Lazy ADK singletons ───────────────────────────────────────────────────────
# NOT created at module level — avoids Windows spawn crash on re-import.

_adk: dict = {}
_adk_lock = threading.Lock()


def _get_adk() -> dict:
    """Initialise ADK objects once, lazily, on first API call."""
    if _adk:
        return _adk
    with _adk_lock:
        if _adk:
            return _adk
        session_service = InMemorySessionService()

        # MCP Confluence toolset — gives agents read/write access to Confluence
        try:
            confluence_tools = get_confluence_toolset()
            logger.info("MCP Confluence toolset loaded.")
        except Exception as exc:
            confluence_tools = None
            logger.warning("MCP Confluence toolset unavailable: %s", exc)

        conv_agent = LlmAgent(
            name="brd_conversation_agent",
            model=DEFAULT_MODEL,
            description="Guides users through BRD data collection.",
            instruction=CONVERSATION_SYSTEM_PROMPT,
            tools=make_tool_list(confluence_tools),
        )
        gen_agent = LlmAgent(
            name="brd_generation_agent",
            model=DEFAULT_MODEL,
            description="Generates full BRD JSON from stakeholder info and documents.",
            instruction=BRD_GENERATION_SYSTEM_PROMPT,
            tools=make_tool_list(confluence_tools),
        )
        _adk["session_service"] = session_service
        _adk["conv_runner"] = Runner(
            agent=conv_agent,
            app_name="brd_conversation",
            session_service=session_service,
        )
        _adk["gen_runner"] = Runner(
            agent=gen_agent,
            app_name="brd_generation",
            session_service=session_service,
        )
        _adk["confluence_available"] = confluence_tools is not None
        logger.info("ADK runners initialised (confluence=%s).", _adk["confluence_available"])
    return _adk


async def _ensure_adk_session(app_name: str, user_id: str, session_id: str) -> None:
    """
    Guarantee an ADK session exists.

    Strategy: always call create_session first.
    - If it succeeds → session is new, we're done.
    - If it raises (session already exists) → swallow and continue.

    This avoids the get_session → raise → create pattern which breaks when
    newer ADK versions return None instead of raising for missing sessions.
    """
    adk = _get_adk()
    try:
        await ensure_session(
            adk["session_service"],
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        logger.info("ADK session created: app=%s sid=%s", app_name, session_id)
    except Exception:
        # Already exists — that's fine
        logger.info("ADK session already exists: app=%s sid=%s", app_name, session_id)


# ── Public entry points ───────────────────────────────────────────────────────

async def process_turn(
    session: ConversationSession,
    user_message: str,
) -> tuple[str, ConversationSession]:
    """Handle one user text message. Returns (reply, updated_session)."""
    logger.info("process_turn: session_id=%s, step=%s, message_preview=%s",
                session.session_id, session.step, user_message[:50])

    # Internal trigger used by create_session — fire greeting without recording
    # the synthetic message in history or attempting project name capture.
    if user_message == "__INIT__":
        logger.info("Initializing session with greeting: session_id=%s", session.session_id)
        return await _run_conversation_agent(session, "Hello")

    session.add_user_message(user_message)

    if session.step == ConversationStep.COMPLETE:
        logger.info("Session already complete: session_id=%s, brd_path=%s",
                   session.session_id, session.final_brd_path)
        reply = (
            "Your BRD is already complete!\n"
            f"📄 File: `{session.final_brd_path}`\n\n"
            "Start a new session to create another BRD."
        )
        session.add_assistant_message(reply)
        return reply, session

    if session.step == ConversationStep.CONFIRM_ROLES:
        logger.info("Handling role confirmation: session_id=%s", session.session_id)
        return await _handle_role_confirmation(session, user_message)

    if session.step == ConversationStep.COLLECT_DOCS:
        logger.info("Processing document collection step: session_id=%s", session.session_id)
        skip_words = ["no", "skip", "none", "generate", "proceed",
                      "done", "no documents", "no files", "no docs", "retry"]
        if any(w in user_message.lower() for w in skip_words):
            return await _trigger_generation(session)
        reply = (
            "📎 Please use **`POST /sessions/{session_id}/upload-docs`** to attach files "
            "(`.pdf`, `.docx`, `.txt`).\n\n"
            "If you have no documents, reply **\"no documents\"**."
        )
        session.add_assistant_message(reply)
        return reply, session

    if session.step == ConversationStep.GENERATING:
        logger.warning("User sent message during generation: session_id=%s", session.session_id)
        reply = "Still generating — please wait..."
        session.add_assistant_message(reply)
        return reply, session

    # ── Brownfield update flow steps (delegated to brd_update_agent) ───────────
    if session.step == ConversationStep.UPDATE_COLLECT_LINK:
        logger.info("Processing update link: session_id=%s", session.session_id)
        return await validate_confluence_page(session, user_message)

    if session.step == ConversationStep.UPDATE_COLLECT_CONTENT:
        logger.info("Processing update content from chat: session_id=%s", session.session_id)
        return await process_update_content_from_chat(session, user_message)

    if session.step == ConversationStep.UPDATE_GENERATING:
        logger.warning("User sent message during update: session_id=%s", session.session_id)
        reply = "Still updating the BRD — please wait..."
        session.add_assistant_message(reply)
        return reply, session

    if session.step == ConversationStep.UPDATE_COMPLETE:
        logger.info("Update already complete: session_id=%s", session.session_id)
        reply = (
            "Your BRD has been updated and published to Confluence!\n"
            f"📄 Page: {session.confluence_page_url or session.confluence_page_id}\n\n"
            "Start a new session to create or update another BRD."
        )
        session.add_assistant_message(reply)
        return reply, session

    # ── Brownfield update flow steps (delegated to brd_update_agent) ───────────
    if session.step == ConversationStep.UPDATE_COLLECT_LINK:
        logger.info("Processing update link: session_id=%s", session.session_id)
        return await validate_confluence_page(session, user_message)

    if session.step == ConversationStep.UPDATE_COLLECT_CONTENT:
        logger.info("Processing update content from chat: session_id=%s", session.session_id)
        return await process_update_content_from_chat(session, user_message)

    if session.step == ConversationStep.UPDATE_GENERATING:
        logger.warning("User sent message during update: session_id=%s", session.session_id)
        reply = "Still updating the BRD — please wait..."
        session.history.append(ChatMessage(role="assistant", content=reply))
        return reply, session

    if session.step == ConversationStep.UPDATE_COMPLETE:
        logger.info("Update already complete: session_id=%s", session.session_id)
        reply = (
            "Your BRD has been updated and published to Confluence!\n"
            f"📄 Page: {session.confluence_page_url or session.confluence_page_id}\n\n"
            "Start a new session to create or update another BRD."
        )
        session.history.append(ChatMessage(role="assistant", content=reply))
        return reply, session

    logger.info("Passing to conversation agent: session_id=%s, step=%s",
                session.session_id, session.step)
    return await _run_conversation_agent(session, user_message)


async def process_docs_uploaded(
    session: ConversationSession,
    accepted_files: list[tuple[str, str]],
    rejected_files: list[str],
    auto_generate: bool = False,
) -> tuple[str, ConversationSession]:
    """
    Called after /upload-docs extracts text.
    Accumulates docs and either asks for more (normal mode) or
    immediately triggers BRD generation (auto_generate=True / one-shot mode).
    """
    logger.info("process_docs_uploaded: session_id=%s, accepted=%d, rejected=%d, auto_generate=%s",
               session.session_id, len(accepted_files), len(rejected_files), auto_generate)
    
    for fname, text in accepted_files:
        logger.info("Adding document: session_id=%s, file=%s, size=%d",
                    session.session_id, fname, len(text))
        session.documents_text.append(f"=== {fname} ===\n{text.strip()}")

    lines: list[str] = []
    if accepted_files:
        names = ", ".join(f"**{f}**" for f, _ in accepted_files)
        lines.append(f"Received and extracted: {names}")
    if rejected_files:
        lines.append(
            f"Could not process: {', '.join(rejected_files)}\n"
            "(Only .pdf, .docx, and .txt are supported.)"
        )
    lines.append(f"\nTotal documents loaded: **{len(session.documents_text)}**")

    if auto_generate:
        logger.info("Auto-generate mode: session_id=%s, stakeholders=%d",
                   session.session_id, len(session.stakeholders))
        # One-shot mode — surface what was captured and ask for confirmation
        if session.stakeholders:
            lines.append(f"\n📋 **Project:** {session.project_name}")
            lines.append("**Stakeholders captured:**")
            for i, s in enumerate(session.stakeholders, start=1):
                lines.append(
                    f"  {i}. {s.name} | {s.email} | {s.role.value}"
                )
        lines.append(
            "\nPlease confirm the stakeholder names, roles and emails to proceed "
            "with BRD draft generation. Type **yes** to continue, or resend "
            "corrected details via chat."
        )
        session.step = ConversationStep.CONFIRM_ROLES
        reply = "\n".join(lines)
        session.add_assistant_message(reply)
        return reply, session
    else:
        lines.append(
            "\nUpload more files, or reply **\"generate\"** to start BRD generation now."
        )
        reply = "\n".join(lines)
        session.add_assistant_message(reply)
        return reply, session


# ── Role confirmation ─────────────────────────────────────────────────────────

async def _handle_role_confirmation(
    session: ConversationSession, user_message: str
) -> tuple[str, ConversationSession]:
    logger.info("_handle_role_confirmation: session_id=%s attempts=%d",
                session.session_id, session.correction_attempts)
    msg    = user_message.strip().lower()
    affirm = any(w in msg for w in
                 ["yes", "correct", "looks good", "ok", "confirm",
                  "proceed", "good", "yep", "yup", "sure"])
    if affirm:
        # Refuse to generate without a usable project name.
        cleaned_name, name_err = validate_project_name(session.project_name)
        if name_err:
            session.step = ConversationStep.COLLECT_PROJECT
            reply = (
                f"I still need a valid project name before generating the BRD.\n\n"
                f"**Issue:** {name_err}\n\n"
                "Please reply with the project name."
            )
            session.add_assistant_message(reply)
            return reply, session
        session.project_name = cleaned_name

        if not session.stakeholders:
            reply = (
                "I don't have any stakeholders yet. Please provide at least one in the format:\n"
                "`Name, email@domain.com, Role`"
            )
            session.add_assistant_message(reply)
            return reply, session

        session.correction_attempts = 0
        logger.info("Roles confirmed: session_id=%s, stakeholders=%d, has_docs=%s",
                   session.session_id, len(session.stakeholders), bool(session.documents_text))
        if session.documents_text:
            return await _trigger_generation(session)
        session.step = ConversationStep.COLLECT_DOCS
        reply = (
            "Great! Now please **upload your source documents**.\n\n"
            "Use **`POST /sessions/{session_id}/upload-docs`** — "
            "attach `.pdf`, `.docx`, or `.txt` files.\n\n"
            "If you have no documents, reply **\"no documents\"**."
        )
    else:
        parsed = parse_stakeholder_block(user_message)
        if parsed and all_valid(parsed):
            new_list = [
                Stakeholder(name=p.name, email=p.email, role=p.role) for p in parsed
            ]
            new_list, removed = dedupe_stakeholders(new_list)
            session.stakeholders = new_list
            session.correction_attempts = 0
            logger.info("Stakeholders updated: session_id=%s, count=%d, deduped=%d",
                       session.session_id, len(new_list), len(removed))
            reply = _confirmation_message(session.stakeholders)
            if removed:
                reply = (
                    f"I removed {len(removed)} duplicate entr"
                    f"{'y' if len(removed)==1 else 'ies'} ({', '.join(removed)}).\n\n"
                    + reply
                )
        else:
            session.correction_attempts += 1
            errors = format_validation_errors(parsed) if parsed else ""
            if session.correction_attempts >= MAX_CORRECTION_ATTEMPTS:
                logger.warning(
                    "Max stakeholder correction attempts reached: session_id=%s",
                    session.session_id,
                )
                session.step = ConversationStep.COLLECT_ROLES
                session.correction_attempts = 0
                reply = (
                    "I'm having trouble parsing the stakeholder list after several attempts.\n\n"
                    + (f"Last issues:\n\n{errors}\n\n" if errors else "")
                    + "Let's start the stakeholder list over. Please send entries one per line:\n"
                    + "`Name, email@domain.com, Role`"
                )
            else:
                reply = (
                    (f"Issues found:\n\n{errors}\n\n" if errors else "")
                    + f"Please resend corrected entries (attempt "
                      f"{session.correction_attempts}/{MAX_CORRECTION_ATTEMPTS}):\n"
                    + "`Name, email@domain.com, Role` — one per line."
                )
    session.add_assistant_message(reply)
    logger.info("Role confirmation handled: session_id=%s, next_step=%s",
                session.session_id, session.step)
    return reply, session


# ── Trigger generation ────────────────────────────────────────────────────────

async def _trigger_generation(
    session: ConversationSession,
) -> tuple[str, ConversationSession]:
    logger.info("Triggering BRD generation: session_id=%s, stakeholders=%d, docs=%d",
               session.session_id, len(session.stakeholders), len(session.documents_text))
    session.step = ConversationStep.GENERATING
    reply = "Generating your BRD — this may take 30–60 seconds..."
    session.add_assistant_message(reply)
    return await _generate_brd(session)


# ── Conversation ADK agent ────────────────────────────────────────────────────

async def _run_conversation_agent(
    session: ConversationSession, user_message: str
) -> tuple[str, ConversationSession]:
    """One turn through the conversation LlmAgent."""
    logger.info("_run_conversation_agent: session_id=%s, step=%s",
                session.session_id, session.step)
    adk    = _get_adk()
    adk_sid = f"conv_{session.session_id}"

    # Always create upfront — never rely on get_session raising for missing sessions
    await _ensure_adk_session("brd_conversation", "user", adk_sid)

    logger.info("Calling ADK conversation agent: adk_sid=%s timeout=%.1fs",
                adk_sid, LLM_CALL_TIMEOUT_SECONDS)

    try:
        agent_reply = await run_runner_to_text(
            adk["conv_runner"],
            user_id="user",
            session_id=adk_sid,
            prompt=user_message,
            timeout_seconds=LLM_CALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Conversation agent timed out: session=%s", session.session_id)
        reply = "Sorry, the assistant took too long to respond. Please try again."
        session.add_assistant_message(reply)
        return reply, session
    except Exception:
        logger.exception("Conversation agent failed: session=%s", session.session_id)
        session.add_assistant_message(_GENERIC_ERROR_MSG)
        return _GENERIC_ERROR_MSG, session

    logger.info("ADK conversation agent response received: length=%d", len(agent_reply))

    # Detect stakeholder block in user message
    parsed = parse_stakeholder_block(user_message)
    if parsed:
        logger.info("Stakeholder block detected: session_id=%s, count=%d",
                    session.session_id, len(parsed))
        errors = format_validation_errors(parsed)
        if errors:
            logger.warning("Validation errors in stakeholder block: session_id=%s", session.session_id)
            reply = f"I found some issues:\n\n{errors}\n\nPlease correct and resend."
            session.add_assistant_message(reply)
            return reply, session
        if all_valid(parsed):
            logger.info("Valid stakeholder block parsed: session_id=%s, count=%d",
                       session.session_id, len(parsed))
            _maybe_capture_project_name(session, user_message)
            new_list = [
                Stakeholder(name=p.name, email=p.email, role=p.role) for p in parsed
            ]
            new_list, removed = dedupe_stakeholders(new_list)
            session.stakeholders = new_list
            session.step = ConversationStep.CONFIRM_ROLES
            reply = _confirmation_message(session.stakeholders)
            if removed:
                reply = (
                    f"I removed {len(removed)} duplicate entr"
                    f"{'y' if len(removed)==1 else 'ies'} ({', '.join(removed)}).\n\n"
                    + reply
                )
            session.add_assistant_message(reply)
            return reply, session

    # Capture project name if still in early steps
    if session.step in (ConversationStep.GREETING, ConversationStep.COLLECT_PROJECT):
        old_name = session.project_name
        _maybe_capture_project_name(session, user_message)
        if session.project_name and session.project_name != old_name:
            logger.info("Project name captured: session_id=%s, name=%s",
                       session.session_id, session.project_name)
        session.step = ConversationStep.COLLECT_PROJECT

    session.add_assistant_message(agent_reply)
    return agent_reply, session


# ── BRD generation ────────────────────────────────────────────────────────────

async def _generate_brd(
    session: ConversationSession,
) -> tuple[str, ConversationSession]:
    logger.info("Starting BRD generation: session_id=%s, project=%s",
               session.session_id, session.project_name)
    try:
        brd_json  = await _call_generation_agent(session)
        # Defensive schema check — the LLM is contractually obliged to return
        # an object with a "sections" object, but real models occasionally
        # return arrays / strings / nulls.  Reject those upfront.
        if not isinstance(brd_json, dict) or not isinstance(brd_json.get("sections"), dict):
            raise RuntimeError(
                "BRD generation returned unexpected JSON shape "
                "(expected object with 'sections' dict)."
            )
        provided_keys = {k for k, v in brd_json["sections"].items()
                         if isinstance(v, dict) and (v.get("content") or "").strip()}
        missing_section_keys = [k for k in _SECTION_KEY_TO_TITLE if k not in provided_keys]
        logger.info("BRD JSON generated: session_id=%s, sections=%d, missing=%d",
                    session.session_id, len(provided_keys), len(missing_section_keys))

        brd_doc   = _build_brd_document(brd_json, session)
        output_dir = os.environ.get("BRD_OUTPUT_DIR", "./output")
        docx_path  = await generate_brd_docx(brd_doc, output_dir)

        session.final_brd_path = docx_path
        session.step           = ConversationStep.COMPLETE
        session.error          = None

        n_assumed = sum(1 for s in brd_doc.sections if s.is_ai_assumed)
        provided  = {s.role for s in session.stakeholders}
        missing_count = len([r for r in StakeholderRole if r not in provided])
        logger.info("BRD generation complete: session_id=%s, path=%s, assumed_sections=%d, missing_roles=%d",
                   session.session_id, docx_path, n_assumed, missing_count)

        notes: list[str] = []
        if missing_section_keys:
            notes.append(
                f"⚠ {len(missing_section_keys)} section(s) were not produced by the model "
                "and have been filled with placeholder content. Review before publishing."
            )
        if n_assumed:
            notes.append(f"ℹ {n_assumed} section(s) include AI-generated assumptions — please validate.")
        reply = "BRD generated successfully" + ("\n\n" + "\n".join(notes) if notes else "")

    except asyncio.TimeoutError:
        logger.error("BRD generation timed out: session=%s", session.session_id)
        session.step  = ConversationStep.COLLECT_DOCS
        session.error = "BRD generation timed out."
        reply = (
            "BRD generation took too long and was cancelled.\n\n"
            "Reply **\"generate\"** to try again, or upload more / fewer documents first."
        )
    except Exception as exc:
        logger.exception("BRD generation failed: session=%s", session.session_id)
        session.step  = ConversationStep.COLLECT_DOCS
        # Stash the technical detail server-side; tell the user something safe.
        session.error = type(exc).__name__
        reply = (
            "I couldn't finish generating the BRD.\n\n"
            "Reply **\"generate\"** to retry, or upload additional source documents first."
        )

    session.add_assistant_message(reply)
    return reply, session


async def _call_generation_agent(session: ConversationSession) -> dict:
    logger.info("_call_generation_agent: session_id=%s", session.session_id)
    adk    = _get_adk()
    adk_sid = f"gen_{session.session_id}"

    # Always create upfront
    await _ensure_adk_session("brd_generation", "system", adk_sid)

    provided = {s.role for s in session.stakeholders}
    missing  = [r for r in StakeholderRole if r not in provided]
    logger.info("Stakeholder analysis: session_id=%s, provided=%d, missing=%d",
                session.session_id, len(provided), len(missing))

    prompt = BRD_GENERATION_USER_PROMPT.format(
        project_name=sanitize_for_prompt(
            session.project_name or "Unnamed Project", "project_name"),
        stakeholders_block="\n".join(
            f"- {sanitize_for_prompt(s.name, 'stakeholder.name')} | "
            f"{sanitize_for_prompt(s.email, 'stakeholder.email')} | {s.role.value}"
            for s in session.stakeholders
        ) or "None provided.",
        missing_roles_block="\n".join(f"- {r.value}" for r in missing)
                            if missing else "None — all roles provided.",
        documents_block=sanitize_for_prompt(
            "\n\n".join(session.documents_text)
            if session.documents_text
            else "No documents provided. Generate all sections from best-practice assumptions.",
            "documents_block"),
    )

    logger.info("Calling ADK generation agent: adk_sid=%s timeout=%.1fs",
                adk_sid, LLM_CALL_TIMEOUT_SECONDS)
    raw = await run_runner_to_text(
        adk["gen_runner"],
        user_id="system",
        session_id=adk_sid,
        prompt=prompt,
        timeout_seconds=LLM_CALL_TIMEOUT_SECONDS,
    )
    logger.info("ADK generation agent response received: length=%d", len(raw))
    return parse_llm_json(raw)


def _build_brd_document(brd_json: dict, session: ConversationSession) -> BRDDocument:
    logger.info("Building BRD document: session_id=%s, sections_in_json=%d",
                session.session_id, len(brd_json.get("sections", {})))
    sections_data = brd_json.get("sections", {})
    sections = []
    for key, title in _SECTION_KEY_TO_TITLE.items():
        sec           = sections_data.get(key, {})
        content       = sec.get("content", "")
        is_ai_assumed = sec.get("is_ai_assumed", not bool(content))
        if not content:
            content = (
                "*⚠ AI-generated assumption — no source data provided. "
                "Please review and validate with stakeholders.*"
            )
            is_ai_assumed = True
        sections.append(BRDSection(title=title, content=content, is_ai_assumed=is_ai_assumed))
    return BRDDocument(
        project_name=session.project_name or brd_json.get("project_name", "Unnamed Project"),
        stakeholders=session.stakeholders,
        sections=sections,
        raw_json=brd_json,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _confirmation_message(stakeholders: list[Stakeholder]) -> str:
    lines = ["Here's what I've captured — please confirm:\n"]
    for i, s in enumerate(stakeholders, 1):
        lines.append(f"**{i}.** {s.name} | {s.email} | {s.role.value}")
    provided = {s.role for s in stakeholders}
    missing  = [r for r in StakeholderRole if r not in provided]
    if missing:
        lines.append(
            "\n**Roles not assigned** (AI will generate those sections with disclaimer):\n"
            + "\n".join(f"  - {r.value}" for r in missing)
        )
    lines.append(
        "\nType **yes** to continue, or correct any entries "
        "(e.g. `2. Bob Jones, bob@acme.com, Solution Architect`)."
    )
    return "\n".join(lines)


def _maybe_capture_project_name(session: ConversationSession, text: str):
    if session.project_name:
        return
    _GREETINGS = {
        "hi", "hello", "hey", "hiya", "howdy", "greetings", "sup", "yo",
        "good morning", "good afternoon", "good evening", "good day",
        "yes", "no", "ok", "okay", "sure", "thanks", "thank you", "bye",
    }
    stripped = text.strip().strip('"\'')
    if stripped.lower() in _GREETINGS:
        return
    candidate: str | None = None
    m = re.search(r"project(?:\s+name)?[:\s]+(.+)", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip().strip('"\'')
    elif len(stripped) < 80 and "@" not in stripped and "," not in stripped:
        candidate = stripped

    if not candidate:
        return
    cleaned, err = validate_project_name(candidate)
    if err:
        logger.info("Project name candidate rejected: %s (%s)", candidate[:80], err)
        return
    session.project_name = cleaned
    logger.info("Project name captured: %s", session.project_name)