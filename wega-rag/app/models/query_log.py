import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name         = Column(String(255), nullable=False, index=True)
    query_text           = Column(Text,        nullable=False)
    answer               = Column(Text,        nullable=True)
    sdlc_phase           = Column(String(50),  nullable=True)
    retrieval_count      = Column(Integer,     nullable=True)
    guardrail_passed     = Column(Boolean,     nullable=True)
    conversation_id      = Column(String(255), nullable=True, index=True)
    # JSON list of {filename, chunk_id, score, version}
    sources              = Column(JSON,        nullable=True)
    clarification_needed = Column(Boolean,     default=False)
    created_at           = Column(DateTime,    default=lambda: datetime.now(UTC), index=True)
