"""
Non-critical Document model — stored in the separate sdlc_kb_non_critical database.

This mirrors app.models.document.Document but is bound to BaseNonCritical so that
SQLAlchemy routes create_all / session operations to the non-critical engine.

If the non-critical Postgres DB is ever removed, only this file (and chunk_nc.py)
need to be deleted and the pipeline NC path replaced with a text-file fallback.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseNonCritical
from app.models.document import DocumentStatus, Classification, SDLCPhase, SourceType


class DocumentNonCritical(BaseNonCritical):
    __tablename__ = "documents"    # same table name — different DB

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename          = Column(String(255), nullable=False)
    original_name     = Column(String(255), nullable=False)
    file_type         = Column(String(20),  nullable=False)
    file_size_bytes   = Column(Integer,     nullable=False)
    content_hash      = Column(String(64),  nullable=True,  index=True)
    version           = Column(Integer,     default=1,      nullable=False, index=True)

    status            = Column(Enum(DocumentStatus),  default=DocumentStatus.PENDING, index=True)
    classification    = Column(Enum(Classification), nullable=True, index=True)
    sdlc_phase        = Column(Enum(SDLCPhase),      nullable=True)
    confidence_score  = Column(Float,   nullable=True)
    triggered_areas   = Column(JSON,    nullable=True)

    chunk_count       = Column(Integer, default=0)
    error_message     = Column(Text,    nullable=True)
    normalized_text   = Column(Text,    nullable=True)

    source_type       = Column(String(50), default=SourceType.UPLOAD.value, nullable=False)
    source_url        = Column(String(2048), nullable=True)
    source_metadata   = Column(JSON, nullable=True)

    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at      = Column(DateTime, nullable=True)
