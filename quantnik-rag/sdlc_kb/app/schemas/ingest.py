from __future__ import annotations

from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.document import DocumentStatus, SDLCPhase


# Maps agent name → default SDLC phase
AGENT_PHASE_MAP: dict[str, SDLCPhase] = {
    "brd_generator":        SDLCPhase.REQUIREMENTS,
    "user_story_generator": SDLCPhase.REQUIREMENTS,
    "design_agent":         SDLCPhase.DESIGN,
    "code_generator":       SDLCPhase.DEVELOPMENT,
    "test_generator":       SDLCPhase.TESTING,
    "security_scanner":     SDLCPhase.SECURITY,
    "deploy_agent":         SDLCPhase.DEPLOYMENT,
}


# ── Discriminated request variants ─────────────────────────────────────────────

class ConfluenceIngestBody(BaseModel):
    source: Literal["confluence"] = "confluence"
    url:   HttpUrl
    email: Optional[str] = None   # overrides CONFLUENCE_EMAIL env var
    token: Optional[str] = None   # overrides CONFLUENCE_TOKEN env var


class WebsiteIngestBody(BaseModel):
    source: Literal["website"] = "website"
    urls: list[HttpUrl]


class SharePointIngestBody(BaseModel):
    source: Literal["sharepoint"] = "sharepoint"
    link: HttpUrl
    token: Optional[str] = None


class RepoIngestBody(BaseModel):
    source: Literal["repo"] = "repo"
    repo_url:    HttpUrl
    branch:      Optional[str] = None
    path_filter: Optional[str] = None
    token:       Optional[str] = None


class AgentOutputIngestBody(BaseModel):
    source: Literal["agent_output"] = "agent_output"
    agent_name:    str
    source_url:    str
    content:       Optional[str]       = None
    title:         Optional[str]       = None
    artifact_type: Optional[str]       = "generic"
    sdlc_phase:    Optional[SDLCPhase] = None
    session_id:    Optional[str]       = None
    parent_doc_id: Optional[UUID]      = None
    payload:       Optional[dict]      = None


IngestRequest = Annotated[
    WebsiteIngestBody | ConfluenceIngestBody | SharePointIngestBody | RepoIngestBody | AgentOutputIngestBody,
    Field(discriminator="source"),
]


# ── Unified response ──────────────────────────────────────────────────────────

class IngestDocumentItem(BaseModel):
    id:      UUID
    name:    str
    status:  DocumentStatus
    message: str


class IngestResponse(BaseModel):
    source:    str
    documents: list[IngestDocumentItem]
    skipped:   list[str] = []
    message:   str
