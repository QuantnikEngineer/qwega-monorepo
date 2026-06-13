"""Capability enforcement middleware for RBAC-protected gateway routes."""

from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.utils.error_codes import INSUFFICIENT_CAPABILITY


class CapabilityMiddleware(BaseHTTPMiddleware):
    """Check JWT scoped claims against route-to-capability requirements."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Skip public routes (already bypassed by JWT middleware)
        if _is_public_route(request):
            return await call_next(request)

        # Skip if no user claims populated (JWT middleware already rejected or route is exempt)
        user_claims = getattr(request.state, "user", None)
        if not user_claims:
            return await call_next(request)

        # Find matching route capability requirement
        required_capability = _get_required_capability(request.method, request.url.path)
        if required_capability is None:
            # No capability mapping for this route — pass through (auth-only)
            return await call_next(request)

        # Check if user has required capability in any applicable scope
        if not _user_has_capability(user_claims, required_capability):
            return _forbidden_response(
                request,
                INSUFFICIENT_CAPABILITY,
                "You do not have permission to perform this action",
                required_capability,
            )

        return await call_next(request)


def _is_public_route(request: Request) -> bool:
    """Check if route is in public allowlist (skip capability check)."""
    if request.method == "OPTIONS":
        return True
    return (request.method.upper(), request.url.path) in settings.public_route_allowlist


def _get_required_capability(method: str, path: str) -> str | None:
    """Look up the required capability for a route. Returns *None* if no mapping exists."""
    method_upper = method.upper()
    # Exact match first
    if (method_upper, path) in settings.route_capability_map:
        return settings.route_capability_map[(method_upper, path)]
    # Prefix match for parameterised routes (e.g. PUT /api/users/{id})
    for (route_method, route_prefix), capability in settings.route_capability_map.items():
        if route_method == method_upper and route_prefix.endswith("/"):
            if path.startswith(route_prefix):
                return capability
        # Wildcard match for /api/users/*/resend-activation patterns
        if route_method == method_upper and "*" in route_prefix:
            parts = route_prefix.split("*")
            if len(parts) == 2 and path.startswith(parts[0]) and path.endswith(parts[1]):
                return capability
    return None  # No mapping — pass through


def _user_has_capability(user_claims: dict, required_capability: str) -> bool:
    """Check if user has the required capability (Phase 5: flat org-scoped model)."""
    # Phase 5: flat capabilities is primary source
    flat_caps = user_claims.get("capabilities", [])
    if required_capability in flat_caps:
        return True

    # Backward compat: check scoped claims from Phase 4 tokens still in circulation
    platform_caps = user_claims.get("platform_capabilities", [])
    org_caps = user_claims.get("org_capabilities", [])
    self_caps = user_claims.get("self_capabilities", [])
    all_scoped_caps = platform_caps + org_caps + self_caps
    if required_capability in all_scoped_caps:
        return True

    return False


def _forbidden_response(
    request: Request, code: str, message: str, required_capability: str = ""
) -> JSONResponse:
    """Return a structured 403 response."""
    request_id = request.headers.get("x-request-id", str(uuid4()))
    return JSONResponse(
        status_code=403,
        content={
            "code": code,
            "message": message,
            "required_capability": required_capability,
            "request_id": request_id,
        },
    )
