from typing import Optional
from pydantic import BaseModel, Field

from app.models.document import SDLCPhase


class ContextEnrichRequest(BaseModel):
    project_name:  str               = Field(..., min_length=1, max_length=255, description="Project name — required gatekeeper")
    artifact_type: str               = Field(..., description="e.g. brd, user_story, test_case, design")
    sdlc_phase:    Optional[SDLCPhase] = Field(None, description="Filter results to a specific SDLC phase")
    top_k:         int               = Field(5, ge=1, le=20)


class ChunkItem(BaseModel):
    content:     str
    source:      str
    score:       float
    source_type: Optional[str] = None  # "feedback" | "upload" | "agent_output" | …


class ContextEnrichResponse(BaseModel):
    artifact_type: str
    sdlc_phase:    Optional[str]
    chunks:        list[ChunkItem]
    total:         int
