"""Tool credential resolver — fetches decrypted secrets for Atlassian proxy auth.

For Jira and Confluence proxy routes, retrieves the project's encrypted PAT
token from auth-service and constructs a Basic auth header
(``base64(email:api-token)``).

Security: secrets are fetched over internal network with X-Internal-Key auth,
cached in-memory for 30s, never persisted to disk. Cache invalidates on
upstream 401 to handle credential rotation.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory cache: (project_id, tool_id) → (timestamp, (base_url, auth_header))
_cred_cache: dict[tuple[str, str], tuple[float, tuple[str, str]]] = {}


def _get_cached_creds(project_id: str, tool_id: str) -> tuple[str, str] | None:
    """Return cached (base_url, auth_header) if within TTL, else None."""
    key = (project_id, tool_id)
    entry = _cred_cache.get(key)
    if entry is None:
        return None
    ts, creds = entry
    if time.monotonic() - ts > settings.settings_cache_ttl:
        del _cred_cache[key]
        return None
    return creds


def _set_cached_creds(project_id: str, tool_id: str, creds: tuple[str, str]) -> None:
    _cred_cache[(project_id, tool_id)] = (time.monotonic(), creds)


def invalidate_cred_cache(project_id: str | None = None, tool_id: str | None = None) -> None:
    """Invalidate credential cache. Pass None for both to clear all."""
    if project_id and tool_id:
        _cred_cache.pop((project_id, tool_id), None)
    else:
        _cred_cache.clear()


async def resolve_atlassian_auth(project_id: str, tool_id: str) -> tuple[str, str] | None:
    """Fetch Atlassian credentials and construct Basic auth header.

    Returns ``(base_url, authorization_header)`` or ``None`` if tool not ready.
    The authorization header is ``Basic base64(email:patToken)``.
    """
    # Check cache first
    cached = _get_cached_creds(project_id, tool_id)
    if cached is not None:
        return cached

    # Fetch from auth-service internal secrets endpoint
    url = (
        f"{settings.auth_service_url.rstrip('/')}"
        f"/api/internal/project-secrets/{project_id}/{tool_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={"X-Internal-Key": settings.internal_api_key},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Secret fetch returned %s for project=%s tool=%s",
                    resp.status_code, project_id, tool_id,
                )
                return None

            data = resp.json()
    except Exception:
        logger.exception("Failed to fetch secrets for project=%s tool=%s", project_id, tool_id)
        return None

    config = data.get("config", {})
    email = config.get("email", "")
    pat_token = data.get("secrets", {}).get("patToken", "")
    base_url = config.get("url", "")

    if not email or not pat_token or not base_url:
        logger.warning(
            "Incomplete credentials for project=%s tool=%s (email=%s, pat=%s, url=%s)",
            project_id, tool_id, bool(email), bool(pat_token), bool(base_url),
        )
        return None

    # Construct Basic auth: base64(email:patToken)
    credentials = f"{email}:{pat_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded}"

    result = (base_url.rstrip("/"), auth_header)
    _set_cached_creds(project_id, tool_id, result)
    return result


async def resolve_atlassian_auth_with_retry(
    project_id: str, tool_id: str
) -> tuple[str, str] | None:
    """Resolve credentials, with one retry on cache miss after invalidation.

    Call this after receiving a 401 from upstream — it invalidates the cache
    and retries once to handle credential rotation.
    """
    invalidate_cred_cache(project_id, tool_id)
    return await resolve_atlassian_auth(project_id, tool_id)
