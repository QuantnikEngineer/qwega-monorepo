"""Confluence proxy route tests."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.header_injection import HeaderInjectionMiddleware
from app.routes import confluence as confluence_routes


def test_confluence_proxy_forwards_to_wiki_path_and_preserves_d07_headers(monkeypatch) -> None:
    """Gateway /confluence/* route preserves D-07 header contract with /wiki rewrite."""
    app = FastAPI()
    app.add_middleware(HeaderInjectionMiddleware)
    app.include_router(confluence_routes.router)
    seen: dict[str, str | bool] = {}

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "conf-user-456"
        request.state.user = {"email": "conf.user@wipro.com", "roles": ["Dev/Test"]}
        return await call_next(request)

    # Mock credential resolver to return test Atlassian credentials
    async def fake_resolve_atlassian_auth(project_id, tool_id):
        return ("https://wegabuildiq.atlassian.net", "Basic dGVzdDp0ZXN0")

    monkeypatch.setattr(
        confluence_routes, "resolve_atlassian_auth", fake_resolve_atlassian_auth
    )

    async def fake_forward_request(*, request, upstream_url: str, headers):
        from fastapi.responses import JSONResponse

        seen["method"] = request.method
        seen["upstream_url"] = upstream_url
        seen["authorization"] = headers.get("Authorization", "")
        seen["x_user_id"] = headers.get("X-User-Id", "")
        seen["x_user_email"] = headers.get("X-User-Email", "")
        seen["x_user_roles"] = headers.get("X-User-Roles", "")
        seen["x_request_id"] = headers.get("X-Request-Id", "")
        return JSONResponse({"ok": True})

    monkeypatch.setattr(confluence_routes.proxy_manager, "forward_request", fake_forward_request)

    with TestClient(app) as client:
        response = client.get(
            "/confluence/api/v2/spaces",
            headers={
                "Authorization": "Bearer fake-token",
                "X-Request-Id": "req-conf-1",
                "X-Project-Id": "proj-456",
            },
        )

    assert response.status_code == 200
    assert seen["method"] == "GET"
    assert seen["upstream_url"] == "https://wegabuildiq.atlassian.net/wiki/api/v2/spaces"
    # Credential injection: Basic auth from resolver replaces Bearer token
    assert seen["authorization"] == "Basic dGVzdDp0ZXN0"
    assert seen["x_user_id"] == "conf-user-456"
    assert seen["x_user_email"] == "conf.user@wipro.com"
    assert seen["x_user_roles"] == "Dev/Test"
    assert seen["x_request_id"] == "req-conf-1"


def test_confluence_proxy_returns_400_without_project_id(monkeypatch) -> None:
    """Confluence proxy requires X-Project-Id header."""
    app = FastAPI()
    app.include_router(confluence_routes.router)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "conf-user-456"
        request.state.user = {"email": "conf.user@wipro.com", "roles": ["Dev/Test"]}
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get("/confluence/api/v2/spaces")

    assert response.status_code == 400
    assert "No active project" in response.json()["error"]


def test_confluence_proxy_returns_424_when_not_configured(monkeypatch) -> None:
    """Confluence proxy returns 424 when credentials cannot be resolved."""
    app = FastAPI()
    app.include_router(confluence_routes.router)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "conf-user-456"
        request.state.user = {"email": "conf.user@wipro.com", "roles": ["Dev/Test"]}
        return await call_next(request)

    async def fake_resolve_no_creds(project_id, tool_id):
        return None

    monkeypatch.setattr(confluence_routes, "resolve_atlassian_auth", fake_resolve_no_creds)

    with TestClient(app) as client:
        response = client.get(
            "/confluence/api/v2/spaces",
            headers={"X-Project-Id": "proj-no-creds"},
        )

    assert response.status_code == 424
    assert "not configured" in response.json()["error"]
