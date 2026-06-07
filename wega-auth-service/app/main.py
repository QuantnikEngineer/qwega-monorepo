"""
Wega Auth Service - Main Application
=====================================
Authentication and authorization service for the WEGA platform.
Phase 1: Health endpoint only (scaffolding).
Phase 2: Login, JWT lifecycle, password management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.jwks import router as jwks_router
from app.api.projects import router as projects_router
from app.api.roles import router as roles_router
from app.api.agents import router as agents_router
from app.api.services import router as services_router
from app.api.users import router as users_router
from app.auth.jwt_manager import JWTManager
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.database import close_db, init_db

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Auth Service", version=settings.app_version, environment=settings.app_env)
    await init_db()
    app.state.jwt_manager = JWTManager()
    logger.info("Auth Service ready", kid=app.state.jwt_manager.kid)
    yield
    await close_db()
    logger.info("Auth Service shutdown complete")


app = FastAPI(
    title="Wega Auth Service",
    description="Authentication and authorization service for WEGA platform",
    version=settings.app_version,
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(jwks_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(roles_router)
app.include_router(services_router)
app.include_router(agents_router)


def get_jwt_manager(request: Request) -> JWTManager:
    """Dependency helper to access JWT manager from app state."""
    return request.app.state.jwt_manager


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Service info endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
