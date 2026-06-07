"""CapabilityMiddleware unit tests — scoped claims, flat fallback, bypass paths."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.capability_check import CapabilityMiddleware
from app.middleware.jwt_validation import JWTValidationMiddleware
from app.services.jwks_cache import JWKSCache
from app.utils.error_codes import INSUFFICIENT_CAPABILITY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KID = "test-kid-1"


def _make_rsa_pair() -> tuple[object, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_scoped_token(
    private_key: object,
    *,
    kid: str = _KID,
    platform_caps: list[str] | None = None,
    org_caps: list[str] | None = None,
    self_caps: list[str] | None = None,
    project_roles: dict | None = None,
    flat_caps: list[str] | None = None,
    expires_in_seconds: int = 300,
    issuer: str = "wega-auth",
    audience: str = "wega-api",
) -> str:
    """Generate a JWT with scoped capability claims."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": "user-123",
        "email": "user@wipro.com",
        "name": "Test User",
        "org_id": "org-123",
        "platform_capabilities": platform_caps or [],
        "org_capabilities": org_caps or [],
        "self_capabilities": self_caps or [],
        "project_roles": project_roles or {},
        "capabilities": flat_caps or [],
        "iat": now,
        "exp": now + timedelta(seconds=expires_in_seconds),
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


async def _async_jwks(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _build_capability_client(
    jwks_cache: JWKSCache,
    *,
    routes: list[tuple[str, str]] | None = None,
) -> TestClient:
    """Build a test client with both JWT and Capability middleware registered."""
    app = FastAPI()

    # LIFO: register CapabilityMiddleware first, then JWTValidation so JWT runs before Capability
    app.add_middleware(CapabilityMiddleware)
    app.add_middleware(JWTValidationMiddleware, jwks_cache=jwks_cache)

    # Default routes matching the route_capability_map
    @app.get("/api/users")
    async def get_users() -> JSONResponse:
        return JSONResponse({"ok": True, "route": "get_users"})

    @app.post("/api/users")
    async def create_user() -> JSONResponse:
        return JSONResponse({"ok": True, "route": "create_user"})

    @app.get("/api/unmapped-route")
    async def unmapped() -> JSONResponse:
        return JSONResponse({"ok": True, "route": "unmapped"})

    @app.get("/api/roles")
    async def get_roles() -> JSONResponse:
        return JSONResponse({"ok": True, "route": "get_roles"})

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    @app.post("/auth/activate")
    async def activate() -> JSONResponse:
        return JSONResponse({"ok": True, "route": "activate"})

    return TestClient(app)


def _make_jwks_cache(public_key: object, kid: str = _KID) -> JWKSCache:
    """Create a JWKS cache pre-loaded with the given public key."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    return JWKSCache(
        fetcher=lambda: _async_jwks({"keys": [{**jwk, "kid": kid}]}),
        ttl_seconds=300,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_route_without_capability_mapping_passes_through() -> None:
    """Request to an unmapped route with valid JWT passes through (auth-only)."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    token = _make_scoped_token(private_key)

    response = client.get(
        "/api/unmapped-route",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_route_with_capability_returns_403_when_missing() -> None:
    """Request to /api/users without required capability passes through.

    NOTE: As of D-21 update, /api/users mapping is set to None
    (backend-enforced auth).  Gateway passes through with auth-only check.
    This test verifies that behavior (200, not 403).
    """
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    # Token with NO capabilities — route_capability_map has None for /api/users
    token = _make_scoped_token(private_key)

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    # None mapping = auth-only, no capability check at gateway
    assert response.status_code == 200


def test_route_with_capability_passes_when_present_in_platform_caps() -> None:
    """JWT with platform_capabilities containing required cap passes through."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    token = _make_scoped_token(private_key, platform_caps=["org:manage_users"])

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_route_with_capability_passes_when_present_in_org_caps() -> None:
    """JWT with org_capabilities containing required cap passes through."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    token = _make_scoped_token(private_key, org_caps=["org:manage_users"])

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_route_with_capability_passes_with_flat_capabilities_fallback() -> None:
    """JWT with Phase 2 flat 'capabilities' claim passes through (backward compat)."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    token = _make_scoped_token(private_key, flat_caps=["org:manage_users"])

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_public_route_bypasses_capability_check() -> None:
    """Activation endpoint (public) bypasses capability check entirely."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)

    # No auth header at all — public route should pass through both middlewares
    response = client.post("/auth/activate")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_options_request_bypasses_capability_check() -> None:
    """OPTIONS request (CORS preflight) bypasses capability check."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)

    response = client.options("/api/users")
    # OPTIONS on public bypass returns 200 (no auth needed)
    assert response.status_code in (200, 405)  # FastAPI may return 405 for unhandled OPTIONS


def test_403_response_includes_required_capability() -> None:
    """Route with None mapping passes through (backend enforces auth).

    NOTE: As of D-21 update, /api/users mapping is set to None
    (backend-enforced auth).  Gateway no longer returns 403 for this route.
    This test verifies the pass-through behavior.
    """
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    token = _make_scoped_token(private_key)

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    # None mapping = pass-through to backend
    assert response.status_code == 200


def test_none_capability_route_passes_any_authenticated_user() -> None:
    """Routes mapped to None (e.g. GET /api/roles) pass for any authenticated user."""
    private_key, public_key = _make_rsa_pair()
    cache = _make_jwks_cache(public_key)
    client = _build_capability_client(cache)
    # Token with no capabilities at all — should still pass because route maps to None
    token = _make_scoped_token(private_key)

    response = client.get(
        "/api/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
