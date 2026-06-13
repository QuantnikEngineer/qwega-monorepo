import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id  = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    qdrant_id    = Column(String(100), nullable=True)

    content      = Column(Text,    nullable=False)
    content_hash = Column(String(64), nullable=True)
    chunk_index  = Column(Integer, nullable=False)
    token_count  = Column(Integer, nullable=True)
    sdlc_phase   = Column(String(50), nullable=True)
    # "critical" or "non_critical" — mirrors the document classification
    criticality  = Column(String(20), nullable=True, index=True)

    created_at   = Column(DateTime, default=datetime.utcnow)