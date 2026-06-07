"""Rate limiting middleware for login endpoint."""

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.rate_limiter import LoginRateLimiter
from app.utils.error_codes import RATE_LIMITED


def _source_ip_from_request(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class LoginRateLimitingMiddleware(BaseHTTPMiddleware):
    """Limit POST /auth/login attempts per source IP."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        rate_limiter: LoginRateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter or LoginRateLimiter()

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        source_ip = _source_ip_from_request(request)
        request.state.source_ip = source_ip

        if request.method == "POST" and request.url.path == "/auth/login":
            is_allowed, retry_after_seconds = self._rate_limiter.check_and_record(source_ip)
            if not is_allowed:
                request_id = request.headers.get("x-request-id", str(uuid4()))
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": RATE_LIMITED,
                        "message": "Too many login attempts",
                        "request_id": request_id,
                        "retry_after_seconds": retry_after_seconds,
                    },
                    headers={"Retry-After": str(retry_after_seconds)},
                )

        return await call_next(request)
