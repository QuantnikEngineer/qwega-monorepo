"""
Tests for direct-to-project registration — gateway route access.
=================================================================
Verifies registration-defaults is publicly reachable (no JWT).

Unit tests (allowlist assertions) run standalone.
Integration tests (actual routing) need quantnik-auth-service running
and are marked with @pytest.mark.integration.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


# ── Unit: allowlist configuration ────────────────────────────────


def test_registration_defaults_in_public_allowlist() -> None:
    """Public route constants include registration-defaults."""
    assert ("GET", "/auth/registration-defaults") in settings.public_route_allowlist


def test_register_endpoint_in_public_allowlist() -> None:
    """POST /auth/register remains in public allowlist."""
    assert ("POST", "/auth/register") in settings.public_route_allowlist


# ── Integration: actual routing through gateway middleware ────────


@pytest.fixture()
def gw_client(monkeypatch: pytest.MonkeyPatch):
    """Gateway TestClient that returns HTTP responses for upstream errors."""
    monkeypatch.setattr("app.config.settings.cors_origins", "http://frontend.example")
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.integration
def test_registration_defaults_not_blocked_by_auth(gw_client) -> None:
    """GET /auth/registration-defaults passes JWT middleware (public route).

    If auth-service is running → 200.
    If auth-service is down → 500 (upstream connect error).
    Must NEVER be 401/403 (would mean auth middleware blocked it).
    """
    response = gw_client.get("/auth/registration-defaults")
    assert response.status_code not in (401, 403), (
        f"Gateway rejected public route with {response.status_code}"
    )


@pytest.mark.integration
def test_register_not_blocked_by_auth(gw_client) -> None:
    """POST /auth/register passes JWT middleware (public route)."""
    response = gw_client.post(
        "/auth/register",
        json={
            "email": "test@wipro.com",
            "display_name": "Test",
            "password": "SecureP@ssw0rd123!",
        },
    )
    assert response.status_code not in (401, 403), (
        f"Gateway rejected public route with {response.status_code}"
    )


@pytest.mark.integration
def test_protected_route_requires_auth(gw_client) -> None:
    """Non-public routes return 401 without token (control test)."""
    response = gw_client.get("/api/projects")
    assert response.status_code in (401, 403)
