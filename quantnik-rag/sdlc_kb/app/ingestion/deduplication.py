from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus, SourceType
from app.models.document_nc import DocumentNonCritical


def build_source_identity_filters(
    model,
    *,
    source_type: str,
    original_name: str,
    source_url: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    exclude_doc_id: Any | None = None,
) -> list[Any]:
    filters: list[Any] = [
        model.source_type == source_type,
        model.status == DocumentStatus.COMPLETED,
    ]

    if source_type == SourceType.AGENT_OUTPUT.value:
        if not source_url:
            raise ValueError("Agent output deduplication requires source_url")
        filters.append(model.source_url == source_url)
    else:
        filters.append(model.original_name == original_name)

    if source_url is not None and source_type != SourceType.AGENT_OUTPUT.value:
        filters.append(model.source_url == source_url)

    branch = (source_metadata or {}).get("branch")
    if branch and source_type in {SourceType.GITHUB.value, SourceType.HARNESS.value}:
        filters.append(model.source_metadata["branch"].as_string() == branch)

    if exclude_doc_id is not None:
        filters.append(model.id != exclude_doc_id)

    return filters


async def find_exact_duplicate(
    db: AsyncSession,
    db_nc: AsyncSession,
    *,
    source_type: str,
    original_name: str,
    content_hash: str,
    source_url: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[Any | None, str | None]:
    filters = build_source_identity_filters(
        Document,
        source_type=source_type,
        original_name=original_name,
        source_url=source_url,
        source_metadata=source_metadata,
    )
    filters.append(Document.content_hash == content_hash)

    result = await db.execute(select(Document).where(*filters).limit(1))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, "critical"

    filters_nc = build_source_identity_filters(
        DocumentNonCritical,
        source_type=source_type,
        original_name=original_name,
        source_url=source_url,
        source_metadata=source_metadata,
    )
    filters_nc.append(DocumentNonCritical.content_hash == content_hash)

    result_nc = await db_nc.execute(select(DocumentNonCritical).where(*filters_nc).limit(1))
    existing_nc = result_nc.scalar_one_or_none()
    if existing_nc is not None:
        return existing_nc, "non_critical"

    return None, None


async def find_url_duplicate(
    db: AsyncSession,
    db_nc: AsyncSession,
    *,
    source_url: str,
    source_type: str = SourceType.AGENT_OUTPUT.value,
) -> tuple[Any | None, str | None]:
    """Check for an existing completed document with the same source_url."""
    filters = [
        Document.source_type == source_type,
        Document.source_url == source_url,
        Document.status == DocumentStatus.COMPLETED,
    ]
    result = await db.execute(select(Document).where(*filters).limit(1))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, "critical"

    filters_nc = [
        DocumentNonCritical.source_type == source_type,
        DocumentNonCritical.source_url == source_url,
        DocumentNonCritical.status == DocumentStatus.COMPLETED,
    ]
    result_nc = await db_nc.execute(select(DocumentNonCritical).where(*filters_nc).limit(1))
    existing_nc = result_nc.scalar_one_or_none()
    if existing_nc is not None:
        return existing_nc, "non_critical"

    return None, None