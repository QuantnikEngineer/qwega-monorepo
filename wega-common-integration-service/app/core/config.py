"""
Configuration Module
====================
Centralized configuration management using Pydantic Settings.
Supports profile-based URL construction for downstream services.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Dict, List
from functools import lru_cache


def get_profile_prefix(profile: str) -> str:
    """Get URL prefix based on profile."""
    if not profile or profile in ("prod", "production"):
        return ""
    return f"{profile}-"


class OrchestratorCapabilities:
    """Capabilities of this and sibling orchestrators for cross-referencing."""
    
    SELF = {
        "name": "common_integration",
        "description": "Handles context enrichment operations: upload, ingest, feedback, query",
        "intents": [
            "context_enrich_upload",
            "context_enrich_ingest",
            "context_enrich_feedback",
            "context_enrich_query"
        ],
        "keywords": [
            "upload", "ingest", "feedback", "query", "context", "enrich",
            "document", "file", "knowledge", "rag", "search", "correction",
            "domain preference", "rating", "website", "sharepoint", "repo"
        ]
    }
    
    SIBLING_PLANNING = {
        "name": "planning",
        "description": "Handles BRD creation, user story generation, and validation",
        "intents": [
            "create_brd",
            "create_user_story",
            "validate_user_story",
            "create_user_manual",
            "brd_summary"
        ],
        "keywords": [
            "brd", "business requirements", "user story", "stories", "epic",
            "validate", "validation", "requirements", "confluence", "jira"
        ]
    }
    
    SIBLING_TEST = {
        "name": "test",
        "description": "Handles test scenario, test script, and test data generation",
        "intents": [
            "generate_test_scenario",
            "generate_test_script",
            "generate_test_data"
        ],
        "keywords": [
            "test", "testing", "scenario", "test case", "test script",
            "automation", "selenium", "playwright", "qa"
        ]
    }


class Settings(BaseSettings):
    """Application Settings for Wega Common Integration Service"""
    
    # Application Info
    app_name: str = "Wega Common Integration Service"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", description="Environment: dev, qa, stage, prod")
    app_profile: str = Field(default="", description="Deployment profile for URL construction (dev, qa, stage, prod)")
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8084, description="Server port")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    # GCP Configuration (for dynamic URL construction)
    gcp_project_number: str = Field(default="204952354085", description="GCP project number for Cloud Run URLs")
    gcp_region: str = Field(default="us-central1", description="GCP region for Cloud Run URLs")
    
    # API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    google_api_key: Optional[str] = Field(default=None, description="Google AI API key")
    google_cloud_project: Optional[str] = Field(default=None, description="Google Cloud project ID")
    google_cloud_location: str = Field(default="global", description="Google Cloud location")
    
    # Redis Configuration (Memory Store)
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    # LLM Configuration
    llm_model: str = Field(default="gemini-2.0-flash", description="Default LLM model")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model for fallback")
    llm_temperature: float = Field(default=0.0, description="LLM temperature")
    llm_max_tokens: int = Field(default=4096, description="Max tokens for LLM response")
    
    # SSL Configuration (set to False for local development if certificate issues occur)
    ssl_verify: bool = Field(default=False, description="Verify SSL certificates")
    
    # RAG Agent URL (can be overridden via env var, otherwise computed from profile)
    rag_agent_url: Optional[str] = Field(
        default=None,
        description="RAG Agent URL (auto-computed from profile if not set)"
    )
    
    # Timeout Configuration (in seconds)
    agent_call_timeout: int = Field(
        default=600,
        description="Timeout for agent HTTP calls in seconds (default: 600 = 10 minutes)"
    )
    request_timeout: int = Field(
        default=600,
        description="General request timeout in seconds (default: 600 = 10 minutes)"
    )
    
    # SSE Streaming Configuration
    sse_heartbeat_interval: int = Field(
        default=10,
        description="Heartbeat interval in seconds for SSE streaming to keep connection alive during long RAG operations"
    )
    
    # Memory Configuration
    conversation_memory_limit: int = Field(default=20, description="Number of messages to keep")
    session_ttl_hours: int = Field(default=24, description="Session TTL in hours")
    
    # Sibling Orchestrator (for cross-referencing)
    planning_orchestrator_url: Optional[str] = Field(
        default=None,
        description="URL of the Planning Orchestrator (auto-computed from profile if not set)"
    )
    
    def get_rag_agent_url(self) -> str:
        """Get RAG Agent URL, computed from profile if not explicitly set."""
        if self.rag_agent_url:
            return self.rag_agent_url
        prefix = get_profile_prefix(self.app_profile)
        return f"https://{prefix}wega-rag-{self.gcp_project_number}.{self.gcp_region}.run.app"
    
    def get_planning_orchestrator_url(self) -> str:
        """Get Planning Orchestrator URL, computed from profile if not explicitly set."""
        if self.planning_orchestrator_url:
            return self.planning_orchestrator_url
        prefix = get_profile_prefix(self.app_profile)
        return f"https://{prefix}wega-planning-orchestrator-{self.gcp_project_number}.{self.gcp_region}.run.app"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
