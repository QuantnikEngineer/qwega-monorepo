"""
Knowledge graph entity and relationship models.

Stores extracted entities and their relationships in Postgres.
Entity embeddings are stored in a dedicated Qdrant collection for
graph-like traversal via similarity search.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class Entity(Base):
    """A named entity extracted from a document chunk."""
    __tablename__ = "entities"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name = Column(String(255), nullable=False, index=True)
    name         = Column(String(512), nullable=False, index=True)
    entity_type  = Column(String(100), nullable=False, index=True)   # SYSTEM, API, PERSON, TECHNOLOGY, PROCESS, REQUIREMENT, ...
    description  = Column(Text, nullable=True)
    doc_id       = Column(UUID(as_uuid=True), nullable=True, index=True)
    sdlc_phase   = Column(String(50), nullable=True)
    mention_count = Column(Integer, default=1)
    created_at   = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at   = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Relationship(Base):
    """A directed relationship between two entities."""
    __tablename__ = "relationships"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name     = Column(String(255), nullable=False, index=True)
    source_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    target_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    relation_type    = Column(String(100), nullable=False, index=True)  # DEPENDS_ON, IMPLEMENTS, TESTS, SECURES, DEPLOYS, ...
    description      = Column(Text, nullable=True)
    confidence       = Column(Float, default=1.0)
    doc_id           = Column(UUID(as_uuid=True), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(UTC))
