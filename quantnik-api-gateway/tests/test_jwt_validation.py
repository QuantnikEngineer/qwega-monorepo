"""JWT validation and JWKS refresh behavior tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.jwt_validation import JWTValidationMiddleware
from app.services.jwks_cache import JWKSCache
from app.utils.error_codes import INVALID_TOKEN, MISSING_TOKEN, TOKEN_EXPIRED


def _make_rsa_pair() -> tuple[object, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(
    private_key: object,
    *,
    kid: str,
    expires_in_seconds: int,
    issuer: str = "quantnik-auth",
    audience: str = "quantnik-api",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": "user-123",
        "email": "user@wipro.com",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in_seconds),
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def _build_client(jwks_cache: JWKSCache) -> TestClient:
    app = FastAPI()
    app.add_middleware(JWTValidationMiddleware, jwks_cache=jwks_cache)

    @app.get("/api/protected")
    async def protected() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    return TestClient(app)


def test_protected_route_requires_bearer_token() -> None:
    """Protected route returns machine-readable 401 when token is missing."""
    jwks_cache = JWKSCache(fetcher=lambda: _async_jwks({"keys": []}), ttl_seconds=300)
    client = _build_client(jwks_cache)
    response = client.get("/api/protected")

    assert response.status_code == 401
    assert response.json()["code"] == MISSING_TOKEN


def test_expired_token_maps_to_token_expired_code() -> None:
    """Expired JWT returns deterministic token_expired code."""
    private_key, public_key = _make_rsa_pair()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwks_cache = JWKSCache(fetcher=lambda: _async_jwks({"keys": [{**jwk, "kid": "kid-1"}]}))
    client = _build_client(jwks_cache)
    token = _make_token(private_key, kid="kid-1", expires_in_seconds=-5)

    response = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == TOKEN_EXPIRED


def test_invalid_token_maps_to_invalid_token_code() -> None:
    """Signature/format failures map to invalid_token code."""
    jwks_cache = JWKSCache(fetcher=lambda: _async_jwks({"keys": []}), ttl_seconds=300)
    client = _build_client(jwks_cache)
    response = client.get("/api/protected", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["code"] == INVALID_TOKEN


def test_jwks_refreshes_on_kid_miss() -> None:
    """Gateway refreshes JWKS when requested kid is not in cached key set."""
    _, public_key_a = _make_rsa_pair()
    private_key_b, public_key_b = _make_rsa_pair()
    key_a = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key_a)), "kid": "kid-a"}
    key_b = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key_b)), "kid": "kid-b"}

    calls = {"count": 0}

    async def fetch_jwks() -> dict[str, Any]:
        calls["count"] += 1
        if calls["count"] == 1:
            return {"keys": [key_a]}
        return {"keys": [key_a, key_b]}

    jwks_cache = JWKSCache(fetcher=fetch_jwks, ttl_seconds=300)
    client = _build_client(jwks_cache)
    token = _make_token(private_key_b, kid="kid-b", expires_in_seconds=60)

    response = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls["count"] == 2


async def _async_jwks(payload: dict[str, Any]) -> dict[str, Any]:
    return payload
