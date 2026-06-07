"""
Non-critical Chunk model — stored in the separate sdlc_kb_non_critical database.

Mirrors app.models.chunk.Chunk but bound to BaseNonCritical.
ForeignKey points to "documents.id" within the same non-critical DB.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseNonCritical


class ChunkNonCritical(BaseNonCritical):
    __tablename__ = "chunks"    # same table name — different DB

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id  = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    qdrant_id    = Column(String(100), nullable=True)

    content      = Column(Text,    nullable=False)
    content_hash = Column(String(64), nullable=True)
    chunk_index  = Column(Integer, nullable=False)
    token_count  = Column(Integer, nullable=True)
    sdlc_phase   = Column(String(50), nullable=True)
    criticality  = Column(String(20), nullable=True, index=True)

    created_at   = Column(DateTime, default=datetime.utcnow)
