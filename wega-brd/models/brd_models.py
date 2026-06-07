"""
models/brd_models.py

All Pydantic data models for the BRD Agent.
The 9 predefined stakeholder roles come directly from the Miro diagram.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Session limits ───────────────────────────────────────────────────────────
# Centralised so api/main.py and the agents agree on the same caps.
MAX_HISTORY_MESSAGES        = 200          # rolling window per session
MAX_DOCUMENTS_TOTAL_BYTES   = 50 * 1024 * 1024  # ~50 MB of extracted text per session
MAX_CORRECTION_ATTEMPTS     = 5            # stakeholder confirmation retries
MAX_UPDATE_MATCH_ATTEMPTS   = 5            # ambiguous / mismatch retries (brownfield)
SESSION_TTL_SECONDS         = 24 * 60 * 60 # idle sessions are evicted after 24 h


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 9 Predefined Roles (from diagram) ────────────────────────────────────────

class StakeholderRole(str, Enum):
    PRODUCT_OWNER            = "Product Owner / Product Manager"
    BUSINESS_SPONSOR         = "Business Sponsor / Executive Sponsor"
    BUSINESS_SME             = "Business SME (Subject Matter Expert)"
    PROCESS_ANALYST          = "Process Analyst"
    UX_RESEARCHER            = "UX Researcher / CX Analyst"
    SOLUTION_ARCHITECT       = "Solution Architect"
    COMPLIANCE_OFFICER       = "Compliance / Risk Officer"
    INFO_SECURITY_OFFICER    = "Information Security Officer"
    PROJECT_MANAGER          = "Project Manager"


ROLE_RESPONSIBILITIES: dict[StakeholderRole, str] = {
    StakeholderRole.PRODUCT_OWNER:         "Defines product vision, business goals, and prioritizes requirements.",
    StakeholderRole.BUSINESS_SPONSOR:      "Provides strategic direction, funding, and final approvals.",
    StakeholderRole.BUSINESS_SME:          "Provides domain knowledge, validates business workflows and requirements.",
    StakeholderRole.PROCESS_ANALYST:       "Documents as-is and to-be processes, ensures process alignment.",
    StakeholderRole.UX_RESEARCHER:         "Adds user research insights and ensures user-centric requirement definition.",
    StakeholderRole.SOLUTION_ARCHITECT:    "Provides NFRs across performance, scalability, standards and maintainability.",
    StakeholderRole.COMPLIANCE_OFFICER:    "Ensures inclusion of regulatory, legal, and risk mitigation requirements.",
    StakeholderRole.INFO_SECURITY_OFFICER: "Includes security requirements and ensures compliance with security policies.",
    StakeholderRole.PROJECT_MANAGER:       "Manages project delivery, dependencies, risks, and stakeholder coordination.",
}

# Short aliases the LLM or user might type → canonical role
ROLE_ALIASES: dict[str, StakeholderRole] = {
    # Product Owner
    "product owner":            StakeholderRole.PRODUCT_OWNER,
    "product manager":          StakeholderRole.PRODUCT_OWNER,
    "po":                       StakeholderRole.PRODUCT_OWNER,
    "pm":                       StakeholderRole.PRODUCT_OWNER,
    # Business Sponsor
    "business sponsor":         StakeholderRole.BUSINESS_SPONSOR,
    "executive sponsor":        StakeholderRole.BUSINESS_SPONSOR,
    "sponsor":                  StakeholderRole.BUSINESS_SPONSOR,
    "exec sponsor":             StakeholderRole.BUSINESS_SPONSOR,
    # Business SME
    "business sme":             StakeholderRole.BUSINESS_SME,
    "sme":                      StakeholderRole.BUSINESS_SME,
    "subject matter expert":    StakeholderRole.BUSINESS_SME,
    # Process Analyst
    "process analyst":          StakeholderRole.PROCESS_ANALYST,
    "process analyst ba":       StakeholderRole.PROCESS_ANALYST,
    # UX Researcher
    "ux researcher":            StakeholderRole.UX_RESEARCHER,
    "cx analyst":               StakeholderRole.UX_RESEARCHER,
    "ux":                       StakeholderRole.UX_RESEARCHER,
    "ux/cx analyst":            StakeholderRole.UX_RESEARCHER,
    # Solution Architect
    "solution architect":       StakeholderRole.SOLUTION_ARCHITECT,
    "architect":                StakeholderRole.SOLUTION_ARCHITECT,
    "sa":                       StakeholderRole.SOLUTION_ARCHITECT,
    # Compliance
    "compliance officer":       StakeholderRole.COMPLIANCE_OFFICER,
    "risk officer":             StakeholderRole.COMPLIANCE_OFFICER,
    "compliance":               StakeholderRole.COMPLIANCE_OFFICER,
    # InfoSec
    "information security officer": StakeholderRole.INFO_SECURITY_OFFICER,
    "infosec":                  StakeholderRole.INFO_SECURITY_OFFICER,
    "security officer":         StakeholderRole.INFO_SECURITY_OFFICER,
    # Project Manager
    "project manager":          StakeholderRole.PROJECT_MANAGER,
    "project manager / pmo":    StakeholderRole.PROJECT_MANAGER,
    "pmo":                      StakeholderRole.PROJECT_MANAGER,
}


# ── Stakeholder ───────────────────────────────────────────────────────────────

class Stakeholder(BaseModel):
    name:  str
    email: str
    role:  StakeholderRole


# ── BRD Document ──────────────────────────────────────────────────────────────

class BRDSection(BaseModel):
    title:         str
    content:       str
    is_ai_assumed: bool = False


class BRDDocument(BaseModel):
    project_name: str
    version:      str = "1.0"
    sections:     list[BRDSection]      = Field(default_factory=list)
    stakeholders: list[Stakeholder]     = Field(default_factory=list)
    raw_json:     dict                  = Field(default_factory=dict)


# ── Conversation Session ──────────────────────────────────────────────────────

class ConversationStep(str, Enum):
    GREETING         = "greeting"           # not yet started
    COLLECT_PROJECT  = "collect_project"    # asking for project name
    COLLECT_ROLES    = "collect_roles"      # asking for stakeholders (role/name/email)
    CONFIRM_ROLES    = "confirm_roles"      # showing parsed list, asking user to confirm
    COLLECT_DOCS     = "collect_docs"       # asking for transcripts / documents
    GENERATING       = "generating"         # BRD generation in progress
    COMPLETE         = "complete"           # BRD .docx ready

    # ── Brownfield (update existing BRD) steps ────────────────────────────
    UPDATE_COLLECT_LINK    = "update_collect_link"      # waiting for Confluence link
    UPDATE_COLLECT_CONTENT = "update_collect_content"   # waiting for update content
    UPDATE_GENERATING      = "update_generating"        # matching + updating BRD
    UPDATE_COMPLETE        = "update_complete"           # updated BRD published


class ChatMessage(BaseModel):
    role:    str   # "user" or "assistant"
    content: str


class ConversationSession(BaseModel):
    session_id:       str
    step:             ConversationStep = ConversationStep.GREETING
    project_name:     str | None       = None
    stakeholders:     list[Stakeholder]= Field(default_factory=list)
    documents_text:   list[str]        = Field(default_factory=list)
    history:          list[ChatMessage]= Field(default_factory=list)
    final_brd_path:   str | None       = None
    error:            str | None       = None
    metadata:         dict[str, Any]   = Field(default_factory=dict)

    # ── Brownfield (update existing BRD) fields ──────────────────────────
    mode:                  str = "new"       # "new" | "update"
    confluence_page_id:    str | None = None
    confluence_page_url:   str | None = None
    existing_brd_content:  str | None = None  # plain-text version of existing BRD
    existing_page_version: int | None = None
    existing_page_title:   str | None = None

    # ── Bookkeeping for retries / TTL / idempotency ──────────────────────
    created_at:            str = Field(default_factory=_utcnow_iso)
    updated_at:            str = Field(default_factory=_utcnow_iso)
    correction_attempts:   int = 0           # CONFIRM_ROLES retries
    update_match_attempts: int = 0           # brownfield ambiguous / mismatch retries
    documents_total_bytes: int = 0
    last_idempotency_key:  str | None = None
    last_idempotent_reply: str | None = None

    def add_message(self, role: str, content: str) -> str:
        self.history.append(ChatMessage(role=role, content=content))
        return content

    def add_user_message(self, content: str) -> str:
        return self.add_message("user", content)

    def add_assistant_message(self, content: str) -> str:
        return self.add_message("assistant", content)

    def touch(self) -> None:
        """Refresh ``updated_at`` to the current time."""
        self.updated_at = _utcnow_iso()
