"""Gateway /confluence/* proxy routes."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.middleware.settings_resolver import strip_tool_headers
from app.middleware.tool_credential_resolver import (
    resolve_atlassian_auth,
    resolve_atlassian_auth_with_retry,
)
from app.services.proxy_manager import ProxyManager

router = APIRouter(prefix="/confluence", tags=["confluence"])
proxy_manager = ProxyManager()


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_confluence(path: str, request: Request):
    """Forward Confluence requests with project-scoped credential injection."""
    headers = getattr(request.state, "forward_headers", dict(request.headers))

    # Strip any spoofed tool headers
    headers = strip_tool_headers(headers)

    # Resolve project ID from JWT context (injected by HeaderInjectionMiddleware)
    project_id = headers.get("X-Project-Id") or headers.get("x-project-id")
    if not project_id:
        return JSONResponse(status_code=400, content={"error": "No active project"})

    # Resolve Atlassian credentials from project secrets
    result = await resolve_atlassian_auth(project_id, "confluence")
    if not result:
        return JSONResponse(status_code=424, content={"error": "Confluence not configured for this project"})

    base_url, auth_header = result
    normalized_path = path.lstrip("/")
    # Confluence API routes live under /wiki
    upstream_base = f"{base_url}/wiki"
    upstream = f"{upstream_base}/{normalized_path}" if normalized_path else upstream_base

    # Replace headers (remove lowercase originals to avoid duplicates)
    headers.pop("host", None)
    headers.pop("authorization", None)
    headers.pop("accept-encoding", None)  # let httpx negotiate its own encoding
    headers["Host"] = urlparse(base_url).hostname or ""
    headers["Authorization"] = auth_header
    headers["Accept"] = "application/json"

    resp = await proxy_manager.forward_request(request=request, upstream_url=upstream, headers=headers)

    # On 401, retry once with fresh credentials (handles credential rotation)
    if resp.status_code == 401:
        retry_result = await resolve_atlassian_auth_with_retry(project_id, "confluence")
        if retry_result:
            base_url, auth_header = retry_result
            upstream_base = f"{base_url}/wiki"
            upstream = f"{upstream_base}/{normalized_path}" if normalized_path else upstream_base
            headers["Authorization"] = auth_header
            headers["Host"] = urlparse(base_url).hostname or ""
            resp = await proxy_manager.forward_request(request=request, upstream_url=upstream, headers=headers)

    return resp
