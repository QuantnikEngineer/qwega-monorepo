"""
Configuration Module
====================
Centralized configuration for SDLC Orchestrator.
Supports profile-based URL construction for child orchestrators.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, computed_field
from typing import Optional, Dict, List
from functools import lru_cache


def get_profile_prefix(profile: str) -> str:
    """Get URL prefix based on profile."""
    if not profile or profile in ("prod", "production"):
        return ""
    return f"{profile}-"


class OrchestratorCapabilities:
    """Defines capabilities of each child orchestrator."""
    
    PLANNING_ORCHESTRATOR = {
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
            "validate", "validation", "requirements", "confluence", "jira",
            "user manual", "documentation", "summary", "summarize"
        ]
    }
    
    TEST_ORCHESTRATOR = {
        "name": "test",
        "description": "Handles test cases, test script, and test data generation",
        "intents": [
            "generate_test_cases",
            "generate_test_script",
            "generate_test_data"
        ],
        "keywords": [
            "test", "testing", "scenario", "test case", "test script",
            "automation", "selenium", "playwright", "qa", "quality",
            "script", "automated test", "test framework",
            "test data", "testdata", "data generation", "test data generator"
        ]
    }
    
    COMMON_INTEGRATION_ORCHESTRATOR = {
        "name": "common_integration",
        "description": "Handles context enrichment operations: upload, ingest, feedback, query, list documents",
        "intents": [
            "context_enrich_upload",
            "context_enrich_ingest",
            "context_enrich_feedback",
            "context_enrich_query",
            "context_enrich_list_documents"
        ],
        "keywords": [
            "upload", "ingest", "feedback", "query", "context", "enrich",
            "document", "file", "knowledge", "rag", "search", "correction",
            "domain preference", "rating", "website", "sharepoint", "repo",
            "knowledge base", "index", "get the document", "fetch document",
            "list document", "show document", "retrieve document"
        ]
    }


class Settings(BaseSettings):
    """Application Settings for SDLC Orchestrator"""
    
    # Application Info
    app_name: str = "Quantnik SDLC Orchestrator"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", description="Environment: dev, qa, stage, prod")
    app_profile: str = Field(default="", description="Deployment profile for URL construction (dev, qa, stage, prod)")
    debug: bool = Field(default=True)
    
    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8081)
    
    # Logging
    log_level: str = Field(default="INFO")
    
    # GCP Configuration (for dynamic URL construction)
    gcp_project_number: str = Field(default="204952354085", description="GCP project number for Cloud Run URLs")
    gcp_region: str = Field(default="us-central1", description="GCP region for Cloud Run URLs")
    
    # API Keys
    openai_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    google_cloud_project: Optional[str] = Field(default=None)
    google_cloud_location: str = Field(default="global")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379")
    redis_password: Optional[str] = Field(default=None)
    
    # LLM Configuration
    llm_model: str = Field(default="gemini-2.0-flash")
    openai_model: str = Field(default="gpt-4-turbo-preview")
    llm_temperature: float = Field(default=0.0)
    llm_max_tokens: int = Field(default=4096)
    
    # SSL Configuration
    ssl_verify: bool = Field(default=True)
    
    # Child Orchestrator URLs (can be overridden via env vars, otherwise computed from profile)
    planning_orchestrator_url: Optional[str] = Field(
        default=None,
        description="URL of the Planning Orchestrator (auto-computed from profile if not set)"
    )
    test_orchestrator_url: Optional[str] = Field(
        default=None,
        description="URL of the Test Orchestrator (auto-computed from profile if not set)"
    )
    common_integration_orchestrator_url: Optional[str] = Field(
        default=None,
        description="URL of the Common Integration Orchestrator (auto-computed from profile if not set)"
    )
    
    # Memory Configuration
    conversation_memory_limit: int = Field(default=20)
    session_ttl_hours: int = Field(default=24)
    
    def get_planning_orchestrator_url(self) -> str:
        """Get Planning Orchestrator URL, computed from profile if not explicitly set."""
        if self.planning_orchestrator_url:
            return self.planning_orchestrator_url
        prefix = get_profile_prefix(self.app_profile)
        return f"https://{prefix}quantnik-planning-orchestrator-{self.gcp_project_number}.{self.gcp_region}.run.app"
    
    def get_test_orchestrator_url(self) -> str:
        """Get Test Orchestrator URL, computed from profile if not explicitly set."""
        if self.test_orchestrator_url:
            return self.test_orchestrator_url
        prefix = get_profile_prefix(self.app_profile)
        return f"https://{prefix}quantnik-test-orchestrator-{self.gcp_project_number}.{self.gcp_region}.run.app"
    
    def get_common_integration_orchestrator_url(self) -> str:
        """Get Common Integration Orchestrator URL, computed from profile if not explicitly set."""
        if self.common_integration_orchestrator_url:
            return self.common_integration_orchestrator_url
        prefix = get_profile_prefix(self.app_profile)
        #return f"http://localhost:8084"
        return f"https://{prefix}quantnik-common-integration-service-{self.gcp_project_number}.{self.gcp_region}.run.app"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
