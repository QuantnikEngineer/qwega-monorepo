"""Audit logging middleware tests."""

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.audit_logging import AuditLoggingMiddleware
from app.services.audit_logger import AuditLogger


def _build_client() -> tuple[TestClient, list[str]]:
    app = FastAPI()
    sink: list[str] = []
    app.add_middleware(
        AuditLoggingMiddleware,
        audit_logger=AuditLogger(sink=sink.append),
    )

    @app.get("/secure")
    async def secure(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True}, status_code=201)

    return TestClient(app), sink


def test_authenticated_requests_emit_required_audit_fields() -> None:
    """Authenticated requests always emit required structured audit keys."""
    client, sink = _build_client()
    response = client.get(
        "/secure",
        headers={
            "x-user-id": "user-123",
            "x-request-id": "req-abc",
            "x-forwarded-for": "198.51.100.9",
            "Authorization": "Bearer super-secret-token",
        },
    )

    assert response.status_code == 201
    assert len(sink) == 1
    event = json.loads(sink[0])

    required = {"user_id", "action", "method", "status", "timestamp", "request_id", "source_ip"}
    assert required.issubset(event.keys())
    assert event["user_id"] == "user-123"
    assert event["request_id"] == "req-abc"
    assert event["action"] == "/secure"
    assert event["method"] == "GET"
    assert event["status"] == 201
    assert event["source_ip"] == "198.51.100.9"
    assert "Authorization" not in event
    assert "super-secret-token" not in json.dumps(event)


def test_unauthenticated_requests_do_not_emit_audit_entries() -> None:
    """Requests without authenticated identity are not audited."""
    client, sink = _build_client()
    response = client.get("/secure")

    assert response.status_code == 201
    assert sink == []
