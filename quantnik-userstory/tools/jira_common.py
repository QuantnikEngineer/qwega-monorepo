import os


class JiraConfigError(RuntimeError):
    """Raised when required Jira environment variables are missing or blank."""


def require_env(name: str) -> str:
    """Return a trimmed environment variable or raise a configuration error."""
    value = os.getenv(name)
    if value is None or not value.strip():
        raise JiraConfigError(
            f"Missing required Jira configuration: {name}. "
            "Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, and JIRA_PROJECT_KEY "
            "environment variables."
        )
    return value.strip()


def get_jira_config(require_project: bool = True) -> tuple[str, tuple[str, str], str | None]:
    """Return Jira base URL, basic auth tuple, and optional project key."""
    base_url = require_env("JIRA_BASE_URL").rstrip("/")
    email = require_env("JIRA_EMAIL")
    token = require_env("JIRA_API_TOKEN")
    project_key = require_env("JIRA_PROJECT_KEY") if require_project else os.getenv("JIRA_PROJECT_KEY")
    if project_key is not None:
        project_key = project_key.strip() or None
    return base_url, (email, token), project_key


def get_optional_jira_auth() -> tuple[str, str] | None:
    """Return Jira basic auth when both credentials are configured, else None."""
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not email or not email.strip() or not token or not token.strip():
        return None
    return email.strip(), token.strip()


def jira_config_error_result(exc: JiraConfigError) -> dict[str, str]:
    """Build the standard structured error result for Jira config problems."""
    return {"status": "error", "error_message": str(exc)}