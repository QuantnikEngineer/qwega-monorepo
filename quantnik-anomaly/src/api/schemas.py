"""
API request/response schemas (Pydantic models).
These are the public interfaces - customers see these, IP stays hidden.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


# ==================== ENUMS ====================

class PipelineDecision(str, Enum):
    PROCEED_AUTOMATION = "PROCEED_AUTOMATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    MONITORING_ONLY = "MONITORING_ONLY"
    TRANSIENT_RESOLVED = "TRANSIENT_RESOLVED"


class RemediationAction(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART = "restart"
    ROLLBACK = "rollback"
    NONE = "none"


class RemediationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ==================== ANALYSIS ENDPOINT ====================

class AnalyzeRequest(BaseModel):
    """Request to analyze an alert."""
    alert_payload: Dict[str, Any] = Field(
        ...,
        description="Raw alert payload from monitoring tool (Datadog, Prometheus, etc.)"
    )
    skip_confirmation_wait: bool = Field(
        default=False,
        description="Skip the confirmation wait period (for testing)"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context (namespace, deployment, etc.)"
    )


class KubernetesAction(BaseModel):
    """Recommended Kubernetes action."""
    action_type: RemediationAction
    target_replicas: Optional[int] = None
    rationale: str


class AnalyzeResponse(BaseModel):
    """Response from alert analysis."""
    request_id: str
    confidence_score: int = Field(..., ge=0, le=100)
    pipeline_decision: PipelineDecision
    automation_approved: bool
    recommended_action: KubernetesAction
    root_cause_analysis: str
    executive_summary: str
    risk_assessment: str
    transient_resolved: bool = False
    original_alert_value: Optional[float] = None
    current_value_after_wait: Optional[float] = None
    analysis_timestamp: datetime
    ai_provider: str
    ai_model: str
    latency_ms: float


# ==================== REMEDIATION ENDPOINT ====================

class RemediateRequest(BaseModel):
    """Request to execute remediation."""
    action: RemediationAction = Field(
        ...,
        description="Action to perform"
    )
    target_replicas: Optional[int] = Field(
        default=None,
        description="Target replica count (for scale actions)"
    )
    deployment: str = Field(
        ...,
        description="Kubernetes deployment name"
    )
    namespace: str = Field(
        ...,
        description="Kubernetes namespace"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Link to analysis request ID"
    )
    force: bool = Field(
        default=False,
        description="Force action even if outside thresholds"
    )


class RemediateResponse(BaseModel):
    """Response from remediation execution."""
    request_id: str
    status: RemediationStatus
    action_performed: RemediationAction
    previous_replicas: Optional[int] = None
    new_replicas: Optional[int] = None
    message: str
    execution_time_ms: float
    timestamp: datetime


# ==================== CHAT ENDPOINT ====================

class ChatRequest(BaseModel):
    """Request for chatbot interaction."""
    message: str = Field(
        ...,
        description="User message/question"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation ID for context continuity"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context"
    )


class ChatResponse(BaseModel):
    """Response from chatbot."""
    conversation_id: str
    response: str
    suggested_actions: List[str] = []
    references: List[Dict[str, str]] = []
    timestamp: datetime


# ==================== STATUS ENDPOINT ====================

class AlertHistoryItem(BaseModel):
    """Single alert history entry."""
    alert_id: str
    title: str
    timestamp: datetime
    severity: str
    decision: PipelineDecision
    remediation_status: RemediationStatus
    confidence_score: int


class SystemStatus(BaseModel):
    """Current system status."""
    status: str  # healthy, degraded, unhealthy
    uptime_seconds: float
    last_alert_time: Optional[datetime] = None
    total_alerts_processed: int
    total_remediations: int
    ai_provider: str
    ai_provider_healthy: bool
    monitoring_adapter: str
    monitoring_adapter_healthy: bool


class StatusResponse(BaseModel):
    """Response from status endpoint."""
    system: SystemStatus
    recent_alerts: List[AlertHistoryItem]
    configuration: Dict[str, Any]


# ==================== HEALTH ENDPOINT ====================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # healthy, unhealthy
    version: str
    components: Dict[str, bool]
