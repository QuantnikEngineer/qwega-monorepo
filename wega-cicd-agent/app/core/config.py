from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"

# Load the full .env into os.environ so Google auth variables like
# GOOGLE_APPLICATION_CREDENTIALS are visible to the SDK as well.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Wega CI Agent"
    app_version: str = "1.0.0"
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8092)
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    default_render_mode: Literal["template", "llm", "hybrid"] = Field(default="template")
    google_api_key: str | None = Field(default=None)
    google_cloud_project: str | None = Field(default=None)
    google_cloud_location: str = Field(default="global")
    llm_model: str = Field(
        default="gemini-3-flash-preview",
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL"),
    )
    llm_temperature: float = Field(default=0.0)
    llm_max_tokens: int = Field(default=4000)
    llm_thinking_budget: int = Field(default=0)
    llm_timeout_seconds: float = Field(default=60.0)
    ssl_verify: bool = Field(default=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()