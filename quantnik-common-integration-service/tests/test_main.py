"""
Tests for main application endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "docs" in data


def test_chat_endpoint_validation():
    """Test chat endpoint request validation."""
    # Missing session_id
    response = client.post(
        "/v1/chat",
        json={"message": "test"}
    )
    assert response.status_code == 422
    
    # Missing message
    response = client.post(
        "/v1/chat",
        json={"session_id": "test_session"}
    )
    assert response.status_code == 422


def test_chat_endpoint_basic():
    """Test basic chat request."""
    response = client.post(
        "/v1/chat",
        json={
            "session_id": "test_session_123",
            "message": "What can you help me with?",
            "selected_model": "gemini-2.0-flash"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "message" in data
    assert "status" in data


def test_simple_chat_endpoint():
    """Test simple chat endpoint with auto-generated session."""
    response = client.post(
        "/v1/chat/simple",
        json="What can you help me with?"
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["session_id"].startswith("sess_")


def test_openapi_spec():
    """Test OpenAPI spec is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
    assert "/v1/chat" in data["paths"]
    assert "/v1/chat/stream" in data["paths"]
    assert "/v1/chat/simple" in data["paths"]
