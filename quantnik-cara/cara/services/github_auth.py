from collections.abc import Callable
from typing import Any

from cara.core.config import Settings
from cara.core.errors import ConfigurationError


def build_github_client_and_token_provider(
    settings: Settings,
) -> tuple[Any, Callable[[], str]]:
    """Build a PyGithub client and a fresh-token provider from settings.

    Prefers GitHub App installation auth (auto-refreshing) when configured.
    Falls back to a static personal/installation token if provided.
    """
    try:
        from github import Auth, Github
    except ImportError as exc:
        raise ConfigurationError("PyGithub is not installed in the current environment.") from exc

    if settings.github_app_auth_configured:
        app_id = settings.github_app_id
        installation_id = settings.github_installation_id
        private_key = settings.github_private_key_value
        assert app_id is not None
        assert installation_id is not None
        assert private_key is not None

        app_auth = Auth.AppAuth(app_id=app_id, private_key=private_key)
        installation_auth = app_auth.get_installation_auth(installation_id)

        def fresh_app_token() -> str:
            return installation_auth.token

        return Github(auth=installation_auth), fresh_app_token

    static_token = settings.github_token_value
    if static_token is not None:
        token_value = static_token

        def fresh_static_token() -> str:
            return token_value

        return Github(auth=Auth.Token(token_value)), fresh_static_token

    raise ConfigurationError(
        "GitHub credentials are not configured. Set GITHUB_APP_ID + "
        "GITHUB_INSTALLATION_ID + GITHUB_PRIVATE_KEY (or GITHUB_PRIVATE_KEY_PATH), "
        "or fall back to GITHUB_TOKEN.",
    )
