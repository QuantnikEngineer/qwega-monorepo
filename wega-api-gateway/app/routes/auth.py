"""Gateway /auth/* proxy routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings
from app.services.proxy_manager import ProxyManager

router = APIRouter(prefix="/auth", tags=["auth"])
proxy_manager = ProxyManager()


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_auth(path: str, request: Request):
    """Forward auth traffic to auth-service with shared proxy plumbing."""
    upstream = f"{settings.auth_service_url.rstrip('/')}/api/auth/{path}".rstrip("/")
    headers = getattr(request.state, "forward_headers", dict(request.headers))
    return await proxy_manager.forward_request(request=request, upstream_url=upstream, headers=headers)
