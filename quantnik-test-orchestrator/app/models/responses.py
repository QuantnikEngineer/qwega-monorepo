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


class AgentExecutionResult(BaseModel):
    """Result from an agent execution."""
    agent_name: str = Field(..., description="Name of the executed agent")
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[Any] = Field(default=None, description="Agent output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tools called during execution")


class MemoryState(BaseModel):
    """Current memory state for a session."""
    session_id: str
    message_count: int = Field(default=0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    last_intent: Optional[str] = Field(default=None)
    last_activity: Optional[datetime] = Field(default=None)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str = Field(default="Quantnik Test Orchestrator")
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
