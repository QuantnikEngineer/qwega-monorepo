"""Harness Code REST client builder.

Harness Code API authenticates via the ``x-api-key`` header (Harness PAT).
We expose a thin builder so the service layer doesn't need to know about
``httpx`` configuration details.
"""

from __future__ import annotations

import logging

from cara.core.config import Settings
from cara.core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def build_harness_client(settings: Settings):
    """Return a configured ``httpx.Client`` plus a fresh-token provider."""
    try:
        import httpx
    except ImportError as exc:
        raise ConfigurationError(
            "httpx is not installed in the current environment.",
        ) from exc

    pat = settings.harness_pat_value
    account_id = settings.harness_account_id
    if pat is None or not account_id:
        raise ConfigurationError(
            "Harness Code is not configured. Set HARNESS_PAT and HARNESS_ACCOUNT_ID.",
        )

    base_url = settings.harness_base_url.rstrip("/")

    client = httpx.Client(
        base_url=base_url,
        headers={
            "x-api-key": pat,
            "Harness-Account": account_id,
            "Accept": "application/json",
            "User-Agent": "cara-ai-review-agent",
        },
        timeout=httpx.Timeout(30.0, connect=10.0),
    )

    def fresh_token() -> str:
        return pat

    return client, fresh_token
