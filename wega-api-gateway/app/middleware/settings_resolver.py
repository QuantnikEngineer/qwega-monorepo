"""Project settings resolver — injects tool config as headers for downstream services.

For non-auth-service requests with an X-Project-Id header, fetches the project's
enabled tool configuration from auth-service and injects them as X-Tool-* headers.
Strips any inbound X-Tool-* headers to prevent spoofing.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Header prefix for tool config injection
_TOOL_HEADER_PREFIX = "x-tool-"

# Known tool-to-header mappings (tool_id → {config_key → header_name})
TOOL_HEADER_MAP: dict[str, dict[str, str]] = {
    "jira": {
        "url": "X-Jira-Base-Url",
        "projectKey": "X-Jira-Project-Key",
    },
    "confluence": {
        "url": "X-Confluence-Base-Url",
        "spaceKey": "X-Confluence-Space-Key",
    },
    "github": {
        "url": "X-Github-Repo-Url",
    },
    "sonarqube": {
        "url": "X-Sonarqube-Url",
    },
    "qtest": {
        "url": "X-Qtest-Api-Url",
        "qtestProjectId": "X-Qtest-Project-Id",
    },
    "sharepoint": {
        "url": "X-Sharepoint-Site-Url",
    },
    "harness-pipelines": {
        "url": "X-Harness-Url",
        "accountId": "X-Harness-Account-Id",
        "orgIdentifier": "X-Harness-Org-Id",
        "projectIdentifier": "X-Harness-Project-Id",
    },
    "harness-repo": {
        "url": "X-Harness-Repo-Url",
        "accountId": "X-Harness-Repo-Account-Id",
        "orgIdentifier": "X-Harness-Repo-Org-Id",
        "repoIdentifier": "X-Harness-Repo-Identifier",
    },
    "snyk": {
        "orgId": "X-Snyk-Org-Id",
    },
    "trivy": {
        "serverUrl": "X-Trivy-Server-Url",
    },
}

# In-memory cache: project_id → (timestamp, tools_dict)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _get_cached(project_id: str) -> dict[str, Any] | None:
    """Return cached tools if within TTL, else None."""
    entry = _cache.get(project_id)
    if entry is None:
        return None
    ts, tools = entry
    if time.monotonic() - ts > settings.settings_cache_ttl:
        del _cache[project_id]
        return None
    return tools


def _set_cached(project_id: str, tools: dict[str, Any]) -> None:
    _cache[project_id] = (time.monotonic(), tools)


def invalidate_cache(project_id: str | None = None) -> None:
    """Invalidate project settings cache. Pass None to clear all."""
    if project_id:
        _cache.pop(project_id, None)
    else:
        _cache.clear()


async def fetch_project_tool_config(project_id: str) -> dict[str, Any]:
    """Fetch non-secret tool config from auth-service internal endpoint."""
    cached = _get_cached(project_id)
    if cached is not None:
        return cached

    url = f"{settings.auth_service_url.rstrip('/')}/api/internal/project-settings/{project_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={"X-Internal-Key": settings.internal_api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                tools = data.get("tools", {})
                _set_cached(project_id, tools)
                return tools
            logger.warning("Settings fetch returned %s for project %s", resp.status_code, project_id)
    except Exception:
        logger.exception("Failed to fetch project settings for %s", project_id)

    return {}


def strip_tool_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove any inbound X-Tool-* headers to prevent client spoofing."""
    return {k: v for k, v in headers.items() if not k.lower().startswith(_TOOL_HEADER_PREFIX)}


def inject_tool_headers(headers: dict[str, str], tools: dict[str, Any]) -> dict[str, str]:
    """Add X-Tool-* headers based on project tool configuration."""
    result = dict(headers)
    for tool_id, config in tools.items():
        mapping = TOOL_HEADER_MAP.get(tool_id, {})
        if not isinstance(config, dict):
            continue
        for config_key, header_name in mapping.items():
            value = config.get(config_key)
            if value:
                result[header_name] = str(value)
    return result
