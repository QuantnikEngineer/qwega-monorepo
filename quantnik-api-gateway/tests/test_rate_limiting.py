"""Rate-limiting middleware tests."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.rate_limiting import LoginRateLimitingMiddleware
from app.services.rate_limiter import LoginRateLimiter
from app.utils.error_codes import RATE_LIMITED


def _build_test_client(max_attempts: int = 2, window_seconds: int = 60) -> TestClient:
    def clock() -> float:
        return 0.0

    app = FastAPI()
    limiter = LoginRateLimiter(
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        clock=clock,
    )
    app.add_middleware(LoginRateLimitingMiddleware, rate_limiter=limiter)

    @app.post("/auth/login")
    async def login() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    return TestClient(app)


def test_login_requests_are_throttled_after_threshold() -> None:
    """POST /auth/login returns 429 once per-IP threshold is exceeded."""
    client = _build_test_client(max_attempts=2, window_seconds=60)
    headers = {"x-forwarded-for": "203.0.113.10"}

    assert client.post("/auth/login", headers=headers).status_code == 200
    assert client.post("/auth/login", headers=headers).status_code == 200

    blocked = client.post("/auth/login", headers=headers)
    assert blocked.status_code == 429
    payload = blocked.json()
    assert payload["code"] == RATE_LIMITED
    assert payload["retry_after_seconds"] > 0
    assert blocked.headers["Retry-After"] == str(payload["retry_after_seconds"])


def test_non_login_routes_are_not_rate_limited() -> None:
    """Rate limiter only applies to POST /auth/login."""
    client = _build_test_client(max_attempts=1, window_seconds=60)
    headers = {"x-forwarded-for": "203.0.113.11"}

    first = client.get("/health", headers=headers)
    second = client.get("/health", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
