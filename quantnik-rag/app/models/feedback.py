import uuid
import enum
from datetime import UTC, datetime

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class FeedbackType(str, enum.Enum):
    RATING            = "rating"
    CORRECTION        = "correction"
    DOMAIN_PREFERENCE = "domain_preference"


class Feedback(Base):
    __tablename__ = "feedback"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name  = Column(String(255), nullable=False, index=True)
    feedback_type = Column(Enum(FeedbackType), nullable=False, index=True)

    # For rating type
    rating        = Column(String(20), nullable=True)   # "positive" | "negative"

    # For correction / domain_preference
    content       = Column(Text,       nullable=True)

    # Context metadata
    artifact_type = Column(String(50),  nullable=True)   # brd, user_story, test_case …
    sdlc_phase    = Column(String(50),  nullable=True)
    agent_name    = Column(String(100), nullable=True)
    session_id    = Column(String(255), nullable=True)
    ref_doc_id    = Column(UUID(as_uuid=True), nullable=True)  # document being rated

    # Indexing state
    indexed       = Column(Boolean, default=False)
    qdrant_doc_id = Column(UUID(as_uuid=True), nullable=True)  # doc created in Qdrant

    created_at    = Column(DateTime, default=lambda: datetime.now(UTC))
