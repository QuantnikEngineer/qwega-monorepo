"""utils/confluence_exporter.py

Helpers for uploading generated BRD .docx files to a Confluence page.

Uses httpx for async HTTP requests to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import httpx
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from html import escape as html_escape, unescape as html_unescape


logger = logging.getLogger(__name__)


# ── Retry helper ─────────────────────────────────────────────────────────────
# Confluence Cloud occasionally returns 429 (rate-limit), 502/503/504, and
# transient connection errors. Retry with exponential backoff + jitter.
_RETRY_STATUS_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 0.75


async def _request_with_retry_async(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Async wrapper around ``httpx`` with bounded retries.

    Retries on transient HTTP statuses and connection-level errors. Honours
    a ``Retry-After`` response header when provided.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = await client.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code not in _RETRY_STATUS_CODES or attempt == _MAX_RETRIES:
                return resp
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            except ValueError:
                wait = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            wait += random.uniform(0, 0.25)
            logger.warning(
                "Confluence %s %s returned %d; retrying in %.2fs (attempt %d/%d)",
                method, url, resp.status_code, wait, attempt, _MAX_RETRIES,
            )
            await asyncio.sleep(wait)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES:
                break
            wait = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            logger.warning(
                "Confluence %s %s connection error: %s; retrying in %.2fs (attempt %d/%d)",
                method, url, exc, wait, attempt, _MAX_RETRIES,
            )
            await asyncio.sleep(wait)
    assert last_exc is not None  # only reachable when all attempts raised
    raise last_exc


@dataclass
class ConfluenceConfig:
    base_url: str
    email: str
    api_token: str
    page_id: str


def _load_config() -> ConfluenceConfig:
    """Load Confluence configuration from environment variables.

    Uses the centralised ``load_confluence_settings()`` which parses
    ``CONFLUENCE_PARENT_PAGE_URL``.  Falls back to legacy env vars so
    the REST API code keeps working either way.

    Raises ``ValueError`` if required values are missing.
    """
    from utils.confluence_config import load_confluence_settings

    cfg = load_confluence_settings()

    if not cfg.page_id:
        raise ValueError(
            "Confluence page_id could not be resolved. "
            "Set CONFLUENCE_PARENT_PAGE_URL with the full page URL."
        )

    return ConfluenceConfig(
        base_url=cfg.base_url,
        email=cfg.email,
        api_token=cfg.api_token,
        page_id=cfg.page_id,
    )


def _build_auth(cfg: ConfluenceConfig) -> httpx.BasicAuth:
    return httpx.BasicAuth(cfg.email, cfg.api_token)


def _build_headers() -> Dict[str, str]:
    return {"X-Atlassian-Token": "no-check"}


async def _get_space_key_for_parent_async(client: httpx.AsyncClient, cfg: ConfluenceConfig) -> str:
    """Resolve the Confluence space key for the configured parent page.

    This lets us keep only a single ``CONFLUENCE_PAGE_ID`` env var which
    acts as the *parent* page (e.g. "Wega BRD" in the screenshot). We look
    up the page once and reuse its ``space.key`` value when creating child
    pages.
    """

    url = f"{cfg.base_url}/rest/api/content/{cfg.page_id}?expand=space"
    resp = await _request_with_retry_async(client, "GET", url, timeout=30.0)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to resolve Confluence space for page {cfg.page_id} "
            f"(status {resp.status_code}): {resp.text}"
        )
    data = resp.json()
    space = data.get("space") or {}
    space_key = (space.get("key") or "").strip()
    if not space_key:
        raise RuntimeError(
            f"Confluence page {cfg.page_id} has no associated space key in API response."
        )
    return space_key


def _slugify_project_name(project_name: str | None) -> str:
    if not project_name:
        return "project"
    # Simple slug: letters/numbers/underscore only, collapse spaces to '_'
    slug = re.sub(r"[^A-Za-z0-9\- ]+", "_", project_name).strip()
    slug = re.sub(r"\s+", "_", slug)
    return slug or "project"


async def _fetch_existing_attachments_async(client: httpx.AsyncClient, cfg: ConfluenceConfig) -> list[dict]:
    """Return all attachment objects on the configured page (paginated).

    The Confluence Cloud API is paginated; we follow ``_links.next`` until
    all results have been collected.
    """

    url = f"{cfg.base_url}/rest/api/content/{cfg.page_id}/child/attachment"
    params = {"limit": "50"}
    results: list[dict] = []

    while True:
        resp = await _request_with_retry_async(client, "GET", url, params=params, timeout=30.0)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Failed to list Confluence attachments (status {resp.status_code}): {resp.text}"
            )
        data = resp.json()
        results.extend(data.get("results", []))

        next_rel = data.get("_links", {}).get("next")
        if not next_rel:
            break
        url = cfg.base_url.rstrip("/") + next_rel
        params = {}

    return results


def _determine_next_version(existing: list[dict], base_prefix: str) -> int:
    """Return the next integer version for the given filename prefix.

    Looks for attachment titles shaped like ``{base_prefix}vN.docx`` and
    returns ``max(N) + 1``. If none are found, returns 1.
    """

    max_version = 0
    pattern = re.compile(re.escape(base_prefix) + r"v(\d+)\.docx$", re.IGNORECASE)
    for item in existing:
        title = (item.get("title") or "").strip()
        m = pattern.search(title)
        if m:
            try:
                ver = int(m.group(1))
                if ver > max_version:
                    max_version = ver
            except ValueError:
                continue
    return max_version + 1 if max_version > 0 else 1


def _docx_to_storage_html(path: Path) -> str:
    """Convert a BRD .docx file into simple Confluence storage HTML.

    The goal is to stay close to the Word layout while keeping the
    implementation small:
    - Heading paragraphs ("Heading 1/2/..." styles) → ``<h1>``, ``<h2>`` …
    - Bullet / numbered lists → ``<ul><li>`` / ``<ol><li>``
    - Normal paragraphs → ``<p>``
    - Basic tables → ``<table><tr><th>/<td>`` with a light header shading
    - AI disclaimer callouts → a bordered, amber-highlighted ``<div>``
    """

    doc = Document(str(path))
    parts: list[str] = []
    open_list: str | None = None  # "ul" | "ol" | None

    def close_list_if_open() -> None:
        """Close any open HTML list tag."""
        nonlocal open_list
        if open_list:
            parts.append(f"</{open_list}>")
            open_list = None

    def render_runs(p: Paragraph) -> str:
        """Render a paragraph's runs with basic bold/italic preservation."""
        chunks: list[str] = []
        for run in p.runs:
            text = (run.text or "")
            if not text:
                continue
            run_html = html_escape(text)
            if getattr(run, "bold", False):
                run_html = f"<strong>{run_html}</strong>"
            if getattr(run, "italic", False):
                run_html = f"<em>{run_html}</em>"
            chunks.append(run_html)
        return "".join(chunks) or html_escape(p.text or "")

    def is_list_paragraph(p: Paragraph) -> bool:
        """Best-effort detection of list paragraphs (bullets/numbers).

        We treat any paragraph with numbering properties as a list item.
        """
        ppr = getattr(p._p, "pPr", None)
        if ppr is None or ppr.numPr is None:
            return False
        return bool(getattr(ppr.numPr, "numId", None))

    # Iterate over block-level items (paragraphs and tables) in document order
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            para = Paragraph(child, doc)
            text = (para.text or "").strip()
            if not text:
                # Blank paragraph breaks any open list but otherwise ignored.
                close_list_if_open()
                continue

            # Special-case the AI disclaimer callout based on its leading text.
            if text.startswith("⚠ AI-Generated Content "):
                close_list_if_open()
                content_html = render_runs(para)
                parts.append(
                    "<div style=\"border-left:4px solid #FFC107;"  "border-top:1px solid #FFC107;"
                    "border-bottom:1px solid #FFC107;background-color:#FFF3CD;"
                    "padding:8px;margin:12px 0;\">"
                    + content_html
                    + "</div>"
                )
                continue

            style_name = (getattr(para.style, "name", "") or "").lower()
            is_list = is_list_paragraph(para)

            if is_list:
                # For now, treat all numbered/bulleted lists as <ul>.
                if open_list != "ul":
                    close_list_if_open()
                    parts.append("<ul>")
                    open_list = "ul"
                item_html = render_runs(para)
                parts.append(f"<li>{item_html}</li>")
                continue

            # Non-list paragraph: ensure any open list is closed first.
            close_list_if_open()

            content_html = render_runs(para)
            if "heading" in style_name:
                # Extract level from "Heading 1", "Heading 2", ...; default h2
                level = 2
                m = re.search(r"(\d+)", style_name)
                if m:
                    try:
                        level = max(1, min(6, int(m.group(1))))
                    except ValueError:
                        pass
                parts.append(f"<h{level}>{content_html}</h{level}>")
            else:
                parts.append(f"<p>{content_html}</p>")

        elif isinstance(child, CT_Tbl):
            # Tables appear where they are in the document flow.
            close_list_if_open()
            table = Table(child, doc)
            parts.append("<table>")
            for row_idx, row in enumerate(table.rows):
                parts.append("<tr>")
                is_header = row_idx == 0
                cell_tag = "th" if is_header else "td"
                style_attr = " style=\"background-color:#D6E4F7;font-weight:bold;\"" if is_header else ""
                for cell in row.cells:
                    cell_text = html_escape((cell.text or "").strip())
                    parts.append(f"<{cell_tag}{style_attr}>{cell_text}</{cell_tag}>")
                parts.append("</tr>")
            parts.append("</table>")

    # Close any trailing list.
    close_list_if_open()

    return "".join(parts) or "<p>[Empty BRD document]</p>"


async def upload_brd_docx_to_confluence(
    file_path: str | os.PathLike[str],
    project_name: str | None,
) -> dict:
    """Upload a generated BRD .docx file as an attachment to Confluence.

    Returns a small dict with ``filename``, ``version`` and ``url`` keys.
    Raises ``ValueError`` for configuration issues and ``RuntimeError`` for
    HTTP/API failures.
    """

    cfg = _load_config()
    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"BRD file not found: {path}")

    slug = _slugify_project_name(project_name)
    base_prefix = f"BRD_{slug}_"

    async with httpx.AsyncClient(auth=_build_auth(cfg), headers=_build_headers()) as client:
        existing = await _fetch_existing_attachments_async(client, cfg)
        next_version = _determine_next_version(existing, base_prefix)

        remote_name = f"{base_prefix}v{next_version}.docx"
        logger.info(
            "Uploading BRD to Confluence: page_id=%s file=%s as %s (v%d)",
            cfg.page_id,
            path,
            remote_name,
            next_version,
        )

        url = f"{cfg.base_url}/rest/api/content/{cfg.page_id}/child/attachment"

        with path.open("rb") as f:
            file_content = f.read()
        
        files = {
            "file": (
                remote_name,
                file_content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        resp = await _request_with_retry_async(client, "POST", url, files=files, timeout=60.0)

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to upload attachment to Confluence (status {resp.status_code}): {resp.text}"
        )

    data = resp.json()
    if not data.get("results"):
        raise RuntimeError("Confluence response missing 'results' after upload")

    attachment = data["results"][0]
    download_rel = attachment.get("_links", {}).get("download")
    download_url = cfg.base_url.rstrip("/") + download_rel if download_rel else None

    return {
        "filename": remote_name,
        "version": next_version,
        "url": download_url,
    }


async def publish_brd_docx_as_page(
    file_path: str | os.PathLike[str],
    project_name: str | None,
) -> dict:
    """Create a Confluence page from the BRD .docx contents.

    Behaviour:
    - Uses ``CONFLUENCE_PAGE_ID`` as the *parent* page (e.g. "Wega BRD")
    - Resolves the target space key from that parent
    - Converts the .docx into simple storage-format HTML
    - Creates a new child page titled ``"BRD - {project_name}"``

    Returns a dict with ``page_id`` and ``page_url``.
    """

    cfg = _load_config()
    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"BRD file not found: {path}")

    body_html = _docx_to_storage_html(path)
    # Page title should be exactly the project name (no versioning/timestamps).
    page_title = (project_name or "Project").strip() or "Project"

    async with httpx.AsyncClient(auth=_build_auth(cfg), headers=_build_headers()) as client:
        space_key = await _get_space_key_for_parent_async(client, cfg)

        logger.info(
            "Creating Confluence page from BRD: parent_page_id=%s space=%s title=%s file=%s",
            cfg.page_id,
            space_key,
            page_title,
            path,
        )

        create_url = f"{cfg.base_url}/rest/api/content"
        payload = {
            "type": "page",
            "title": page_title,
            "ancestors": [{"id": cfg.page_id}],
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                }
            },
        }

        resp = await _request_with_retry_async(client, "POST", create_url, json=payload, timeout=60.0)

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to create Confluence page (status {resp.status_code}): {resp.text}"
        )

    page_data = resp.json()
    page_id = (page_data.get("id") or "").strip()
    if not page_id:
        raise RuntimeError("Confluence did not return a page id after creation.")

    page_links = page_data.get("_links", {})
    webui_rel = page_links.get("webui") or page_links.get("self")
    page_url = cfg.base_url.rstrip("/") + webui_rel if webui_rel else None

    return {
        "page_id": page_id,
        "page_url": page_url,
    }


# ── Direct REST helpers (no LLM, no MCP) ─────────────────────────────────────
# These power the brownfield validate / update flow. Going direct removes the
# fragile LLM->MCP->stdio->subprocess chain and lets real HTTP errors surface.

_PAGE_ID_FROM_URL_RE = re.compile(r"/pages/(\d+)", re.IGNORECASE)
_PAGE_ID_FROM_LEGACY_RE = re.compile(r"[?&]pageId=(\d+)", re.IGNORECASE)
_BARE_PAGE_ID_RE = re.compile(r"^\d+$")


def extract_page_id(link: str) -> str | None:
    """Extract a numeric page id from a Confluence URL or bare id string."""
    s = (link or "").strip()
    if not s:
        return None
    if _BARE_PAGE_ID_RE.match(s):
        return s
    m = _PAGE_ID_FROM_URL_RE.search(s)
    if m:
        return m.group(1)
    m = _PAGE_ID_FROM_LEGACY_RE.search(s)
    if m:
        return m.group(1)
    return None


def _storage_html_to_text(html: str) -> str:
    """Convert Confluence storage-format HTML into plain text (best-effort)."""
    if not html:
        return ""
    text = html
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(td|th)\s*>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def fetch_confluence_page(page_id: str) -> dict:
    """Fetch a Confluence page directly via REST.

    Raises ``RuntimeError`` with the HTTP status embedded in the message so
    upstream classifiers (auth/not_found/etc.) can match correctly.
    """
    cfg = _load_config()
    url = (
        f"{cfg.base_url}/rest/api/content/{page_id}"
        f"?expand=body.storage,version,space"
    )
    async with httpx.AsyncClient(auth=_build_auth(cfg), headers=_build_headers()) as client:
        resp = await _request_with_retry_async(client, "GET", url, timeout=30.0)

    if resp.status_code == 404:
        raise RuntimeError(f"Confluence page not found (404) for page_id={page_id}")
    if resp.status_code in (401, 403):
        raise RuntimeError(
            f"Confluence rejected credentials ({resp.status_code}): {resp.text[:200]}"
        )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Confluence get_page failed (status {resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    body_html = (data.get("body", {}).get("storage", {}) or {}).get("value", "") or ""
    content_text = _storage_html_to_text(body_html)
    version_raw = ((data.get("version") or {}).get("number")) or 1
    try:
        version_int = int(version_raw)
    except (TypeError, ValueError):
        version_int = 1

    links = data.get("_links", {}) or {}
    webui_rel = links.get("webui") or links.get("tinyui") or ""
    page_url = (cfg.base_url.rstrip("/") + webui_rel) if webui_rel else None

    return {
        "page_id": str(data.get("id") or page_id),
        "title": data.get("title", "") or "",
        "version": version_int,
        "content": content_text,
        "body_html": body_html,
        "space_key": ((data.get("space") or {}).get("key") or "").strip(),
        "page_url": page_url,
    }


async def update_confluence_page(
    page_id: str,
    *,
    title: str,
    body_html: str,
    current_version: int,
) -> dict:
    """Update an existing Confluence page via REST.

    Raises ``RuntimeError`` (with status) on conflict / auth / other failures.
    """
    cfg = _load_config()
    url = f"{cfg.base_url}/rest/api/content/{page_id}"
    payload = {
        "id": str(page_id),
        "type": "page",
        "title": title,
        "version": {"number": int(current_version) + 1},
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }

    async with httpx.AsyncClient(auth=_build_auth(cfg), headers=_build_headers()) as client:
        resp = await _request_with_retry_async(client, "PUT", url, json=payload, timeout=60.0)

    if resp.status_code == 409:
        raise RuntimeError(f"Confluence version conflict (409): {resp.text[:300]}")
    if resp.status_code in (401, 403):
        raise RuntimeError(
            f"Confluence rejected credentials ({resp.status_code}): {resp.text[:200]}"
        )
    if resp.status_code == 404:
        raise RuntimeError(f"Confluence page not found (404) for page_id={page_id}")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Confluence update_page failed (status {resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    new_version_raw = ((data.get("version") or {}).get("number")) or (int(current_version) + 1)
    try:
        new_version = int(new_version_raw)
    except (TypeError, ValueError):
        new_version = int(current_version) + 1
    links = data.get("_links", {}) or {}
    webui_rel = links.get("webui") or links.get("tinyui") or ""
    page_url = (cfg.base_url.rstrip("/") + webui_rel) if webui_rel else None

    return {
        "page_id": str(data.get("id") or page_id),
        "new_version": new_version,
        "page_url": page_url,
    }
