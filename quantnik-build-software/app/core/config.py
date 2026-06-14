"""
Configuration — Build Software Orchestrator
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Quantnik Build-Software Orchestrator"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8083)
    log_level: str = Field(default="INFO")

    # GCP / Cloud Run
    gcp_project_number: str = Field(default="204952354085")
    gcp_region: str = Field(default="us-central1")
    app_profile: str = Field(default="")

    # LLM
    google_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    llm_model: str = Field(default="gemini-2.0-flash")
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=8192)

    # SSL
    ssl_verify: bool = Field(default=True)

    # Child orchestrator URLs — override in .env or auto-built from profile
    planning_orchestrator_url: Optional[str] = Field(default=None)
    test_orchestrator_url: Optional[str] = Field(default=None)

    # Atlassian — Jira + Confluence direct REST API
    atlassian_email: Optional[str] = Field(default=None, alias="MCP_ATLASSIAN_EMAIL")
    atlassian_token: Optional[str] = Field(default=None, alias="MCP_ATLASSIAN_TOKEN")
    atlassian_url: str = Field(default="https://engquant.atlassian.net", alias="MCP_ATLASSIAN_URL")

    # GitHub integration
    github_token: Optional[str] = Field(default=None)
    github_org: str = Field(default="QuantnikEngineer")

    # Deployment (Vercel)
    vercel_token: Optional[str] = Field(default=None)

    def _prefix(self) -> str:
        return f"{self.app_profile}-" if self.app_profile and self.app_profile not in ("prod", "production") else ""

    def get_planning_url(self) -> str:
        if self.planning_orchestrator_url:
            return self.planning_orchestrator_url
        return f"https://{self._prefix()}quantnik-planning-orchestrator-{self.gcp_project_number}.{self.gcp_region}.run.app"

    def get_test_url(self) -> str:
        if self.test_orchestrator_url:
            return self.test_orchestrator_url
        return f"https://{self._prefix()}quantnik-test-orchestrator-{self.gcp_project_number}.{self.gcp_region}.run.app"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
