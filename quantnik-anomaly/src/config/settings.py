"""
Configuration settings loaded from environment variables.
Customer-tunable parameters are exposed here while IP remains protected in core/.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # ==================== ADAPTER SELECTION ====================
    monitoring_adapter: Literal["datadog", "prometheus", "cloudwatch", "splunk", "dynatrace"] = Field(
        default="datadog",
        description="Monitoring tool adapter"
    )
    
    ai_provider: Literal["gemini", "bedrock", "vertex", "openai", "azure_openai"] = Field(
        default="gemini",
        description="AI provider for analysis"
    )
    
    orchestrator_adapter: Literal["harness", "jenkins", "argocd", "gitlab_ci", "tekton", "none"] = Field(
        default="harness",
        description="CI/CD orchestrator adapter"
    )
    
    # ==================== THRESHOLDS (Customer Tunable) ====================
    confidence_auto_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Auto-remediate if confidence >= this value"
    )
    
    confidence_review_threshold: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Human review if confidence between review and auto thresholds"
    )
    
    transient_cpu_threshold: int = Field(
        default=50,
        ge=0,
        le=100,
        description="CPU percentage below which issue is considered transient"
    )
    
    confirmation_wait_seconds: int = Field(
        default=300,
        ge=0,
        description="Seconds to wait before confirming sustained issue"
    )
    
    # ==================== SCALING LIMITS ====================
    scaling_min_replicas: int = Field(
        default=1,
        ge=1,
        description="Minimum pod replicas"
    )
    
    scaling_max_replicas: int = Field(
        default=10,
        ge=1,
        description="Maximum pod replicas"
    )
    
    scaling_cooldown_seconds: int = Field(
        default=300,
        ge=0,
        description="Cooldown period between scaling operations"
    )
    
    # ==================== BEHAVIOR ====================
    auto_remediate_enabled: bool = Field(
        default=True,
        description="Enable automatic remediation"
    )
    
    require_human_approval: bool = Field(
        default=False,
        description="Always require human approval before action"
    )
    
    notification_slack_webhook: Optional[str] = Field(
        default=None,
        description="Slack webhook URL for notifications"
    )
    
    notification_email: Optional[str] = Field(
        default=None,
        description="Email address for notifications"
    )
    
    # ==================== AI PROVIDER SETTINGS ====================
    ai_model: str = Field(
        default="gemini-2.5-flash",
        description="AI model name (provider-specific)"
    )
    
    ai_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="AI API call timeout in seconds"
    )
    
    ai_max_tokens: int = Field(
        default=8192,
        ge=100,
        description="Maximum tokens for AI response"
    )
    
    # ==================== SECRETS ====================
    ai_api_key: str = Field(
        default="",
        description="API key for AI provider"
    )
    
    monitoring_api_key: str = Field(
        default="",
        description="API key for monitoring tool"
    )
    
    monitoring_app_key: Optional[str] = Field(
        default=None,
        description="Application key for monitoring tool (e.g., Datadog)"
    )
    
    # ==================== KUBERNETES ====================
    k8s_namespace: str = Field(
        default="default",
        description="Kubernetes namespace for operations"
    )
    
    k8s_in_cluster: bool = Field(
        default=True,
        description="Running inside Kubernetes cluster"
    )
    
    # ==================== SERVER ====================
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # ==================== CLIENT INFO ====================
    client_name: str = Field(
        default="default",
        description="Client identifier for multi-tenant deployments"
    )
    
    environment: Literal["demo", "staging", "production"] = Field(
        default="demo",
        description="Deployment environment"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
