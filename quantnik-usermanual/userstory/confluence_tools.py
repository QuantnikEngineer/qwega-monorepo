"""Confluence read/publish helpers for the User Manual Writer pipeline.

Public API:
    - publish_manual_to_confluence(markdown_text, project_name, ...)
    - confluence_page_exists(project_name)
    - upload_manual_pdf_to_confluence_attachment(local_pdf_path, project_name)
    - read_confluence_page_content(url)
    - markdown_to_confluence_storage_html(markdown_text)
    - derive_project_name(source_url)
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, unquote_plus, urlparse

import markdown
import requests

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceConfig:
    base_url: str
    email: str
    api_token: str
    parent_page_id: str
    space_key: Optional[str] = None


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return u
    if u.endswith("/wiki"):
        return u
    return f"{u}/wiki"


def _get_config() -> ConfluenceConfig:
    parent_page_id = (
        os.getenv("CONFLUENCE_PARENT_PAGE_ID", "").strip()
        or os.getenv("CONFLUENCE_PAGE_ID", "").strip()
    )
    cfg = ConfluenceConfig(
        base_url=_normalize_base_url(os.getenv("CONFLUENCE_BASE_URL", "")),
        email=os.getenv("CONFLUENCE_EMAIL", "").strip(),
        api_token=os.getenv("CONFLUENCE_API_TOKEN", "").strip(),
        parent_page_id=parent_page_id,
        space_key=os.getenv("CONFLUENCE_SPACE_KEY", "").strip() or None,
    )
    missing = [
        key for key, value in {
            "CONFLUENCE_BASE_URL": cfg.base_url,
            "CONFLUENCE_EMAIL": cfg.email,
            "CONFLUENCE_API_TOKEN": cfg.api_token,
            "CONFLUENCE_PARENT_PAGE_ID or CONFLUENCE_PAGE_ID": cfg.parent_page_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Confluence is not configured. Missing env vars: " + ", ".join(missing)
        )
    return cfg


def _auth_header(email: str, token: str) -> Dict[str, str]:
    raw = f"{email}:{token}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def _get_space_key_for_parent(cfg: ConfluenceConfig) -> str:
    if cfg.space_key:
        return cfg.space_key

    endpoint = f"{cfg.base_url}/rest/api/content/{cfg.parent_page_id}?expand=space"
    headers = {**_auth_header(cfg.email, cfg.api_token), "Accept": "application/json"}
    resp = requests.get(endpoint, headers=headers, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to resolve Confluence space for parent page {cfg.parent_page_id} "
            f"({resp.status_code}): {resp.text}"
        )
    data = resp.json()
    space_key = ((data.get("space") or {}).get("key") or "").strip()
    if not space_key:
        raise RuntimeError(
            f"Confluence parent page {cfg.parent_page_id} did not return a space key."
        )
    return space_key


def _sanitize_title(title: str) -> str:
    """Tidy a title for use as the Confluence page title.

    Replaces underscores with spaces (so ``My_Page_Manual`` becomes
    ``My Page Manual``), collapses runs of whitespace, and caps length
    at the Confluence limit.
    """
    raw = (title or "").strip().replace("_", " ")
    cleaned = re.sub(r"\s+", " ", raw)
    return cleaned[:240] if cleaned else "Project"


# ---------------------------------------------------------------------------
# Markdown -> Confluence storage HTML
# ---------------------------------------------------------------------------

LOCAL_IMG_PATH_PATTERN = re.compile(
    r'<img[^>]+src=["\'](?P<src>(?:file://)?(?:/|[A-Za-z]:[/\\]|\.{1,2}/|data/)[^"\']+)["\'][^>]*>',
    flags=re.IGNORECASE,
)


def _is_local_path(src: str) -> bool:
    if not src:
        return False
    s = src.strip()
    if s.startswith(("http://", "https://", "data:")):
        return False
    return True


def _collect_local_image_refs(html: str) -> List[Tuple[str, str]]:
    """Return list of (full_img_tag, src) for every <img> with a local-path src."""
    refs: List[Tuple[str, str]] = []
    for match in re.finditer(r'<img[^>]+src=["\'](?P<src>[^"\']+)["\'][^>]*>', html, flags=re.IGNORECASE):
        src = match.group("src")
        if _is_local_path(src):
            refs.append((match.group(0), src))
    return refs


_TOC_MACRO = (
    '<ac:structured-macro ac:name="toc" ac:schema-version="1">'
    '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
    '<ac:parameter ac:name="minLevel">2</ac:parameter>'
    '<ac:parameter ac:name="outline">true</ac:parameter>'
    '<ac:parameter ac:name="style">disc</ac:parameter>'
    '</ac:structured-macro>'
)


def _inject_toc_after_h1(html: str) -> str:
    """Insert a Confluence TOC macro right after the first <h1>...</h1>."""
    match = re.search(r"</h1>", html, flags=re.IGNORECASE)
    if not match:
        return _TOC_MACRO + html
    insert_at = match.end()
    return html[:insert_at] + _TOC_MACRO + html[insert_at:]


def markdown_to_confluence_storage_html(markdown_text: str) -> str:
    """Convert rendered user manual markdown into Confluence storage HTML.

    Adds:
      * Confluence TOC macro right after the H1.
      * Light styling on tables (header background, cell borders).
      * Slightly tighter spacing on definition-style tables (Glossary).

    Local image rewriting / attachment upload is a separate step performed
    by ``publish_manual_to_confluence``.
    """
    html = markdown.markdown(
        markdown_text or "",
        extensions=["tables", "sane_lists", "fenced_code"],
        output_format="xhtml",
    )

    # Promote tables: full-width, bordered, header tinted.
    html = re.sub(
        r"<table>",
        '<table style="border-collapse:collapse;width:100%;margin:12px 0;">',
        html, flags=re.IGNORECASE,
    )
    # Inject a colgroup after every <table ...> tag so Confluence honours
    # the 28/72 column-width split (Term vs Definition).
    html = re.sub(
        r"(<table[^>]*>)",
        r'\1<colgroup><col style="width:28%" /><col style="width:72%" /></colgroup>',
        html, flags=re.IGNORECASE,
    )
    # Header cells: explicit color so Confluence theme cannot override with
    # its link-blue; vertical-align:middle centres the label in the cell.
    html = re.sub(
        r"<th>",
        '<th style="background-color:#deebff;padding:8px 10px;border:1px solid #b3c7f7;'
        'text-align:left;font-weight:600;color:#172b4d;vertical-align:middle;">',
        html, flags=re.IGNORECASE,
    )
    # Body cells: all cells get base style.
    html = re.sub(
        r"<td>",
        '<td style="padding:8px 10px;border:1px solid #d0d7de;vertical-align:top;">',
        html, flags=re.IGNORECASE,
    )
    # First <td> per row (Term column) gets bold so it stands out from the
    # definition text.  Pattern matches <tr> + optional whitespace + <td style=
    # which is always the first cell after python-markdown's table conversion.
    html = re.sub(
        r'(<tr>\s*)(<td style=")',
        r'\1<td style="font-weight:600;',
        html,
    )

    # Inject the TOC for navigation.
    html = _inject_toc_after_h1(html)

    section_pattern = re.compile(
        r"(<h([1-3])[^>]*>[^<]*(?:\[AI\]|\(AI\)|AI[- ]generated)[^<]*</h\2>)(.*?)(?=<h[1-3]\b|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def _wrap_ai(match: re.Match[str]) -> str:
        section = match.group(1) + (match.group(3) or "")
        return (
            '<div style="border:1px solid #f5b971;background:#fff7e6;padding:10px 12px;'
            'margin:10px 0;border-radius:4px;">'
            f"{section}"
            "</div>"
        )

    return section_pattern.sub(_wrap_ai, html)


# ---------------------------------------------------------------------------
# Confluence page create + image attachments
# ---------------------------------------------------------------------------

def _create_confluence_page(
    cfg: ConfluenceConfig, title: str, storage_html: str,
) -> Dict[str, str]:
    endpoint = f"{cfg.base_url}/rest/api/content"
    headers = {
        **_auth_header(cfg.email, cfg.api_token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "type": "page",
        "title": _sanitize_title(title),
        "space": {"key": _get_space_key_for_parent(cfg)},
        "ancestors": [{"id": str(cfg.parent_page_id)}],
        "body": {"storage": {"value": storage_html, "representation": "storage"}},
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"Confluence page create failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    page_id = str(data.get("id") or "")
    page_title = data.get("title") or payload["title"]
    webui = data.get("_links", {}).get("webui", "")
    page_url = f"{cfg.base_url}{webui}" if webui else ""
    return {"page_id": page_id, "title": page_title, "url": page_url}


def _update_page_storage(cfg: ConfluenceConfig, page_id: str, title: str, storage_html: str) -> None:
    endpoint = f"{cfg.base_url}/rest/api/content/{page_id}"
    headers = {
        **_auth_header(cfg.email, cfg.api_token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    get_resp = requests.get(f"{endpoint}?expand=version", headers=headers, timeout=30)
    get_resp.raise_for_status()
    current_version = ((get_resp.json().get("version") or {}).get("number") or 1)
    payload = {
        "id": page_id,
        "type": "page",
        "title": _sanitize_title(title),
        "version": {"number": int(current_version) + 1},
        "body": {"storage": {"value": storage_html, "representation": "storage"}},
    }
    upd = requests.put(endpoint, headers=headers, json=payload, timeout=60)
    if upd.status_code >= 400:
        raise RuntimeError(f"Confluence page update failed ({upd.status_code}): {upd.text}")


def _upload_image_attachment(
    cfg: ConfluenceConfig, page_id: str, local_path: Path,
) -> Optional[str]:
    """Upload a single image as an attachment of the given page.

    Returns the attachment filename (as stored on Confluence) on success.
    """
    if not local_path.exists():
        logger.warning("Skipping missing image attachment: %s", local_path)
        return None
    headers = {
        **_auth_header(cfg.email, cfg.api_token),
        "Accept": "application/json",
        "X-Atlassian-Token": "no-check",
    }
    mime, _ = mimetypes.guess_type(local_path.name)
    if not mime:
        mime = "application/octet-stream"

    upload_url = f"{cfg.base_url}/rest/api/content/{page_id}/child/attachment"
    with local_path.open("rb") as fh:
        files = {"file": (local_path.name, fh, mime)}
        data = {"comment": "Auto-uploaded by User Manual Writer"}
        resp = requests.post(upload_url, headers=headers, files=files, data=data, timeout=120)
    if resp.status_code >= 400:
        logger.warning(
            "Confluence attachment upload failed for %s (%s): %s",
            local_path.name, resp.status_code, resp.text[:300],
        )
        return None
    payload = resp.json()
    item = (payload.get("results") or [payload])[0]
    return (item.get("title") or local_path.name)


def _ac_image_tag(filename: str) -> str:
    safe = filename.replace('"', "&quot;")
    return (
        '<ac:image ac:align="center" ac:layout="center">'
        f'<ri:attachment ri:filename="{safe}" />'
        '</ac:image>'
    )


def _rewrite_image_refs(storage_html: str, src_to_filename: Dict[str, str]) -> str:
    """Replace <img> tags whose src is in `src_to_filename` with <ac:image>."""
    def _repl(match: re.Match[str]) -> str:
        src = match.group("src")
        filename = src_to_filename.get(src)
        if not filename:
            return match.group(0)
        return _ac_image_tag(filename)

    return re.sub(
        r'<img[^>]+src=["\'](?P<src>[^"\']+)["\'][^>]*>',
        _repl, storage_html, flags=re.IGNORECASE,
    )


def _resolve_local_image(src: str) -> Optional[Path]:
    """Resolve an HTML img src to a local Path on disk, if possible."""
    s = src.strip()
    if s.startswith("file://"):
        s = s[len("file://"):]
    candidate = Path(s)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    # Try project root relative
    project_root = Path(__file__).resolve().parent.parent
    rel = (project_root / s).resolve()
    if rel.exists():
        return rel
    return None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def confluence_page_exists(project_name: str) -> bool:
    cfg = _get_config()
    title = _sanitize_title(project_name)
    space_key = _get_space_key_for_parent(cfg)
    endpoint = f"{cfg.base_url}/rest/api/content"
    headers = {**_auth_header(cfg.email, cfg.api_token), "Accept": "application/json"}
    params = {
        "title": title, "spaceKey": space_key, "type": "page",
        "ancestor": cfg.parent_page_id, "limit": 1,
    }
    resp = requests.get(endpoint, headers=headers, params=params, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to query Confluence for existing pages ({resp.status_code}): {resp.text}"
        )
    return resp.json().get("size", 0) > 0


def publish_manual_to_confluence(
    markdown_text: str,
    project_name: str,
) -> Dict[str, str]:
    """Publish the generated user manual as a native Confluence child page.

    Local image references (e.g. produced by the Role and Common-Sections
    agents) are uploaded as page attachments and rewritten to Confluence's
    ``<ac:image><ri:attachment .../></ac:image>`` storage form so they
    render correctly inside Confluence.
    """
    cfg = _get_config()

    # 1. Markdown -> HTML.
    storage_html = markdown_to_confluence_storage_html(markdown_text)

    # 2. Detect every local image reference.
    refs = _collect_local_image_refs(storage_html)
    unique_srcs: List[str] = []
    seen = set()
    for _, src in refs:
        if src not in seen:
            seen.add(src)
            unique_srcs.append(src)

    # 3. Create the Confluence page first (so we have a page_id for attachments).
    page = _create_confluence_page(
        cfg=cfg, title=_sanitize_title(project_name), storage_html=storage_html,
    )
    page_id = page["page_id"]

    # 4. Upload each unique local image as an attachment, build src->filename map.
    #    Uploads run concurrently — they are independent HTTP requests against
    #    the same Confluence page id. Bounded by CONFLUENCE_UPLOAD_CONCURRENCY.
    src_to_filename: Dict[str, str] = {}
    uploaded = 0
    upload_concurrency = int(os.getenv("CONFLUENCE_UPLOAD_CONCURRENCY", "4"))

    def _do_upload(src: str) -> Tuple[str, Optional[str]]:
        local = _resolve_local_image(src)
        if not local:
            logger.warning("Could not resolve local image src '%s'; leaving original tag.", src)
            return src, None
        return src, _upload_image_attachment(cfg, page_id, local)

    if unique_srcs:
        workers = max(1, min(upload_concurrency, len(unique_srcs)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_do_upload, src) for src in unique_srcs]
            for fut in as_completed(futures):
                try:
                    src, filename = fut.result()
                except Exception as exc:
                    logger.warning("Confluence attachment upload task failed: %s", exc)
                    continue
                if filename:
                    src_to_filename[src] = filename
                    uploaded += 1

    # 5. If we uploaded anything, rewrite the page body to use ac:image.
    if src_to_filename:
        rewritten = _rewrite_image_refs(storage_html, src_to_filename)
        _update_page_storage(cfg, page_id, project_name, rewritten)
        logger.info("Confluence: uploaded %d image attachment(s) for page %s", uploaded, page_id)

    return {
        "status": "success",
        "mode": "storage_html",
        "page_id": page_id,
        "title": page["title"],
        "confluence_url": page["url"],
        "images_uploaded": uploaded,
    }


def upload_manual_pdf_to_confluence_attachment(
    local_pdf_path: str, project_name: str,
) -> Dict[str, str]:
    cfg = _get_config()
    headers = {
        **_auth_header(cfg.email, cfg.api_token),
        "Accept": "application/json",
        "X-Atlassian-Token": "no-check",
    }
    list_url = (
        f"{cfg.base_url}/rest/api/content/{cfg.parent_page_id}"
        f"/child/attachment?limit=1000"
    )
    list_resp = requests.get(list_url, headers=headers, timeout=60)
    list_resp.raise_for_status()
    existing = [item.get("title", "") for item in list_resp.json().get("results", [])]

    base_name = f"UserManual_{_sanitize_title(project_name).replace(' ', '_')}"
    pattern = re.compile(rf"^{re.escape(base_name)}_v(\d+)\.pdf$", flags=re.IGNORECASE)
    max_v = 0
    for title in existing:
        m = pattern.match((title or "").strip())
        if m:
            max_v = max(max_v, int(m.group(1)))
    file_name = f"{base_name}_v{max_v + 1}.pdf"

    upload_url = f"{cfg.base_url}/rest/api/content/{cfg.parent_page_id}/child/attachment"
    pdf_path = Path(local_pdf_path)
    with pdf_path.open("rb") as fh:
        files = {"file": (file_name, fh, "application/pdf")}
        data = {"comment": f"Auto-uploaded user manual attachment {file_name}"}
        resp = requests.post(upload_url, headers=headers, files=files, data=data, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Confluence attachment upload failed ({resp.status_code}): {resp.text}")

    payload = resp.json()
    item = (payload.get("results") or [{}])[0]
    download_rel = item.get("_links", {}).get("download", "")
    download_url = f"{cfg.base_url}{download_rel}" if download_rel else ""
    return {
        "status": "success",
        "mode": "raw_attachment",
        "file_name": file_name,
        "download_url": download_url,
    }


def derive_project_name(source_url: Optional[str]) -> str:
    raw = (source_url or "").rstrip("/")
    if not raw:
        return "Project"
    leaf = raw.split("/")[-1].strip()
    leaf = unquote_plus(leaf)
    leaf = re.sub(r"[^A-Za-z0-9 _-]", " ", leaf)
    leaf = re.sub(r"\s+", " ", leaf).strip()
    return leaf or "Project"


# ---------------------------------------------------------------------------
# Confluence page reading (text only). Image attachments are now handled by
# file_reader_tools._read_from_confluence.
# ---------------------------------------------------------------------------

def _parse_confluence_page_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    match = re.search(r"/pages/(\d+)", parsed.path)
    return base_url, (match.group(1) if match else "")


def _html_to_text(html: str) -> str:
    class _TextExtractor(HTMLParser):
        BLOCK_TAGS = {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
                      "li", "tr", "div", "section", "article", "pre"}
        SKIP_TAGS = {"script", "style"}

        def __init__(self):
            super().__init__()
            self._parts: list[str] = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in self.SKIP_TAGS:
                self._skip = True
            elif tag in self.BLOCK_TAGS:
                self._parts.append("\n")

        def handle_endtag(self, tag):
            if tag in self.SKIP_TAGS:
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                self._parts.append(data)

        def get_text(self) -> str:
            return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()

    extractor = _TextExtractor()
    extractor.feed(html or "")
    return extractor.get_text()


def read_confluence_page_content(url: str) -> dict:
    """Backwards-compatible text-only Confluence reader.

    For new code, prefer ``file_reader_tools.read_all_files_from_data`` which
    also extracts image attachments.
    """
    base_url, page_id = _parse_confluence_page_url(url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from Confluence URL: {url}")

    email = os.getenv("CONFLUENCE_EMAIL", "").strip()
    api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
    if not email or not api_token:
        raise RuntimeError(
            "CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN must be set to read Confluence pages."
        )

    auth_headers = {
        **_auth_header(email, api_token),
        "Accept": "application/json",
    }

    def _fetch_page(pid: str) -> str:
        endpoint = (
            f"{base_url}/wiki/rest/api/content/{pid}?expand=body.export_view,title"
        )
        resp = requests.get(endpoint, headers=auth_headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Confluence API returned {resp.status_code} for page {pid}: {resp.text}"
            )
        data = resp.json()
        title = data.get("title", "")
        html_body = (data.get("body") or {}).get("export_view", {}).get("value", "")
        text = _html_to_text(html_body)
        return f"# {title}\n\n{text}" if title else text

    documents: list[str] = [_fetch_page(page_id)]
    children_url = (
        f"{base_url}/wiki/rest/api/content/{page_id}/child/page?limit=50&expand=title"
    )
    children_resp = requests.get(children_url, headers=auth_headers, timeout=30)
    if children_resp.ok:
        for child in children_resp.json().get("results", []):
            child_id = child.get("id")
            if child_id:
                try:
                    documents.append(_fetch_page(child_id))
                except Exception:
                    pass

    return {
        "status": "success",
        "documents": documents,
        "source": "confluence_input",
        "folder": url,
    }
