"""ToolAdapter — declarative contract for a tool's proxy behavior.

Consolidates all tool-specific proxy metadata in one place:
upstream path prefix and extra static headers.
The gateway TOOL_ADAPTERS dict is the explicit security allowlist
for which tools can be proxied.

Auth strategy is owned by the auth-service (stored in service_registry
default_config._auth_type). The gateway does not duplicate it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolAdapter:
    """Immutable descriptor for a tool's proxy behavior."""

    tool_id: str
    prefix: str                                       # gateway route prefix, e.g. "/jira"
    upstream_path_prefix: str = ""                    # appended between base_url and request path
    extra_headers: dict[str, str] = field(default_factory=dict)
