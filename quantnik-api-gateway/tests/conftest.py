"""Shared fixtures for gateway middleware tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def gateway_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Create gateway app with a protected route for auth enforcement tests."""
    monkeypatch.setattr("app.config.settings.cors_origins", "http://frontend.example")

    app = create_app()

    @app.get("/protected")
    async def protected_endpoint() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        yield client
