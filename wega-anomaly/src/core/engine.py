"""
Core Anomaly Detection Engine.
This contains the protected IP - decision logic, analysis algorithms.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.config.settings import Settings
from src.adapters.ai_providers.base import BaseAIProvider, AIRequest
from src.adapters.monitoring.base import BaseMonitoringAdapter, AlertData
from src.api.schemas import (
    AnalyzeResponse,
    RemediateResponse,
    ChatResponse,
    StatusResponse,
    PipelineDecision,
    RemediationAction,
    RemediationStatus,
    KubernetesAction,
    SystemStatus,
    AlertHistoryItem
)
from src.core.prompts import build_analysis_prompt, build_chat_prompt
from src.core.confidence import calculate_confidence
from src.kubernetes.client import K8sClient


logger = logging.getLogger("anomaly-agent")


class AnomalyEngine:
    """
    Core anomaly detection and remediation engine.
    Contains protected IP: decision algorithms, prompt engineering, scoring logic.
    """
    
    def __init__(
        self,
        ai_provider: BaseAIProvider,
        monitoring_adapter: BaseMonitoringAdapter,
        settings: Settings
    ):
        self.ai_provider = ai_provider
        self.monitoring_adapter = monitoring_adapter
        self.settings = settings
        self.k8s_client = K8sClient(
            in_cluster=settings.k8s_in_cluster,
            namespace=settings.k8s_namespace
        )
        
        # State tracking
        self._start_time = datetime.now()
        self._alerts_processed = 0
        self._remediations_performed = 0
        self._alert_history: list[AlertHistoryItem] = []
        self._conversations: Dict[str, list] = {}
    
    async def analyze(
        self,
        alert_payload: Dict[str, Any],
        skip_confirmation_wait: bool = False,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AnalyzeResponse:
        """
        Analyze an alert and return AI-powered decision.
        
        This is the main entry point for alert analysis.
        """
        request_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Step 1: Parse alert from monitoring tool
        alert = self.monitoring_adapter.parse_webhook(alert_payload)
        logger.info(f"[{request_id}] Parsed alert: {alert.title} (metric={alert.metric_name}, value={alert.metric_value})")
        
        original_value = alert.metric_value
        
        # Step 2: Confirmation wait (transient detection)
        if not skip_confirmation_wait and self.settings.confirmation_wait_seconds > 0:
            logger.info(f"[{request_id}] Waiting {self.settings.confirmation_wait_seconds}s for confirmation...")
            await asyncio.sleep(self.settings.confirmation_wait_seconds)
        
        # Step 3: Fetch current metrics to check if issue persists
        namespace = additional_context.get("namespace") if additional_context else alert.namespace
        deployment = additional_context.get("deployment") if additional_context else alert.deployment
        
        now = datetime.now()
        recent_metrics = await self.monitoring_adapter.fetch_cpu_metrics(
            target=deployment or alert.hostname,
            start_time=now - timedelta(minutes=5),
            end_time=now,
            namespace=namespace
        )
        
        current_value = recent_metrics.latest if recent_metrics.data_points else alert.metric_value
        
        # Step 4: Check for transient resolution
        transient_resolved = False
        if current_value < self.settings.transient_cpu_threshold:
            logger.info(f"[{request_id}] Transient spike detected: {original_value}% -> {current_value}%")
            transient_resolved = True
            
            return AnalyzeResponse(
                request_id=request_id,
                confidence_score=95,
                pipeline_decision=PipelineDecision.TRANSIENT_RESOLVED,
                automation_approved=False,
                recommended_action=KubernetesAction(
                    action_type=RemediationAction.NONE,
                    target_replicas=None,
                    rationale="Issue self-resolved during confirmation wait"
                ),
                root_cause_analysis="Transient CPU spike detected. Issue resolved before remediation needed.",
                executive_summary=f"Alert was triggered at {original_value}% but CPU dropped to {current_value}% after waiting. No action required.",
                risk_assessment="Low - transient spike, self-resolved",
                transient_resolved=True,
                original_alert_value=original_value,
                current_value_after_wait=current_value,
                analysis_timestamp=datetime.now(),
                ai_provider=self.ai_provider.provider_name,
                ai_model=self.settings.ai_model,
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
        
        # Step 5: Fetch historical context for AI analysis
        historical_metrics = await self.monitoring_adapter.fetch_cpu_metrics(
            target=deployment or alert.hostname,
            start_time=now - timedelta(hours=24),
            end_time=now - timedelta(minutes=5),
            namespace=namespace
        )
        
        historical_alerts = await self.monitoring_adapter.fetch_historical_alerts(
            target=alert.hostname,
            start_time=now - timedelta(days=7),
            end_time=now
        )
        
        # Step 6: Build AI prompt with all context
        context = {
            "alert": alert.model_dump(),
            "current_cpu": current_value,
            "original_cpu": original_value,
            "recent_metrics": {
                "avg": recent_metrics.avg,
                "max": recent_metrics.max,
                "min": recent_metrics.min
            },
            "historical_metrics": {
                "avg": historical_metrics.avg,
                "max": historical_metrics.max,
                "min": historical_metrics.min
            },
            "historical_alerts_count": len(historical_alerts),
            "thresholds": {
                "auto": self.settings.confidence_auto_threshold,
                "review": self.settings.confidence_review_threshold,
                "transient": self.settings.transient_cpu_threshold
            },
            "scaling_limits": {
                "min": self.settings.scaling_min_replicas,
                "max": self.settings.scaling_max_replicas
            },
            "additional": additional_context or {}
        }
        
        prompt = build_analysis_prompt(context)
        
        # Step 7: Call AI provider
        ai_request = AIRequest(
            prompt=prompt,
            context=context,
            max_tokens=self.settings.ai_max_tokens,
            temperature=0.3
        )
        
        ai_response = await self.ai_provider.analyze(ai_request)
        
        # Step 8: Parse AI response and calculate final confidence
        import json
        try:
            ai_decision = json.loads(ai_response.content)
        except json.JSONDecodeError:
            logger.error(f"[{request_id}] Failed to parse AI response as JSON")
            ai_decision = {"confidence_score": 50, "recommended_action": "monitor"}
        
        # Apply confidence calculation (IP - proprietary algorithm)
        confidence = calculate_confidence(
            ai_score=ai_decision.get("confidence_score", 50),
            current_cpu=current_value,
            historical_avg=historical_metrics.avg,
            alert_frequency=len(historical_alerts)
        )
        
        # Step 9: Determine pipeline decision
        if confidence >= self.settings.confidence_auto_threshold and self.settings.auto_remediate_enabled:
            decision = PipelineDecision.PROCEED_AUTOMATION
            automation_approved = not self.settings.require_human_approval
        elif confidence >= self.settings.confidence_review_threshold:
            decision = PipelineDecision.HUMAN_REVIEW
            automation_approved = False
        else:
            decision = PipelineDecision.MONITORING_ONLY
            automation_approved = False
        
        # Step 10: Build recommended action
        action_type = RemediationAction(ai_decision.get("recommended_action", "none"))
        target_replicas = ai_decision.get("target_replicas")
        
        if target_replicas:
            target_replicas = max(self.settings.scaling_min_replicas, 
                                 min(self.settings.scaling_max_replicas, target_replicas))
        
        recommended_action = KubernetesAction(
            action_type=action_type,
            target_replicas=target_replicas,
            rationale=ai_decision.get("rationale", "AI-recommended action")
        )
        
        # Track for history
        self._alerts_processed += 1
        self._alert_history.append(AlertHistoryItem(
            alert_id=alert.alert_id,
            title=alert.title,
            timestamp=datetime.now(),
            severity=alert.severity.value,
            decision=decision,
            remediation_status=RemediationStatus.PENDING if automation_approved else RemediationStatus.SKIPPED,
            confidence_score=confidence
        ))
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return AnalyzeResponse(
            request_id=request_id,
            confidence_score=confidence,
            pipeline_decision=decision,
            automation_approved=automation_approved,
            recommended_action=recommended_action,
            root_cause_analysis=ai_decision.get("root_cause", "Analysis pending"),
            executive_summary=ai_decision.get("summary", ""),
            risk_assessment=ai_decision.get("risk_assessment", ""),
            transient_resolved=False,
            original_alert_value=original_value,
            current_value_after_wait=current_value,
            analysis_timestamp=datetime.now(),
            ai_provider=self.ai_provider.provider_name,
            ai_model=self.settings.ai_model,
            latency_ms=latency_ms
        )
    
    async def remediate(
        self,
        action: RemediationAction,
        deployment: str,
        namespace: str,
        target_replicas: Optional[int] = None,
        request_id: Optional[str] = None,
        force: bool = False
    ) -> RemediateResponse:
        """Execute remediation action on Kubernetes."""
        
        request_id = request_id or str(uuid.uuid4())
        start_time = datetime.now()
        
        # Get current state
        current_replicas = await self.k8s_client.get_replicas(deployment, namespace)
        
        try:
            if action == RemediationAction.SCALE_UP:
                new_replicas = target_replicas or (current_replicas + 1)
                new_replicas = min(new_replicas, self.settings.scaling_max_replicas)
                await self.k8s_client.scale(deployment, namespace, new_replicas)
                message = f"Scaled up from {current_replicas} to {new_replicas} replicas"
                
            elif action == RemediationAction.SCALE_DOWN:
                new_replicas = target_replicas or (current_replicas - 1)
                new_replicas = max(new_replicas, self.settings.scaling_min_replicas)
                await self.k8s_client.scale(deployment, namespace, new_replicas)
                message = f"Scaled down from {current_replicas} to {new_replicas} replicas"
                
            elif action == RemediationAction.RESTART:
                await self.k8s_client.restart(deployment, namespace)
                new_replicas = current_replicas
                message = f"Rolling restart initiated for {deployment}"
                
            elif action == RemediationAction.ROLLBACK:
                await self.k8s_client.rollback(deployment, namespace)
                new_replicas = current_replicas
                message = f"Rollback initiated for {deployment}"
                
            else:
                new_replicas = current_replicas
                message = "No action performed"
            
            status = RemediationStatus.SUCCESS
            self._remediations_performed += 1
            
        except Exception as e:
            logger.error(f"[{request_id}] Remediation failed: {e}")
            status = RemediationStatus.FAILED
            new_replicas = current_replicas
            message = f"Remediation failed: {str(e)}"
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return RemediateResponse(
            request_id=request_id,
            status=status,
            action_performed=action,
            previous_replicas=current_replicas,
            new_replicas=new_replicas,
            message=message,
            execution_time_ms=execution_time,
            timestamp=datetime.now()
        )
    
    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """Handle chatbot queries."""
        
        conversation_id = conversation_id or str(uuid.uuid4())
        
        # Get or create conversation history
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        
        history = self._conversations[conversation_id]
        
        # Build system context
        system_context = {
            "alerts_processed": self._alerts_processed,
            "remediations_performed": self._remediations_performed,
            "recent_alerts": [a.model_dump() for a in self._alert_history[-10:]],
            "configuration": {
                "monitoring": self.settings.monitoring_adapter,
                "ai_provider": self.settings.ai_provider,
                "thresholds": {
                    "auto": self.settings.confidence_auto_threshold,
                    "review": self.settings.confidence_review_threshold
                }
            },
            "user_context": context or {}
        }
        
        prompt = build_chat_prompt(message, history, system_context)
        
        ai_request = AIRequest(
            prompt=prompt,
            context=system_context,
            max_tokens=2048,
            temperature=0.7
        )
        
        ai_response = await self.ai_provider.analyze(ai_request)
        
        # Parse response
        import json
        try:
            response_data = json.loads(ai_response.content)
            response_text = response_data.get("response", ai_response.content)
            suggested_actions = response_data.get("suggested_actions", [])
            references = response_data.get("references", [])
        except json.JSONDecodeError:
            response_text = ai_response.content
            suggested_actions = []
            references = []
        
        # Update conversation history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response_text})
        
        # Keep history manageable
        if len(history) > 20:
            history = history[-20:]
        self._conversations[conversation_id] = history
        
        return ChatResponse(
            conversation_id=conversation_id,
            response=response_text,
            suggested_actions=suggested_actions,
            references=references,
            timestamp=datetime.now()
        )
    
    async def get_status(self) -> StatusResponse:
        """Get current system status."""
        
        ai_healthy = await self.ai_provider.health_check()
        monitoring_healthy = await self.monitoring_adapter.health_check()
        
        uptime = (datetime.now() - self._start_time).total_seconds()
        last_alert = self._alert_history[-1].timestamp if self._alert_history else None
        
        system = SystemStatus(
            status="healthy" if (ai_healthy and monitoring_healthy) else "degraded",
            uptime_seconds=uptime,
            last_alert_time=last_alert,
            total_alerts_processed=self._alerts_processed,
            total_remediations=self._remediations_performed,
            ai_provider=self.ai_provider.provider_name,
            ai_provider_healthy=ai_healthy,
            monitoring_adapter=self.monitoring_adapter.adapter_name,
            monitoring_adapter_healthy=monitoring_healthy
        )
        
        return StatusResponse(
            system=system,
            recent_alerts=self._alert_history[-20:],
            configuration={
                "environment": self.settings.environment,
                "client": self.settings.client_name,
                "auto_remediate": self.settings.auto_remediate_enabled,
                "confidence_auto_threshold": self.settings.confidence_auto_threshold,
                "confidence_review_threshold": self.settings.confidence_review_threshold,
                "scaling_min": self.settings.scaling_min_replicas,
                "scaling_max": self.settings.scaling_max_replicas
            }
        )
