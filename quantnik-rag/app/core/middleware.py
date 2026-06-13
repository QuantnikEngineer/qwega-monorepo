"""
API authentication and rate limiting middleware.

Supports two auth modes:
  1. API key (header: X-API-Key) — simple, for service-to-service calls
  2. Bearer token (header: Authorization: Bearer <token>) — for user sessions

Rate limiting is per-client (IP or API key), in-memory with sliding window.
Replace with Redis-backed limiter when Redis is available.
"""
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger


# ── API Key Auth ──────────────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Paths that don't require auth
_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Simple API key authentication middleware.

    Checks X-API-Key header against configured keys.
    Skipped for health/docs endpoints and when AUTH_ENABLED=false.
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        bearer = request.headers.get("Authorization", "")

        if api_key and api_key in settings.API_KEYS:
            request.state.client_id = f"key:{api_key[:8]}"
            return await call_next(request)

        if bearer.startswith("Bearer ") and bearer[7:] in settings.API_KEYS:
            request.state.client_id = f"bearer:{bearer[7:15]}"
            return await call_next(request)

        logger.warning("auth_rejected", path=path)
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})


# ── Rate Limiter ──────────────────────────────────────────────────────────────

class _SlidingWindowCounter:
    """In-memory sliding window rate limiter. Replace with Redis when available."""

    _GC_INTERVAL = 300  # garbage-collect stale keys every 5 minutes

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._last_gc: float = time.monotonic()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        # Prune old entries for this key
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]
        if len(self._windows[key]) >= max_requests:
            return False
        self._windows[key].append(now)
        # Periodically purge keys with no recent requests
        if now - self._last_gc > self._GC_INTERVAL:
            self._gc(cutoff)
        return True

    def _gc(self, cutoff: float) -> None:
        stale = [k for k, v in self._windows.items() if not v or v[-1] <= cutoff]
        for k in stale:
            del self._windows[k]
        self._last_gc = time.monotonic()


_limiter = _SlidingWindowCounter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-client rate limiting middleware.

    Limits are per-minute, keyed by API key or client IP.
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        # Client identity: API key > forwarded IP > direct IP
        client_id = getattr(request.state, "client_id", None)
        if not client_id:
            client_id = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or request.client.host
            )

        if not _limiter.is_allowed(client_id, settings.RATE_LIMIT_PER_MINUTE, 60):
            logger.warning("rate_limited", client=client_id, path=path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry later."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
