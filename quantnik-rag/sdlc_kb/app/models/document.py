import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class Classification(str, enum.Enum):
    CRITICAL     = "critical"
    NON_CRITICAL = "non_critical"


class SDLCPhase(str, enum.Enum):
    REQUIREMENTS = "requirements"
    DESIGN       = "design"
    DEVELOPMENT  = "development"
    TESTING      = "testing"
    DEPLOYMENT   = "deployment"
    SECURITY     = "security"
    GENERAL      = "general"


class SourceType(str, enum.Enum):
    UPLOAD       = "upload"
    GITHUB       = "github"
    HARNESS      = "harness"
    CICD         = "cicd"
    AGENT_OUTPUT = "agent_output"
    CONFLUENCE   = "confluence"
    SHAREPOINT   = "sharepoint"
    WEBSITE      = "website"
    FEEDBACK     = "feedback"


class Document(Base):
    __tablename__ = "documents"

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

    # Source tracking
    source_type       = Column(String(50), default=SourceType.UPLOAD.value, nullable=False)
    source_url        = Column(String(2048), nullable=True)
    source_metadata   = Column(JSON, nullable=True)

    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at      = Column(DateTime, nullable=True)
