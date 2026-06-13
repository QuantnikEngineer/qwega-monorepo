"""Audit logging middleware for authenticated requests."""

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.middleware.rate_limiting import _source_ip_from_request
from app.services.audit_logger import AuditLogger


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured audit event per authenticated request."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        super().__init__(app)
        self._audit_logger = audit_logger or AuditLogger()

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)

        user_id = _resolve_user_id(request)
        if user_id:
            request_id = _resolve_request_id(request)
            source_ip = getattr(request.state, "source_ip", None) or _source_ip_from_request(request)
            self._audit_logger.emit_authenticated_request(
                user_id=user_id,
                action=request.url.path,
                method=request.method,
                status=response.status_code,
                request_id=request_id,
                source_ip=source_ip,
            )

        return response


def _resolve_user_id(request: Request) -> str | None:
    state_user_id = getattr(request.state, "user_id", None)
    if state_user_id:
        return str(state_user_id)

    state_user = getattr(request.state, "user", None)
    if isinstance(state_user, dict):
        for key in ("user_id", "id", "sub"):
            value = state_user.get(key)
            if value:
                return str(value)

    header_user_id = request.headers.get("x-user-id")
    if header_user_id:
        return header_user_id

    return None


def _resolve_request_id(request: Request) -> str:
    state_request_id = getattr(request.state, "request_id", None)
    if state_request_id:
        return str(state_request_id)
    return request.headers.get("x-request-id", str(uuid4()))
