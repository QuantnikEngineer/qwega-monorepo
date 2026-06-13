"""JWKS cache with refresh-on-kid-miss behavior."""

from __future__ import annotations

import json
import time
from typing import Awaitable, Callable

import httpx
from jwt.algorithms import RSAAlgorithm

from app.config import settings

JWKSFetcher = Callable[[], Awaitable[dict]]


class JWKSCache:
    """Cache JWKS keys and refresh when cache expires or key is missing."""

    def __init__(
        self,
        *,
        ttl_seconds: int | None = None,
        fetcher: JWKSFetcher | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.jwks_cache_ttl_seconds
        self._fetcher = fetcher or self._fetch_jwks
        self._clock = clock or time.monotonic
        self._keys_by_kid: dict[str, object] = {}
        self._expires_at = 0.0

    async def get_key(self, kid: str) -> object | None:
        """Resolve public key by kid, refreshing cache on miss."""
        if not kid:
            return None

        if self._is_expired():
            await self.refresh()

        key = self._keys_by_kid.get(kid)
        if key is not None:
            return key

        await self.refresh(force=True)
        return self._keys_by_kid.get(kid)

    async def refresh(self, *, force: bool = False) -> None:
        """Refresh key cache from upstream JWKS endpoint."""
        if not force and not self._is_expired():
            return

        jwks_payload = await self._fetcher()
        self._keys_by_kid = _parse_jwks_keys(jwks_payload)
        self._expires_at = self._clock() + max(self._ttl_seconds, 1)

    async def _fetch_jwks(self) -> dict:
        upstream_url = f"{settings.auth_service_url.rstrip('/')}/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(upstream_url)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("JWKS payload must be a JSON object")
            return payload

    def _is_expired(self) -> bool:
        return self._clock() >= self._expires_at


def _parse_jwks_keys(payload: dict) -> dict[str, object]:
    keys = payload.get("keys")
    if not isinstance(keys, list):
        return {}

    resolved: dict[str, object] = {}
    for jwk in keys:
        if not isinstance(jwk, dict):
            continue
        kid = jwk.get("kid")
        if not kid:
            continue
        try:
            resolved[str(kid)] = RSAAlgorithm.from_jwk(json.dumps(jwk))
        except Exception:  # noqa: BLE001
            continue

    return resolved
