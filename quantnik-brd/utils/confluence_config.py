"""utils/confluence_config.py

Centralised Confluence configuration derived from a single page URL.

The user provides ONE URL in .env:

    CONFLUENCE_PARENT_PAGE_URL=https://domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456/Page+Title

From this we extract:
    - base_url   → https://domain.atlassian.net/wiki
    - space_key  → SPACEKEY
    - page_id    → 123456
    - page_title → Page Title

Other required env vars:
    CONFLUENCE_EMAIL     – Atlassian account email
    CONFLUENCE_API_TOKEN – API token
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import unquote_plus


@dataclass
class ConfluenceSettings:
    base_url: str
    space_key: str
    page_id: str
    page_title: str
    email: str
    api_token: str


# Matches:  .../wiki/spaces/<space_key>/pages/<page_id>/<optional_title>
_PAGE_URL_RE = re.compile(
    r"^(?P<base>https?://.+?/wiki)"
    r"/spaces/(?P<space>[^/]+)"
    r"/pages/(?P<page_id>\d+)"
    r"(?:/(?P<title>[^?#]*))?",
    re.IGNORECASE,
)


def parse_confluence_page_url(url: str) -> dict:
    """Parse a Confluence page URL into its components.

    Returns a dict with keys: base_url, space_key, page_id, page_title.
    Raises ``ValueError`` if the URL doesn't match the expected pattern.
    """
    m = _PAGE_URL_RE.match(url.strip())
    if not m:
        raise ValueError(
            f"Invalid Confluence page URL: {url!r}\n"
            "Expected format: https://<domain>/wiki/spaces/<SPACE>/pages/<PAGE_ID>/<Title>"
        )
    return {
        "base_url": m.group("base").rstrip("/"),
        "space_key": m.group("space"),
        "page_id": m.group("page_id"),
        "page_title": unquote_plus(m.group("title") or ""),
    }


def load_confluence_settings() -> ConfluenceSettings:
    """Load Confluence settings from environment variables.

    Reads ``CONFLUENCE_PARENT_PAGE_URL``, ``CONFLUENCE_EMAIL``, and
    ``CONFLUENCE_API_TOKEN`` from the environment.

    Falls back to legacy env vars (``CONFLUENCE_BASE_URL``, ``CONFLUENCE_URL``,
    ``CONFLUENCE_PAGE_ID``, etc.) if the new URL var is not set, so existing
    deployments continue to work.

    Raises ``ValueError`` if required values are missing.
    """
    page_url = os.environ.get("CONFLUENCE_PARENT_PAGE_URL", "").strip()

    if page_url:
        parsed = parse_confluence_page_url(page_url)
        base_url = parsed["base_url"]
        space_key = parsed["space_key"]
        page_id = parsed["page_id"]
        page_title = parsed["page_title"]
    else:
        # Legacy fallback
        base_url = (
            os.environ.get("CONFLUENCE_BASE_URL")
            or os.environ.get("CONFLUENCE_URL")
            or ""
        ).strip().rstrip("/")
        space_key = ""
        page_id = os.environ.get("CONFLUENCE_PAGE_ID", "").strip()
        page_title = ""

    email = (
        os.environ.get("CONFLUENCE_EMAIL")
        or os.environ.get("CONFLUENCE_USERNAME")
        or ""
    ).strip()
    api_token = os.environ.get("CONFLUENCE_API_TOKEN", "").strip()

    missing = []
    if not base_url:
        missing.append("CONFLUENCE_PARENT_PAGE_URL (or CONFLUENCE_BASE_URL)")
    if not email:
        missing.append("CONFLUENCE_EMAIL")
    if not api_token:
        missing.append("CONFLUENCE_API_TOKEN")
    if missing:
        raise ValueError("Missing Confluence configuration: " + ", ".join(missing))

    return ConfluenceSettings(
        base_url=base_url,
        space_key=space_key,
        page_id=page_id,
        page_title=page_title,
        email=email,
        api_token=api_token,
    )
