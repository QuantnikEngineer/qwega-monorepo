"""Generic tool proxy route factory.

Creates a FastAPI router for any tool based on its ToolAdapter definition.
Uses FastAPI Depends() for credential resolution and proxy transport so
tests can use ``app.dependency_overrides`` — no monkeypatching needed.

Bakes in proxy pitfalls discovered during Jira/Confluence development:
  1. Header sanitization (host, authorization, accept-encoding)
  2. Host header left to httpx (not manually set)
  3. 401 retry with credential cache invalidation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.middleware.settings_resolver import strip_tool_headers
from app.middleware.tool_credential_resolver import (
    ResolveFailure,
    ToolCredentialError,
    ToolCredentialResolver,
    ToolCredentials,
    get_credential_resolver,
)
from app.models.tool_adapter import ToolAdapter
from app.services.proxy_manager import ProxyManager

# ── Shared ProxyManager dependency ───────────────────────────────────────────

_proxy_manager = ProxyManager()


def get_proxy_manager() -> ProxyManager:
    """FastAPI dependency provider for the proxy transport."""
    return _proxy_manager


# ── Pure helpers (easy to unit-test independently) ───────────────────────────

def _normalize_headers(raw: dict[str, str]) -> dict[str, str]:
    """Lowercase all header keys for consistent lookup/mutation."""
    return {k.lower(): v for k, v in raw.items()}


def _build_upstream_url(base_url: str, path_prefix: str, path: str) -> str:
    """Construct the full upstream URL."""
    base = f"{base_url}{path_prefix}" if path_prefix else base_url
    normalized = path.lstrip("/")
    return f"{base}/{normalized}" if normalized else base


def _prepare_outbound_headers(
    headers: dict[str, str],
    creds: ToolCredentials,
    adapter: ToolAdapter,
) -> dict[str, str]:
    """Sanitize inbound headers and inject auth + adapter headers."""
    out = dict(headers)
    # Remove headers that must not be forwarded to upstream
    out.pop("host", None)
    out.pop("authorization", None)
    out.pop("accept-encoding", None)  # let httpx negotiate encoding
    # Inject auth headers from credential strategy
    out.update(creds.headers)
    # Inject any extra static headers from adapter
    out.update(adapter.extra_headers)
    return out


def _failure_to_response(error: ToolCredentialError, tool_id: str) -> JSONResponse:
    """Map structured credential failures to appropriate HTTP responses."""
    if error.failure == ResolveFailure.NOT_CONFIGURED:
        return JSONResponse(
            status_code=424,
            content={"error": f"{tool_id} not configured for this project"},
        )
    if error.failure == ResolveFailure.UPSTREAM_ERROR:
        return JSONResponse(
            status_code=502,
            content={"error": f"Unable to resolve {tool_id} credentials: {error.detail}"},
        )
    # INVALID_PAYLOAD, UNKNOWN_AUTH_TYPE
    return JSONResponse(
        status_code=502,
        content={"error": f"Invalid credential data for {tool_id}: {error.detail}"},
    )


# ── Factory ──────────────────────────────────────────────────────────────────

def create_tool_proxy_router(adapter: ToolAdapter) -> APIRouter:
    """Create a proxy router for any tool from its adapter config."""
    router = APIRouter(prefix=adapter.prefix, tags=[adapter.tool_id])

    @router.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def proxy_tool(
        path: str,
        request: Request,
        resolver: ToolCredentialResolver = Depends(get_credential_resolver),
        proxy: ProxyManager = Depends(get_proxy_manager),
    ):
        """Forward requests with project-scoped credential injection."""
        headers = getattr(request.state, "forward_headers", dict(request.headers))
        headers = _normalize_headers(strip_tool_headers(headers))

        project_id = headers.get("x-project-id")
        if not project_id:
            return JSONResponse(status_code=400, content={"error": "No active project"})

        result = await resolver.resolve(project_id, adapter.tool_id)
        if isinstance(result, ToolCredentialError):
            return _failure_to_response(result, adapter.tool_id)

        upstream = _build_upstream_url(result.base_url, adapter.upstream_path_prefix, path)
        out_headers = _prepare_outbound_headers(headers, result, adapter)

        resp = await proxy.forward_request(
            request=request, upstream_url=upstream, headers=out_headers,
        )

        # On 401, retry once with fresh credentials (handles credential rotation)
        if resp.status_code == 401:
            retry_result = await resolver.resolve_with_retry(project_id, adapter.tool_id)
            if isinstance(retry_result, ToolCredentials):
                upstream = _build_upstream_url(retry_result.base_url, adapter.upstream_path_prefix, path)
                out_headers = _prepare_outbound_headers(headers, retry_result, adapter)
                resp = await proxy.forward_request(
                    request=request, upstream_url=upstream, headers=out_headers,
                )

        return resp

    return router
