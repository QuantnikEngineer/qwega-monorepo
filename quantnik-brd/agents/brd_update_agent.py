"""
agents/brd_update_agent.py

Brownfield BRD update flow.
Uses MCP Confluence tools (via mcp_confluence) for all page operations.

Flow:
  1. validate_confluence_page  → agent uses MCP to fetch + validate page
  2. process_update_*          → agent matches content + publishes via MCP
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
    ConversationSession, ConversationStep, ChatMessage,
    MAX_UPDATE_MATCH_ATTEMPTS,
)
from utils.prompts import (
    BRD_UPDATE_VALIDATE_SYSTEM_PROMPT,
    BRD_UPDATE_VALIDATE_USER_PROMPT,
    BRD_UPDATE_MATCH_AND_UPDATE_SYSTEM_PROMPT,
    BRD_UPDATE_MATCH_AND_UPDATE_USER_PROMPT,
)
from utils.adk_helpers import ensure_session, make_tool_list, run_runner_to_text
from utils.mcp_confluence import get_confluence_toolset
from utils.json_parser import parse_llm_json
from utils.sanitizer import sanitize_for_prompt
from utils.confluence_exporter import (
    fetch_confluence_page,
    extract_page_id,
    update_confluence_page,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
LLM_CALL_TIMEOUT_SECONDS = float(os.environ.get("LLM_CALL_TIMEOUT_SECONDS", "180"))

_GENERIC_UPDATE_ERROR = (
    "Sorry, something went wrong while updating the BRD. Please try again. "
    "If the issue persists, contact support with this session id."
)


def _classify_mcp_error(exc: BaseException) -> str:
    """Return a short human-readable category for an MCP / Confluence error.

    Pattern-matches the message because the underlying transport doesn't
    expose typed exceptions consistently.
    """
    msg = str(exc).lower()
    if any(t in msg for t in ("timeout", "timed out")):
        return "timeout"
    if any(t in msg for t in ("401", "403", "unauthor", "forbidden", "authentic")):
        return "auth"
    if any(t in msg for t in ("connection", "refused", "unreachable", "dns", "network")):
        return "network"
    if any(t in msg for t in ("404", "not found")):
        return "not_found"
    if any(t in msg for t in ("429", "rate limit")):
        return "rate_limited"
    return "unknown"


def _user_message_for_mcp_error(category: str) -> str:
    return {
        "timeout":      "Confluence took too long to respond. Please try again.",
        "auth":         "Confluence rejected the credentials. Ask an admin to verify the API token.",
        "network":      "I couldn't reach Confluence — the network may be down. Please retry shortly.",
        "not_found":    "Confluence couldn't find that page. Please re-check the URL or page ID.",
        "rate_limited": "Confluence is rate-limiting us right now. Please retry in a minute.",
    }.get(category, "There was a problem talking to Confluence. Please try again.")


# ── Lazy ADK singletons ──────────────────────────────────────────────────────

_update_adk: dict = {}
_update_adk_lock = threading.Lock()


def _get_update_adk() -> dict:
    """Initialise update-specific ADK objects once, lazily."""
    if _update_adk:
        return _update_adk
    with _update_adk_lock:
        if _update_adk:
            return _update_adk

        session_service = InMemorySessionService()

        try:
            confluence_tools = get_confluence_toolset()
            logger.info("MCP Confluence toolset loaded for update agents.")
        except Exception as exc:
            confluence_tools = None
            logger.warning("MCP Confluence unavailable for update agents: %s", exc)

        validate_agent = LlmAgent(
            name="brd_validate_agent",
            model=DEFAULT_MODEL,
            description="Validates Confluence BRD pages via MCP tools.",
            instruction=BRD_UPDATE_VALIDATE_SYSTEM_PROMPT,
            tools=make_tool_list(confluence_tools),
        )
        # The update agent only does matching + body generation. Publishing is
        # done by the host app via the direct Confluence REST API, so no MCP
        # tools are passed in. This avoids LLM->MCP failures during publish.
        update_agent = LlmAgent(
            name="brd_update_agent",
            model=DEFAULT_MODEL,
            description="Matches content and merges BRD updates (publishing handled by host).",
            instruction=BRD_UPDATE_MATCH_AND_UPDATE_SYSTEM_PROMPT,
            tools=[],
        )

        _update_adk["session_service"] = session_service
        _update_adk["validate_runner"] = Runner(
            agent=validate_agent,
            app_name="brd_validate",
            session_service=session_service,
        )
        _update_adk["update_runner"] = Runner(
            agent=update_agent,
            app_name="brd_update",
            session_service=session_service,
        )
        _update_adk["confluence_available"] = confluence_tools is not None
        logger.info("Update ADK runners initialised (confluence=%s).",
                     _update_adk["confluence_available"])
    return _update_adk


async def _ensure_session(app_name: str, user_id: str, session_id: str) -> None:
    adk = _get_update_adk()
    await ensure_session(
        adk["session_service"],
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )


# ── URL / page-ID pre-validator ───────────────────────────────────────────────

# Confluence URL patterns accepted:
#   Cloud  : https://<tenant>.atlassian.net/wiki/spaces/<KEY>/pages/<id>/...
#   Server : https://<host>/wiki/spaces/<KEY>/pages/<id>/...
#   Server : https://<host>/wiki/display/<KEY>/...
#   Legacy : https://<host>/pages/viewpage.action?pageId=<id>
# A bare numeric page ID is also accepted.
_CONFLUENCE_URL_RE = re.compile(
    r"https?://[^\s]+"                          # scheme + host
    r"(?:"
    r"/wiki/(?:spaces/[^/\s]+/pages/\d+|display/[^/\s]+)"  # /wiki/spaces/.../pages/<id> or /wiki/display/
    r"|/pages/viewpage\.action\?[^\s]*pageId=\d+"           # legacy viewpage.action
    r")",
    re.IGNORECASE,
)
_CONFLUENCE_PAGE_ID_RE = re.compile(r"^\d+$")

_BRD_TITLE_HINTS = (
    "brd",
    "business requirements",
    "requirements document",
)
_BRD_CONTENT_HINTS = (
    "executive summary",
    "business background",
    "business objectives",
    "scope",
    "business requirements",
    "non-functional",
    "stakeholder",
    "raci",
    "glossary",
)
_MIN_EXISTING_BRD_CONTENT_CHARS = 40


def _normalise_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _looks_like_brd_page(title: str, content: str) -> bool:
    normalised_title = _normalise_text(title).lower()
    if any(hint in normalised_title for hint in _BRD_TITLE_HINTS):
        return True

    normalised_content = _normalise_text(content).lower()
    if len(normalised_content) < _MIN_EXISTING_BRD_CONTENT_CHARS:
        return False

    marker_hits = sum(1 for hint in _BRD_CONTENT_HINTS if hint in normalised_content)
    return marker_hits >= 2


def _get_page_validation_error(result: dict) -> str | None:
    page_id = str(result.get("page_id", "")).strip()
    title = str(result.get("title", "")).strip()
    content = str(result.get("content", "")).strip()
    explicit_is_brd = result.get("is_brd")

    if not page_id:
        return "Confluence returned the page, but not a usable page ID. Please try again."
    if not title:
        return "Confluence returned the page, but not a usable page title. Please try again."
    if explicit_is_brd is False:
        return result.get("reason") or "The page exists, but it does not appear to be a BRD page."
    if len(_normalise_text(content)) < _MIN_EXISTING_BRD_CONTENT_CHARS:
        return (
            "I found the page, but it doesn't contain enough readable BRD content to compare safely. "
            "Please provide the actual BRD page."
        )

    if explicit_is_brd is not True and not _looks_like_brd_page(title, content):
        return (
            "The page exists, but it doesn't look like a BRD page with enough structured BRD content "
            "to compare safely. Please provide the actual BRD page."
        )

    return None


def _set_revalidation_state(session: ConversationSession, current_version: int | None = None) -> None:
    session.step = ConversationStep.UPDATE_COLLECT_LINK
    session.existing_brd_content = None
    if current_version is not None:
        session.existing_page_version = current_version


def _safe_prompt_text(text: str | None, field_name: str) -> str:
    return sanitize_for_prompt(text or "", field_name)


def _is_valid_confluence_input(link: str) -> bool:
    """Return True only if `link` is a Confluence page URL or a bare numeric page ID."""
    stripped = link.strip()
    return bool(_CONFLUENCE_URL_RE.search(stripped)) or bool(_CONFLUENCE_PAGE_ID_RE.match(stripped))


# ── Public entry points ──────────────────────────────────────────────────────

async def validate_confluence_page(
    session: ConversationSession,
    link: str,
) -> tuple[str, ConversationSession]:
    """Validate a Confluence page via MCP tools and store page info in session."""
    logger.info("validate_confluence_page: session_id=%s, link=%s",
                session.session_id, link[:100])

    # Fast-fail: reject obviously invalid input before calling the LLM+MCP stack.
    # session.step intentionally stays at UPDATE_COLLECT_LINK so the user is re-prompted.
    if not _is_valid_confluence_input(link):
        reply = (
            "That doesn't look like a valid Confluence link.\n\n"
            "Please provide one of:\n"
            "- A full Confluence page URL, e.g. "
            "`https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/123456/Page-Title`\n"
            "- A numeric Confluence page ID, e.g. `123456`"
        )
        session.add_assistant_message(reply)
        return reply, session

    try:
        result = await _call_validate_agent(session, link)
    except asyncio.TimeoutError:
        logger.error("Validation agent timed out: session=%s", session.session_id)
        reply = "Confluence took too long to respond while validating the page. Please try again."
        session.add_assistant_message(reply)
        return reply, session
    except Exception as exc:
        logger.exception("Validation agent failed: session=%s", session.session_id)
        category = _classify_mcp_error(exc)
        friendly = _user_message_for_mcp_error(category)
        reply = (
            f"I couldn't validate the Confluence page.\n\n"
            f"**Reason:** {friendly}\n\n"
            "Please provide a valid Confluence page URL or page ID."
        )
        session.add_assistant_message(reply)
        return reply, session

    if not result.get("found"):
        error = result.get("error", "Page not found")
        reply = (
            f"I couldn't find a BRD at that link.\n\n"
            f"**Reason:** {error}\n\n"
            "Please provide a valid Confluence page URL or page ID."
        )
        session.add_assistant_message(reply)
        return reply, session

    validation_error = _get_page_validation_error(result)
    if validation_error:
        reply = (
            "I found the Confluence page, but I can't safely use it for BRD updates.\n\n"
            f"**Reason:** {validation_error}\n\n"
            "Please provide the actual BRD page URL or page ID."
        )
        session.add_assistant_message(reply)
        return reply, session

    # Store page info in session
    session.confluence_page_id = str(result.get("page_id", ""))
    session.confluence_page_url = result.get("page_url") or (link.strip() if _CONFLUENCE_URL_RE.search(link.strip()) else None)
    session.existing_page_title = result.get("title", "")
    session.existing_page_version = result.get("version", 1)
    session.existing_brd_content = result.get("content", "")
    session.project_name = session.existing_page_title
    session.step = ConversationStep.UPDATE_COLLECT_CONTENT
    session.error = None
    # Re-validating the link resets any prior match-attempt counter so a
    # fresh content cycle starts from zero.
    session.update_match_attempts = 0

    reply = (
        f"Found the existing BRD: **{session.existing_page_title}** "
        f"(version {session.existing_page_version})\n\n"
        "Now, please provide the content you'd like to update. You can:\n"
        "1. **Upload a document** (`.pdf`, `.docx`, `.txt`) with the changes\n"
        "2. **Type the update content** directly in the chat\n\n"
        "I'll verify the content matches this BRD before applying updates."
    )
    session.add_assistant_message(reply)
    logger.info("Confluence page validated via MCP: session_id=%s, title=%s",
                session.session_id, session.existing_page_title)
    return reply, session


async def process_update_content_from_chat(
    session: ConversationSession,
    user_message: str,
) -> tuple[str, ConversationSession]:
    """Process update content provided via chat."""
    logger.info("process_update_content_from_chat: session_id=%s, len=%d",
                session.session_id, len(user_message))
    if not user_message.strip():
        reply = (
            "I didn't receive any update content.\n\n"
            "Please type the changes you want to apply, or upload a document with the update content."
        )
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        session.add_assistant_message(reply)
        return reply, session

    session.step = ConversationStep.UPDATE_GENERATING
    session.add_assistant_message("Analyzing your update content against the existing BRD...")
    return await _match_and_update_brd(session, user_message, source="chat message")


async def process_update_docs_uploaded(
    session: ConversationSession,
    accepted_files: list[tuple[str, str]],
    rejected_files: list[str],
) -> tuple[str, ConversationSession]:
    """Process uploaded files for BRD update."""
    logger.info("process_update_docs_uploaded: session_id=%s, accepted=%d, rejected=%d",
                session.session_id, len(accepted_files), len(rejected_files))

    if not accepted_files:
        lines = []
        if rejected_files:
            lines.append(f"Could not process: {', '.join(rejected_files)}")
        lines.append("Please upload a valid document or type the update content in chat.")
        reply = "\n".join(lines)
        session.add_assistant_message(reply)
        return reply, session

    combined = "\n\n".join(f"=== {f} ===\n{t.strip()}" for f, t in accepted_files)
    file_names = ", ".join(f"**{f}**" for f, _ in accepted_files)

    session.step = ConversationStep.UPDATE_GENERATING
    session.add_assistant_message(f"Received: {file_names}\nAnalyzing against the existing BRD...")
    return await _match_and_update_brd(session, combined, source=f"uploaded: {file_names}")


# ── Internal agent calls ─────────────────────────────────────────────────────

async def _call_validate_agent(session: ConversationSession, link: str) -> dict:
    """Validate a Confluence page directly via the REST API.

    Replaces the previous LLM+MCP roundtrip. The LLM path was non-deterministic
    (often returned malformed JSON for long page bodies, which surfaced as a
    generic "There was a problem talking to Confluence" error). Going direct
    is faster, deterministic, and lets real HTTP errors (401/403/404) reach
    the classifier so the user sees an accurate reason.
    """
    page_id = extract_page_id(link)
    if not page_id:
        return {
            "found": False,
            "error": "Could not extract a numeric Confluence page ID from the input.",
        }

    logger.info("validate(direct REST): session_id=%s page_id=%s",
                session.session_id, page_id)

    page = await fetch_confluence_page(page_id)

    return {
        "found": True,
        "page_id": page["page_id"],
        "title": page["title"],
        "version": page["version"],
        "page_url": page["page_url"],
        "content": page["content"],
    }


async def _match_and_update_brd(
    session: ConversationSession,
    update_content: str,
    source: str,
) -> tuple[str, ConversationSession]:
    """Single agent call: match content + update BRD via MCP Confluence tools."""
    logger.info("_match_and_update_brd: session_id=%s, source=%s, attempts=%d",
                session.session_id, source, session.update_match_attempts)

    try:
        result = await _call_update_agent(session, update_content, source)
    except asyncio.TimeoutError:
        logger.error("Update agent timed out: session=%s", session.session_id)
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        session.error = "timeout"
        reply = "Confluence took too long to respond. Please try again."
        session.add_assistant_message(reply)
        return reply, session
    except Exception as exc:
        logger.exception("Update agent failed: session=%s", session.session_id)
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        category = _classify_mcp_error(exc)
        session.error = category
        friendly = _user_message_for_mcp_error(category)
        reply = f"Update failed: {friendly}\n\nPlease try again."
        session.add_assistant_message(reply)
        return reply, session

    if result.get("version_conflict"):
        current_version = result.get("current_version")
        previous_version = session.existing_page_version
        if isinstance(current_version, int):
            _set_revalidation_state(session, current_version=current_version)
        else:
            _set_revalidation_state(session)
        session.update_match_attempts = 0
        session.error = result.get("error") or "Confluence page version changed during update."
        version_line = ""
        if isinstance(current_version, int) and previous_version is not None:
            version_line = (
                f"\n**Version detected:** Confluence is now at v{current_version}, "
                f"but I had v{previous_version}.\n"
            )
        reply = (
            "The BRD changed in Confluence after validation, so I stopped the update to "
            "avoid overwriting a newer version.\n"
            f"{version_line}"
            f"\n**Reason:** {session.error}\n\n"
            "Please resend the Confluence page URL or page ID so I can re-validate "
            "the latest version before retrying."
        )
        session.add_assistant_message(reply)
        return reply, session

    if result.get("ambiguous"):
        session.update_match_attempts += 1
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        session.error = None
        reason = result.get(
            "reason",
            "The content may be related, but the match is not strong enough to update safely.",
        )
        suggested_focus = result.get(
            "suggested_focus",
            "Please provide the exact BRD section, project terms, or concrete changes you want updated.",
        )
        if session.update_match_attempts >= MAX_UPDATE_MATCH_ATTEMPTS:
            logger.warning("Max ambiguous-match attempts reached: session_id=%s",
                           session.session_id)
            session.update_match_attempts = 0
            session.step = ConversationStep.UPDATE_COLLECT_LINK
            reply = (
                "I'm still not able to safely match your update content to the existing BRD "
                f"after {MAX_UPDATE_MATCH_ATTEMPTS} attempts.\n\n"
                f"**Last reason:** {reason}\n\n"
                "Please re-send the Confluence page URL/ID to re-validate, or contact support "
                "if the BRD page should match this content."
            )
        else:
            reply = (
                "I can't safely apply this update yet because the match with the existing BRD is ambiguous.\n\n"
                f"**Reason:** {reason}\n\n"
                f"**What to send next:** {suggested_focus}\n\n"
                f"_Attempt {session.update_match_attempts}/{MAX_UPDATE_MATCH_ATTEMPTS}._"
            )
        session.add_assistant_message(reply)
        return reply, session

    if not result.get("match"):
        session.update_match_attempts += 1
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        session.error = None
        reason = result.get("reason", "Content does not appear related")
        if session.update_match_attempts >= MAX_UPDATE_MATCH_ATTEMPTS:
            logger.warning("Max no-match attempts reached: session_id=%s",
                           session.session_id)
            session.update_match_attempts = 0
            session.step = ConversationStep.UPDATE_COLLECT_LINK
            reply = (
                f"After {MAX_UPDATE_MATCH_ATTEMPTS} attempts, the content you've provided still "
                f"doesn't match **{session.existing_page_title}**.\n\n"
                "Please re-send the Confluence page URL/ID — you may have intended a different BRD."
            )
        else:
            reply = (
                "The content you provided doesn't appear to match the existing BRD.\n\n"
                f"**Reason:** {reason}\n\n"
                f"The existing BRD is: **{session.existing_page_title}**\n\n"
                "Please provide content that relates to this BRD:\n"
                "1. **Upload a different document**\n"
                "2. **Type the correct update content** in the chat\n\n"
                f"_Attempt {session.update_match_attempts}/{MAX_UPDATE_MATCH_ATTEMPTS}._"
            )
        session.add_assistant_message(reply)
        return reply, session

    if result.get("no_changes"):
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        session.error = None
        reason = result.get("reason", "The provided content is already fully reflected in the existing BRD.")
        reply = (
            "No changes detected — the content you provided is already up to date in the BRD.\n\n"
            f"**Reason:** {reason}\n\n"
            f"The existing BRD **{session.existing_page_title}** was not modified.\n\n"
            "If you have new or different updates, please provide them."
        )
        session.add_assistant_message(reply)
        return reply, session

    published = result.get("published", False)
    summary = result.get("summary", "BRD updated.")
    sections = result.get("sections_updated", [])
    new_version = result.get("new_version")

    if published:
        session.step = ConversationStep.UPDATE_COMPLETE
        session.error = None
        session.update_match_attempts = 0
        if new_version:
            session.existing_page_version = new_version
        sections_list = "\n".join(f"  - **{s}**" for s in sections) if sections else ""
        reply = (
            "BRD updated and published to Confluence!"
            + (f" (version {new_version})" if new_version else "") + "\n\n"
            f"**Summary:** {summary}\n"
            + (f"\n**Sections updated:**\n{sections_list}\n" if sections_list else "")
            + f"\n📄 Page: {session.confluence_page_url or session.confluence_page_id}"
        )
    else:
        session.step = ConversationStep.UPDATE_COLLECT_CONTENT
        raw_err = result.get("error") or "Unknown error"
        session.error = raw_err
        category = _classify_mcp_error(Exception(raw_err))
        friendly = _user_message_for_mcp_error(category) if category != "unknown" else raw_err
        reply = (
            "I matched your content to the BRD, but publishing the update to Confluence failed.\n\n"
            f"**Reason:** {friendly}\n\n"
            "Please retry by re-sending the same update content (the match has been validated)."
        )

    session.add_assistant_message(reply)
    return reply, session


async def _call_update_agent(
    session: ConversationSession,
    update_content: str,
    source: str,
) -> dict:
    """Run the LLM merge step, then publish via the Confluence REST API.

    The LLM only produces the merged Confluence storage HTML in its JSON
    response. Publishing is performed here with a direct PUT to Confluence,
    so a single fragile MCP/stdio path is no longer in the critical path.
    """
    adk = _get_update_adk()
    adk_sid = f"update_{session.session_id}"
    await _ensure_session("brd_update", "user", adk_sid)

    prompt = BRD_UPDATE_MATCH_AND_UPDATE_USER_PROMPT.format(
        page_id=_safe_prompt_text(session.confluence_page_id or "", "page_id"),
        page_title=_safe_prompt_text(session.existing_page_title or "", "page_title"),
        current_version=session.existing_page_version or 1,
        existing_brd_content=_safe_prompt_text(
            session.existing_brd_content or "(empty)",
            "existing_brd_content",
        ),
        update_source=_safe_prompt_text(source, "update_source"),
        update_content=_safe_prompt_text(update_content, "update_content"),
    )

    raw = await run_runner_to_text(
        adk["update_runner"],
        user_id="user",
        session_id=adk_sid,
        prompt=prompt,
        timeout_seconds=LLM_CALL_TIMEOUT_SECONDS,
    )
    logger.info("Update agent response: length=%d", len(raw))
    parsed = parse_llm_json(raw)

    # If the LLM rejected the match or detected no changes, nothing to publish.
    if not parsed.get("match") or parsed.get("ambiguous") or parsed.get("no_changes"):
        return parsed

    body_html = (parsed.get("body_html") or "").strip()
    if not body_html:
        logger.error("Update agent did not return body_html; raw preview=%s", raw[:500])
        return {
            "match": True,
            "no_changes": False,
            "published": False,
            "summary": parsed.get("summary", ""),
            "sections_updated": parsed.get("sections_updated", []),
            "error": "Update agent did not produce a merged page body.",
        }

    page_id = session.confluence_page_id or ""
    title = session.existing_page_title or ""
    current_version = session.existing_page_version or 1

    # Re-fetch the latest version to detect upstream edits before we overwrite.
    try:
        latest = await fetch_confluence_page(page_id)
    except Exception as exc:
        logger.exception("Pre-publish fetch failed: session=%s", session.session_id)
        return {
            "match": True,
            "no_changes": False,
            "published": False,
            "summary": parsed.get("summary", ""),
            "sections_updated": parsed.get("sections_updated", []),
            "error": str(exc),
        }

    if int(latest.get("version") or 0) != int(current_version):
        return {
            "match": True,
            "no_changes": False,
            "published": False,
            "version_conflict": True,
            "current_version": int(latest.get("version") or 0),
            "error": "Confluence page version changed during update.",
        }

    try:
        publish = await update_confluence_page(
            page_id,
            title=title,
            body_html=body_html,
            current_version=int(current_version),
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "409" in msg:
            try:
                latest = await fetch_confluence_page(page_id)
                current = int(latest.get("version") or 0)
            except Exception:
                current = int(current_version)
            return {
                "match": True,
                "no_changes": False,
                "published": False,
                "version_conflict": True,
                "current_version": current,
                "error": msg,
            }
        return {
            "match": True,
            "no_changes": False,
            "published": False,
            "summary": parsed.get("summary", ""),
            "sections_updated": parsed.get("sections_updated", []),
            "error": msg,
        }

    return {
        "match": True,
        "no_changes": False,
        "published": True,
        "summary": parsed.get("summary", "BRD updated."),
        "sections_updated": parsed.get("sections_updated", []),
        "new_version": publish.get("new_version"),
        "page_url": publish.get("page_url"),
    }
