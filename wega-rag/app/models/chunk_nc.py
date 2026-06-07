"""
Non-critical Chunk model — stored in the separate sdlc_kb_non_critical database.

Mirrors app.models.chunk.Chunk but bound to BaseNonCritical.
ForeignKey points to "documents.id" within the same non-critical DB.
"""
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseNonCritical
from app.models._mixins import ChunkMixin


class ChunkNonCritical(ChunkMixin, BaseNonCritical):
    __tablename__ = "chunks"    # same table name — different DB

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
