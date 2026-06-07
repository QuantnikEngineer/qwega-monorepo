"""
WEGA Anomaly Agent - Main Application Entry Point

AI-powered anomaly detection and auto-remediation engine for Kubernetes.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from src.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    settings = get_settings()
    
    app = FastAPI(
        title="WEGA Anomaly Agent",
        description="AI-powered anomaly detection and auto-remediation for Kubernetes",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(router)
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize on startup."""
        import logging
        logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
        logger = logging.getLogger("anomaly-agent")
        logger.info(f"Starting WEGA Anomaly Agent v1.0.0")
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"AI Provider: {settings.ai_provider}")
        logger.info(f"Monitoring Adapter: {settings.monitoring_adapter}")
        logger.info(f"Auto-remediate: {settings.auto_remediate_enabled}")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        import logging
        logger = logging.getLogger("anomaly-agent")
        logger.info("Shutting down WEGA Anomaly Agent")
    
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
