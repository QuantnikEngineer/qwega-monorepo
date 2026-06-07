"""Per-request factory that resolves the right ``RepoProvider``.

Routing rules (first match wins):

1. Caller-supplied ``provider`` field on the reference / job request.
2. URL-pattern fallback when the natural-language command mentions a Harness
   host (``git.harness.io`` or ``app.harness.io/.../code/...``).
3. Default to GitHub.
"""

from __future__ import annotations

import re

from cara.core.config import Settings
from cara.core.errors import ConfigurationError
from cara.interfaces.repo_provider import RepoProvider
from cara.models.domain import RepoProviderName

_HARNESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"git\.harness\.io", re.IGNORECASE),
    re.compile(r"app\.harness\.io/[^\s]*?/code/", re.IGNORECASE),
    re.compile(r"app\.harness\.io/[^\s]*?/orgs/[^\s]*?/projects/[^\s]*?/repos/", re.IGNORECASE),
)


def detect_provider_from_text(text: str | None) -> RepoProviderName:
    """Best-effort URL/text scanner used by the prompt extractor."""
    if not text:
        return RepoProviderName.GITHUB
    for pattern in _HARNESS_PATTERNS:
        if pattern.search(text):
            return RepoProviderName.HARNESS
    return RepoProviderName.GITHUB


def build_provider(provider_name: RepoProviderName, settings: Settings) -> RepoProvider:
    """Return a provider implementation for ``provider_name``.

    ``GitHubService`` and ``HarnessCodeService`` are imported lazily so a
    GitHub-only deployment never triggers Harness configuration errors at
    import time, and vice versa.
    """
    if provider_name == RepoProviderName.GITHUB:
        from cara.services.github_auth import build_github_client_and_token_provider
        from cara.services.github_service import GitHubService

        client, token_provider = build_github_client_and_token_provider(settings)
        return GitHubService(client=client, token_provider=token_provider, settings=settings)

    if provider_name == RepoProviderName.HARNESS:
        if not settings.harness_configured:
            raise ConfigurationError(
                "Harness Code is not configured. Set HARNESS_PAT and HARNESS_ACCOUNT_ID.",
            )
        from cara.services.harness_code_auth import build_harness_client
        from cara.services.harness_code_service import HarnessCodeService

        client, token_provider = build_harness_client(settings)
        return HarnessCodeService(client=client, token_provider=token_provider, settings=settings)

    raise ConfigurationError(f"Unsupported repository provider: {provider_name!r}")
