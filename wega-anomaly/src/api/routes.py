"""
FastAPI route definitions.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional

from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    RemediateRequest,
    RemediateResponse,
    ChatRequest,
    ChatResponse,
    StatusResponse,
    HealthResponse,
    PipelineDecision,
    RemediationAction,
    RemediationStatus,
    KubernetesAction,
    SystemStatus,
    AlertHistoryItem
)
from src.config.settings import get_settings
from src.core.engine import AnomalyEngine
from src.adapters.ai_providers import get_ai_provider
from src.adapters.monitoring import get_monitoring_adapter


router = APIRouter()

# Global engine instance (initialized on startup)
_engine: Optional[AnomalyEngine] = None


def get_engine() -> AnomalyEngine:
    """Get or create the anomaly engine instance."""
    global _engine
    if _engine is None:
        settings = get_settings()
        
        ai_provider = get_ai_provider(
            provider=settings.ai_provider,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            timeout=settings.ai_timeout_seconds
        )
        
        monitoring_adapter = get_monitoring_adapter(
            adapter=settings.monitoring_adapter,
            api_key=settings.monitoring_api_key,
            app_key=settings.monitoring_app_key
        )
        
        _engine = AnomalyEngine(
            ai_provider=ai_provider,
            monitoring_adapter=monitoring_adapter,
            settings=settings
        )
    
    return _engine


# ==================== ANALYZE ENDPOINT ====================

@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_alert(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze an alert and return AI-powered decision.
    
    This endpoint:
    1. Parses the alert payload from any supported monitoring tool
    2. Fetches additional metrics for context enrichment
    3. Optionally waits for confirmation (transient detection)
    4. Calls AI provider for root cause analysis
    5. Returns confidence score and recommended action
    """
    try:
        engine = get_engine()
        result = await engine.analyze(
            alert_payload=request.alert_payload,
            skip_confirmation_wait=request.skip_confirmation_wait,
            additional_context=request.context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== REMEDIATE ENDPOINT ====================

@router.post("/api/v1/remediate", response_model=RemediateResponse)
async def execute_remediation(request: RemediateRequest):
    """
    Execute a remediation action on Kubernetes.
    
    Actions:
    - scale_up: Increase replica count
    - scale_down: Decrease replica count
    - restart: Rolling restart of deployment
    - rollback: Rollback to previous revision
    """
    try:
        engine = get_engine()
        result = await engine.remediate(
            action=request.action,
            deployment=request.deployment,
            namespace=request.namespace,
            target_replicas=request.target_replicas,
            request_id=request.request_id,
            force=request.force
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CHAT ENDPOINT ====================

@router.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle chatbot queries about the anomaly system.
    
    Can answer questions about:
    - Current system status
    - Recent alerts and remediations
    - Configuration and thresholds
    - Remediation actions
    """
    try:
        engine = get_engine()
        result = await engine.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== STATUS ENDPOINT ====================

@router.get("/api/v1/status", response_model=StatusResponse)
async def get_status():
    """
    Get current system status and recent activity.
    """
    try:
        engine = get_engine()
        return await engine.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HEALTH ENDPOINTS ====================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check."""
    settings = get_settings()
    
    components = {
        "api": True,
        "config": True,
    }
    
    try:
        engine = get_engine()
        components["ai_provider"] = await engine.ai_provider.health_check()
        components["monitoring"] = await engine.monitoring_adapter.health_check()
    except Exception:
        components["ai_provider"] = False
        components["monitoring"] = False
    
    overall = all(components.values())
    
    return HealthResponse(
        status="healthy" if overall else "unhealthy",
        version="1.0.0",
        components=components
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    try:
        engine = get_engine()
        ai_ok = await engine.ai_provider.health_check()
        if not ai_ok:
            raise HTTPException(status_code=503, detail="AI provider not ready")
        return {"status": "ready"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}
