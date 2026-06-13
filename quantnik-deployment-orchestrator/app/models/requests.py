from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChildAgentType(str, Enum):
    CI = "ci"
    CD = "cd"
    UNKNOWN = "unknown"


class IntentType(str, Enum):
    GENERATE_CI_PIPELINE = "generate_ci_pipeline"
    GENERATE_CD_PIPELINE = "generate_cd_pipeline"
    GENERAL_QUESTION = "general_question"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


INTENT_TO_AGENT = {
    IntentType.GENERATE_CI_PIPELINE: ChildAgentType.CI,
    IntentType.GENERATE_CD_PIPELINE: ChildAgentType.CD,
    IntentType.GENERAL_QUESTION: ChildAgentType.UNKNOWN,
    IntentType.CONFIRMATION: ChildAgentType.UNKNOWN,
    IntentType.UNKNOWN: ChildAgentType.UNKNOWN,
}


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: dict[str, Any] | None = None
    history: list[ChatMessage] | None = None
    explicit_intent: str | None = None
    target_agent: str | None = None