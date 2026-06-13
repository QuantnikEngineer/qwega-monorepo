from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QUANTNIK Code Review Agent"
    environment: str = "development"
    log_level: str = "INFO"

    github_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GITHUB_TOKEN", "GITHUB_TOKEN"),
    )
    github_app_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GITHUB_APP_ID", "GITHUB_APP_ID"),
    )
    github_installation_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GITHUB_INSTALLATION_ID", "GITHUB_INSTALLATION_ID"),
    )
    github_private_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GITHUB_PRIVATE_KEY", "GITHUB_PRIVATE_KEY"),
        description=(
            "When environment is 'production', this holds the inline PEM contents. "
            "Otherwise it is treated as a filesystem path to a PEM file."
        ),
    )
    github_webhook_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GITHUB_WEBHOOK_SECRET", "GITHUB_WEBHOOK_SECRET"),
    )
    google_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_GOOGLE_API_KEY", "GOOGLE_API_KEY"),
    )
    jira_server_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_JIRA_SERVER_URL", "JIRA_SERVER_URL"),
    )
    jira_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_JIRA_USERNAME", "JIRA_USERNAME"),
    )
    jira_api_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_JIRA_API_TOKEN", "JIRA_API_TOKEN"),
    )

    harness_pat: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_HARNESS_PAT", "HARNESS_PAT"),
        description="Personal Access Token used for Harness Code REST API calls.",
    )
    harness_account_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_HARNESS_ACCOUNT_ID", "HARNESS_ACCOUNT_ID"),
        description="Harness account identifier (visible in the platform URL).",
    )
    harness_base_url: str = Field(
        default="https://app.harness.io",
        validation_alias=AliasChoices("CARA_HARNESS_BASE_URL", "HARNESS_BASE_URL"),
        description=(
            "Base URL for the Harness platform. Override for self-hosted Gitness "
            "or non-prod Harness instances."
        ),
    )
    harness_webhook_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CARA_HARNESS_WEBHOOK_SECRET", "HARNESS_WEBHOOK_SECRET"),
    )

    llm_model_fast: str = Field(
        default="gemini-fast-latest",
        validation_alias=AliasChoices(
            "CARA_LLM_MODEL_FAST",
            "LLM_MODEL_FAST",
            "CARA_GENAI_PROMPT_PARSER_MODEL",
            "GENAI_PROMPT_PARSER_MODEL",
        ),
    )
    llm_model_reasoning: str = Field(
        default="gemini-pro-latest",
        validation_alias=AliasChoices(
            "CARA_LLM_MODEL_REASONING",
            "LLM_MODEL_REASONING",
            "CARA_GENAI_REVIEW_MODEL",
            "GENAI_REVIEW_MODEL",
        ),
    )
    reports_base_path: Path = Field(
        default=Path("/tmp/reports"),
        validation_alias=AliasChoices("CARA_REPORTS_BASE_PATH", "REPORTS_BASE_PATH"),
    )
    max_context_files: int = Field(default=150, ge=1)
    max_context_file_bytes: int = Field(default=131_072, ge=1024)
    max_diff_characters: int = Field(default=80_000, ge=1000)
    repository_archive_timeout_seconds: int = Field(default=60, ge=5, le=300)
    upload_concurrency: int = Field(
        default=16,
        ge=1,
        le=64,
        validation_alias=AliasChoices("CARA_UPLOAD_CONCURRENCY", "UPLOAD_CONCURRENCY"),
        description=(
            "Number of parallel workers used when uploading context files to "
            "the Gemini Files API. Set to 1 for sequential uploads."
        ),
    )

    # Browsers cannot reach CARA without CORS preflight succeeding. The default
    # list covers the SPA dev server, the prod build served via nginx locally,
    # and the ngrok tunnel. Override per environment with
    # `CORS_ALLOW_ORIGINS="http://a,https://b"` (comma-separated) or the JSON
    # list form `["http://a","https://b"]`. Use ["*"] to disable origin checks.
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "https://flyover-barometer-overkill.ngrok-free.dev",
        ],
        validation_alias=AliasChoices("CARA_CORS_ALLOW_ORIGINS", "CORS_ALLOW_ORIGINS"),
        description="Origins allowed by browser CORS preflight.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # Accept either a JSON list ['http://a','http://b'] or a comma-separated
        # string 'http://a,http://b' from env. Anything else is passed through.
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                # Pydantic itself parses JSON list strings — leave as-is.
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def github_token_value(self) -> str | None:
        if self.github_token is None:
            return None
        return self.github_token.get_secret_value()

    @property
    def github_private_key_value(self) -> str | None:
        if self.github_private_key is None:
            return None

        raw_value = self.github_private_key.get_secret_value().strip()
        if not raw_value:
            return None

        # Production always carries the inline PEM contents.
        if self.environment.lower() == "production":
            return raw_value

        # Non-production: treat as a path. Allow inline PEM as a convenience
        # when the value clearly looks like one.
        if raw_value.lstrip().startswith("-----BEGIN"):
            return raw_value
        return Path(raw_value).expanduser().read_text(encoding="utf-8")

    @property
    def github_app_auth_configured(self) -> bool:
        return (
            self.github_app_id is not None
            and self.github_installation_id is not None
            and self.github_private_key_value is not None
        )

    @property
    def github_webhook_secret_value(self) -> str | None:
        if self.github_webhook_secret is None:
            return None
        return self.github_webhook_secret.get_secret_value()

    @property
    def google_api_key_value(self) -> str | None:
        if self.google_api_key is None:
            return None
        return self.google_api_key.get_secret_value()

    @property
    def jira_api_token_value(self) -> str | None:
        if self.jira_api_token is None:
            return None
        return self.jira_api_token.get_secret_value()

    @property
    def harness_pat_value(self) -> str | None:
        if self.harness_pat is None:
            return None
        return self.harness_pat.get_secret_value()

    @property
    def harness_webhook_secret_value(self) -> str | None:
        if self.harness_webhook_secret is None:
            return None
        return self.harness_webhook_secret.get_secret_value()

    @property
    def harness_configured(self) -> bool:
        return self.harness_pat_value is not None and bool(self.harness_account_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
