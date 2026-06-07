"""JWT validation middleware for protected gateway routes."""

from __future__ import annotations

from uuid import uuid4

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.services.jwks_cache import JWKSCache
from app.utils.error_codes import INVALID_TOKEN, MISSING_TOKEN, TOKEN_EXPIRED


class JWTValidationMiddleware(BaseHTTPMiddleware):
    """Validate RS256 bearer tokens on all non-public routes."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        jwks_cache: JWKSCache | None = None,
    ) -> None:
        super().__init__(app)
        self._jwks_cache = jwks_cache or JWKSCache()

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if _is_public_route(request):
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization", ""))
        if not token:
            return _unauthorized_response(request, MISSING_TOKEN, "Missing bearer token")

        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = str(unverified_header.get("kid", ""))
            key = await self._jwks_cache.get_key(kid)
            if key is None:
                raise jwt.InvalidTokenError("Unable to resolve signing key")

            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            )
            request.state.user_id = str(claims.get("sub", ""))
            request.state.user = claims
        except jwt.ExpiredSignatureError:
            return _unauthorized_response(request, TOKEN_EXPIRED, "Access token expired")
        except jwt.PyJWTError:
            return _unauthorized_response(request, INVALID_TOKEN, "Invalid access token")

        return await call_next(request)


def _is_public_route(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    return (request.method.upper(), request.url.path) in settings.public_route_allowlist


def _extract_bearer_token(header_value: str) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _unauthorized_response(request: Request, code: str, message: str) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    return JSONResponse(
        status_code=401,
        content={"code": code, "message": message, "request_id": request_id},
    )
