from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class SuggestedAction(BaseModel):
    action: str
    intent: str | None = None
    agent: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    nextagentflow: str | None = None
    data: dict[str, Any] | None = None
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
    routed_to: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    child_agents: dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)