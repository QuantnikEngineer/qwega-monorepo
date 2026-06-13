"""
Streaming Models
================
Models for SSE streaming responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class MilestoneStage(str, Enum):
    """Milestone stages for streaming progress."""
    RECEIVED = "received"
    THINKING = "thinking"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    COMPLETE = "complete"
    ERROR = "error"


class MilestoneEvent(BaseModel):
    """A streaming milestone event."""
    type: str = Field(default="milestone", description="Event type")
    stage: MilestoneStage = Field(..., description="Current stage")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Detailed description")
    icon: str = Field(default="⏳", description="Icon for UI")
    progress: Optional[float] = Field(default=None, ge=0, le=1, description="Progress 0-1")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Stage-specific data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"


class StreamingResponse(BaseModel):
    """Final streaming response."""
    type: str = Field(default="complete", description="Event type")
    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Final response message")
    status: str = Field(default="success", description="Response status")
    nextagentflow: Optional[str] = Field(default=None, description="Next agent flow identifier for frontend")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"


class StreamingError(BaseModel):
    """Streaming error event."""
    type: str = Field(default="error", description="Event type")
    stage: str = Field(default="error", description="Stage at which error occurred")
    title: str = Field(default="Error", description="Error title")
    message: str = Field(..., description="Error message")
    icon: str = Field(default="❌", description="Error icon")
    error_code: Optional[str] = Field(default=None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"


class HeartbeatEvent(BaseModel):
    """Heartbeat event to keep SSE connection alive during long operations."""
    type: str = Field(default="heartbeat", description="Event type")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"



class CommonIntegrationMilestones:
    """Factory for common integration milestones."""
    
    @staticmethod
    def received(session_id: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.RECEIVED,
            title="Request Received",
            description=f"Processing request for session {session_id}",
            icon="📥",
            progress=0.1
        )
    
    @staticmethod
    def thinking(message_preview: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.THINKING,
            title="Analyzing Request",
            description=f"Understanding: {message_preview}...",
            icon="🤔",
            progress=0.2
        )
    
    @staticmethod
    def analyzing_intent(intent: Optional[str] = None, confidence: Optional[float] = None) -> MilestoneEvent:
        data = {}
        if intent:
            data["intent"] = intent
        if confidence:
            data["confidence"] = confidence
        return MilestoneEvent(
            stage=MilestoneStage.ANALYZING,
            title="Intent Classified",
            description=f"Detected intent: {intent}" if intent else "Classifying intent...",
            icon="🎯",
            progress=0.3,
            data=data if data else None
        )
    
    @staticmethod
    def executing(action: str, progress: float = 0.5) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Executing Action",
            description=f"Performing: {action}",
            icon="⚙️",
            progress=progress
        )
    
    @staticmethod
    def uploading_files(file_count: int) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Uploading Files",
            description=f"Uploading {file_count} file(s) to knowledge base",
            icon="📤",
            progress=0.5
        )
    
    @staticmethod
    def ingesting(source: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Ingesting Content",
            description=f"Ingesting content from {source}",
            icon="📥",
            progress=0.5
        )
    
    @staticmethod
    def submitting_feedback() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Submitting Feedback",
            description="Submitting feedback to knowledge base",
            icon="💬",
            progress=0.5
        )
    
    @staticmethod
    def querying() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Querying Knowledge Base",
            description="Searching knowledge base for relevant information",
            icon="🔍",
            progress=0.5
        )
    
    @staticmethod
    def complete(summary: str, data: Optional[Dict[str, Any]] = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.COMPLETE,
            title="Complete",
            description=summary,
            icon="✅",
            progress=1.0,
            data=data
        )
    
    @staticmethod
    def error(message: str, error_code: Optional[str] = None) -> StreamingError:
        return StreamingError(
            message=message,
            error_code=error_code
        )
