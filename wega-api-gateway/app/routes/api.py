"""Gateway /api/* proxy routes with SSE passthrough support."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings
from app.middleware.settings_resolver import (
    fetch_project_tool_config,
    inject_tool_headers,
    strip_tool_headers,
)
from app.services.proxy_manager import ProxyManager

router = APIRouter(prefix="/api", tags=["api"])
proxy_manager = ProxyManager()

SSE_PATH_SUFFIXES = (
    "/stream",
    "/chat/stream",
    "/chat/stream/forward",
)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_api(path: str, request: Request):
    """Forward API traffic to orchestrators with shared proxy semantics."""
    upstream = _resolve_upstream_url(path)
    headers = getattr(request.state, "forward_headers", dict(request.headers))

    # For non-auth-service routes, resolve project tool settings → headers
    first_segment = path.split("/", 1)[0]
    if first_segment not in _AUTH_SERVICE_PREFIXES:
        headers = strip_tool_headers(headers)
        project_id = headers.get("X-Project-Id") or headers.get("x-project-id")
        if project_id:
            tools = await fetch_project_tool_config(project_id)
            if tools:
                headers = inject_tool_headers(headers, tools)

    if _is_sse_route(path):
        return await proxy_manager.forward_sse(request=request, upstream_url=upstream, headers=headers)

    return await proxy_manager.forward_request(request=request, upstream_url=upstream, headers=headers)


_AUTH_SERVICE_PREFIXES = ("users", "roles", "projects", "capabilities", "services", "agents")


def _resolve_upstream_url(path: str) -> str:
    """Build the full upstream URL for the given gateway path.

    Auth-service endpoints live under /api/*, so we prepend /api/.
    Orchestrators expose endpoints at the root (e.g. /v1/chat), no /api/ prefix.
    Planning paths arrive as planning/... — strip the gateway prefix before forwarding.
    Test-case agent paths (bulk generation + job status) go directly to the agent.
    Code-assistant paths (v1/code-assistant/*) are routed to the SDLC orchestrator.
    """
    first_segment = path.split("/", 1)[0]
    if first_segment in _AUTH_SERVICE_PREFIXES:
        return f"{settings.auth_service_url.rstrip('/')}/api/{path}"
    if path.startswith("brain/"):
        remainder = path[len("brain/"):]
        return f"{settings.rag_service_url.rstrip('/')}/api/{remainder}"
    if path.startswith("planning/"):
        remainder = path[len("planning/"):]
        return f"{settings.planning_orchestrator_url.rstrip('/')}/{remainder}"
    if _is_testcase_agent_path(path):
        if path.startswith("v1/jobs/"):
            return f"{settings.testcase_poll_url.rstrip('/')}/{path}"
        return f"{settings.testcase_agent_url.rstrip('/')}/{path}"
    # Code Assistant endpoints are routed through SDLC Orchestrator
    if path.startswith("v1/code-assistant/"):
        return f"{settings.orchestrator_url.rstrip('/')}/{path}"
    return f"{settings.orchestrator_url.rstrip('/')}/{path}"


_TESTCASE_AGENT_PREFIXES = ("v1/generate-test-cases", "v1/jobs/")


def _is_testcase_agent_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _TESTCASE_AGENT_PREFIXES)


def _is_sse_route(path: str) -> bool:
    normalized = "/" + path.lstrip("/")
    return any(normalized.endswith(suffix) for suffix in SSE_PATH_SUFFIXES)
