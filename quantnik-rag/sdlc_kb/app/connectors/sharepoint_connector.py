import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.exceptions import ParsingError
from app.core.logging import logger
from app.ingestion.doc_ingestion import SUPPORTED_EXTENSIONS, ingest as ingest_document


_REQUEST_TIMEOUT = 30.0
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def is_sharepoint_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "sharepoint" in host


class SharePointConnector:
    """
    Fetches supported document files from a SharePoint link.

    When ``tenant_id``, ``client_id``, and ``client_secret`` are provided (or
    set via SHAREPOINT_TENANT_ID / SHAREPOINT_CLIENT_ID /
    SHAREPOINT_CLIENT_SECRET), the connector uses the **Microsoft Graph API**
    to recursively enumerate and download every supported file inside the
    given SharePoint folder URL.

    Without Graph API credentials it falls back to HTML-scraping the page for
    direct document links (legacy behaviour, useful for single-file URLs).
    """

    def __init__(
        self,
        token: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._token = token
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret

    # ── Public entry point ────────────────────────────────────────────────────

    async def fetch_documents(self, url: str) -> list[dict]:
        if not is_sharepoint_url(url):
            raise ParsingError(url, "URL is not a SharePoint link")

        if self._tenant_id and self._client_id and self._client_secret:
            return await self._fetch_via_graph_api(url)

        return await self._fetch_via_html_scraping(url)

    # ══════════════════════════════════════════════════════════════════════════
    #  Microsoft Graph API path
    # ══════════════════════════════════════════════════════════════════════════

    async def _get_access_token(self) -> str:
        token_url = _TOKEN_URL.format(tenant_id=self._tenant_id)
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                resp = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                resp.raise_for_status()
                return resp.json()["access_token"]
            except httpx.HTTPStatusError as exc:
                raise ParsingError(
                    token_url,
                    f"Failed to obtain Graph API token (HTTP {exc.response.status_code}): "
                    f"{exc.response.text[:300]}",
                )

    async def _fetch_via_graph_api(self, url: str) -> list[dict]:
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        site_host, site_path, library_name, folder_path = self._parse_sharepoint_url(url)
        logger.info(
            "sharepoint_graph_resolve",
            site_host=site_host,
            site_path=site_path,
            library=library_name,
            folder=folder_path,
        )

        # Resolve site
        site = await self._graph_get(
            f"{_GRAPH_BASE}/sites/{site_host}:{site_path}", headers
        )
        site_id = site["id"]

        # Resolve drive (document library)
        drive_id = await self._resolve_drive(site_id, library_name, headers)

        # Recursively collect all supported files
        documents: list[dict] = []
        await self._collect_files(drive_id, folder_path, headers, documents, parent_url=url)

        if not documents:
            raise ParsingError(
                url,
                "No supported document files found in the SharePoint folder "
                f"(looking for: {', '.join(sorted(SUPPORTED_EXTENSIONS))})",
            )

        logger.info("sharepoint_graph_fetched", url=url, documents=len(documents))
        return documents

    def _parse_sharepoint_url(self, url: str) -> tuple[str, str, str, str]:
        """
        Parse a SharePoint URL into (hostname, site_path, library_name, folder_path).

        Handles the two common formats:
          1. AllItems.aspx with ``?id=...`` query param
             e.g. https://tenant.sharepoint.com/sites/Site/Shared%20Documents/Forms/AllItems.aspx
                      ?id=%2Fsites%2FSite%2FShared%20Documents%2FGeneral&...
          2. Direct folder URL
             e.g. https://tenant.sharepoint.com/sites/Site/Shared%20Documents/General
        """
        parsed = urlparse(url)
        hostname = parsed.netloc

        # Prefer the `id` query param – it carries the server-relative folder path
        qs = parse_qs(parsed.query)
        if "id" in qs:
            full_path = unquote(qs["id"][0])
        else:
            full_path = unquote(parsed.path)

        full_path = full_path.rstrip("/")
        parts = [p for p in full_path.split("/") if p]

        # Pattern: /sites/{name}/... or /teams/{name}/...
        if len(parts) >= 2 and parts[0].lower() in ("sites", "teams"):
            site_path = f"/{parts[0]}/{parts[1]}"
            if len(parts) >= 3:
                library_name = parts[2]
                # Skip "Forms" segment that appears in AllItems.aspx URLs
                remaining = [p for p in parts[3:] if p.lower() != "forms"]
                folder_path = "/".join(remaining)
            else:
                library_name = "Shared Documents"
                folder_path = ""
        else:
            site_path = "/"
            library_name = parts[0] if parts else "Shared Documents"
            folder_path = "/".join(parts[1:]) if len(parts) > 1 else ""

        return hostname, site_path, library_name, folder_path

    async def _resolve_drive(
        self, site_id: str, library_name: str, headers: dict
    ) -> str:
        """Return the Graph API drive-id for the given document library name."""
        resp = await self._graph_get(f"{_GRAPH_BASE}/sites/{site_id}/drives", headers)
        drives: list[dict] = resp.get("value", [])

        # Exact match (case-insensitive)
        for drive in drives:
            if drive.get("name", "").lower() == library_name.lower():
                return drive["id"]

        # Common aliases ("Shared Documents" ↔ "Documents")
        aliases: dict[str, str] = {
            "shared documents": "documents",
            "documents": "shared documents",
        }
        alias = aliases.get(library_name.lower())
        if alias:
            for drive in drives:
                if drive.get("name", "").lower() == alias:
                    return drive["id"]

        if drives:
            logger.warning(
                "sharepoint_drive_fallback",
                requested=library_name,
                using=drives[0].get("name"),
            )
            return drives[0]["id"]

        raise ParsingError("", f"No drives found in the SharePoint site for library '{library_name}'")

    async def _collect_files(
        self,
        drive_id: str,
        folder_path: str,
        headers: dict,
        results: list[dict],
        parent_url: str,
    ) -> None:
        """Recursively walk folder_path and append downloaded-file dicts to results."""
        if folder_path:
            list_url: str | None = (
                f"{_GRAPH_BASE}/drives/{drive_id}/root:/{folder_path}:/children"
            )
        else:
            list_url = f"{_GRAPH_BASE}/drives/{drive_id}/root/children"

        while list_url:
            data = await self._graph_get(list_url, headers)
            for item in data.get("value", []):
                if "folder" in item:
                    sub = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                    await self._collect_files(drive_id, sub, headers, results, parent_url)
                elif "file" in item:
                    ext = Path(item["name"]).suffix.lower()
                    if ext not in SUPPORTED_EXTENSIONS:
                        logger.info(
                            "sharepoint_skip_unsupported_ext",
                            name=item["name"],
                            ext=ext,
                        )
                        continue
                    doc = await self._download_graph_item(drive_id, item, headers, parent_url)
                    if doc is not None:
                        results.append(doc)

            list_url = data.get("@odata.nextLink")

    async def _download_graph_item(
        self,
        drive_id: str,
        item: dict,
        headers: dict,
        parent_url: str,
    ) -> dict | None:
        """Download a Graph drive item and return a normalised document dict."""
        file_id: str = item["id"]
        name: str = item["name"]
        size: int = item.get("size", 0)

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if size > max_bytes:
            logger.warning(
                "sharepoint_skip_too_large",
                name=name,
                size_mb=round(size / 1024 / 1024, 1),
            )
            return None

        # Graph items expose a pre-authenticated download URL
        download_url: str | None = item.get("@microsoft.graph.downloadUrl")
        if not download_url:
            meta = await self._graph_get(
                f"{_GRAPH_BASE}/drives/{drive_id}/items/{file_id}", headers
            )
            download_url = meta.get("@microsoft.graph.downloadUrl")

        if not download_url:
            logger.warning("sharepoint_no_download_url", name=name)
            return None

        try:
            async with httpx.AsyncClient(
                timeout=_REQUEST_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(download_url)
                resp.raise_for_status()
                content = resp.content
        except Exception as exc:
            logger.warning("sharepoint_download_failed", name=name, error=str(exc))
            return None

        suffix = Path(name).suffix.lower()
        temp_fd, temp_name = tempfile.mkstemp(suffix=suffix)
        os.close(temp_fd)
        temp_path = Path(temp_name)

        try:
            temp_path.write_bytes(content)
            normalized = ingest_document(temp_path)
        except Exception as exc:
            logger.warning("sharepoint_parse_failed", name=name, error=str(exc))
            return None
        finally:
            temp_path.unlink(missing_ok=True)

        web_url: str = item.get("webUrl", parent_url)
        parent_ref_path: str = item.get("parentReference", {}).get("path", "")

        return {
            "original_name": name,
            "file_type": suffix.lstrip("."),
            "file_size_bytes": len(content),
            "source_url": web_url,
            "normalized": normalized,
            "metadata": {
                "parent_url": parent_url,
                "file_url": web_url,
                "path": parent_ref_path,
                "host": urlparse(parent_url).netloc,
                "graph_item_id": file_id,
                "drive_id": drive_id,
            },
        }

    async def _graph_get(self, url: str, headers: dict) -> dict:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                raise ParsingError(
                    url,
                    f"Graph API error HTTP {exc.response.status_code}: "
                    f"{exc.response.text[:300]}",
                )
            except httpx.RequestError as exc:
                raise ParsingError(url, str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    #  HTML-scraping fallback (legacy / single-file bearer-token flows)
    # ══════════════════════════════════════════════════════════════════════════

    async def _fetch_via_html_scraping(self, url: str) -> list[dict]:
        headers = {
            "User-Agent": "SDLC-KB-Bot/1.0 (knowledge-base indexing)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await self._get(client, url)
            if self._is_supported_file_response(response):
                return [await self._download_document(response, parent_url=url)]

            links = self._extract_document_links(response.text, str(response.url))
            if not links:
                raise ParsingError(url, "No supported document links were found in the SharePoint page")

            documents: list[dict] = []
            for link in links:
                doc_response = await self._get(client, link)
                if not self._is_supported_file_response(doc_response):
                    logger.warning("sharepoint_skip_non_document", url=link)
                    continue
                documents.append(
                    await self._download_document(doc_response, parent_url=url)
                )

        if not documents:
            raise ParsingError(url, "Supported document links were found, but none could be downloaded")

        logger.info("sharepoint_fetched", url=url, documents=len(documents))
        return documents

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise ParsingError(url, f"HTTP {exc.response.status_code}")
        except httpx.RequestError as exc:
            raise ParsingError(url, str(exc))

    def _extract_document_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links: set[str] = set()

        for tag in soup.find_all(True):
            for value in tag.attrs.values():
                candidates = value if isinstance(value, list) else [value]
                for candidate in candidates:
                    if not isinstance(candidate, str):
                        continue
                    absolute = urljoin(base_url, candidate)
                    if self._looks_like_document_url(absolute):
                        links.add(absolute)

        for match in re.findall(r'https?://[^"\'\s>]+', html, flags=re.IGNORECASE):
            if self._looks_like_document_url(match):
                links.add(match)

        return sorted(links)

    def _looks_like_document_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not is_sharepoint_url(url):
            return False
        lower_url = url.lower()
        return any(ext in lower_url for ext in SUPPORTED_EXTENSIONS)

    def _is_supported_file_response(self, response: httpx.Response) -> bool:
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" in content_type or content_type.startswith("application/xml") or content_type.startswith("text/xml"):
            return False
        filename = self._infer_filename(response, str(response.url))
        return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS

    async def _download_document(
        self,
        response: httpx.Response,
        *,
        parent_url: str,
    ) -> dict:
        file_url = response.url
        content = response.content

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ParsingError(str(file_url), f"File too large ({len(content) / 1024 / 1024:.1f}MB)")

        filename = self._infer_filename(response, str(file_url))
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ParsingError(str(file_url), f"Unsupported SharePoint document type '{suffix}'")

        temp_fd, temp_name = tempfile.mkstemp(suffix=suffix)
        os.close(temp_fd)
        temp_path = Path(temp_name)

        try:
            temp_path.write_bytes(content)
            normalized = ingest_document(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

        path = unquote(urlparse(str(file_url)).path)
        original_name = path or filename

        return {
            "original_name": original_name,
            "file_type": suffix.lstrip("."),
            "file_size_bytes": len(content),
            "source_url": str(file_url),
            "normalized": normalized,
            "metadata": {
                "parent_url": parent_url,
                "file_url": str(file_url),
                "path": path,
                "host": urlparse(str(file_url)).netloc,
            },
        }

    def _infer_filename(self, response: httpx.Response | None, url: str) -> str:
        if response is not None:
            disposition = response.headers.get("content-disposition", "")
            match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, re.IGNORECASE)
            if match:
                return unquote(match.group(1)).strip()

        path_name = Path(unquote(urlparse(url).path)).name
        if path_name:
            return path_name
        return "sharepoint_document"