from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cara.core.config import get_settings
from cara.core.errors import register_exception_handlers
from cara.core.logging import configure_logging
from cara.routers import harness_webhook, prompt, reports, webhook


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Stateless FastAPI backend for automated AI pull request reviews.",
    )

    # CORS: required so browser preflight OPTIONS requests against /prompt and
    # /reports succeed. Without this, FastAPI replies 405 to OPTIONS because
    # only POST/GET are registered on the routes.
    cors_origins = settings.cors_allow_origins or []
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=None,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Accept",
            "Authorization",
            "ngrok-skip-browser-warning",
        ],
        max_age=600,
    )

    register_exception_handlers(application)
    application.include_router(webhook.router)
    application.include_router(harness_webhook.router)
    application.include_router(prompt.router)
    application.include_router(reports.router)
    return application


app = create_app()
