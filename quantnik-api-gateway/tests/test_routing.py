"""Gateway route forwarding behavior tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import api as api_routes
from app.routes import auth as auth_routes


def test_auth_proxy_routes_forward_to_auth_service(monkeypatch) -> None:
    """Requests under /auth/* are forwarded via auth proxy manager."""
    app = FastAPI()
    app.include_router(auth_routes.router)
    seen: dict[str, str] = {}

    async def fake_forward_request(*, request, upstream_url: str, headers):
        from fastapi.responses import JSONResponse

        seen["method"] = request.method
        seen["upstream_url"] = upstream_url
        return JSONResponse({"ok": True})

    monkeypatch.setattr(auth_routes.proxy_manager, "forward_request", fake_forward_request)

    with TestClient(app) as client:
        response = client.post("/auth/logout")

    assert response.status_code == 200
    assert seen["method"] == "POST"
    assert seen["upstream_url"].endswith("/auth/logout")


def test_api_proxy_routes_map_to_expected_downstream(monkeypatch) -> None:
    """Gateway maps /api/* to orchestrator and planning routes correctly."""
    app = FastAPI()
    app.include_router(api_routes.router)
    seen: list[str] = []

    async def fake_forward_request(*, request, upstream_url: str, headers):
        from fastapi.responses import JSONResponse

        seen.append(upstream_url)
        return JSONResponse({"ok": True, "url": upstream_url})

    monkeypatch.setattr(api_routes.proxy_manager, "forward_request", fake_forward_request)

    with TestClient(app) as client:
        response_orch = client.get("/api/v1/chat")
        response_plan = client.get("/api/planning/v1/chat")

    assert response_orch.status_code == 200
    assert response_plan.status_code == 200
    # Orchestrator routes: gateway strips /api prefix, upstream = orchestrator_url/v1/chat
    assert any(url.endswith("/v1/chat") for url in seen)
    # Planning routes: gateway strips /api prefix, path = planning/v1/chat → strips planning/ → v1/chat
    assert any(url.endswith("/v1/chat") for url in seen)
