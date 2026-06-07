"""
Request Models
==============
Pydantic models for API request validation - Common Integration Service specific.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union, Literal
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    """Supported intent types for the common integration service."""
    CONTEXT_ENRICH_UPLOAD = "context_enrich_upload"
    CONTEXT_ENRICH_INGEST = "context_enrich_ingest"
    CONTEXT_ENRICH_FEEDBACK = "context_enrich_feedback"
    CONTEXT_ENRICH_QUERY = "context_enrich_query"
    CONTEXT_ENRICH_LIST_DOCUMENTS = "context_enrich_list_documents"
    GENERAL_QUESTION = "general_question"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


class SDLCPhase(str, Enum):
    """SDLC phases supported by the RAG agent."""
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    GENERAL = "general"


class FeedbackType(str, Enum):
    """Feedback types supported by the RAG agent."""
    RATING = "rating"
    CORRECTION = "correction"
    DOMAIN_PREFERENCE = "domain_preference"


class IngestSource(str, Enum):
    """Ingest source types supported by the RAG agent."""
    WEBSITE = "website"
    SHAREPOINT = "sharepoint"
    REPO = "repo"
    AGENT_OUTPUT = "agent_output"


class ChatMessage(BaseModel):
    """A single chat message in the conversation."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class ChatRequest(BaseModel):
    """
    Main chat request model for common integration service.
    
    Example for context enrichment upload:
        {
            "session_id": "sess_123",
            "message": "Upload documents to knowledge base",
            "context": {
                "files": [...]
            },
            "explicit_intent": "context_enrich_upload",
            "selected_model": "gemini-2.0-flash"
        }
    """
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="User's natural language message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages")
    explicit_intent: Optional[str] = Field(default=None, description="Explicit intent override")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection for downstream APIs")
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('session_id cannot be empty')
        return v.strip()
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('message cannot be empty')
        return v.strip()


# === Upload Request Models ===
class UploadRequest(BaseModel):
    """Request model for document upload (context_enrich_upload)."""
    session_id: str = Field(..., description="Session identifier")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


# === Ingest Request Models ===
class WebsiteIngestRequest(BaseModel):
    """Request for website ingestion."""
    source: Literal["website"] = "website"
    urls: List[str] = Field(..., min_length=1, description="URLs to ingest")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


class SharePointIngestRequest(BaseModel):
    """Request for SharePoint ingestion."""
    source: Literal["sharepoint"] = "sharepoint"
    link: str = Field(..., description="SharePoint link to ingest")
    token: Optional[str] = Field(default=None, description="Optional auth token")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


class RepoIngestRequest(BaseModel):
    """Request for repository ingestion."""
    source: Literal["repo"] = "repo"
    repo_url: str = Field(..., description="Repository URL")
    branch: Optional[str] = Field(default=None, description="Branch to ingest")
    path_filter: Optional[str] = Field(default=None, description="Path filter pattern")
    token: Optional[str] = Field(default=None, description="Optional auth token")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


class AgentOutputIngestRequest(BaseModel):
    """Request for agent output ingestion."""
    source: Literal["agent_output"] = "agent_output"
    agent_name: str = Field(..., description="Name of the agent")
    source_url: str = Field(..., description="Source URL")
    content: Optional[str] = Field(default=None, description="Content to ingest")
    title: Optional[str] = Field(default=None, description="Title of the content")
    artifact_type: Optional[str] = Field(default="generic", description="Artifact type")
    sdlc_phase: Optional[SDLCPhase] = Field(default=None, description="SDLC phase")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    parent_doc_id: Optional[str] = Field(default=None, description="Parent document ID")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Additional payload")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


IngestRequest = Union[WebsiteIngestRequest, SharePointIngestRequest, RepoIngestRequest, AgentOutputIngestRequest]


class IngestChatContext(BaseModel):
    """Context for ingest operations passed via ChatRequest."""
    source: IngestSource = Field(..., description="Ingest source type")
    urls: Optional[List[str]] = Field(default=None, description="URLs for website ingestion")
    link: Optional[str] = Field(default=None, description="SharePoint link")
    repo_url: Optional[str] = Field(default=None, description="Repository URL")
    branch: Optional[str] = Field(default=None, description="Repository branch")
    path_filter: Optional[str] = Field(default=None, description="Path filter for repo")
    token: Optional[str] = Field(default=None, description="Auth token")
    agent_name: Optional[str] = Field(default=None, description="Agent name for agent_output")
    source_url: Optional[str] = Field(default=None, description="Source URL for agent_output")
    content: Optional[str] = Field(default=None, description="Content for agent_output")
    title: Optional[str] = Field(default=None, description="Title for agent_output")
    artifact_type: Optional[str] = Field(default="generic", description="Artifact type")
    sdlc_phase: Optional[SDLCPhase] = Field(default=None, description="SDLC phase")
    parent_doc_id: Optional[str] = Field(default=None, description="Parent document ID")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Additional payload")


# === Feedback Request Models ===
class FeedbackRequest(BaseModel):
    """Request model for feedback submission (context_enrich_feedback)."""
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    rating: Optional[Literal["positive", "negative"]] = Field(default=None, description="Rating for 'rating' type")
    content: Optional[str] = Field(default=None, description="Feedback content")
    artifact_type: Optional[str] = Field(default=None, description="Artifact type")
    sdlc_phase: Optional[str] = Field(default=None, description="SDLC phase")
    agent_name: Optional[str] = Field(default=None, description="Agent name")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    ref_doc_id: Optional[str] = Field(default=None, description="Reference document ID")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


class FeedbackChatContext(BaseModel):
    """Context for feedback operations passed via ChatRequest."""
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    rating: Optional[Literal["positive", "negative"]] = Field(default=None)
    content: Optional[str] = Field(default=None)
    artifact_type: Optional[str] = Field(default=None)
    sdlc_phase: Optional[str] = Field(default=None)
    agent_name: Optional[str] = Field(default=None)
    ref_doc_id: Optional[str] = Field(default=None)


# === Query Request Models ===
class QueryRequest(BaseModel):
    """Request model for knowledge base query (context_enrich_query)."""
    query: str = Field(..., min_length=3, max_length=1000, description="Query string")
    sdlc_phase: Optional[SDLCPhase] = Field(default=None, description="Filter by SDLC phase")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    include_sources: bool = Field(default=True, description="Include source references")
    criticality: Optional[Literal["critical", "non_critical"]] = Field(default=None, description="Filter by criticality")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")


class QueryChatContext(BaseModel):
    """Context for query operations passed via ChatRequest."""
    query: str = Field(..., min_length=3, max_length=1000)
    sdlc_phase: Optional[SDLCPhase] = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = Field(default=True)
    criticality: Optional[Literal["critical", "non_critical"]] = Field(default=None)


class LegacyAnalyzeRequest(BaseModel):
    """Legacy request model for backward compatibility."""
    query_text: str = Field(..., description="User query text")
    nextagentflow: Optional[str] = Field(default=None, description="Agent flow identifier")
    selected_model: Optional[str] = Field(default=None, description="Optional model selection")
