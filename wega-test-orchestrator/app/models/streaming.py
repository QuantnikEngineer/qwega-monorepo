"""
Streaming Models for Test Orchestrator
======================================
Models for real-time milestone streaming via Server-Sent Events (SSE).
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
    """A single milestone event sent via SSE."""
    type: str = Field(default="milestone")
    stage: MilestoneStage
    title: str
    description: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    icon: str = Field(default="🔄")
    animation: AnimationType = Field(default=AnimationType.PULSE)
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_hint_ms: Optional[int] = None
    
    def to_sse(self) -> str:
        # Use model_dump_json() which properly handles datetime serialization
        return f"data: {self.model_dump_json()}\n\n"


class StreamingResponse(BaseModel):
    """Final response sent after all milestones."""
    type: str = Field(default="response")
    session_id: str
    message: str
    status: str
    nextagentflow: Optional[str] = Field(default=None, description="Next agent flow identifier for frontend")
    data: Optional[Dict[str, Any]] = None
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list)
    total_duration_ms: int = 0
    
    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class StreamingError(BaseModel):
    """Error event for streaming."""
    type: str = Field(default="error")
    stage: MilestoneStage = Field(default=MilestoneStage.ERROR)
    title: str = Field(default="Error Occurred")
    message: str
    icon: str = Field(default="❌")
    source_agent: Optional[str] = Field(default=None, description="Source agent if error from child agent")
    
    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class ChildAgentEvent(BaseModel):
    """Event forwarded from a child agent."""
    type: str = Field(default="child_agent_event")
    source_agent: str = Field(..., description="Name of the child agent (e.g., test_scenario_agent)")
    original_event: Dict[str, Any] = Field(..., description="Original event data from child agent")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        data = self.model_dump(mode="json")
        data["timestamp"] = self.timestamp.isoformat()
        return f"data: {json.dumps(data)}\n\n"


class TestMilestones:
    """Test Orchestrator specific milestones."""
    
    @staticmethod
    def received(session_id: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.RECEIVED,
            title="Request Received",
            description="Processing your test automation request...",
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
            description="Understanding your testing requirements...",
            progress=0.15,
            icon="🤔",
            animation=AnimationType.PULSE,
            duration_hint_ms=2000
        )
    
    @staticmethod
    def analyzing_intent(intent: str = None, confidence: float = None) -> MilestoneEvent:
        desc = "Analyzing your intent..."
        if intent:
            intent_display = intent.replace('_', ' ').title()
            desc = f"Detected intent: {intent_display}"
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
    def planning(actions: List[str] = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PLANNING,
            title="Planning Test Generation",
            description="Determining the best testing approach...",
            progress=0.35,
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
            progress=0.40 + (0.40 * index / total),
            icon="⚡",
            animation=AnimationType.GLOW,
            details={"action": action, "step": index, "total": total}
        )
    
    @staticmethod
    def generating_scenarios(story_count: int = None) -> MilestoneEvent:
        desc = "Creating test scenarios from user stories..."
        if story_count:
            desc = f"Generating scenarios for {story_count} user stories..."
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Generating Test Scenarios",
            description=desc,
            progress=0.55,
            icon="🎯",
            animation=AnimationType.GLOW,
            details={"story_count": story_count} if story_count else None,
            duration_hint_ms=30000
        )
    
    @staticmethod
    def calling_scenario_agent() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.CALLING_AGENT,
            title="Calling Test Scenario Agent",
            description="Generating comprehensive test scenarios...",
            progress=0.55,
            icon="📡",
            animation=AnimationType.PULSE,
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
    def calling_script_agent(framework: str = "Selenium") -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.CALLING_AGENT,
            title="Calling Test Script Agent",
            description=f"Generating {framework} automation scripts...",
            progress=0.60,
            icon="📡",
            animation=AnimationType.PULSE,
            duration_hint_ms=45000
        )
    
    @staticmethod
    def calling_test_data_agent() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.CALLING_AGENT,
            title="Calling Test Data Agent",
            description="Generating structured test data from test cases...",
            progress=0.60,
            icon="📡",
            animation=AnimationType.PULSE,
            duration_hint_ms=30000
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
    
    @staticmethod
    def processing_response() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title="Processing Response",
            description="Analyzing test generation results...",
            progress=0.85,
            icon="⚙️",
            animation=AnimationType.SPIN
        )
    
    @staticmethod
    def synthesizing() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.SYNTHESIZING,
            title="Preparing Response",
            description="Synthesizing your test results...",
            progress=0.92,
            icon="✨",
            animation=AnimationType.GLOW
        )
    
    @staticmethod
    def complete(summary: str = "Test generation completed successfully") -> MilestoneEvent:
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
