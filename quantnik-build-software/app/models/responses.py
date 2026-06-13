from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.requests import PipelineStatus, StepStatus


class StepResult(BaseModel):
    step: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PipelineRun(BaseModel):
    run_id: str
    project_name: str
    status: PipelineStatus = PipelineStatus.PENDING
    current_step: Optional[str] = None
    steps: List[StepResult] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Key → URL map: brd_url, jira_epic_url, test_cases_url, repo_url, deployment_url"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class SSEEvent(BaseModel):
    event_type: str          # milestone | log | artifact | error | complete
    step: Optional[str] = None
    title: str = ""
    detail: Optional[str] = None
    progress: float = 0.0    # 0–1
    artifact_key: Optional[str] = None
    artifact_url: Optional[str] = None
    run_id: Optional[str] = None
