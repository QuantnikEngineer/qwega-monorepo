"""
Health Endpoint Tests
=====================
Smoke tests for the Auth Service health endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    """Health endpoint returns 200 with expected fields."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Quantnik Auth Service"
    assert "version" in data


def test_root_returns_200():
    """Root endpoint returns 200 with service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Quantnik Auth Service"
    assert data["status"] == "running"
