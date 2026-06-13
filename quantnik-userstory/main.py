import os
import logging
import io
import sys
import uuid
import contextvars
from logging.handlers import RotatingFileHandler
from typing import TextIO

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routes.brownfield import router as brownfield_router
from routes.health import router as health_router
from routes.jira import router as jira_router
from routes.user_stories import router as user_stories_router

# Correlation ID propagated through all log records of a single request.
_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class _RequestIdFilter(logging.Filter):
    """Inject the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = _REQUEST_ID.get()
        return True


def _build_safe_log_stream(stream: TextIO | None = None) -> TextIO:
    """Return a console stream that won't crash on non-ASCII log messages."""

    target_stream = stream or sys.stderr
    reconfigure = getattr(target_stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            target_stream.reconfigure(errors="backslashreplace")
            return target_stream
        except Exception:
            pass

    buffer = getattr(target_stream, "buffer", None)
    if buffer is not None:
        try:
            return io.TextIOWrapper(
                buffer,
                encoding=getattr(target_stream, "encoding", None) or "utf-8",
                errors="backslashreplace",
                line_buffering=True,
            )
        except Exception:
            pass

    return target_stream


# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(request_id)s] %(name)s %(levelname)s %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, "app.log"),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        ),
        logging.StreamHandler(_build_safe_log_stream())
    ]
)

# Attach the request-id filter to every existing handler so the format string
# above always has a value to substitute (avoids KeyError on background logs).
for _handler in logging.getLogger().handlers:
    _handler.addFilter(_RequestIdFilter())

logger = logging.getLogger(__name__)
logger.info("Application starting up...")


app = FastAPI(
    title="User Story Agent API",
    description="Provide a BRD Confluence URL and generate Epics & User Stories.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    """Honor inbound X-Request-ID or mint a new UUID, then echo it back.

    Logged automatically through the request_id LogRecord field.  Critical
    for tracing requests when the orchestrator forwards calls to this agent.
    """
    incoming = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = _REQUEST_ID.set(incoming)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = incoming
        return response
    finally:
        _REQUEST_ID.reset(token)


app.include_router(user_stories_router)
app.include_router(jira_router)
app.include_router(brownfield_router)
app.include_router(health_router)
