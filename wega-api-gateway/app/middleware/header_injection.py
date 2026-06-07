"""Header injection middleware for downstream gateway forwarding."""

from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings


class HeaderInjectionMiddleware(BaseHTTPMiddleware):
    """Inject trusted X-User-* headers and remove bearer token before proxying."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        request.state.forward_headers = build_forward_headers(request, request_id=request_id)
        return await call_next(request)


def build_forward_headers(request: Request, *, request_id: str) -> dict[str, str]:
    """Construct downstream-safe headers with trusted identity context."""
    forward_headers = {key: value for key, value in request.headers.items()}

    # Strip hop-by-hop and routing headers that must not be forwarded.
    # The `host` header must be removed so httpx sets the correct Host for
    # the upstream URL — forwarding the gateway's Host to a different Cloud
    # Run service triggers domain-fronting blocks (e.g., Zscaler).
    for hdr in ("host", "Host", "authorization", "Authorization"):
        forward_headers.pop(hdr, None)

    # Preserve deterministic request correlation.
    forward_headers["X-Request-Id"] = request_id

    # Establish trust with downstream services (auth-service uses this
    # to accept X-User-* headers when IP-based trust isn't available,
    # e.g., on Cloud Run where gateway IP is dynamic).
    forward_headers["X-Internal-Key"] = settings.internal_api_key

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        claims = getattr(request.state, "user", {}) or {}
        forward_headers["X-User-Id"] = str(user_id)
        forward_headers["X-User-Email"] = str(claims.get("email", ""))
        forward_headers["X-User-Org-Id"] = str(claims.get("org_id", ""))
        roles = claims.get("roles", [])
        if isinstance(roles, list):
            forward_headers["X-User-Roles"] = ",".join(str(role) for role in roles)
        elif roles:
            forward_headers["X-User-Roles"] = str(roles)
        else:
            forward_headers["X-User-Roles"] = ""
        capabilities = claims.get("capabilities", [])
        if isinstance(capabilities, list):
            forward_headers["X-User-Capabilities"] = ",".join(str(cap) for cap in capabilities)
        elif capabilities:
            forward_headers["X-User-Capabilities"] = str(capabilities)
        else:
            forward_headers["X-User-Capabilities"] = ""

        # Project context: primary project + all memberships
        project_id = claims.get("project_id")
        project_ids = claims.get("project_ids", [])

        # Allow frontend to override active project via request header,
        # validated against the user's project_ids from JWT
        active_override = request.headers.get("x-active-project-id")
        if active_override and active_override in project_ids:
            forward_headers["X-Project-Id"] = str(active_override)
        elif project_id:
            forward_headers["X-Project-Id"] = str(project_id)

        if isinstance(project_ids, list) and project_ids:
            forward_headers["X-Project-Ids"] = ",".join(str(pid) for pid in project_ids)

    return forward_headers
