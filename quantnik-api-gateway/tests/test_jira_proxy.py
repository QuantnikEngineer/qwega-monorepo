"""Jira proxy route tests."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.header_injection import HeaderInjectionMiddleware
from app.routes import jira as jira_routes


def test_jira_proxy_forwards_to_atlassian_base_and_preserves_d07_headers(monkeypatch) -> None:
    """Gateway /jira/* route preserves D-07 header contract while forwarding path."""
    app = FastAPI()
    app.add_middleware(HeaderInjectionMiddleware)
    app.include_router(jira_routes.router)
    seen: dict[str, str | bool] = {}

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "jira-user-123"
        request.state.user = {"email": "jira.user@wipro.com", "roles": ["PM", "FDE"]}
        return await call_next(request)

    # Mock credential resolver to return test Atlassian credentials
    async def fake_resolve_atlassian_auth(project_id, tool_id):
        return ("https://quantnikbuildiq.atlassian.net", "Basic dGVzdDp0ZXN0")

    monkeypatch.setattr(
        jira_routes, "resolve_atlassian_auth", fake_resolve_atlassian_auth
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

    monkeypatch.setattr(jira_routes.proxy_manager, "forward_request", fake_forward_request)

    with TestClient(app) as client:
        response = client.get(
            "/jira/rest/api/3/project/search",
            headers={
                "Authorization": "Bearer fake-token",
                "X-Request-Id": "req-jira-1",
                "X-Project-Id": "proj-123",
            },
        )

    assert response.status_code == 200
    assert seen["method"] == "GET"
    assert seen["upstream_url"] == "https://quantnikbuildiq.atlassian.net/rest/api/3/project/search"
    # Credential injection: Basic auth from resolver replaces Bearer token
    assert seen["authorization"] == "Basic dGVzdDp0ZXN0"
    assert seen["x_user_id"] == "jira-user-123"
    assert seen["x_user_email"] == "jira.user@wipro.com"
    assert seen["x_user_roles"] == "PM,FDE"
    assert seen["x_request_id"] == "req-jira-1"


def test_jira_proxy_returns_400_without_project_id(monkeypatch) -> None:
    """Jira proxy requires X-Project-Id header."""
    app = FastAPI()
    app.include_router(jira_routes.router)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "jira-user-123"
        request.state.user = {"email": "jira.user@wipro.com", "roles": ["PM"]}
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get("/jira/rest/api/3/project/search")

    assert response.status_code == 400
    assert "No active project" in response.json()["error"]


def test_jira_proxy_returns_424_when_not_configured(monkeypatch) -> None:
    """Jira proxy returns 424 when credentials cannot be resolved."""
    app = FastAPI()
    app.include_router(jira_routes.router)

    @app.middleware("http")
    async def seed_user_claims(request: Request, call_next):
        request.state.user_id = "jira-user-123"
        request.state.user = {"email": "jira.user@wipro.com", "roles": ["PM"]}
        return await call_next(request)

    async def fake_resolve_no_creds(project_id, tool_id):
        return None

    monkeypatch.setattr(jira_routes, "resolve_atlassian_auth", fake_resolve_no_creds)

    with TestClient(app) as client:
        response = client.get(
            "/jira/rest/api/3/project/search",
            headers={"X-Project-Id": "proj-no-creds"},
        )

    assert response.status_code == 424
    assert "not configured" in response.json()["error"]
