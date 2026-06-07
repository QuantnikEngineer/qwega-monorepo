"""WEGA API Gateway bootstrap and route wiring."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from app.config import settings
from app.middleware.audit_logging import AuditLoggingMiddleware
from app.middleware.capability_check import CapabilityMiddleware
from app.middleware.header_injection import HeaderInjectionMiddleware
from app.middleware.jwt_validation import JWTValidationMiddleware
from app.middleware.rate_limiting import LoginRateLimitingMiddleware
from app.services.rate_limiter import LoginRateLimiter
from app.models import ErrorResponse
from app.routes.api import router as api_router
from app.routes.auth import router as auth_router
from app.routes.confluence import router as confluence_router
from app.routes.health import router as health_router
from app.routes.jira import router as jira_router
from app.routes.jwks import router as jwks_router
from app.utils.error_codes import INTERNAL_ERROR


def create_app() -> FastAPI:
    """Create configured FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Dedicated API gateway for WEGA backend enforcement.",
    )

    # Keep explicit route includes (T-03-02 mitigation).
    app.include_router(health_router)
    app.include_router(jwks_router)
    app.include_router(auth_router)
    app.include_router(api_router)
    app.include_router(jira_router)
    app.include_router(confluence_router)

    app.add_middleware(
        LoginRateLimitingMiddleware,
        rate_limiter=LoginRateLimiter(
            max_attempts=settings.login_rate_limit_max,
            window_seconds=settings.login_rate_limit_window,
        ),
    )
    app.add_middleware(AuditLoggingMiddleware)
    app.add_middleware(HeaderInjectionMiddleware)
    app.add_middleware(CapabilityMiddleware)
    app.add_middleware(JWTValidationMiddleware)

    # Register CORS last for LIFO middleware execution compatibility.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(req: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid4())
        logger.exception("Unhandled error [%s] %s %s", request_id, req.method, req.url.path)
        payload = ErrorResponse(
            code=INTERNAL_ERROR,
            message="Internal gateway error",
            request_id=request_id,
        )
        origin = req.headers.get("origin", "")
        allowed_origins = (
            ["*"] if settings.cors_origins == "*"
            else settings.cors_origins.split(",")
        )
        cors_origin = origin if (origin and ("*" in allowed_origins or origin in allowed_origins)) else ""
        headers = {}
        if cors_origin:
            headers["access-control-allow-origin"] = cors_origin
            headers["access-control-allow-credentials"] = "true"
        return JSONResponse(status_code=500, content=payload.model_dump(), headers=headers)

    return app


app = create_app()
