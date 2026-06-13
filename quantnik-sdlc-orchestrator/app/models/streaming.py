"""
Streaming Models
================
Models for real-time milestone streaming via Server-Sent Events (SSE).
Provides visual feedback during request processing.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json


class MilestoneStage(str, Enum):
    """Stages of request processing."""
    RECEIVED = "received"
    THINKING = "thinking"
    ANALYZING = "analyzing"
    ROUTING = "routing"
    PLANNING = "planning"
    EXECUTING = "executing"
    CALLING_AGENT = "calling_agent"
    PROCESSING = "processing"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    ERROR = "error"


class AnimationType(str, Enum):
    """Animation types for frontend transitions."""
    PULSE = "pulse"
    SPIN = "spin"
    FADE = "fade"
    BOUNCE = "bounce"
    SLIDE = "slide"
    GLOW = "glow"
    NONE = "none"


class MilestoneEvent(BaseModel):
    """
    A single milestone event sent via SSE.
    
    Frontend can use these to show animated progress indicators.
    """
    type: str = Field(default="milestone", description="Event type")
    stage: MilestoneStage = Field(..., description="Current processing stage")
    title: str = Field(..., description="Human-readable milestone title")
    description: str = Field(..., description="Detailed description")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress 0-1")
    icon: str = Field(default="🔄", description="Emoji icon for visual feedback")
    animation: AnimationType = Field(default=AnimationType.PULSE)
    details: Optional[Dict[str, Any]] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_hint_ms: Optional[int] = Field(default=None, description="Expected duration hint")
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = self.model_dump(mode="json")
        data["timestamp"] = self.timestamp.isoformat()
        return f"data: {json.dumps(data)}\n\n"


class StreamingResponse(BaseModel):
    """Final response sent after all milestones."""
    type: str = Field(default="response")
    session_id: str
    message: str
    status: str
    job_id: Optional[str] = None
    nextagentflow: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    push_results: Optional[Dict[str, Any]] = Field(default=None, description="Push results from child orchestrator")
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list)
    routed_to: Optional[str] = None
    total_duration_ms: int = 0
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"


class StreamingError(BaseModel):
    """Error event for streaming."""
    type: str = Field(default="error")
    stage: MilestoneStage = Field(default=MilestoneStage.ERROR)
    title: str = Field(default="Error Occurred")
    message: str
    icon: str = Field(default="❌")
    animation: AnimationType = Field(default=AnimationType.NONE)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {self.model_dump_json()}\n\n"


# Pre-defined milestone templates for consistent UX
class MilestoneTemplates:
    """Pre-defined milestone templates for common stages."""
    
    @staticmethod
    def received(session_id: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.RECEIVED,
            title="Request Received",
            description="Processing your request...",
            progress=0.05,
            icon="📥",
            animation=AnimationType.FADE,
            details={"session_id": session_id}
        )
    
    @staticmethod
    def thinking(message_preview: str = "") -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.THINKING,
            title="Thinking",
            description=f"Understanding what you need...",
            progress=0.15,
            icon="🤔",
            animation=AnimationType.PULSE,
            details={"analyzing": message_preview[:50]} if message_preview else None,
            duration_hint_ms=2000
        )
    
    @staticmethod
    def analyzing_intent(intent: str = None, confidence: float = None) -> MilestoneEvent:
        desc = "Analyzing your intent..."
        if intent:
            desc = f"Detected intent: {intent.replace('_', ' ').title()}"
        return MilestoneEvent(
            stage=MilestoneStage.ANALYZING,
            title="Analyzing Intent",
            description=desc,
            progress=0.25,
            icon="🔍",
            animation=AnimationType.SPIN,
            details={"intent": intent, "confidence": confidence} if intent else None
        )
    
    @staticmethod
    def routing(target: str) -> MilestoneEvent:
        target_name = target.replace("_", " ").title() if target else "appropriate"
        return MilestoneEvent(
            stage=MilestoneStage.ROUTING,
            title="Routing Request",
            description=f"Directing to {target_name} Orchestrator...",
            progress=0.35,
            icon="🔀",
            animation=AnimationType.SLIDE,
            details={"target": target}
        )
    
    @staticmethod
    def planning(actions: List[str] = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PLANNING,
            title="Planning Actions",
            description="Determining the best approach...",
            progress=0.40,
            icon="📋",
            animation=AnimationType.BOUNCE,
            details={"planned_actions": actions} if actions else None
        )
    
    @staticmethod
    def executing(action: str, index: int = 1, total: int = 1) -> MilestoneEvent:
        action_name = action.replace("_", " ").title()
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title=f"Executing ({index}/{total})",
            description=f"{action_name}...",
            progress=0.45 + (0.35 * index / total),
            icon="⚡",
            animation=AnimationType.GLOW,
            details={"action": action, "step": index, "total": total}
        )
    
    @staticmethod
    def calling_agent(agent_name: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.CALLING_AGENT,
            title=f"Calling {agent_name}",
            description=f"Communicating with {agent_name}...",
            progress=0.60,
            icon="📡",
            animation=AnimationType.PULSE,
            details={"agent": agent_name},
            duration_hint_ms=10000
        )
    
    @staticmethod
    def processing_response() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title="Processing Response",
            description="Analyzing results...",
            progress=0.80,
            icon="⚙️",
            animation=AnimationType.SPIN
        )
    
    @staticmethod
    def synthesizing() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.SYNTHESIZING,
            title="Preparing Response",
            description="Synthesizing your response...",
            progress=0.90,
            icon="✨",
            animation=AnimationType.GLOW
        )
    
    @staticmethod
    def complete(summary: str = "Request completed successfully") -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.COMPLETE,
            title="Complete",
            description=summary,
            progress=1.0,
            icon="✅",
            animation=AnimationType.FADE
        )
    
    @staticmethod
    def error(message: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ERROR,
            title="Error",
            description=message,
            progress=1.0,
            icon="❌",
            animation=AnimationType.NONE
        )


# SDLC-specific milestones
class SDLCMilestones(MilestoneTemplates):
    """SDLC Orchestrator specific milestones."""
    
    @staticmethod
    def routing_to_planning() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ROUTING,
            title="Routing to Planning",
            description="Connecting to Planning Orchestrator for BRD/User Story tasks...",
            progress=0.35,
            icon="📝",
            animation=AnimationType.SLIDE,
            details={"target": "planning"}
        )
    
    @staticmethod
    def routing_to_test() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ROUTING,
            title="Routing to Test",
            description="Connecting to Test Orchestrator for test automation tasks...",
            progress=0.35,
            icon="🧪",
            animation=AnimationType.SLIDE,
            details={"target": "test"}
        )
    
    @staticmethod
    def awaiting_child_response(orchestrator: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title=f"Awaiting {orchestrator.title()} Response",
            description=f"Waiting for {orchestrator} orchestrator to complete...",
            progress=0.70,
            icon="⏳",
            animation=AnimationType.PULSE,
            details={"orchestrator": orchestrator},
            duration_hint_ms=30000
        )


# Planning-specific milestones
class PlanningMilestones(MilestoneTemplates):
    """Planning Orchestrator specific milestones."""
    
    @staticmethod
    def creating_brd(project_name: str = None) -> MilestoneEvent:
        desc = "Creating Business Requirements Document..."
        if project_name:
            desc = f"Creating BRD for {project_name}..."
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Creating BRD",
            description=desc,
            progress=0.50,
            icon="📄",
            animation=AnimationType.GLOW,
            details={"project": project_name} if project_name else None,
            duration_hint_ms=30000
        )
    
    @staticmethod
    def analyzing_transcript() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ANALYZING,
            title="Analyzing Transcript",
            description="Extracting requirements from transcript...",
            progress=0.45,
            icon="📝",
            animation=AnimationType.SPIN,
            duration_hint_ms=15000
        )
    
    @staticmethod
    def generating_user_stories(brd_link: str = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Generating User Stories",
            description="Creating epics and user stories from BRD...",
            progress=0.55,
            icon="📋",
            animation=AnimationType.GLOW,
            details={"brd_link": brd_link} if brd_link else None,
            duration_hint_ms=45000
        )
    
    @staticmethod
    def validating_stories() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Validating User Stories",
            description="Checking stories against BRD requirements...",
            progress=0.60,
            icon="✓",
            animation=AnimationType.PULSE,
            duration_hint_ms=20000
        )
    
    @staticmethod
    def updating_confluence() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title="Updating Confluence",
            description="Saving document to Confluence...",
            progress=0.85,
            icon="☁️",
            animation=AnimationType.SPIN
        )
    
    @staticmethod
    def summarizing_brd() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Summarizing BRD",
            description="Generating intelligent summary...",
            progress=0.55,
            icon="📊",
            animation=AnimationType.GLOW
        )


# Test-specific milestones
class TestMilestones(MilestoneTemplates):
    """Test Orchestrator specific milestones."""
    
    @staticmethod
    def generating_scenarios(story_count: int = None) -> MilestoneEvent:
        desc = "Creating test cases from user stories..."
        if story_count:
            desc = f"Generating cases for {story_count} user stories..."
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Generating Test Cases",
            description=desc,
            progress=0.55,
            icon="🎯",
            animation=AnimationType.GLOW,
            details={"story_count": story_count} if story_count else None,
            duration_hint_ms=30000
        )
    
    @staticmethod
    def generating_scripts(framework: str = "Selenium", language: str = "Java") -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Generating Test Scripts",
            description=f"Creating {framework} scripts in {language}...",
            progress=0.60,
            icon="💻",
            animation=AnimationType.GLOW,
            details={"framework": framework, "language": language},
            duration_hint_ms=45000
        )
    
    @staticmethod
    def pushing_to_repo() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title="Pushing to Repository",
            description="Committing generated scripts to repository...",
            progress=0.85,
            icon="📤",
            animation=AnimationType.SPIN
        )
    
    @staticmethod
    def analyzing_coverage() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ANALYZING,
            title="Analyzing Coverage",
            description="Calculating test coverage...",
            progress=0.75,
            icon="📈",
            animation=AnimationType.PULSE
        )
