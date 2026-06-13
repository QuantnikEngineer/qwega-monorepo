from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.api.deps import get_db
from app.models.document import Document
from app.schemas.document import DocumentStatusResponse, DocumentListResponse
from app.retrieval.qdrant_store import QdrantStore

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    skip:        int            = 0,
    limit:       int            = 20,
    filename:    Optional[str] = None,
    source_type: Optional[str] = None,
    db:          AsyncSession   = Depends(get_db),
):
    query = select(Document)
    if filename:
        term = f"%{filename}%"
        query = query.where(
            or_(
                Document.original_name.ilike(term),
                Document.source_url.ilike(term),
            )
        )
    if source_type:
        query = query.where(Document.source_type == source_type)
    total  = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    docs = result.scalars().all()
    return DocumentListResponse(total=total, documents=docs)


@router.get("/documents/{doc_id}", response_model=DocumentStatusResponse)
async def get_document(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    QdrantStore().delete_by_document(str(doc_id))
    await db.delete(doc)
    await db.commit()