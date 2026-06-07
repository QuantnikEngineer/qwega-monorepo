from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.models.document import SDLCPhase


class ConversationTurn(BaseModel):
    role:    Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    query:                str       = Field(..., min_length=3, max_length=1000)
    sdlc_phase:           Optional[SDLCPhase] = None
    top_k:                int       = Field(default=5, ge=1, le=20)
    include_sources:      bool      = True
    # Filter by criticality tier; None (default) searches both collections
    criticality:          Optional[Literal["critical", "non_critical"]] = None
    # Conversation context — pass the last few turns so the LLM can resolve references
    conversation_id:      Optional[str]           = None
    conversation_history: list[ConversationTurn]  = []
    # Version disambiguation — set after user responds to a clarification prompt
    document_name:        Optional[str]           = None
    document_version:     Optional[int]           = None


class SourceItem(BaseModel):
    chunk_id:    str
    filename:    str
    sdlc_phase:  str
    score:       float
    content:     str
    criticality: str = "critical"
    version:     int = 1
    ingested_at: str = ""


class QueryResponse(BaseModel):
    query:                str
    answer:               str
    sources:              list[SourceItem]
    guardrail_passed:     bool
    retrieval_count:      int
    sdlc_phase:           Optional[str]
    # Populated when the retriever detects multiple versions of the same document
    clarification_needed: bool                 = False
    available_versions:   dict[str, list[int]] = {}  # filename -> [v1, v2, ...]