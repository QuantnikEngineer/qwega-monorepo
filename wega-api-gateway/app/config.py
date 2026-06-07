"""Gateway configuration settings."""

from functools import lru_cache
from typing import FrozenSet, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the API gateway."""

    app_name: str = "Wega API Gateway"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    auth_service_url: str = Field(default="http://localhost:8090")
    orchestrator_url: str = Field(default="http://localhost:8081")
    integration_service_url: str = Field(default="http://localhost:8084")
    rag_service_url: str = Field(default="http://localhost:8085")
    planning_orchestrator_url: str = Field(default="http://localhost:8082")
    testcase_agent_url: str = Field(default="")
    testcase_poll_url: str = Field(default="")
    gcp_project_number: str = Field(default="")
    gcp_region: str = Field(default="us-central1")
    gcp_profile_prefix: str = Field(default="dev-")
    cors_origins: str = Field(default="*")
    jwt_issuer: str = Field(default="wega-auth")
    jwt_audience: str = Field(default="wega-api")
    jwks_cache_ttl_seconds: int = Field(default=300)
    sse_heartbeat_seconds: int = Field(default=15)
    sse_reconnect_ms: int = Field(default=3000)

    # Internal API key for auth-service internal endpoints
    internal_api_key: str = Field(
        default="wega-internal-dev-key",
        description="Shared key for internal service-to-service calls",
    )
    # Cache TTL for project settings resolution (seconds)
    settings_cache_ttl: int = Field(default=30)

    # Login rate limiting
    login_rate_limit_max: int = Field(default=15, description="Max login attempts per IP per window")
    login_rate_limit_window: int = Field(default=60, description="Login rate limit window in seconds")

    # D-06 public contract (method, path)
    public_route_allowlist: FrozenSet[Tuple[str, str]] = frozenset(
        {
            ("GET", "/health"),
            ("POST", "/auth/login"),
            ("POST", "/auth/refresh"),
            ("GET", "/auth/jwks"),
            ("POST", "/auth/activate"),
            ("GET", "/auth/activate"),
            ("POST", "/auth/register"),
            ("GET", "/auth/registration-defaults"),
        }
    )

    # D-21: Route-to-capability mapping for gateway enforcement.
    # Format: (method, path_prefix) -> required_capability string.
    # None value = no specific capability required (auth-only enforcement).
    # Routes not in this map pass through with no capability check.
    route_capability_map: dict = {
        # User management — backend enforces PM vs SA scoping (Phase 5)
        ("GET", "/api/users"): None,
        ("POST", "/api/users"): None,
        ("PUT", "/api/users/"): None,
        ("DELETE", "/api/users/"): None,
        ("POST", "/api/users/*/resend-activation"): None,
        ("POST", "/api/users/*/reset-password"): None,
        # Roles and agents — any authenticated user
        ("GET", "/api/roles"): None,
        ("GET", "/api/roles/agents"): None,   # Phase 5 agent mapping
        ("GET", "/api/capabilities"): None,
        # Projects — CRUD and membership (backend enforces authorization)
        ("GET", "/api/projects"): None,
        ("POST", "/api/projects"): None,
        ("GET", "/api/projects/"): None,
        ("PUT", "/api/projects/"): None,
        ("DELETE", "/api/projects/"): None,
        ("GET", "/api/projects/*/members"): None,
        ("POST", "/api/projects/*/members"): None,
        ("DELETE", "/api/projects/*/members/"): None,
        ("GET", "/api/projects/*/settings"): None,
        ("PUT", "/api/projects/*/settings/"): None,
        # Service registry — any authenticated user can read, backend enforces write
        ("GET", "/api/services"): None,
        ("POST", "/api/services"): None,
        ("PUT", "/api/services/"): None,
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def model_post_init(self, __context):
        """Auto-compute upstream service URLs from GCP profile prefix + project number.

        Mirrors the pattern in deploy.sh:
          ORCHESTRATOR_URL = https://{prefix}wega-sdlc-orchestrator-{number}.{region}.run.app
          PLANNING_URL     = https://{prefix}wega-planning-orchestrator-{number}.{region}.run.app
          TESTCASE_URL     = https://{prefix}wega-userstory-to-testcases-agent-{number}.{region}.run.app

        NOTE: Only auto-computes when app_env != 'development'. In development
        mode (local dev), the explicit URLs in .env are always respected. This
        prevents the common mistake of GCP_PROJECT_NUMBER silently overriding
        localhost URLs to remote Cloud Run services.
        """
        prefix = self.gcp_profile_prefix
        number = self.gcp_project_number
        region = self.gcp_region

        if number and prefix and self.app_env != "development":
            base_domain = f"{number}.{region}.run.app"

            if self.orchestrator_url == "http://localhost:8081":
                url = f"https://{prefix}wega-sdlc-orchestrator-{base_domain}"
                object.__setattr__(self, "orchestrator_url", url)

            if self.planning_orchestrator_url == "http://localhost:8082":
                url = f"https://{prefix}wega-planning-orchestrator-{base_domain}"
                object.__setattr__(self, "planning_orchestrator_url", url)

            if self.rag_service_url == "http://localhost:8085":
                url = f"https://{prefix}wega-rag-{base_domain}"
                object.__setattr__(self, "rag_service_url", url)

            if not self.testcase_agent_url:
                url = f"https://{prefix}wega-userstory-to-testcases-agent-{base_domain}"
                object.__setattr__(self, "testcase_agent_url", url)
            if not self.testcase_poll_url:
                url = f"https://{prefix}wega-userstory-to-testcases-agent-{base_domain}"
                object.__setattr__(self, "testcase_poll_url", url)

        if not self.testcase_agent_url:
            object.__setattr__(self, "testcase_agent_url", "http://localhost:8083")
        if not self.testcase_poll_url:
            object.__setattr__(self, "testcase_poll_url", "http://localhost:8083")


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
