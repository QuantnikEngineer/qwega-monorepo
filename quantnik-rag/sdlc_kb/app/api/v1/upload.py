import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.models.document import Document, DocumentStatus, SourceType
from app.models.document_nc import DocumentNonCritical
from app.schemas.document import DocumentBatchUploadResponse, DocumentUploadResponse
from app.ingestion.pipeline import IngestionPipeline

router = APIRouter()


@router.post("/upload", response_model=DocumentBatchUploadResponse, status_code=202)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files:            list[UploadFile] = File(...),
    db:               AsyncSession = Depends(get_db),
):
    pending_uploads = []

    for upload in files:
        pending_uploads.append(await _prepare_upload(upload))
        await upload.close()

    created_documents = []
    skipped_filenames: list[str] = []
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocalNonCritical() as db_nc:
        for pending in pending_uploads:
            # Exact-duplicate check: same filename + same content hash already in KB
            if await _is_exact_duplicate(db, db_nc, pending["filename"], pending["content_hash"]):
                skipped_filenames.append(pending["filename"])
                continue

            doc_id    = uuid.uuid4()
            safe_name = f"{doc_id}{pending['ext']}"
            file_path = settings.UPLOAD_DIR / safe_name

            with open(file_path, "wb") as handle:
                handle.write(pending["content"])

            doc = Document(
                id              = doc_id,
                filename        = safe_name,
                original_name   = pending["filename"],
                file_type       = pending["ext"].lstrip("."),
                file_size_bytes = len(pending["content"]),
                content_hash    = pending["content_hash"],
            )
            db.add(doc)
            created_documents.append((doc, file_path))

    await db.commit()

    for doc, file_path in created_documents:
        background_tasks.add_task(_run_pipeline, str(doc.id), file_path)

    accepted = len(created_documents)
    skipped  = len(skipped_filenames)

    parts = []
    if accepted:
        parts.append(f"{accepted} document(s) accepted. Processing started.")
    if skipped:
        parts.append(f"{skipped} duplicate(s) skipped (no changes detected).")

    return DocumentBatchUploadResponse(
        documents=[
            DocumentUploadResponse(
                id              = doc.id,
                filename        = doc.original_name,
                file_type       = doc.file_type,
                file_size_bytes = doc.file_size_bytes,
                status          = doc.status,
                message         = "Document accepted. Processing started.",
            )
            for doc, _ in created_documents
        ],
        skipped = skipped_filenames,
        message = " ".join(parts) if parts else "No new documents to process.",
    )


async def _is_exact_duplicate(
    db,
    db_nc,
    original_name: str,
    content_hash: str,
) -> bool:
    """
    Returns True if a completed uploaded document with the same filename AND
    the same content hash already exists in either the critical or NC database.
    """
    result = await db.execute(
        select(Document).where(
            Document.original_name == original_name,
            Document.source_type   == SourceType.UPLOAD.value,
            Document.status        == DocumentStatus.COMPLETED,
            Document.content_hash  == content_hash,
        ).limit(1)
    )
    if result.scalar_one_or_none():
        return True

    result_nc = await db_nc.execute(
        select(DocumentNonCritical).where(
            DocumentNonCritical.original_name == original_name,
            DocumentNonCritical.source_type   == SourceType.UPLOAD.value,
            DocumentNonCritical.status        == DocumentStatus.COMPLETED,
            DocumentNonCritical.content_hash  == content_hash,
        ).limit(1)
    )
    return result_nc.scalar_one_or_none() is not None


async def _prepare_upload(file: UploadFile) -> dict[str, Any]:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {settings.ALLOWED_EXTENSIONS}")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f}MB). Max: {settings.MAX_UPLOAD_MB}MB")

    return {
        "filename": filename,
        "ext": ext,
        "content": content,
        "content_hash": hashlib.sha256(content).hexdigest(),
    }


async def _run_pipeline(doc_id: str, file_path: Path):
    async with AsyncSessionLocal() as db, AsyncSessionLocalNonCritical() as db_nc:
        pipeline = IngestionPipeline(db, db_nc)
        await pipeline.run(doc_id, file_path)


from app.db.session import AsyncSessionLocal, AsyncSessionLocalNonCritical  # noqa: E402