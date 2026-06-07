import re
from base64 import b64encode
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.logging import logger
from app.core.exceptions import ParsingError

_REQUEST_TIMEOUT = 30.0

# Matches:  /wiki/spaces/<KEY>/pages/<ID>/...
#           /wiki/pages/<ID>
_PAGE_ID_RE = re.compile(r"/wiki/(?:spaces/[^/]+/)?pages/(\d+)")


def is_confluence_url(url: str) -> bool:
    """Return True if the URL points to an Atlassian Confluence Cloud instance."""
    host = urlparse(url).netloc.lower()
    return "atlassian.net" in host and "/wiki/" in url


def _extract_page_id(url: str) -> str:
    m = _PAGE_ID_RE.search(url)
    if not m:
        raise ParsingError(url, "Could not extract Confluence page ID from URL")
    return m.group(1)


def _base_url(url: str) -> str:
    """Return https://<domain> from any Confluence URL."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


class ConfluenceConnector:
    """
    Fetches a Confluence Cloud page via the REST API using Basic Auth
    (user email + API token).

    Returns the same normalised dict shape as WebsiteConnector.fetch().
    """

    def __init__(self, email: str, token: str) -> None:
        if not email or not token:
            raise ValueError("CONFLUENCE_EMAIL and CONFLUENCE_TOKEN must be set to fetch Confluence pages")
        creds = b64encode(f"{email}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
        }

    async def fetch(self, url: str) -> dict:
        page_id  = _extract_page_id(url)
        base     = _base_url(url)
        api_url  = f"{base}/wiki/rest/api/content/{page_id}?expand=body.storage,title"

        try:
            async with httpx.AsyncClient(
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=True,
                headers=self._headers,
            ) as client:
                resp = await client.get(api_url)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ParsingError(url, f"Confluence API returned HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except httpx.RequestError as exc:
            raise ParsingError(url, str(exc))

        data  = resp.json()
        title = data.get("title", "")
        html  = data.get("body", {}).get("storage", {}).get("value", "")

        if not html:
            raise ParsingError(url, "Confluence page returned empty body")

        text, sections, tables = _parse_storage_html(html)

        logger.info(
            "confluence_fetched",
            url=url,
            page_id=page_id,
            title=title,
            word_count=len(text.split()),
        )

        return {
            "text":       text,
            "sections":   sections,
            "tables":     tables,
            "page_count": 1,
            "word_count": len(text.split()),
            "metadata": {
                "title":   title,
                "page_id": page_id,
                "url":     url,
            },
        }


# ── HTML parser for Confluence storage format ─────────────────────────────────

_STRIP_TAGS = {"script", "style", "noscript", "iframe"}


def _parse_storage_html(html: str) -> tuple[str, list[dict], list[list]]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # Sections from headings
    sections = []
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        text = heading.get_text(strip=True)
        if text:
            sections.append({"title": text, "level": int(heading.name[1])})

    # Tables
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    # Plain text — preserve line breaks around block elements
    for tag in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr"]):
        tag.insert_before("\n")

    text = re.sub(r"\n{3,}", "\n\n", soup.get_text()).strip()

    return text, sections, tables
