from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):

    # App
    APP_NAME:    str  = "SDLC Knowledge Base"
    APP_VERSION: str  = "1.0.0"
    APP_ENV:     str  = "development"
    DEBUG:       bool = False

    # PostgreSQL — critical DB
    POSTGRES_HOST:     str = "localhost"
    POSTGRES_PORT:     int = 5432
    POSTGRES_DB:       str = "sdlc_kb"
    POSTGRES_USER:     str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"

    # PostgreSQL — non-critical DB  (separate container; host port 5433 in docker-compose)
    # To migrate away from Postgres: remove engine_nc from db/session.py,
    # delete document_nc.py / chunk_nc.py, and update pipeline._write_non_critical.
    POSTGRES_HOST_NC:     str = "localhost"
    POSTGRES_PORT_NC:     int = 5432
    POSTGRES_DB_NON_CRITICAL: str = "sdlc_kb_non_critical"

    # SSL mode for Postgres connections ("disable", "require", "verify-full", etc.)
    POSTGRES_SSLMODE: str = "require"

    @property
    def DATABASE_URL(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
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
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST_NC,
            port=self.POSTGRES_PORT_NC,
            database=self.POSTGRES_DB_NON_CRITICAL,
            query={"sslmode": self.POSTGRES_SSLMODE, "connect_timeout": "30"},
        )

    # Qdrant
    QDRANT_URL:                     str = ""
    QDRANT_API_KEY:                 str = ""
    QDRANT_COLLECTION:              str = "sdlc_kb"           # critical
    QDRANT_COLLECTION_NON_CRITICAL: str = "sdlc_kb_non_critical"
    QDRANT_VECTOR_SIZE:             int = 768
    QDRANT_VERIFY_SSL:              bool = True   # set False in dev when cert chain is untrusted

    # Vertex AI
    VERTEX_PROJECT_ID:      str = "digital-rig-poc"
    VERTEX_LOCATION:        str = "us-central1"
    VERTEX_EMBEDDING_MODEL: str = "text-embedding-004"
    VERTEX_LLM_MODEL:       str = "gemini-1.5-pro"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Chunking
    CHUNK_SIZE:    int = 512
    CHUNK_OVERLAP: int = 64

    # Retrieval
    TOP_K:                int   = 5
    SIMILARITY_THRESHOLD: float = 0.7

    # Classification
    CONFIDENCE_THRESHOLD: float = 0.75

    # Upload
    MAX_UPLOAD_MB:       int      = 50
    UPLOAD_DIR:          Path     = Path("uploads")
    NON_CRITICAL_DIR:    Path     = Path("uploads/non_critical")
    ALLOWED_EXTENSIONS:  list[str] = [".pdf", ".docx", ".xlsx", ".json"]

    # Repository tokens (used as defaults when not passed in the request)
    GITHUB_TOKEN:  str = ""
    HARNESS_TOKEN: str = ""

    # Confluence
    CONFLUENCE_EMAIL: str = ""
    CONFLUENCE_TOKEN: str = ""

    # SharePoint / Microsoft 365
    # Legacy: a pre-obtained bearer token (used by the HTML-scraping fallback)
    SHAREPOINT_TOKEN: str = ""
    # Graph API credentials (Azure AD app registration with Sites.Read.All + Files.Read.All)
    SHAREPOINT_TENANT_ID:     str = ""
    SHAREPOINT_CLIENT_ID:     str = ""
    SHAREPOINT_CLIENT_SECRET: str = ""

    class Config:
        env_file      = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()