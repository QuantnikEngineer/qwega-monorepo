import logging
import os
import re
from typing import Optional
from html import unescape
from urllib.parse import urlparse

import requests

from .http_utils import (
    ERROR_AUTH,
    ERROR_NOT_FOUND,
    ERROR_PERMANENT,
    ERROR_RATE_LIMITED,
    ERROR_TRANSIENT,
    classify_http_error,
    http_request_with_retry,
)
from .jira_common import get_optional_jira_auth

logger = logging.getLogger(__name__)


# Minimum useful BRD content length, in characters.  Anything below this is
# almost certainly an empty/placeholder Confluence page and should be rejected
# rather than fed to the agent (which would otherwise hallucinate output).
MIN_BRD_CONTENT_CHARS = int(os.getenv("MIN_BRD_CONTENT_CHARS", "50"))

# Hard cap on URL length to prevent memory abuse / oversized HTTP requests.
MAX_CONFLUENCE_URL_LENGTH = 2048


def validate_confluence_url(url: str) -> tuple[bool, str]:
    """Validate that the given URL points to a Confluence page.

    Accepts:
    - Atlassian Cloud:  https://<tenant>.atlassian.net/wiki/...
    - Confluence Server/DC: any host where the path contains /wiki/spaces/
      or /pages/ (common on-premise patterns)

    Returns:
        (True, "") if valid.
        (False, reason) if invalid.
    """
    if not url or not url.strip():
        return False, "URL must not be empty."

    if len(url) > MAX_CONFLUENCE_URL_LENGTH:
        return False, f"URL exceeds maximum length of {MAX_CONFLUENCE_URL_LENGTH} characters."

    if any(ord(ch) < 32 for ch in url):
        return False, "URL contains control characters."

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "Could not parse the provided URL."

    # Must have a proper scheme
    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://."

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    if not host:
        return False, "URL does not contain a valid host."

    # --- Atlassian Cloud ---
    # e.g. mycompany.atlassian.net
    is_atlassian_cloud = host.endswith(".atlassian.net") or host == "atlassian.net"

    # --- Confluence Server / Data Center ---
    # Host contains "confluence" OR path contains Confluence-specific segments
    is_confluence_host = "confluence" in host
    is_confluence_path = (
        "/wiki/spaces/" in path
        or "/wiki/display/" in path
        or re.search(r"/pages/\d+", path) is not None
    )

    if not (is_atlassian_cloud or is_confluence_host or is_confluence_path):
        return (
            False,
            "Only Confluence page URLs are accepted. "
            "Expected a URL from an Atlassian Cloud tenant (*.atlassian.net/wiki/...) "
            "or a Confluence Server/Data Center instance "
            "(e.g. confluence.company.com/... or .../wiki/spaces/.../pages/...).",
        )

    return True, ""


def _extract_page_id_and_base(url: str) -> tuple[str | None, str | None]:
    """Extract the Confluence page ID and base URL from a human-readable URL.

    Supported URL formats:
    - https://domain.atlassian.net/wiki/spaces/SPACE/pages/12345/Title
    - https://domain.atlassian.net/wiki/spaces/SPACE/pages/12345
    """
    match = re.search(r"(/wiki)/spaces/[^/]+/pages/(\d+)", url)
    if match:
        wiki_path = match.group(1)
        page_id = match.group(2)
        # Derive base URL (everything before /wiki)
        base_idx = url.find(wiki_path)
        base_url = url[:base_idx + len(wiki_path)] if base_idx >= 0 else None
        return page_id, base_url
    return None, None


def _html_to_text(html: str) -> str:
    """Convert Confluence storage-format HTML to readable plain text.

    Preserves structure: headings become uppercase lines, list items get
    bullet prefixes, table cells are tab-separated, and <br/> becomes
    newlines.  Formulae and calculation text embedded in <p>, <li>, or
    <td> elements are kept intact.
    """
    if not html:
        return ""

    # Replace common block tags with newlines
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|tr|table|thead|tbody)[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Headings → prefix with marker
    def _heading_repl(m):
        level = m.group(1)
        content = m.group(2)
        prefix = "#" * int(level)
        return f"\n{prefix} {content}\n"

    text = re.sub(r"<h(\d)[^>]*>(.*?)</h\1>", _heading_repl, text, flags=re.IGNORECASE | re.DOTALL)

    # List items → bullet points
    text = re.sub(r"<li[^>]*>\s*", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[ou]l[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Table cells → tab-separated
    text = re.sub(r"<t[dh][^>]*>\s*", "\t", text, flags=re.IGNORECASE)
    text = re.sub(r"</t[dh]>", "", text, flags=re.IGNORECASE)

    # Bold / strong → keep as markers for the LLM
    text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.IGNORECASE | re.DOTALL)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = unescape(text)

    # Clean up excessive whitespace while keeping structure
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
        elif cleaned and cleaned[-1] != "":
            cleaned.append("")

    return "\n".join(cleaned).strip()


def _brd_error(category: str, message: str) -> dict:
    """Build the standard structured BRD parser error response."""
    return {
        "status": "error",
        "error_category": category,
        "error_message": message,
    }


def _validate_brd_content_length(text: str, *, context: str) -> dict | None:
    """Reject empty or trivially short BRD content with stable error responses."""
    stripped_text = text.strip()
    if not stripped_text:
        logger.error("%s returned empty content", context)
        return _brd_error(ERROR_PERMANENT, f"{context} is empty")
    if len(stripped_text) < MIN_BRD_CONTENT_CHARS:
        logger.error(
            "BRD content too short for %s (%d chars, min %d)",
            context,
            len(stripped_text),
            MIN_BRD_CONTENT_CHARS,
        )
        return _brd_error(
            ERROR_PERMANENT,
            (
                f"BRD content is too short ({len(stripped_text)} chars). "
                f"Provide a Confluence page with at least {MIN_BRD_CONTENT_CHARS} characters of content."
            ),
        )
    return None


def parse_brd_from_confluence(url: str) -> dict:
    """Fetches BRD-like content from a Confluence page URL.

    Tries the Confluence REST API first (``/rest/api/content/{id}?expand=body.storage``)
    to get clean structured HTML, then converts it to readable text.  Falls
    back to a raw HTTP GET if the page-ID cannot be extracted from the URL.

    Uses optional Basic Auth via environment variables:

    - JIRA_EMAIL
    - JIRA_API_TOKEN

    Returns ``{"status": "success", "content": text}`` on success,
    otherwise ``{"status": "error", "error_message": ...}``.
    """

    logger.info(f"Fetching BRD content from Confluence URL: {url}")

    if not url or not url.strip():
        logger.error("Empty Confluence URL provided")
        return _brd_error(ERROR_PERMANENT, "Empty Confluence URL")

    auth = get_optional_jira_auth()

    try:
        page_id, base_wiki_url = _extract_page_id_and_base(url.strip())

        if page_id and base_wiki_url:
            api_url = f"{base_wiki_url}/rest/api/content/{page_id}?expand=body.storage,title"
            logger.info("Using Confluence REST API: %s", api_url)

            try:
                response = http_request_with_retry(
                    "GET",
                    api_url,
                    auth=auth,
                    headers={"Accept": "application/json"},
                )
            except requests.exceptions.RequestException as exc:
                logger.error("Confluence REST API network error: %s", exc)
                return _brd_error(
                    ERROR_TRANSIENT,
                    f"Network error contacting Confluence: {exc}",
                )

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    logger.error("Confluence REST API returned non-JSON body")
                    return _brd_error(
                        ERROR_PERMANENT,
                        "Confluence REST API returned a non-JSON response.",
                    )
                page_title = data.get("title", "")
                storage_html = (
                    data.get("body", {}).get("storage", {}).get("value", "")
                )

                if not storage_html or not storage_html.strip():
                    logger.error(
                        "Confluence REST API returned empty body for page %s", page_id
                    )
                    return _brd_error(
                        ERROR_PERMANENT,
                        "Confluence page exists but contains no content. Add BRD content to the page and retry.",
                    )

                text = _html_to_text(storage_html)
                if page_title:
                    text = f"# {page_title}\n\n{text}"

                length_error = _validate_brd_content_length(
                    text,
                    context=f"Confluence page {page_id}",
                )
                if length_error:
                    return length_error

                logger.info(
                    "Confluence REST API fetch completed. Extracted %d characters",
                    len(text),
                )
                return {
                    "status": "success",
                    "content": text,
                    "title": page_title or "",
                }

            # Non-200 from REST API — classify and decide whether to fall back.
            category = classify_http_error(response.status_code)
            if category in (ERROR_AUTH, ERROR_NOT_FOUND, ERROR_RATE_LIMITED):
                # These are deterministic — falling back to raw GET will fail the same way
                # (and for 401/403 may even leak HTML login pages).  Surface immediately.
                logger.error(
                    "Confluence REST API returned %s (%s); not falling back. Body: %s",
                    response.status_code, category, response.text,
                )
                return {
                    **_brd_error(
                        category,
                        _format_http_error("Confluence", response.status_code, response.text),
                    )
                }

            logger.warning(
                "Confluence REST API returned %s, falling back to raw fetch. Body: %s",
                response.status_code, response.text,
            )

        # Fallback: raw HTTP GET
        logger.info("Falling back to raw HTTP GET for: %s", url)
        try:
            response = http_request_with_retry(
                "GET",
                url,
                auth=auth,
                headers={"Accept": "*/*"},
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Confluence raw fetch network error: %s", exc)
            return _brd_error(
                ERROR_TRANSIENT,
                f"Network error contacting Confluence: {exc}",
            )

        if response.status_code != 200:
            category = classify_http_error(response.status_code)
            logger.error(
                "Failed to fetch Confluence page. Status: %s (%s). Body: %s",
                response.status_code, category, response.text,
            )
            return {
                **_brd_error(
                    category,
                    _format_http_error("Confluence", response.status_code, response.text),
                )
            }

        text = response.text or ""
        length_error = _validate_brd_content_length(text, context="Confluence page")
        if length_error:
            if not text.strip():
                return _brd_error(ERROR_PERMANENT, "Confluence page is empty")
            return length_error

        logger.info("Confluence BRD fetch completed. Extracted %d characters", len(text))
        return {"status": "success", "content": text, "title": ""}

    except Exception as e:
        logger.exception("Error fetching BRD from Confluence URL %s: %s", url, str(e))
        return _brd_error(ERROR_TRANSIENT, str(e))


def _format_http_error(service: str, status_code: int, body: str | None) -> str:
    """Build a stable, user-facing error message for an upstream HTTP failure."""
    snippet = (body or "").strip()
    # Keep a generous slice so operators can debug, but bound it so we don't
    # leak entire HTML login pages back to API clients.
    if len(snippet) > 1000:
        snippet = snippet[:1000] + "..."
    if status_code in (401, 403):
        return (
            f"{service} authentication failed (HTTP {status_code}). "
            "Check JIRA_EMAIL / JIRA_API_TOKEN."
        )
    if status_code == 404:
        return f"{service} resource not found (HTTP 404)."
    if status_code == 429:
        return f"{service} is rate-limiting requests (HTTP 429). Retry shortly."
    if 500 <= status_code < 600:
        return f"{service} is currently unavailable (HTTP {status_code})."
    return f"{service} request failed (HTTP {status_code}): {snippet}"