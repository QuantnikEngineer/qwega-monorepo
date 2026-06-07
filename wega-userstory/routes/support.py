import asyncio
import json
import logging
import os
from typing import Any

from fastapi import HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


logger = logging.getLogger("main")


AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_TIMEOUT_SECONDS", "480"))


def extract_text_from_event(event) -> str | None:
    """Safely extract non-thought text from an ADK event."""
    try:
        if event.content and event.content.parts:
            return "".join(
                part.text for part in event.content.parts
                if hasattr(part, "text") and part.text
                and not getattr(part, "thought", False)
            )
    except Exception:
        pass
    return None


def _strip_markdown_code_fences(text: str) -> str:
    """Remove surrounding Markdown code fences and return inner text."""
    if not text or "```" not in text:
        return text

    import re

    matches = list(re.finditer(r"```(?:json)?\s*\n?([\s\S]*?)```", text, re.IGNORECASE))
    if matches:
        return matches[-1].group(1).strip()

    first = text.find("```")
    last = text.rfind("```")
    if first == -1 or last == -1 or first == last:
        return text

    inner = text[first + 3:last].lstrip()
    if inner.lower().startswith("json"):
        inner = inner[4:].lstrip("\n\r ")

    return inner.strip()


def parse_agent_json(final_text: str | None) -> dict | None:
    """Strictly extract the JSON object emitted by an agent."""
    if not final_text:
        return None

    cleaned = _strip_markdown_code_fences(final_text)

    try:
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else None
    except Exception:
        pass

    depth = 0
    start = -1
    in_string = False
    escape = False
    for idx, ch in enumerate(cleaned):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = cleaned[start:idx + 1]
                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else None
                except Exception:
                    start = -1
    return None


async def _run_agent_to_text(
    agent,
    app_name: str,
    user_text: str,
    timeout_seconds: float = AGENT_TIMEOUT_SECONDS,
) -> str | None:
    """Run an ADK agent and return the final response text."""

    async def _run() -> str | None:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            session_service=session_service,
            app_name=app_name,
        )
        session = await session_service.create_session(
            app_name=app_name, user_id="api_user",
        )
        message = Content(role="user", parts=[Part(text=user_text)])
        text: str | None = None
        event_count = 0
        async for event in runner.run_async(
            user_id="api_user", session_id=session.id, new_message=message,
        ):
            event_count += 1
            if event.is_final_response():
                text = extract_text_from_event(event)
        logger.debug("Agent %s yielded %d events", app_name, event_count)
        return text

    return await asyncio.wait_for(_run(), timeout=timeout_seconds)


async def run_agent_or_timeout_http(
    *,
    agent,
    app_name: str,
    user_text: str,
    timeout_log_label: str,
    timeout_detail: str,
) -> str | None:
    """Run an agent and translate model timeouts into a 504 HTTP response."""
    try:
        return await _run_agent_to_text(
            agent,
            app_name=app_name,
            user_text=user_text,
        )
    except asyncio.TimeoutError:
        logger.error(
            "%s exceeded timeout of %.0fs",
            timeout_log_label,
            AGENT_TIMEOUT_SECONDS,
        )
        raise HTTPException(504, timeout_detail)


def build_story_update_description(new_description: str, acceptance_criteria: list) -> str:
    """Combine story description and acceptance criteria into a single string."""
    parts = [new_description.strip()]
    if acceptance_criteria:
        parts.append("\nAcceptance Criteria:")
        for ac in acceptance_criteria:
            criterion = ac.get("criterion") if isinstance(ac, dict) else str(ac)
            if criterion:
                parts.append(f"- {criterion}")
    return "\n".join(parts)


def brd_error_to_http_status(category: str | None) -> int:
    """Map a brd_parser error_category to an outward HTTP status."""
    return {
        "auth": 502,
        "not_found": 404,
        "rate_limit": 503,
        "transient": 502,
        "permanent": 400,
    }.get(category or "", 400)


def find_duplicate_strings(values: list[str]) -> list[str]:
    """Return a sorted list of duplicate strings while preserving behavior."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return sorted(duplicates)


def batch_operation_status(results: list[dict[str, Any]]) -> str:
    """Collapse per-item operation results into a top-level API status."""
    return (
        "success"
        if all(result.get("status") == "success" for result in results)
        else "partial_error"
    )


def raise_internal_error(log_message: str, detail_prefix: str, exc: Exception) -> None:
    """Log an exception and raise the endpoint's standard 500 response."""
    logger.exception("%s: %s", log_message, str(exc))
    raise HTTPException(
        status_code=500,
        detail=f"{detail_prefix}: {str(exc)}",
    )