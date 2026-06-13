import re
from urllib.parse import urljoin, urlparse
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.logging import logger
from app.core.exceptions import ParsingError


# Tags that carry no useful content
_STRIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"}

# Max page size to protect against huge responses (10 MB)
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Request timeout in seconds
_REQUEST_TIMEOUT = 30.0


class WebsiteConnector:
    """Fetches a web page and extracts its textual content."""

    def __init__(self) -> None:
        self._client_kwargs: dict[str, Any] = {
            "timeout": _REQUEST_TIMEOUT,
            "follow_redirects": True,
            "headers": {
                "User-Agent": "SDLC-KB-Bot/1.0 (knowledge-base indexing)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        }

    async def fetch(self, url: str) -> dict:
        """
        Fetch a URL and return a normalised document dict compatible with
        the ingestion pipeline.

        Returns the same shape as ``doc_ingestion.ingest()``:
            text, sections, tables, page_count, word_count, metadata
        """
        self._validate_url(url)

        try:
            async with httpx.AsyncClient(**self._client_kwargs) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ParsingError(url, f"HTTP {exc.response.status_code}")
        except httpx.RequestError as exc:
            raise ParsingError(url, str(exc))

        content_length = len(resp.content)
        if content_length > _MAX_RESPONSE_BYTES:
            raise ParsingError(url, f"Response too large ({content_length / 1024 / 1024:.1f}MB)")

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type and "xml" not in content_type:
            raise ParsingError(url, f"Unsupported content-type: {content_type}")

        html = resp.text
        result = self._extract(html, url)

        logger.info(
            "website_fetched",
            url=url,
            word_count=result["word_count"],
            sections=len(result["sections"]),
        )
        return result

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ParsingError(url, f"Invalid scheme '{parsed.scheme}'. Only http/https allowed.")
        if not parsed.netloc:
            raise ParsingError(url, "Missing hostname")

    @staticmethod
    def _extract(html: str, source_url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")

        # Remove noisy tags
        for tag in soup.find_all(_STRIP_TAGS):
            tag.decompose()

        # Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Meta description
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].strip()

        # Sections from headings
        sections = []
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            heading_text = heading.get_text(strip=True)
            if heading_text:
                sections.append({"title": heading_text, "level": int(heading.name[1])})

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

        # Main body text
        # Prefer <main> or <article>; fall back to <body>
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main is None:
            main = soup

        text = main.get_text(separator="\n", strip=True)

        # Light cleanup
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = text.strip()

        word_count = len(text.split())

        return {
            "text": text,
            "sections": sections,
            "tables": tables,
            "page_count": 1,
            "word_count": word_count,
            "metadata": {
                "title": title,
                "description": meta_desc,
                "source_url": source_url,
                "domain": urlparse(source_url).netloc,
            },
        }
