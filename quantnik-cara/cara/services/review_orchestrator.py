import logging
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from cara.core.config import Settings
from cara.core.errors import AppError
from cara.interfaces.report_storage import ReportStorageInterface
from cara.interfaces.repo_provider import RepoProvider
from cara.models.domain import (
    PersistedReviewReport,
    RepoProviderName,
    RepositoryScanJobRequest,
    ReviewFinding,
    ReviewFindingCategory,
    ReviewJobRequest,
    ReviewMode,
    ReviewOverallStatus,
    ReviewReport,
    ReviewSeverity,
)
from cara.services.genai_service import GenAIService
from cara.services.github_service import GitHubService
from cara.services.jira_service import JiraService

logger = logging.getLogger(__name__)


def _progress(stage: str, percent: int, message: str) -> dict[str, Any]:
    return {"event": "progress", "stage": stage, "percent": percent, "message": message}


def _complete(report: PersistedReviewReport) -> dict[str, Any]:
    return {"event": "complete", "report": report.model_dump(mode="json")}


def _error(detail: str) -> dict[str, Any]:
    return {"event": "error", "detail": detail}


class ReviewOrchestrator:
    def __init__(
        self,
        github_service: "GitHubService | RepoProvider | None" = None,
        jira_service: "JiraService | None" = None,
        genai_service: "GenAIService | None" = None,
        storage: "ReportStorageInterface | None" = None,
        settings: "Settings | None" = None,
        *,
        repo_provider_resolver: "Callable[[RepoProviderName], RepoProvider] | None" = None,
    ) -> None:
        # ``github_service`` is preserved as a keyword for backward compatibility
        # with tests and existing callers; it is treated as a default provider.
        self._default_provider = github_service
        self._provider_resolver = repo_provider_resolver
        self._jira_service = jira_service
        self._genai_service = genai_service
        self._storage = storage
        self._settings = settings

    def _resolve_provider(self, provider_name: "RepoProviderName | None" = None) -> "RepoProvider":
        """Pick the provider for the current job.

        - If a per-request resolver is configured, ask it for the named provider.
        - Otherwise fall back to the default provider supplied at construction
          time (legacy behaviour). When neither is set we fail loudly.
        """
        if self._provider_resolver is not None and provider_name is not None:
            return self._provider_resolver(provider_name)
        if self._default_provider is not None:
            return self._default_provider
        raise AppError("ReviewOrchestrator has no repository provider configured.")

    def process_review(self, job: ReviewJobRequest) -> PersistedReviewReport:
        pull_request = None
        jira_issue_key: str | None = None
        provider = self._resolve_provider(job.provider)

        try:
            logger.info(
                "review_started owner=%s repo=%s pr_number=%s source=%s provider=%s",
                job.owner,
                job.repo,
                job.pr_number,
                job.source,
                job.provider,
            )
            pull_request = provider.get_pull_request_context(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
            )
            jira_issue_key = self._jira_service.extract_issue_key(
                pull_request.title,
                pull_request.body,
            )
            jira_issue = None
            jira_validation_override = None
            if jira_issue_key is not None:
                if self._jira_service.enabled:
                    jira_issue = self._jira_service.get_issue_context(jira_issue_key)
                else:
                    jira_validation_override = self._jira_service.build_not_evaluated_result(
                        jira_issue_key,
                        "Jira credentials are not configured for this deployment.",
                    )

            with tempfile.TemporaryDirectory(prefix="cara-pr-") as temp_directory:
                repository_root = provider.download_repository_archive(
                    owner=job.owner,
                    repo=job.repo,
                    ref=pull_request.head_sha,
                    target_dir=Path(temp_directory),
                )
                context_files = provider.collect_context_files(
                    repository_root=repository_root,
                    max_files=self._settings.max_context_files,
                    max_file_bytes=self._settings.max_context_file_bytes,
                )
                uploaded_context = self._genai_service.upload_context_files(
                    repository_root=repository_root,
                    files=context_files,
                )
                review = self._genai_service.generate_review(
                    pull_request=pull_request,
                    context_files=uploaded_context,
                    jira_issue=jira_issue,
                )

            if jira_validation_override is not None:
                review.jira_validation = jira_validation_override

            report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=pull_request.html_url,
                reviewed_commit_sha=pull_request.head_sha,
                jira_issue_key=jira_issue_key,
                context_files=[context_file.path for context_file in uploaded_context],
                provider=job.provider,
                **review.model_dump(),
            )
            stored_report = self._storage.save_report(report)
            logger.info(
                "review_completed owner=%s repo=%s pr_number=%s version=%s",
                stored_report.owner,
                stored_report.repo,
                stored_report.pr_number,
                stored_report.version,
            )
            return stored_report
        except Exception as exc:
            logger.exception(
                "review_failed owner=%s repo=%s pr_number=%s error=%s",
                job.owner,
                job.repo,
                job.pr_number,
                exc,
            )
            failure_reason = exc.detail if isinstance(exc, AppError) else str(exc)
            failure_report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=pull_request.html_url if pull_request is not None else None,
                reviewed_commit_sha=pull_request.head_sha if pull_request is not None else None,
                jira_issue_key=jira_issue_key,
                context_files=[],
                provider=job.provider,
                overall_status=ReviewOverallStatus.FAILED,
                summary=f"Review execution failed: {failure_reason}",
                strengths=[],
                findings=[
                    ReviewFinding(
                        title="Review pipeline failure",
                        severity=ReviewSeverity.HIGH,
                        category=ReviewFindingCategory.OPERATIONAL,
                        description=failure_reason,
                        recommendation=(
                            "Inspect service credentials, remote integrations, and logs "
                            "before retrying."
                        ),
                    ),
                ],
                jira_validation=(
                    self._jira_service.build_not_evaluated_result(
                        jira_issue_key,
                        "The review pipeline failed before Jira validation completed.",
                    )
                    if jira_issue_key is not None
                    else None
                ),
            )
            return self._storage.save_report(failure_report)

    def process_repo_scan(self, job: RepositoryScanJobRequest) -> PersistedReviewReport:
        scan_context = None
        provider = self._resolve_provider(job.provider)

        try:
            logger.info(
                "repo_scan_started owner=%s repo=%s ref=%s folder=%s source=%s provider=%s",
                job.owner,
                job.repo,
                job.ref,
                job.folder,
                job.source,
                job.provider,
            )
            scan_context = provider.get_repository_scan_context(
                owner=job.owner,
                repo=job.repo,
                ref=job.ref,
                folder=job.folder,
            )

            with tempfile.TemporaryDirectory(prefix="cara-scan-") as temp_directory:
                repository_root = provider.download_repository_archive(
                    owner=job.owner,
                    repo=job.repo,
                    ref=scan_context.head_sha,
                    target_dir=Path(temp_directory),
                )
                context_files = provider.collect_context_files(
                    repository_root=repository_root,
                    max_files=self._settings.max_context_files,
                    max_file_bytes=self._settings.max_context_file_bytes,
                    folder=scan_context.folder,
                )
                uploaded_context = self._genai_service.upload_context_files(
                    repository_root=repository_root,
                    files=context_files,
                )
                review = self._genai_service.generate_repo_scan_review(
                    scan_context=scan_context,
                    context_files=uploaded_context,
                )

            report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=0,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=None,
                reviewed_commit_sha=scan_context.head_sha,
                jira_issue_key=None,
                context_files=[context_file.path for context_file in uploaded_context],
                mode=ReviewMode.REPOSITORY,
                scanned_ref=scan_context.ref,
                scanned_folder=scan_context.folder,
                repository_url=scan_context.html_url,
                provider=job.provider,
                **review.model_dump(),
            )
            stored_report = self._storage.save_report(report)
            logger.info(
                "repo_scan_completed owner=%s repo=%s ref=%s folder=%s version=%s",
                stored_report.owner,
                stored_report.repo,
                stored_report.scanned_ref,
                stored_report.scanned_folder,
                stored_report.version,
            )
            return stored_report
        except Exception as exc:
            logger.exception(
                "repo_scan_failed owner=%s repo=%s ref=%s folder=%s error=%s",
                job.owner,
                job.repo,
                job.ref,
                job.folder,
                exc,
            )
            failure_reason = exc.detail if isinstance(exc, AppError) else str(exc)
            failure_report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=0,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=None,
                reviewed_commit_sha=(
                    scan_context.head_sha if scan_context is not None else None
                ),
                jira_issue_key=None,
                context_files=[],
                mode=ReviewMode.REPOSITORY,
                scanned_ref=(
                    scan_context.ref if scan_context is not None else job.ref
                ),
                scanned_folder=(
                    scan_context.folder if scan_context is not None else job.folder
                ),
                repository_url=(
                    scan_context.html_url if scan_context is not None else None
                ),
                provider=job.provider,
                overall_status=ReviewOverallStatus.FAILED,
                summary=f"Repository scan execution failed: {failure_reason}",
                strengths=[],
                findings=[
                    ReviewFinding(
                        title="Repository scan pipeline failure",
                        severity=ReviewSeverity.HIGH,
                        category=ReviewFindingCategory.OPERATIONAL,
                        description=failure_reason,
                        recommendation=(
                            "Inspect service credentials, remote integrations, and logs "
                            "before retrying."
                        ),
                    ),
                ],
                jira_validation=None,
            )
            return self._storage.save_report(failure_report)

    # ── Streaming variants ────────────────────────────────────────────────────
    # These mirror process_review / process_repo_scan but yield progress events
    # at each major step so callers (the SSE endpoint) can stream live updates
    # to the client. The final yielded event is either {"event": "complete",
    # "report": ...} or {"event": "error", "detail": ...}. The persisted report
    # written to storage is identical to the non-streaming code path.

    def process_review_stream(
        self, job: ReviewJobRequest
    ) -> Iterator[dict[str, Any]]:
        pull_request = None
        jira_issue_key: str | None = None
        provider = self._resolve_provider(job.provider)
        try:
            yield _progress("resolve_pr", 5, "Resolving pull request metadata")
            logger.info(
                "review_started owner=%s repo=%s pr_number=%s source=%s provider=%s",
                job.owner,
                job.repo,
                job.pr_number,
                job.source,
                job.provider,
            )
            pull_request = provider.get_pull_request_context(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
            )

            yield _progress("jira_link", 15, "Linking Jira issue")
            jira_issue_key = self._jira_service.extract_issue_key(
                pull_request.title,
                pull_request.body,
            )
            jira_issue = None
            jira_validation_override = None
            if jira_issue_key is not None:
                if self._jira_service.enabled:
                    jira_issue = self._jira_service.get_issue_context(jira_issue_key)
                else:
                    jira_validation_override = self._jira_service.build_not_evaluated_result(
                        jira_issue_key,
                        "Jira credentials are not configured for this deployment.",
                    )

            with tempfile.TemporaryDirectory(prefix="cara-pr-") as temp_directory:
                yield _progress("download_repo", 25, "Downloading repository archive")
                repository_root = provider.download_repository_archive(
                    owner=job.owner,
                    repo=job.repo,
                    ref=pull_request.head_sha,
                    target_dir=Path(temp_directory),
                )
                yield _progress("collect_context", 45, "Collecting context files")
                context_files = provider.collect_context_files(
                    repository_root=repository_root,
                    max_files=self._settings.max_context_files,
                    max_file_bytes=self._settings.max_context_file_bytes,
                )
                yield _progress("upload_context", 60, "Uploading context to Gemini")
                uploaded_context = self._genai_service.upload_context_files(
                    repository_root=repository_root,
                    files=context_files,
                )
                yield _progress("generate_review", 80, "Generating AI review")
                review = self._genai_service.generate_review(
                    pull_request=pull_request,
                    context_files=uploaded_context,
                    jira_issue=jira_issue,
                )

            if jira_validation_override is not None:
                review.jira_validation = jira_validation_override

            yield _progress("persist_report", 95, "Persisting review report")
            report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=pull_request.html_url,
                reviewed_commit_sha=pull_request.head_sha,
                jira_issue_key=jira_issue_key,
                context_files=[context_file.path for context_file in uploaded_context],
                provider=job.provider,
                **review.model_dump(),
            )
            stored_report = self._storage.save_report(report)
            logger.info(
                "review_completed owner=%s repo=%s pr_number=%s version=%s",
                stored_report.owner,
                stored_report.repo,
                stored_report.pr_number,
                stored_report.version,
            )
            yield _complete(stored_report)
        except Exception as exc:
            logger.exception(
                "review_failed owner=%s repo=%s pr_number=%s error=%s",
                job.owner,
                job.repo,
                job.pr_number,
                exc,
            )
            failure_reason = exc.detail if isinstance(exc, AppError) else str(exc)
            failure_report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=job.pr_number,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=pull_request.html_url if pull_request is not None else None,
                reviewed_commit_sha=pull_request.head_sha if pull_request is not None else None,
                jira_issue_key=jira_issue_key,
                context_files=[],
                provider=job.provider,
                overall_status=ReviewOverallStatus.FAILED,
                summary=f"Review execution failed: {failure_reason}",
                strengths=[],
                findings=[
                    ReviewFinding(
                        title="Review pipeline failure",
                        severity=ReviewSeverity.HIGH,
                        category=ReviewFindingCategory.OPERATIONAL,
                        description=failure_reason,
                        recommendation=(
                            "Inspect service credentials, remote integrations, and logs "
                            "before retrying."
                        ),
                    ),
                ],
                jira_validation=(
                    self._jira_service.build_not_evaluated_result(
                        jira_issue_key,
                        "The review pipeline failed before Jira validation completed.",
                    )
                    if jira_issue_key is not None
                    else None
                ),
            )
            stored_failure = self._storage.save_report(failure_report)
            yield _error(failure_reason)
            yield _complete(stored_failure)

    def process_repo_scan_stream(
        self, job: RepositoryScanJobRequest
    ) -> Iterator[dict[str, Any]]:
        scan_context = None
        provider = self._resolve_provider(job.provider)
        try:
            yield _progress("resolve_repo", 5, "Resolving repository metadata")
            logger.info(
                "repo_scan_started owner=%s repo=%s ref=%s folder=%s source=%s provider=%s",
                job.owner,
                job.repo,
                job.ref,
                job.folder,
                job.source,
                job.provider,
            )
            scan_context = provider.get_repository_scan_context(
                owner=job.owner,
                repo=job.repo,
                ref=job.ref,
                folder=job.folder,
            )

            with tempfile.TemporaryDirectory(prefix="cara-scan-") as temp_directory:
                yield _progress("download_repo", 25, "Downloading repository archive")
                repository_root = provider.download_repository_archive(
                    owner=job.owner,
                    repo=job.repo,
                    ref=scan_context.head_sha,
                    target_dir=Path(temp_directory),
                )
                yield _progress("collect_context", 45, "Collecting context files")
                context_files = provider.collect_context_files(
                    repository_root=repository_root,
                    max_files=self._settings.max_context_files,
                    max_file_bytes=self._settings.max_context_file_bytes,
                    folder=scan_context.folder,
                )
                yield _progress("upload_context", 60, "Uploading context to Gemini")
                uploaded_context = self._genai_service.upload_context_files(
                    repository_root=repository_root,
                    files=context_files,
                )
                yield _progress("generate_review", 80, "Generating AI scan review")
                review = self._genai_service.generate_repo_scan_review(
                    scan_context=scan_context,
                    context_files=uploaded_context,
                )

            yield _progress("persist_report", 95, "Persisting scan report")
            report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=0,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=None,
                reviewed_commit_sha=scan_context.head_sha,
                jira_issue_key=None,
                context_files=[context_file.path for context_file in uploaded_context],
                mode=ReviewMode.REPOSITORY,
                scanned_ref=scan_context.ref,
                scanned_folder=scan_context.folder,
                repository_url=scan_context.html_url,
                provider=job.provider,
                **review.model_dump(),
            )
            stored_report = self._storage.save_report(report)
            logger.info(
                "repo_scan_completed owner=%s repo=%s ref=%s folder=%s version=%s",
                stored_report.owner,
                stored_report.repo,
                stored_report.scanned_ref,
                stored_report.scanned_folder,
                stored_report.version,
            )
            yield _complete(stored_report)
        except Exception as exc:
            logger.exception(
                "repo_scan_failed owner=%s repo=%s ref=%s folder=%s error=%s",
                job.owner,
                job.repo,
                job.ref,
                job.folder,
                exc,
            )
            failure_reason = exc.detail if isinstance(exc, AppError) else str(exc)
            failure_report = ReviewReport(
                owner=job.owner,
                repo=job.repo,
                pr_number=0,
                source=job.source,
                trigger_event=job.trigger_event,
                pull_request_url=None,
                reviewed_commit_sha=(
                    scan_context.head_sha if scan_context is not None else None
                ),
                jira_issue_key=None,
                context_files=[],
                mode=ReviewMode.REPOSITORY,
                scanned_ref=(
                    scan_context.ref if scan_context is not None else job.ref
                ),
                scanned_folder=(
                    scan_context.folder if scan_context is not None else job.folder
                ),
                repository_url=(
                    scan_context.html_url if scan_context is not None else None
                ),
                provider=job.provider,
                overall_status=ReviewOverallStatus.FAILED,
                summary=f"Repository scan execution failed: {failure_reason}",
                strengths=[],
                findings=[
                    ReviewFinding(
                        title="Repository scan pipeline failure",
                        severity=ReviewSeverity.HIGH,
                        category=ReviewFindingCategory.OPERATIONAL,
                        description=failure_reason,
                        recommendation=(
                            "Inspect service credentials, remote integrations, and logs "
                            "before retrying."
                        ),
                    ),
                ],
                jira_validation=None,
            )
            stored_failure = self._storage.save_report(failure_report)
            yield _error(failure_reason)
            yield _complete(stored_failure)
