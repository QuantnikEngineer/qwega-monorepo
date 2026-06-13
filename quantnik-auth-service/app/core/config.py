"""
Configuration Module
====================
Centralized configuration for Quantnik Auth Service.
Uses pydantic-settings to load from .env files.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application Settings for Quantnik Auth Service."""

    # Application Info
    app_name: str = "Quantnik Auth Service"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=True)

    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8090)

    # Logging
    log_level: str = Field(default="INFO")

    # Database — always PostgreSQL (localhost for dev, AWS RDS for Cloud Run)
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/quantnik_auth",
        description="Database connection URL (PostgreSQL)"
    )
    database_echo: bool = Field(default=False, description="SQLAlchemy echo SQL statements")

    # JWT Configuration (Phase 2 implementation)
    jwt_private_key_path: str = Field(
        default="",
        description="Path to RS256 private key PEM file"
    )
    jwt_public_key_path: str = Field(
        default="",
        description="Path to RS256 public key PEM file"
    )
    jwt_issuer: str = Field(default="quantnik-auth")
    jwt_audience: str = Field(default="quantnik-api")
    jwt_access_token_expire_minutes: int = Field(default=15)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # Argon2 Password Hashing (Phase 2 implementation — OWASP 2025 params)
    argon2_time_cost: int = Field(default=3, description="Argon2id iterations")
    argon2_memory_cost: int = Field(default=65536, description="Argon2id memory in KiB (64 MB)")
    argon2_parallelism: int = Field(default=1, description="Argon2id parallel threads")
    argon2_hash_len: int = Field(default=32, description="Argon2id hash output length")
    argon2_salt_len: int = Field(default=16, description="Argon2id salt length")

    # Cookie configuration
    cookie_secure: bool = Field(default=False, description="Set Secure flag on cookies (True in prod)")
    cookie_samesite: str = Field(default="strict", description="SameSite cookie policy")
    cookie_path: str = Field(default="/auth", description="Cookie path scope (matches gateway-facing URL)")

    # CORS
    cors_origins: str = Field(
        default="*",
        description="Comma-separated allowed origins (tighten in Phase 3)"
    )

    # Trusted proxy headers (Phase 2 security hardening)
    trusted_proxy_ips: str = Field(
        default="127.0.0.1",
        description="Comma-separated proxy source IPs allowed to supply X-User-* headers",
    )

    # Frontend URL (for activation link generation)
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend base URL for activation links",
    )

    # GCP Cloud Run context (for auto-computing URLs)
    gcp_project_number: str = Field(default="")
    gcp_region: str = Field(default="us-central1")
    gcp_profile_prefix: str = Field(default="", description="Cloud Run profile prefix (dev-, qa-, stage-, prod-)")

    # Account lockout controls (Phase 3 ENFC-06)
    lockout_threshold: int = Field(default=15, description="Failed logins before account lockout")
    lockout_window_minutes: int = Field(default=5, description="Lockout duration in minutes")
    lockout_backoff_base_seconds: int = Field(default=1, description="Base retry delay for exponential backoff")
    lockout_backoff_max_seconds: int = Field(default=10, description="Maximum retry delay in seconds")

    # Registration rate limiting
    registration_rate_limit_max: int = Field(default=30, description="Max registrations per IP per window")
    registration_rate_limit_window: int = Field(default=3600, description="Rate limit window in seconds")

    # Internal API key for gateway-to-auth-service communication
    internal_api_key: str = Field(
        default="quantnik-internal-dev-key",
        description="Shared key for internal service-to-service calls (set in prod)",
    )

    # Fernet encryption key for project secrets (PAT tokens, API keys)
    quantnik_secret_key: Optional[str] = Field(
        default=None,
        description="Base64 Fernet key for encrypting project secrets. Auto-generated if not set.",
    )

    # Registration defaults (direct-to-project registration)
    registration_default_project_slug: str = Field(
        default="",
        description="Default project slug for self-registration. Empty = PM-mode registration.",
    )
    registration_default_role: str = Field(
        default="po_sm_ba",
        description="Role assigned to users who self-register via project mode.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def model_post_init(self, __context):
        """Auto-correct frontend_url on Cloud Run if it uses the wrong service name."""
        if self.gcp_project_number and "quantnik-frontend" in self.frontend_url:
            prefix = self.gcp_profile_prefix or "dev-"
            corrected = f"https://{prefix}quantnik-sdlc-{self.gcp_project_number}.{self.gcp_region}.run.app"
            object.__setattr__(self, "frontend_url", corrected)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
