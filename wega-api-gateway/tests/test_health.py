"""Gateway foundation health/public-route tests."""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """Gateway health endpoint is publicly available."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == settings.app_name
    assert "version" in payload


def test_jwks_route_is_publicly_reachable() -> None:
    """Gateway JWKS contract endpoint is reachable without auth token."""
    response = client.get("/auth/jwks")
    assert response.status_code == 200
    assert "keys" in response.json()


def test_public_allowlist_contains_d06_contract() -> None:
    """Public route constants include D-06 allowlist entries."""
    expected = {
        ("GET", "/health"),
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("GET", "/auth/jwks"),
    }
    assert expected.issubset(settings.public_route_allowlist)
