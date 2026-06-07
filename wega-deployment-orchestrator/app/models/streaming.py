from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MilestoneStage(str, Enum):
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
    PULSE = "pulse"
    SPIN = "spin"
    FADE = "fade"
    BOUNCE = "bounce"
    SLIDE = "slide"
    GLOW = "glow"
    NONE = "none"


class MilestoneEvent(BaseModel):
    type: str = Field(default="milestone")
    stage: MilestoneStage
    title: str
    description: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    icon: str = Field(default="...")
    animation: AnimationType = Field(default=AnimationType.PULSE)
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_hint_ms: int | None = None

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class StreamingResponse(BaseModel):
    type: str = Field(default="response")
    session_id: str
    message: str
    status: str
    nextagentflow: str | None = None
    data: dict[str, Any] | None = None
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    routed_to: str | None = None
    total_duration_ms: int = 0

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class StreamingError(BaseModel):
    type: str = Field(default="error")
    stage: MilestoneStage = Field(default=MilestoneStage.ERROR)
    title: str = Field(default="Error")
    message: str
    icon: str = Field(default="ERR")
    animation: AnimationType = Field(default=AnimationType.NONE)
    details: dict[str, Any] | None = None

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class MilestoneTemplates:
    @staticmethod
    def received(session_id: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.RECEIVED,
            title="Request Received",
            description="Processing your deployment workflow request.",
            progress=0.05,
            icon="IN",
            animation=AnimationType.FADE,
            details={"session_id": session_id},
        )

    @staticmethod
    def thinking(message_preview: str = "") -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.THINKING,
            title="Thinking",
            description="Understanding the requested CI workflow.",
            progress=0.15,
            icon="...",
            animation=AnimationType.PULSE,
            details={"message_preview": message_preview[:80]} if message_preview else None,
            duration_hint_ms=1000,
        )

    @staticmethod
    def analyzing_intent(intent: str | None = None, confidence: float | None = None) -> MilestoneEvent:
        description = "Analyzing deployment intent."
        if intent:
            description = f"Detected intent: {intent.replace('_', ' ')}"
        return MilestoneEvent(
            stage=MilestoneStage.ANALYZING,
            title="Analyzing Intent",
            description=description,
            progress=0.28,
            icon="AI",
            animation=AnimationType.SPIN,
            details={"intent": intent, "confidence": confidence} if intent else None,
        )

    @staticmethod
    def planning(actions: list[str] | None = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PLANNING,
            title="Planning Actions",
            description="Preparing the deployment orchestration steps.",
            progress=0.38,
            icon="PLAN",
            animation=AnimationType.BOUNCE,
            details={"actions": actions} if actions else None,
        )

    @staticmethod
    def executing(action: str, progress: float, details: dict[str, Any] | None = None) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.EXECUTING,
            title="Executing",
            description=action,
            progress=progress,
            icon="RUN",
            animation=AnimationType.GLOW,
            details=details,
        )

    @staticmethod
    def calling_agent(agent_name: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.CALLING_AGENT,
            title=f"Calling {agent_name}",
            description=f"Sending the normalized CI request to {agent_name}.",
            progress=0.62,
            icon="NET",
            animation=AnimationType.PULSE,
            details={"agent": agent_name},
            duration_hint_ms=8000,
        )

    @staticmethod
    def processing_response() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.PROCESSING,
            title="Processing Response",
            description="Normalizing the CI agent response for upstream streaming.",
            progress=0.82,
            icon="OUT",
            animation=AnimationType.SPIN,
        )

    @staticmethod
    def complete(summary: str) -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.COMPLETE,
            title="Complete",
            description=summary,
            progress=1.0,
            icon="OK",
            animation=AnimationType.FADE,
        )


class DeploymentMilestones(MilestoneTemplates):
    @staticmethod
    def routing_to_ci() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ROUTING,
            title="Routing to CI Agent",
            description="Directing the request to the CI agent.",
            progress=0.48,
            icon="CI",
            animation=AnimationType.SLIDE,
            details={"target_agent": "ci"},
        )

    @staticmethod
    def routing_to_cd() -> MilestoneEvent:
        return MilestoneEvent(
            stage=MilestoneStage.ROUTING,
            title="Routing to CD Agent",
            description="Directing the request to the CD agent.",
            progress=0.48,
            icon="CD",
            animation=AnimationType.SLIDE,
            details={"target_agent": "cd"},
        )