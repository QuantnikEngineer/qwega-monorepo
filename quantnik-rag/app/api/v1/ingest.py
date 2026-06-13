"""
Unified ingestion endpoint for non-upload sources:
    POST /ingest   { "source": "website" | "sharepoint" | "repo" | "agent_output", ... }

File uploads remain on POST /upload (multipart form-data).
"""
import hashlib
import re
import uuid
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.connectors.confluence_connector import ConfluenceConnector, is_confluence_url
from app.connectors.repository_connector import RepositoryConnector, detect_platform
from app.connectors.sharepoint_connector import SharePointConnector
from app.connectors.website_connector import WebsiteConnector
from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal, AsyncSessionLocalNonCritical
from app.ingestion.deduplication import find_exact_duplicate
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document, DocumentStatus, SDLCPhase, SourceType
from app.schemas.ingest import (
    AGENT_PHASE_MAP,
    AgentOutputIngestBody,
    ConfluenceIngestBody,
    IngestDocumentItem,
    IngestRequest,
    IngestResponse,
    RepoIngestBody,
    SharePointIngestBody,
    WebsiteIngestBody,
)

router = APIRouter()


# ── Single unified endpoint ───────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(
    body:             IngestRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    """
    Unified ingestion for all non-file sources.

    Discriminated on ``source``:
      - **website**      – fetch & index one or more URLs
      - **sharepoint**   – fetch & index supported documents from a SharePoint link
      - **repo**         – fetch & index files from a GitHub / Harness repository
      - **agent_output** – index agent-generated content
    """
    if isinstance(body, WebsiteIngestBody):
        return await _ingest_website(body, background_tasks, db)
    if isinstance(body, ConfluenceIngestBody):
        return await _ingest_confluence(body, background_tasks, db)
    if isinstance(body, SharePointIngestBody):
        return await _ingest_sharepoint(body, background_tasks, db)
    if isinstance(body, RepoIngestBody):
        return await _ingest_repo(body, background_tasks, db)
    if isinstance(body, AgentOutputIngestBody):
        return await _ingest_agent_output(body, background_tasks, db)


# ═══════════════════════════════════════════════════════════════════════════════
#  Website
# ═══════════════════════════════════════════════════════════════════════════════

_website_connector = WebsiteConnector()


async def _ingest_website(
    body: WebsiteIngestBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> IngestResponse:
    if not body.urls:
        raise HTTPException(400, "At least one URL is required")

    created: list[tuple[Document, str, dict]] = []
    skipped_urls: list[str] = []

    async with AsyncSessionLocalNonCritical() as db_nc:
        for url in body.urls:
            url_str = str(url)
            domain = urlparse(url_str).netloc

            try:
                normalized = await _website_connector.fetch(url_str)
            except Exception as exc:
                raise HTTPException(422, f"Failed to fetch URL '{url_str}': {exc}")

            content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()
            existing, _ = await find_exact_duplicate(
                db, db_nc,
                source_type=SourceType.WEBSITE.value,
                original_name=url_str,
                project_name=body.project_name,
                source_url=url_str,
                source_metadata={"domain": domain},
                content_hash=content_hash,
            )
            if existing is not None:
                skipped_urls.append(url_str)
                continue

            doc_id = uuid.uuid4()
            doc = Document(
                id=doc_id,
                project_name=body.project_name,
                filename=f"{doc_id}.html",
                original_name=url_str,
                file_type="html",
                file_size_bytes=len(normalized["text"].encode("utf-8")),
                source_type=SourceType.WEBSITE.value,
                source_url=url_str,
                source_metadata={"domain": domain},
                content_hash=content_hash,
            )
            db.add(doc)
            created.append((doc, url_str, normalized))

    await db.commit()

    for doc, _, normalized in created:
        background_tasks.add_task(_run_text_pipeline, str(doc.id), normalized, "website")

    accepted, skipped = len(created), len(skipped_urls)
    parts = []
    if accepted:
        parts.append(f"{accepted} URL(s) accepted. Processing started.")
    if skipped:
        parts.append(f"{skipped} duplicate URL(s) skipped (no changes detected).")

    return IngestResponse(
        source="website",
        documents=[
            IngestDocumentItem(
                id=doc.id, name=url_str, status=doc.status,
                message="URL accepted. Processing started.",
            )
            for doc, url_str, _ in created
        ],
        skipped=skipped_urls,
        message=" ".join(parts) if parts else "No new URLs to process.",
    )


# ── Shared pipeline runners ───────────────────────────────────────────────────

async def _run_text_pipeline(doc_id: str, normalized: dict, source_label: str = "text"):
    """Shared background task for any source that provides pre-normalized text."""
    async with AsyncSessionLocal() as db, AsyncSessionLocalNonCritical() as db_nc:
        pipeline = IngestionPipeline(db, db_nc)
        try:
            await pipeline.run_from_text(doc_id, normalized)
        except Exception as exc:
            logger.error(f"{source_label}_pipeline_failed", doc_id=doc_id, error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
#  Confluence
# ═══════════════════════════════════════════════════════════════════════════════

async def _ingest_confluence(
    body: ConfluenceIngestBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> IngestResponse:
    url_str = str(body.url)
    email = body.email or settings.CONFLUENCE_EMAIL
    token = body.token or settings.CONFLUENCE_TOKEN.get_secret_value()

    if not email or not token:
        raise HTTPException(
            422,
            "Confluence credentials are not configured. "
            "Set CONFLUENCE_EMAIL and CONFLUENCE_TOKEN, or pass them in the request body.",
        )

    connector = ConfluenceConnector(email=email, token=token)
    try:
        normalized = await connector.fetch(url_str)
    except Exception as exc:
        raise HTTPException(422, f"Failed to fetch Confluence page '{url_str}': {exc}")

    content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()

    async with AsyncSessionLocalNonCritical() as db_nc:
        existing, _ = await find_exact_duplicate(
            db, db_nc,
            source_type=SourceType.CONFLUENCE.value,
            original_name=url_str,
            project_name=body.project_name,
            source_url=url_str,
            source_metadata=normalized.get("metadata", {}),
            content_hash=content_hash,
        )
    if existing is not None:
        return IngestResponse(
            source="confluence",
            documents=[IngestDocumentItem(
                id=existing.id, name=url_str,
                status=existing.status,
                message="Duplicate skipped (no changes detected).",
            )],
            skipped=[url_str],
            message="Duplicate skipped (no changes detected).",
        )

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_name=body.project_name,
        filename=f"{doc_id}.html",
        original_name=url_str,
        file_type="html",
        file_size_bytes=len(normalized["text"].encode("utf-8")),
        source_type=SourceType.CONFLUENCE.value,
        source_url=url_str,
        source_metadata=normalized.get("metadata", {}),
        content_hash=content_hash,
    )
    db.add(doc)
    await db.commit()

    background_tasks.add_task(_run_text_pipeline, str(doc.id), normalized, "confluence")

    return IngestResponse(
        source="confluence",
        documents=[IngestDocumentItem(
            id=doc.id, name=url_str, status=doc.status,
            message="Confluence page accepted. Processing started.",
        )],
        message="Confluence page accepted. Processing started.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SharePoint
# ═══════════════════════════════════════════════════════════════════════════════

async def _ingest_sharepoint(
    body: SharePointIngestBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> IngestResponse:
    link = str(body.link).strip()
    token = body.token or settings.SHAREPOINT_TOKEN.get_secret_value() or None
    connector = SharePointConnector(
        token=token,
        tenant_id=settings.SHAREPOINT_TENANT_ID or None,
        client_id=settings.SHAREPOINT_CLIENT_ID or None,
        client_secret=settings.SHAREPOINT_CLIENT_SECRET.get_secret_value() or None,
    )

    try:
        files = await connector.fetch_documents(link)
    except Exception as exc:
        raise HTTPException(422, f"Failed to fetch SharePoint link: {exc}")

    if not files:
        raise HTTPException(404, "No supported document files found at the SharePoint link.")

    created: list[tuple[Document, dict]] = []
    skipped_files: list[str] = []

    async with AsyncSessionLocalNonCritical() as db_nc:
        for item in files:
            normalized = item["normalized"]
            source_url = item["source_url"]
            original_name = item["original_name"]
            content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()

            existing, _ = await find_exact_duplicate(
                db, db_nc,
                source_type=SourceType.SHAREPOINT.value,
                original_name=original_name,
                project_name=body.project_name,
                source_url=source_url,
                source_metadata=item["metadata"],
                content_hash=content_hash,
            )
            if existing is not None:
                skipped_files.append(original_name)
                continue

            doc_id = uuid.uuid4()
            doc = Document(
                id=doc_id,
                project_name=body.project_name,
                filename=f"{doc_id}.{item['file_type']}" if item["file_type"] else str(doc_id),
                original_name=original_name,
                file_type=item["file_type"] or "txt",
                file_size_bytes=item["file_size_bytes"],
                source_type=SourceType.SHAREPOINT.value,
                source_url=source_url,
                source_metadata=item["metadata"],
                content_hash=content_hash,
            )
            db.add(doc)
            created.append((doc, normalized))

    await db.commit()

    for doc, normalized in created:
        background_tasks.add_task(_run_text_pipeline, str(doc.id), normalized, "sharepoint")

    accepted, skipped = len(created), len(skipped_files)
    parts = []
    if accepted:
        parts.append(f"{accepted} SharePoint document(s) accepted. Processing started.")
    if skipped:
        parts.append(f"{skipped} duplicate SharePoint document(s) skipped (no changes detected).")

    return IngestResponse(
        source="sharepoint",
        documents=[
            IngestDocumentItem(
                id=doc.id,
                name=doc.original_name,
                status=doc.status,
                message="SharePoint document accepted. Processing started.",
            )
            for doc, _ in created
        ],
        skipped=skipped_files,
        message=" ".join(parts) if parts else "No new SharePoint documents to process.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Repository
# ═══════════════════════════════════════════════════════════════════════════════

async def _ingest_repo(
    body: RepoIngestBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> IngestResponse:
    repo_url = str(body.repo_url).rstrip("/")

    try:
        platform = detect_platform(repo_url)
    except Exception as exc:
        raise HTTPException(422, str(exc))

    source_type = SourceType.HARNESS if platform == "harness" else SourceType.GITHUB

    token = body.token
    if not token:
        token = settings.HARNESS_TOKEN.get_secret_value() if platform == "harness" else settings.GITHUB_TOKEN.get_secret_value()
        token = token or None

    connector = RepositoryConnector(token=token)

    try:
        files = await connector.fetch_repo(
            repo_url=repo_url, branch=body.branch, path_filter=body.path_filter,
        )
    except Exception as exc:
        raise HTTPException(422, f"Failed to fetch repository: {exc}")

    if not files:
        raise HTTPException(404, "No indexable files found. Check the repo URL, branch, and path filter.")

    created: list[tuple[Document, dict]] = []
    skipped_files: list[str] = []

    async with AsyncSessionLocalNonCritical() as db_nc:
        for normalized in files:
            file_path = normalized["metadata"]["file_path"]
            ext = PurePosixPath(file_path).suffix.lstrip(".")
            doc_id = uuid.uuid4()
            content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()

            existing, _ = await find_exact_duplicate(
                db, db_nc,
                source_type=source_type.value,
                original_name=file_path,
                project_name=body.project_name,
                source_url=repo_url,
                source_metadata=normalized["metadata"],
                content_hash=content_hash,
            )
            if existing is not None:
                skipped_files.append(file_path)
                continue

            doc = Document(
                id=doc_id,
                project_name=body.project_name,
                filename=f"{doc_id}.{ext}" if ext else str(doc_id),
                original_name=file_path,
                file_type=ext or "txt",
                file_size_bytes=len(normalized["text"].encode("utf-8")),
                source_type=source_type.value,
                source_url=repo_url,
                source_metadata=normalized["metadata"],
                content_hash=content_hash,
            )
            db.add(doc)
            created.append((doc, normalized))

    await db.commit()

    for doc, normalized in created:
        background_tasks.add_task(_run_text_pipeline, str(doc.id), normalized, "repo")

    branch = files[0]["metadata"].get("branch") if files else body.branch
    accepted, skipped = len(created), len(skipped_files)

    parts = []
    if accepted:
        parts.append(f"{accepted} file(s) from repo accepted. Processing started.")
    if skipped:
        parts.append(f"{skipped} duplicate file(s) skipped (no changes detected).")

    return IngestResponse(
        source="repo",
        documents=[
            IngestDocumentItem(
                id=doc.id, name=normalized["metadata"]["file_path"],
                status=doc.status,
                message="File accepted. Processing started.",
            )
            for doc, normalized in created
        ],
        skipped=skipped_files,
        message=" ".join(parts) if parts else "No new repository files to process.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Agent Output
# ═══════════════════════════════════════════════════════════════════════════════

async def _ingest_agent_output(
    body: AgentOutputIngestBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> IngestResponse:
    agent_name    = body.agent_name.strip().lower()
    artifact_type = (body.artifact_type or "generic").strip().lower()
    title         = body.title or f"{agent_name}:{artifact_type}"
    sdlc_phase    = body.sdlc_phase or AGENT_PHASE_MAP.get(agent_name, SDLCPhase.GENERAL)

    source_meta: dict = {
        "agent_name":    agent_name,
        "artifact_type": artifact_type,
        "sdlc_phase":    sdlc_phase.value,
    }
    if body.session_id:
        source_meta["session_id"] = body.session_id
    if body.parent_doc_id:
        source_meta["parent_doc_id"] = str(body.parent_doc_id)
    if body.payload:
        source_meta["agent_payload"] = body.payload

    normalized = await _resolve_agent_content(
        inline_content=body.content,
        payload=body.payload,
        title=title,
        agent_name=agent_name,
        artifact_type=artifact_type,
    )

    if normalized is None and not (body.source_url and body.source_url.strip()):
        raise HTTPException(
            422,
            "Provide `content` directly, include substantive text in `payload`, or supply a valid `source_url`.",
        )

    content_hash = ""
    if normalized is not None:
        content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()
        async with AsyncSessionLocalNonCritical() as db_nc:
            existing, _ = await find_exact_duplicate(
                db, db_nc,
                source_type=SourceType.AGENT_OUTPUT.value,
                original_name=title,
                project_name=body.project_name,
                source_url=body.source_url,
                source_metadata=source_meta,
                content_hash=content_hash,
            )
            if existing is not None:
                return IngestResponse(
                    source="agent_output",
                    documents=[IngestDocumentItem(
                        id=existing.id, name=title,
                        status=existing.status,
                        message="Duplicate skipped (no changes detected).",
                    )],
                    message="Duplicate skipped (no changes detected).",
                )
    elif body.source_url and body.source_url.strip():
        try:
            normalized = await _fetch_url_content(
                body.source_url.strip(), title, agent_name, artifact_type,
            )
            content_hash = hashlib.sha256(normalized["text"].encode("utf-8")).hexdigest()
            async with AsyncSessionLocalNonCritical() as db_nc:
                existing, _ = await find_exact_duplicate(
                    db, db_nc,
                    source_type=SourceType.AGENT_OUTPUT.value,
                    original_name=title,
                    project_name=body.project_name,
                    source_url=body.source_url,
                    source_metadata=source_meta,
                    content_hash=content_hash,
                )
                if existing is not None:
                    return IngestResponse(
                        source="agent_output",
                        documents=[IngestDocumentItem(
                            id=existing.id, name=title,
                            status=existing.status,
                            message="Duplicate skipped (no changes detected).",
                        )],
                        message="Duplicate skipped (no changes detected).",
                    )
        except Exception as exc:
            logger.warning("agent_eager_fetch_failed", url=body.source_url, error=str(exc))
            normalized = None

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_name=body.project_name,
        filename=f"{doc_id}.txt",
        original_name=title,
        file_type="agent_output",
        file_size_bytes=len(normalized["text"].encode("utf-8")) if normalized else 0,
        content_hash=content_hash,
        source_type=SourceType.AGENT_OUTPUT.value,
        source_url=body.source_url,
        source_metadata=source_meta,
    )
    db.add(doc)
    await db.commit()

    background_tasks.add_task(
        _run_agent_pipeline, str(doc.id), normalized, sdlc_phase.value,
        source_url=body.source_url, agent_name=agent_name,
        artifact_type=artifact_type, title=title,
    )

    return IngestResponse(
        source="agent_output",
        documents=[IngestDocumentItem(
            id=doc.id, name=title, status=doc.status,
            message="Agent output accepted. Indexing started.",
        )],
        message="Agent output accepted. Indexing started.",
    )


# ── Agent helpers ──────────────────────────────────────────────────────────────

async def _fetch_url_content(url: str, title: str, agent_name: str, artifact_type: str) -> dict:
    if is_confluence_url(url):
        connector = ConfluenceConnector(
            email=settings.CONFLUENCE_EMAIL, token=settings.CONFLUENCE_TOKEN.get_secret_value(),
        )
    else:
        connector = WebsiteConnector()

    fetched = await connector.fetch(url)
    return _build_normalized(fetched["text"], title, agent_name, artifact_type)


async def _run_agent_pipeline(
    doc_id: str,
    normalized: dict | None,
    sdlc_phase: str,
    *,
    source_url: str | None = None,
    agent_name: str = "",
    artifact_type: str = "generic",
    title: str = "",
):
    async with AsyncSessionLocal() as db, AsyncSessionLocalNonCritical() as db_nc:
        pipeline = IngestionPipeline(db, db_nc)
        doc = await pipeline._get_doc(doc_id)
        try:
            if normalized is None:
                url = source_url or doc.source_url
                logger.info("agent_fetching_url_background", url=url, doc_id=doc_id)

                if is_confluence_url(url):
                    connector = ConfluenceConnector(
                        email=settings.CONFLUENCE_EMAIL, token=settings.CONFLUENCE_TOKEN.get_secret_value(),
                    )
                else:
                    connector = WebsiteConnector()

                fetched = await connector.fetch(url)
                normalized = _build_normalized(
                    fetched["text"], title or doc.original_name, agent_name, artifact_type,
                )
                doc.content_hash = hashlib.sha256(normalized["text"].encode()).hexdigest()

            await pipeline.run_agent_output(doc_id, normalized, sdlc_phase)
        except Exception as exc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)
            await db.commit()
            logger.error("agent_pipeline_failed", doc_id=doc_id, error=str(exc))


async def _resolve_agent_content(
    inline_content: str | None,
    payload: dict | None,
    title: str,
    agent_name: str,
    artifact_type: str,
) -> dict | None:
    if inline_content and inline_content.strip():
        text = inline_content.strip()
    else:
        text = _extract_payload_text(payload)
    if not text:
        return None
    return _build_normalized(text, title, agent_name, artifact_type)


_PREFERRED_PAYLOAD_KEYS = {
    "acceptance_criteria", "answer", "artifact", "artifact_content",
    "artifact_text", "body", "brd", "content", "description", "document",
    "generated_content", "generated_text", "markdown", "output",
    "requirements", "result", "summary", "text",
}


def _extract_payload_text(payload: dict | None) -> str | None:
    if not payload:
        return None
    text_blocks = _collect_payload_text(payload)
    if not text_blocks:
        return None
    combined = "\n\n".join(block.strip() for block in text_blocks if block and block.strip())
    combined = re.sub(r"\n{3,}", "\n\n", combined).strip()
    if len(combined) < 40 or len(combined.split()) < 8:
        return None
    return combined


def _collect_payload_text(value, *, key: str | None = None) -> list[str]:
    if isinstance(value, str):
        return [_format_payload_string(value, key)] if _is_substantive_text(value) else []
    if isinstance(value, Mapping):
        texts: list[str] = []
        for child_key, child_value in value.items():
            texts.extend(_collect_payload_text(child_value, key=str(child_key)))
        return texts
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        texts: list[str] = []
        for item in value:
            texts.extend(_collect_payload_text(item, key=key))
        return texts
    return []


def _format_payload_string(value: str, key: str | None) -> str:
    cleaned = value.strip()
    if not key:
        return cleaned
    normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized_key in _PREFERRED_PAYLOAD_KEYS:
        return cleaned
    label = key.strip().replace("_", " ").replace("-", " ").title()
    return f"## {label}\n{cleaned}"


def _is_substantive_text(value: str) -> bool:
    cleaned = value.strip()
    if len(cleaned) < 20:
        return False
    if re.fullmatch(r"https?://\S+", cleaned):
        return False
    if re.fullmatch(r"[\w.-]+@[\w.-]+", cleaned):
        return False
    return bool(re.search(r"[A-Za-z]", cleaned)) and len(cleaned.split()) >= 4


def _build_normalized(text: str, title: str, agent_name: str, artifact_type: str) -> dict:
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    sections = []
    for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
        sections.append({"title": m.group(2).strip(), "level": len(m.group(1))})

    return {
        "text": text,
        "sections": sections,
        "tables": [],
        "page_count": 1,
        "word_count": len(text.split()),
        "metadata": {
            "title": title,
            "agent_name": agent_name,
            "artifact_type": artifact_type,
        },
    }
