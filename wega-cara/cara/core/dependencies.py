from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from cara.core.config import Settings, get_settings
from cara.core.errors import ConfigurationError
from cara.interfaces.report_storage import ReportStorageInterface
from cara.interfaces.repo_provider import RepoProvider
from cara.models.domain import RepoProviderName
from cara.services.genai_service import GenAIService
from cara.services.github_auth import build_github_client_and_token_provider
from cara.services.github_service import GitHubService
from cara.services.jira_service import JiraService
from cara.services.report_storage import LocalFilesystemReportStorage
from cara.services.repo_provider_factory import build_provider
from cara.services.review_orchestrator import ReviewOrchestrator


def get_report_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportStorageInterface:
    return LocalFilesystemReportStorage(base_path=settings.reports_base_path)


def get_github_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GitHubService:
    """Back-compat factory used by the GitHub-specific webhook router.

    For provider-agnostic code paths prefer ``resolve_repo_provider`` below.
    """
    client, token_provider = build_github_client_and_token_provider(settings)
    return GitHubService(client=client, token_provider=token_provider, settings=settings)


def resolve_repo_provider(
    provider: RepoProviderName,
    settings: Settings,
) -> RepoProvider:
    """Construct a repo provider on demand for a specific request."""
    return build_provider(provider, settings)


def get_repo_provider_resolver(
    github_service: Annotated[GitHubService, Depends(get_github_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Callable[[RepoProviderName], RepoProvider]:
    """Build a per-request resolver that returns a ``RepoProvider`` by name.

    Routes the GitHub case through the existing ``get_github_service``
    dependency so test overrides on that symbol keep working unchanged.
    Harness providers are constructed fresh because they have no equivalent
    long-lived DI factory.
    """

    def _resolve(provider_name: RepoProviderName) -> RepoProvider:
        if provider_name == RepoProviderName.GITHUB:
            return github_service
        return resolve_repo_provider(provider_name, settings)

    return _resolve


def get_jira_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> JiraService:
    if (
        settings.jira_server_url is None
        or settings.jira_username is None
        or settings.jira_api_token_value is None
    ):
        return JiraService(client=None)

    try:
        from jira import JIRA
    except ImportError as exc:
        raise ConfigurationError("jira is not installed in the current environment.") from exc

    return JiraService(
        client=JIRA(
            server=settings.jira_server_url,
            basic_auth=(settings.jira_username, settings.jira_api_token_value),
        ),
    )


def get_genai_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenAIService:
    api_key = settings.google_api_key_value
    if api_key is None:
        raise ConfigurationError("GOOGLE_API_KEY must be configured to invoke Gemini.")

    try:
        from google import genai
    except ImportError as exc:
        raise ConfigurationError(
            "google-genai is not installed in the current environment.",
        ) from exc

    return GenAIService(client=genai.Client(api_key=api_key), settings=settings)


def get_review_orchestrator(
    jira_service: Annotated[JiraService, Depends(get_jira_service)],
    genai_service: Annotated[GenAIService, Depends(get_genai_service)],
    storage: Annotated[ReportStorageInterface, Depends(get_report_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReviewOrchestrator:
    """Build a ReviewOrchestrator that resolves repo providers per request.

    Each invocation of ``process_review`` / ``process_repo_scan`` looks up the
    right provider via the closure below; constructing a GitHub client at DI
    time would force every Harness-only review to also load PyGithub.
    """
    def _resolve(provider_name: RepoProviderName):
        return resolve_repo_provider(provider_name, settings)

    return ReviewOrchestrator(
        repo_provider_resolver=_resolve,
        jira_service=jira_service,
        genai_service=genai_service,
        storage=storage,
        settings=settings,
    )
