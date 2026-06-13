"""SSE passthrough behavior tests for gateway proxying."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from app.middleware.header_injection import HeaderInjectionMiddleware
from app.routes import api as api_routes


def test_sse_routes_use_stream_passthrough_without_repackaging(monkeypatch) -> None:
    """SSE routes invoke streaming forwarder and preserve upstream chunks."""
    app = FastAPI()
    app.add_middleware(HeaderInjectionMiddleware)
    app.include_router(api_routes.router)
    seen = {"called": False}

    async def fake_forward_sse(*, request, upstream_url: str, headers):
        seen["called"] = True
        seen["upstream_url"] = upstream_url
        seen["authorization_present"] = (
            "authorization" in headers or "Authorization" in headers
        )
        seen["x_request_id"] = headers.get("X-Request-Id", "")

        async def events():
            yield b"event: heartbeat\ndata: ping\n\n"
            yield b"data: chunk-1\n\n"
            yield b"data: chunk-2\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-SSE-Heartbeat-Seconds": "15",
                "X-SSE-Reconnect-Ms": "3000",
            },
        )

    monkeypatch.setattr(api_routes.proxy_manager, "forward_sse", fake_forward_sse)

    with TestClient(app) as client:
        with client.stream(
            "GET",
            "/api/v1/chat/stream",
            headers={"Authorization": "Bearer fake"},
        ) as response:
            body = b"".join(response.iter_bytes())
            headers = response.headers

    assert seen["called"] is True
    # Orchestrator route: gateway strips /api prefix → path is v1/chat/stream
    # upstream = orchestrator_url/v1/chat/stream (no /api/ prefix)
    assert seen["upstream_url"].endswith("/v1/chat/stream")
    assert seen["authorization_present"] is False
    assert seen["x_request_id"] != ""
    assert body == (
        b"event: heartbeat\ndata: ping\n\n"
        b"data: chunk-1\n\n"
        b"data: chunk-2\n\n"
    )
    assert headers.get("content-type", "").startswith("text/event-stream")
    assert headers.get("x-accel-buffering") == "no"
    assert headers.get("x-sse-heartbeat-seconds") == "15"
    assert headers.get("x-sse-reconnect-ms") == "3000"
