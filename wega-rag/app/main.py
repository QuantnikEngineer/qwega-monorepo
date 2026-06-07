import asyncio
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.core.exceptions import (
    SDLCKBException,
    DocumentNotFoundError,
    GuardrailViolationError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.core.middleware import AuthMiddleware, RateLimitMiddleware
from app.core.resilience import CircuitOpenError
from app.api.v1 import upload, documents, query, ingest, feedback, context
from app.api.v1 import knowledge_graph
from app.db.session import engine, engine_nc, ensure_databases
from app.db.base import Base, BaseNonCritical
from app.retrieval.qdrant_store import QdrantStore

configure_logging()

_EXCEPTION_STATUS_MAP: dict[type, int] = {
    DocumentNotFoundError:    404,
    GuardrailViolationError:  422,
    FileTooLargeError:        413,
    UnsupportedFileTypeError: 415,
}


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────
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

    if not db_ready:
        logger.warning("db_not_ready_at_startup")

    if db_ready:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with engine_nc.begin() as conn:
                await conn.run_sync(BaseNonCritical.metadata.create_all)
            logger.info("db_tables_created")
        except Exception as e:
            logger.error("db_create_tables_failed", error=str(e))

    try:
        store = QdrantStore()
        await store.ensure_collection()
        await store.ensure_entity_collection()
    except Exception as e:
        logger.error("qdrant_init_failed", error=str(e))

    logger.info("app_started", env=settings.APP_ENV)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    await engine.dispose()
    await engine_nc.dispose()
    logger.info("app_shutdown")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)


@app.exception_handler(SDLCKBException)
async def sdlc_exception_handler(request: Request, exc: SDLCKBException):
    status_code = _EXCEPTION_STATUS_MAP.get(type(exc), 422)
    return JSONResponse(
        status_code=status_code,
        content={"error_code": exc.code, "message": exc.message},
    )


@app.exception_handler(CircuitOpenError)
async def circuit_open_handler(request: Request, exc: CircuitOpenError):
    return JSONResponse(
        status_code=503,
        content={"error_code": "SERVICE_UNAVAILABLE", "message": str(exc)},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(upload.router,    prefix="/api/v1", tags=["Ingestion"])
app.include_router(ingest.router,    prefix="/api/v1", tags=["Ingestion"])
app.include_router(feedback.router,  prefix="/api/v1", tags=["Feedback"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(query.router,     prefix="/api/v1", tags=["Query"])
app.include_router(context.router,   prefix="/api/v1", tags=["Context"])
app.include_router(knowledge_graph.router, prefix="/api/v1", tags=["Knowledge Graph"])


@app.get("/health", tags=["Health"])
async def health():
    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal, AsyncSessionLocalNonCritical

    checks = {"app": "ok"}

    # Postgres critical DB
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres_critical"] = "ok"
    except Exception as e:
        checks["postgres_critical"] = f"error: {str(e)[:100]}"

    # Postgres non-critical DB
    try:
        async with AsyncSessionLocalNonCritical() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres_non_critical"] = "ok"
    except Exception as e:
        checks["postgres_non_critical"] = f"error: {str(e)[:100]}"

    # Qdrant
    try:
        store = QdrantStore()
        await store._client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {str(e)[:100]}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "checks": checks,
        },
    )