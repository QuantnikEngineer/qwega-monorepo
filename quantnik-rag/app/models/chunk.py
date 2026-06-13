from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.models._mixins import ChunkMixin


class Chunk(ChunkMixin, Base):
    __tablename__ = "chunks"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)