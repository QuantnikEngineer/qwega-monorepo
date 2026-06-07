from pathlib import Path
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # App
    APP_NAME:    str  = "SDLC Knowledge Base"
    APP_VERSION: str  = "1.0.0"
    APP_ENV:     str  = "development"
    DEBUG:       bool = False

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # PostgreSQL — critical DB
    POSTGRES_HOST:     str       = "localhost"
    POSTGRES_PORT:     int       = 5432
    POSTGRES_DB:       str       = "sdlc_kb"
    POSTGRES_USER:     str       = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")

    # PostgreSQL — non-critical DB
    POSTGRES_HOST_NC:         str = "localhost"
    POSTGRES_PORT_NC:         int = 5432
    POSTGRES_DB_NON_CRITICAL: str = "sdlc_kb_non_critical"

    # SSL mode for Postgres connections ("disable", "require", "verify-full", etc.)
    POSTGRES_SSLMODE: str = "require"

    @property
    def DATABASE_URL(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
            query={"sslmode": self.POSTGRES_SSLMODE, "connect_timeout": "30"},
        )

    @property
    def DATABASE_URL_NON_CRITICAL(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST_NC,
            port=self.POSTGRES_PORT_NC,
            database=self.POSTGRES_DB_NON_CRITICAL,
            query={"sslmode": self.POSTGRES_SSLMODE, "connect_timeout": "30"},
        )

    # Qdrant
    QDRANT_URL:                     str       = ""
    QDRANT_API_KEY:                 SecretStr = SecretStr("")
    QDRANT_COLLECTION:              str       = "sdlc_kb"
    QDRANT_COLLECTION_NON_CRITICAL: str       = "sdlc_kb_non_critical"
    QDRANT_VECTOR_SIZE:             int       = 768
    QDRANT_VERIFY_SSL:              bool      = True
    QDRANT_HNSW_EF:                 int       = 128

    # Vertex AI
    VERTEX_PROJECT_ID:              str = "digital-rig-poc"
    VERTEX_LOCATION:                str = "us-central1"
    VERTEX_EMBEDDING_MODEL:         str = "text-embedding-004"
    VERTEX_LLM_MODEL:               str = "gemini-1.5-pro"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Chunking
    CHUNK_SIZE:    int = 1024
    CHUNK_OVERLAP: int = 128

    # Retrieval
    TOP_K:                int   = 5
    SIMILARITY_THRESHOLD: float = 0.7

    # Classification
    CONFIDENCE_THRESHOLD: float = 0.75

    # Upload
    MAX_UPLOAD_MB:       int       = 50
    UPLOAD_DIR:          Path      = Path("uploads")
    ALLOWED_EXTENSIONS:  list[str] = [".pdf", ".docx", ".xlsx", ".json"]

    # Repository tokens
    GITHUB_TOKEN:  SecretStr = SecretStr("")
    HARNESS_TOKEN: SecretStr = SecretStr("")

    # Confluence
    CONFLUENCE_EMAIL: str       = ""
    CONFLUENCE_TOKEN: SecretStr = SecretStr("")

    # SharePoint / Microsoft 365
    SHAREPOINT_TOKEN:         SecretStr = SecretStr("")
    SHAREPOINT_TENANT_ID:     str       = ""
    SHAREPOINT_CLIENT_ID:     str       = ""
    SHAREPOINT_CLIENT_SECRET: SecretStr = SecretStr("")

    # Authentication
    AUTH_ENABLED:          bool      = False   # set True in production
    API_KEYS:              list[str] = []      # valid API keys (env: API_KEYS='["key1","key2"]')

    # Rate limiting (backend safety net — primary limiting is at Kong gateway)
    RATE_LIMIT_ENABLED:    bool = False        # enable as fallback if Kong is not in front
    RATE_LIMIT_PER_MINUTE: int  = 200          # high threshold; Kong handles fine-grained limits

    # Query timeout (seconds)
    QUERY_TIMEOUT: float = 120.0


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()