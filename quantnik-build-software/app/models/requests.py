"""
Request / Response models — Build Software Orchestrator
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class BuildRequest(BaseModel):
    """
    Kick off the full software-build pipeline.

    Provide either a free-text `description` of what you want built,
    or a pre-existing `confluence_brd_url` to skip BRD creation.
    """
    run_id: Optional[str] = Field(default=None, description="Resume a prior run (leave blank for new)")
    project_name: str = Field(..., description="Short slug used for Jira project, repo name, etc.")
    description: str = Field(..., description="What the software should do (becomes BRD source)")
    confluence_space_key: str = Field(..., description="Confluence space to publish BRD + reports")
    jira_project_key: str = Field(..., description="Jira project key for stories / test cases")
    github_repo: Optional[str] = Field(default=None, description="Existing repo name (created if absent)")
    tech_stack: Dict[str, str] = Field(
        default={"frontend": "react", "backend": "nodejs"},
        description="Tech stack for code generation"
    )
    skip_steps: List[str] = Field(
        default=[],
        description="Steps to skip, e.g. ['create_brd'] if you already have one"
    )


class PipelineStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    PAUSED    = "paused"      # human-in-the-loop gate
    COMPLETED = "completed"
    FAILED    = "failed"


class StepStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    SKIPPED   = "skipped"
    FAILED    = "failed"
