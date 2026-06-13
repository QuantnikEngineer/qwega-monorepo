"""Gateway proxy forwarding services, including SSE passthrough."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
from collections.abc import AsyncIterator

import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from app.config import settings

_logger = logging.getLogger(__name__)

try:
    import truststore
    _ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:
    _ssl_ctx = True  # httpx default (certifi bundle)


HOP_BY_HOP_HEADERS = {
    "connection",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    # httpx auto-decompresses; strip these so downstream doesn't double-decode
    "content-encoding",
    "content-length",
}


class ProxyManager:
    """Shared proxy transport for auth and /api forwarding."""

    def __init__(self, *, timeout: float = 60.0, stream_timeout: float = 600.0) -> None:
        self._timeout = timeout
        self._stream_timeout = stream_timeout

    async def forward_request(
        self,
        *,
        request: Request,
        upstream_url: str,
        headers: dict[str, str],
    ) -> Response:
        body = await request.body()
        outbound = _sanitize_outbound_headers(headers)

        # Use extended timeout for file uploads (multipart) which involve LLM processing
        content_type = outbound.get("content-type", outbound.get("Content-Type", ""))
        timeout = self._stream_timeout if "multipart/form-data" in content_type else self._timeout

        _logger.info("forward_request %s %s (timeout=%ss, body=%d bytes)", request.method, upstream_url, timeout, len(body))
        async with httpx.AsyncClient(timeout=timeout, verify=_ssl_ctx) as client:
            upstream = await client.request(
                request.method,
                upstream_url,
                params=request.query_params,
                content=body if body else None,
                headers=outbound,
            )
        _logger.info("forward_request response: %s %s", upstream.status_code, upstream_url)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=_sanitize_response_headers(upstream.headers),
            media_type=upstream.headers.get("content-type"),
        )

    async def forward_sse(
        self,
        *,
        request: Request,
        upstream_url: str,
        headers: dict[str, str],
    ) -> StreamingResponse:
        request_body = await request.body()
        outbound = _sanitize_outbound_headers(headers)
        client = httpx.AsyncClient(timeout=self._stream_timeout, verify=_ssl_ctx)
        upstream = await client.send(
            client.build_request(
                request.method,
                upstream_url,
                params=request.query_params,
                content=request_body if request_body else None,
                headers=outbound,
            ),
            stream=True,
        )

        heartbeat_interval = settings.sse_heartbeat_seconds
        _heartbeat = b": heartbeat\n\n"
        _SENTINEL = object()

        async def stream_with_heartbeats() -> AsyncIterator[bytes]:
            """Stream upstream SSE bytes, injecting heartbeat comments during idle gaps.

            Uses a background reader task + asyncio.Queue to avoid the
            ``asyncio.wait_for`` + ``__anext__()`` cancellation bug: wait_for
            cancels the inner coroutine on timeout, which corrupts the httpx
            stream iterator and silently kills the connection.

            Pattern:
            1. A background task reads chunks from upstream into a queue.
            2. The generator races ``queue.get()`` against ``asyncio.sleep()``
               via ``asyncio.wait(return_when=FIRST_COMPLETED)``.
            3. If sleep wins → yield heartbeat; if queue wins → yield chunk.
            """
            queue: asyncio.Queue = asyncio.Queue()

            async def _reader() -> None:
                """Read all upstream chunks into the queue, then push sentinel."""
                try:
                    async for chunk in upstream.aiter_raw():
                        await queue.put(chunk)
                except Exception as exc:
                    _logger.warning("SSE upstream reader error: %s", exc)
                finally:
                    await queue.put(_SENTINEL)

            reader_task = asyncio.create_task(_reader())
            try:
                while True:
                    get_task = asyncio.create_task(queue.get())
                    sleep_task = asyncio.create_task(
                        asyncio.sleep(heartbeat_interval)
                    )
                    done, pending = await asyncio.wait(
                        {get_task, sleep_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()

                    if get_task in done:
                        item = get_task.result()
                        if item is _SENTINEL:
                            break
                        yield item
                        # Drain any already-queued chunks before sleeping again
                        while not queue.empty():
                            item = queue.get_nowait()
                            if item is _SENTINEL:
                                break
                            yield item
                        else:
                            continue
                        break  # sentinel found during drain
                    else:
                        # Timeout — inject heartbeat to keep HTTP/2 alive
                        _logger.debug("SSE heartbeat injected (idle >%ds)", heartbeat_interval)
                        yield _heartbeat
            finally:
                reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader_task
                await upstream.aclose()
                await client.aclose()

        response_headers = _sanitize_response_headers(upstream.headers)
        response_headers.update(
            {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-SSE-Heartbeat-Seconds": str(heartbeat_interval),
                "X-SSE-Reconnect-Ms": str(settings.sse_reconnect_ms),
            }
        )

        return StreamingResponse(
            stream_with_heartbeats(),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            headers=response_headers,
        )


def _sanitize_outbound_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip hop-by-hop and proxy-hostile headers before forwarding upstream."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


def _sanitize_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
