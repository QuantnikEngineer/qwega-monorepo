"""Header injection contract tests (D-07)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.header_injection import HeaderInjectionMiddleware


def test_header_injection_adds_trusted_identity_and_strips_authorization() -> None:
    """Forward headers include trusted identity and exclude bearer Authorization."""
    app = FastAPI()
    app.add_middleware(HeaderInjectionMiddleware)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "user-123"
        request.state.user = {
            "email": "user@wipro.com",
            "roles": ["PM", "FDE"],
            "capabilities": ["sdlc:execute", "org:manage_users"],
            "org_id": "org-456",
        }
        return await call_next(request)

    @app.get("/inspect")
    async def inspect(request: Request) -> dict[str, str]:
        headers = request.state.forward_headers
        return {
            "x_user_id": headers.get("X-User-Id", ""),
            "x_user_email": headers.get("X-User-Email", ""),
            "x_user_roles": headers.get("X-User-Roles", ""),
            "x_user_capabilities": headers.get("X-User-Capabilities", ""),
            "x_user_org_id": headers.get("X-User-Org-Id", ""),
            "has_authorization": str(
                "authorization" in headers or "Authorization" in headers
            ).lower(),
            "x_request_id": headers.get("X-Request-Id", ""),
        }

    with TestClient(app) as client:
        response = client.get("/inspect", headers={"Authorization": "Bearer abc"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["x_user_id"] == "user-123"
    assert payload["x_user_email"] == "user@wipro.com"
    assert payload["x_user_roles"] == "PM,FDE"
    assert payload["x_user_capabilities"] == "sdlc:execute,org:manage_users"
    assert payload["x_user_org_id"] == "org-456"
    assert payload["has_authorization"] == "false"
    assert payload["x_request_id"] != ""


def test_header_injection_preserves_existing_request_id() -> None:
    """Existing X-Request-Id from caller should be propagated downstream."""
    app = FastAPI()
    app.add_middleware(HeaderInjectionMiddleware)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "user-999"
        request.state.user = {"email": "person@wipro.com", "roles": ["Dev/Test"]}
        return await call_next(request)

    @app.get("/inspect")
    async def inspect(request: Request) -> dict[str, str]:
        headers = request.state.forward_headers
        return {"request_id": headers.get("X-Request-Id", "")}

    with TestClient(app) as client:
        response = client.get("/inspect", headers={"X-Request-Id": "req-123"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "req-123"
