import sys

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.core.exceptions import SDLCKBException
from app.api.v1 import upload, documents, query, ingest, feedback, context
from app.db.session import engine
from app.db.base import Base, BaseNonCritical
from app.db.session import engine_nc
from app.retrieval.qdrant_store import QdrantStore
from app.db.session import ensure_databases
import app.models.feedback  # noqa: F401 — registers Feedback table with SQLAlchemy metadata

configure_logging()

app = FastAPI(
    title   = settings.APP_NAME,
    version = settings.APP_VERSION,
    docs_url= "/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["*"],
    allow_headers = ["*"],
)


@app.exception_handler(SDLCKBException)
async def sdlc_exception_handler(request: Request, exc: SDLCKBException):
    return JSONResponse(
        status_code=422,
        content={"error_code": exc.code, "message": exc.message},
    )


@app.on_event("startup")
async def startup():
    import asyncio

    # Retry DB connections — Cloud Run may need time to establish network path
    db_ready = False
    for attempt in range(1, 6):
        try:
            await ensure_databases()
            db_ready = True
            break
        except Exception as e:
            logger.warning("db_connect_retry", attempt=attempt, error=str(e))
            if attempt == 5:
                logger.error("db_connect_failed", error=str(e))
            else:
                await asyncio.sleep(2 ** attempt)

    if db_ready:
        try:
            # Critical DB (sdlc_kb) — documents, chunks, feedback
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Non-Critical DB (sdlc_kb_non_critical) — documents, chunks only
            async with engine_nc.begin() as conn:
                await conn.run_sync(BaseNonCritical.metadata.create_all)
        except Exception as e:
            logger.error("db_table_creation_failed", error=str(e))
    else:
        logger.warning("skipping_table_creation_db_not_ready")

    # Ensure both Qdrant collections exist
    try:
        QdrantStore().ensure_collection()
    except Exception as e:
        logger.error("qdrant_init_failed", error=str(e))

    logger.info("app_started", env=settings.APP_ENV)


app.include_router(upload.router,       prefix="/api/v1", tags=["Ingestion"])
app.include_router(ingest.router,       prefix="/api/v1", tags=["Ingestion"])
app.include_router(feedback.router,     prefix="/api/v1", tags=["Feedback"])
app.include_router(documents.router,    prefix="/api/v1", tags=["Documents"])
app.include_router(query.router,        prefix="/api/v1", tags=["Query"])
app.include_router(context.router,      prefix="/api/v1", tags=["Context"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/debug/config", tags=["Debug"])
async def debug_config():
    """Temporary endpoint to verify env vars and DB connectivity in Cloud Run."""
    import socket
    result = {
        "POSTGRES_HOST": settings.POSTGRES_HOST,
        "POSTGRES_PORT": settings.POSTGRES_PORT,
        "POSTGRES_DB": settings.POSTGRES_DB,
        "POSTGRES_SSLMODE": settings.POSTGRES_SSLMODE,
        "QDRANT_URL": settings.QDRANT_URL[:40] + "..." if settings.QDRANT_URL else "",
        "APP_ENV": settings.APP_ENV,
    }
    # Test raw TCP connectivity to Postgres
    try:
        sock = socket.create_connection(
            (settings.POSTGRES_HOST, settings.POSTGRES_PORT), timeout=10
        )
        sock.close()
        result["pg_tcp"] = "reachable"
    except Exception as e:
        result["pg_tcp"] = f"FAILED: {e}"
    # Test DNS resolution
    try:
        ip = socket.getaddrinfo(settings.POSTGRES_HOST, settings.POSTGRES_PORT)[0][4][0]
        result["pg_resolved_ip"] = ip
    except Exception as e:
        result["pg_resolved_ip"] = f"FAILED: {e}"
    return result