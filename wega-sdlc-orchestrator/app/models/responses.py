"""
Response Models
===============
Pydantic models for SDLC Orchestrator API responses.
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
    orchestrator: Optional[str] = Field(default=None, description="Target orchestrator")
    confidence: float = Field(default=1.0)


class ChatResponse(BaseModel):
    """Main chat response model."""
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Response message")
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    job_id: Optional[str] = Field(default=None, description="Job ID from child orchestrator")
    nextagentflow: Optional[str] = Field(default=None, description="Next agent flow from child orchestrator")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Structured data")
    push_results: Optional[Dict[str, Any]] = Field(default=None, description="Push results from child orchestrator")
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    routed_to: Optional[str] = Field(default=None, description="Which orchestrator handled the request")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrchestratorCapability(BaseModel):
    """Capability description for an orchestrator."""
    name: str
    description: str
    intents: List[str]
    keywords: List[str]
    url: str
    status: str = "healthy"


class CapabilitiesResponse(BaseModel):
    """Response containing orchestrator capabilities."""
    orchestrators: List[OrchestratorCapability]
    total_intents: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str = Field(default="Wega SDLC Orchestrator")
    version: str
    components: Dict[str, str] = Field(default_factory=dict)
    child_orchestrators: Dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standardized error response."""
    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LegacyAnalyzeResponse(BaseModel):
    """Legacy response format for backward compatibility."""
    success: bool
    result: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    nextagentflow: Optional[str] = Field(default=None)
    next_suggested_action: Optional[str] = Field(default=None)
    nextuserflow: Optional[str] = Field(default=None)
    updatedNextQuery: Optional[str] = Field(default=None)
    routed_to: Optional[str] = Field(default=None)
