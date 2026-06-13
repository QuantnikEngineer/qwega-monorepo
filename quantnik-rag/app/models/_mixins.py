"""
SQLAlchemy column mixins shared by critical and non-critical model variants.

SQLAlchemy copies Column() objects declared in a non-mapped mixin to each
mapped subclass, so both Document/DocumentNonCritical and Chunk/ChunkNonCritical
can inherit the same column definitions without duplication.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, Float, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models._enums import Classification, DocumentStatus, SDLCPhase, SourceType


class DocumentMixin:
    """Shared columns for Document and DocumentNonCritical."""

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name      = Column(String(255), nullable=False, index=True)
    filename          = Column(String(255), nullable=False)
    original_name     = Column(String(255), nullable=False)
    file_type         = Column(String(20),  nullable=False)
    file_size_bytes   = Column(Integer,     nullable=False)
    content_hash      = Column(String(64),  nullable=True,  index=True)
    version           = Column(Integer,     default=1,      nullable=False, index=True)

    status            = Column(Enum(DocumentStatus),  default=DocumentStatus.PENDING, index=True)
    classification    = Column(Enum(Classification),  nullable=True, index=True)
    sdlc_phase        = Column(Enum(SDLCPhase),       nullable=True)
    confidence_score  = Column(Float,   nullable=True)
    triggered_areas   = Column(JSON,    nullable=True)

    chunk_count       = Column(Integer, default=0)
    error_message     = Column(Text,    nullable=True)
    normalized_text   = Column(Text,    nullable=True)

    source_type       = Column(String(50),   default=SourceType.UPLOAD.value, nullable=False)
    source_url        = Column(String(2048), nullable=True)
    source_metadata   = Column(JSON,         nullable=True)

    created_at        = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at        = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    processed_at      = Column(DateTime, nullable=True)


class ChunkMixin:
    """Shared columns for Chunk and ChunkNonCritical."""

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name = Column(String(255), nullable=False, index=True)
    # ForeignKey is NOT declared here because it references the same DB's documents table,
    # which differs between critical and non-critical. Each model declares it directly.
    qdrant_id    = Column(String(100), nullable=True)

    content      = Column(Text,       nullable=False)
    content_hash = Column(String(64), nullable=True)
    chunk_index  = Column(Integer,    nullable=False)
    token_count  = Column(Integer,    nullable=True)
    sdlc_phase   = Column(String(50), nullable=True)
    criticality  = Column(String(20), nullable=True, index=True)

    created_at   = Column(DateTime, default=lambda: datetime.now(UTC))
