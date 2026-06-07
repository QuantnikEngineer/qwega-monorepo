"""
Response Models
===============
Pydantic models for API response structure.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status enumeration."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class SuggestedAction(BaseModel):
    """Suggested next action for the user."""
    action: str = Field(..., description="Suggested action description")
    intent: Optional[str] = Field(default=None, description="Intent if user accepts")
    confidence: float = Field(default=1.0, description="Confidence score 0-1")


class ChatResponse(BaseModel):
    """Main chat response model."""
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Response message for the user")
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    nextagentflow: Optional[str] = Field(default=None, description="Next agent flow identifier for frontend")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Structured response data")
    suggested_actions: List[SuggestedAction] = Field(default_factory=list, description="Suggested next actions")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Execution metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# === Upload Response Models ===
class DocumentUploadItem(BaseModel):
    """Individual document upload result."""
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Filename")
    file_type: str = Field(..., description="File type")
    file_size_bytes: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Upload status")
    message: str = Field(..., description="Status message")


class UploadResponse(BaseModel):
    """Response for document upload."""
    documents: List[DocumentUploadItem] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    message: str = Field(..., description="Overall message")


# === Ingest Response Models ===
class IngestDocumentItem(BaseModel):
    """Individual ingest document result."""
    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    status: str = Field(..., description="Ingest status")
    message: str = Field(..., description="Status message")


class IngestResponse(BaseModel):
    """Response for ingestion operations."""
    source: str = Field(..., description="Ingestion source type")
    documents: List[IngestDocumentItem] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    message: str = Field(..., description="Overall message")


# === Feedback Response Models ===
class FeedbackResponse(BaseModel):
    """Response for feedback submission."""
    id: str = Field(..., description="Feedback ID")
    feedback_type: str = Field(..., description="Type of feedback")
    indexed: bool = Field(..., description="Whether feedback was indexed")
    message: str = Field(..., description="Status message")
    status: Optional[str] = Field(default=None, description="Moderation lifecycle status: pending/approved/rejected/quarantined")
    query_log_id: Optional[str] = Field(default=None, description="Echoed query_log_id (when feedback was tied to a prior query)")


# === Query Response Models ===
class SourceItem(BaseModel):
    """Source item in query results."""
    chunk_id: str = Field(..., description="Chunk ID")
    filename: str = Field(..., description="Source filename")
    sdlc_phase: str = Field(..., description="SDLC phase")
    score: float = Field(..., description="Relevance score")
    content: str = Field(..., description="Chunk content")
    criticality: str = Field(default="critical", description="Criticality level")


class QueryResponse(BaseModel):
    """Response for knowledge base query."""
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: List[SourceItem] = Field(default_factory=list)
    guardrail_passed: bool = Field(..., description="Whether guardrail check passed")
    retrieval_count: int = Field(..., description="Number of retrieved chunks")
    sdlc_phase: Optional[str] = Field(default=None, description="SDLC phase filter applied")
    query_log_id: Optional[str] = Field(default=None, description="ID of the persisted QueryLog row — used as the anchor for downstream feedback")
    conversation_id: Optional[str] = Field(default=None, description="Conversation thread identifier")


# === Document List Response Models ===
class DocumentStatusItem(BaseModel):
    """Individual document status from list documents."""
    id: str = Field(..., description="Document UUID")
    filename: str = Field(..., description="Stored filename")
    original_name: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type/extension")
    status: str = Field(..., description="Document status: pending, processing, completed, failed")
    classification: Optional[str] = Field(default=None, description="Classification: critical, non_critical")
    sdlc_phase: Optional[str] = Field(default=None, description="SDLC phase")
    confidence_score: Optional[float] = Field(default=None, description="Classification confidence score")
    triggered_areas: Optional[List[Any]] = Field(default=None, description="Triggered areas")
    chunk_count: int = Field(default=0, description="Number of chunks")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    processed_at: Optional[str] = Field(default=None, description="Processing timestamp")


class DocumentListResponse(BaseModel):
    """Response for list documents endpoint."""
    total: int = Field(..., description="Total number of documents")
    documents: List[DocumentStatusItem] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str = Field(default="Wega Common Integration Service")
    version: str
    components: Dict[str, str] = Field(default_factory=dict, description="Health status of sub-components")


class ErrorResponse(BaseModel):
    """Standardized error response."""
    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error_code: str = Field(..., description="Error code for client handling")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LegacyAnalyzeResponse(BaseModel):
    """Legacy response format for backward compatibility."""
    success: bool = Field(..., description="Whether the request succeeded")
    result: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    nextagentflow: Optional[str] = Field(default=None)
    next_suggested_action: Optional[str] = Field(default=None)
    nextuserflow: Optional[str] = Field(default=None)
    updatedNextQuery: Optional[str] = Field(default=None)
