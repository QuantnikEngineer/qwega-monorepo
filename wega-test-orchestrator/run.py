"""
Wega Test Orchestrator - Entry Point
"""

import os

# Suppress gRPC SSL handshake errors locally (ssl_transport_security.cc messages)
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "")

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app",host=settings.host,port=settings.port,reload=settings.debug,log_level=settings.log_level.lower())
