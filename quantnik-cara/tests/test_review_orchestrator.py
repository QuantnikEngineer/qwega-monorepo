from pathlib import Path

from cara.core.config import Settings
from cara.core.errors import ExternalServiceError
from cara.interfaces.report_storage import ReportStorageInterface
from cara.models.domain import (
    JiraIssueContext,
    JiraValidationResult,
    JiraValidationStatus,
    PersistedReviewReport,
    PullRequestContext,
    RepositoryScanContext,
    RepositoryScanJobRequest,
    ReviewAssessment,
    ReviewFinding,
    ReviewFindingCategory,
    ReviewIssueType,
    ReviewJobRequest,
    ReviewMode,
    ReviewOverallStatus,
    ReviewReport,
    ReviewSeverity,
    ReviewSource,
)
from cara.services.genai_service import UploadedContextFile
from cara.services.review_orchestrator import ReviewOrchestrator


class FakeGitHubService:
    def get_pull_request_context(self, owner: str, repo: str, pr_number: int) -> PullRequestContext:
        return PullRequestContext(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title="Implement login flow PROJ-123",
            body="Implements the requested authentication changes.",
            html_url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            head_sha="deadbeef",
            head_ref="feature/login",
            base_ref="main",
            diff="diff --git a/src/app.py b/src/app.py\n+print('ok')",
            files=[],
        )

    def download_repository_archive(
        self,
        owner: str,
        repo: str,
        ref: str,
        target_dir: Path,
    ) -> Path:
        repository_root = target_dir / f"{repo}-{ref}"
        repository_root.mkdir(parents=True)
        source_file = repository_root / "src" / "app.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("print('ok')\n", encoding="utf-8")
        return repository_root

    def collect_context_files(
        self,
        repository_root: Path,
        max_files: int,
        max_file_bytes: int,
        folder: str | None = None,
    ) -> list[Path]:
        return [repository_root / "src" / "app.py"]

    def get_repository_scan_context(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
        folder: str | None = None,
    ) -> RepositoryScanContext:
        return RepositoryScanContext(
            owner=owner,
            repo=repo,
            ref=ref or "main",
            folder=folder,
            head_sha="cafebabe",
            html_url=f"https://github.com/{owner}/{repo}",
            default_branch="main",
        )


class FakeJiraService:
    enabled = True

    def extract_issue_key(self, *texts: str | None) -> str | None:
        return "PROJ-123"

    def get_issue_context(self, issue_key: str) -> JiraIssueContext:
        return JiraIssueContext(
            issue_key=issue_key,
            summary="Implement login flow",
            description="Acceptance Criteria:\n- Add login endpoint\n- Add session validation",
            status="In Progress",
            acceptance_criteria=["Add login endpoint", "Add session validation"],
        )

    def build_not_evaluated_result(self, issue_key: str, reason: str) -> JiraValidationResult:
        return JiraValidationResult(
            issue_key=issue_key,
            status=JiraValidationStatus.NOT_EVALUATED,
            summary=reason,
            uncovered_requirements=[],
        )


class FakeGenAIService:
    def upload_context_files(
        self,
        repository_root: Path,
        files: list[Path],
    ) -> list[UploadedContextFile]:
        return [
            UploadedContextFile(
                path=files[0].relative_to(repository_root).as_posix(),
                uri="gs://fake/context-file",
                mime_type="text/plain",
                handle=object(),
            )
        ]

    def generate_review(
        self,
        pull_request: PullRequestContext,
        context_files: list[UploadedContextFile],
        jira_issue: JiraIssueContext | None,
    ) -> ReviewAssessment:
        return ReviewAssessment(
            overall_status=ReviewOverallStatus.NEEDS_ATTENTION,
            summary="The PR introduces a shell boundary that still needs validation.",
            strengths=["Repository context was available to the reviewer."],
            findings=[
                ReviewFinding(
                    title="Input validation gap",
                    severity=ReviewSeverity.MEDIUM,
                    category=ReviewFindingCategory.SECURITY,
                    description="The new command path accepts unsanitized input.",
                    recommendation="Validate the command arguments before use.",
                    file_path="src/app.py",
                    line_number=1,
                    issue_type=ReviewIssueType.SECURITY_VULNERABILITY,
                    severity_score=6,
                    comment="The new command path accepts unsanitized input.",
                    cwe_identifier="CWE-20",
                    suggested_remediation_code="sanitized_input = validate(user_input)",
                )
            ],
            jira_validation=(
                JiraValidationResult(
                    issue_key=jira_issue.issue_key,
                    status=JiraValidationStatus.PARTIALLY_ALIGNED,
                    summary="The login endpoint was added, but session validation is missing.",
                    uncovered_requirements=["Add session validation"],
                )
                if jira_issue is not None
                else None
            ),
        )

    def generate_repo_scan_review(
        self,
        scan_context: RepositoryScanContext,
        context_files: list[UploadedContextFile],
    ) -> ReviewAssessment:
        return ReviewAssessment(
            overall_status=ReviewOverallStatus.PASS,
            summary=(
                f"Repository scan of {scan_context.owner}/{scan_context.repo} "
                f"({scan_context.ref}) completed."
            ),
            strengths=["Folder layout follows conventions."],
            findings=[],
            jira_validation=None,
        )


class FailingGenAIService(FakeGenAIService):
    def generate_review(
        self,
        pull_request: PullRequestContext,
        context_files: list[UploadedContextFile],
        jira_issue: JiraIssueContext | None,
    ) -> ReviewAssessment:
        raise ExternalServiceError("Gemini was unavailable.")


class InMemoryReportStorage(ReportStorageInterface):
    def __init__(self) -> None:
        self.saved_reports: list[PersistedReviewReport] = []

    def save_report(self, report: ReviewReport) -> PersistedReviewReport:
        persisted = PersistedReviewReport(
            **report.model_dump(),
            version=len(self.saved_reports) + 1,
        )
        self.saved_reports.append(persisted)
        return persisted

    def get_report(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        version: int | None = None,
    ) -> PersistedReviewReport:
        target_version = version or len(self.saved_reports)
        return self.saved_reports[target_version - 1]

    def get_latest_version(self, owner: str, repo: str, pr_number: int) -> int | None:
        if not self.saved_reports:
            return None
        return self.saved_reports[-1].version


def test_review_orchestrator_persists_successful_reviews() -> None:
    storage = InMemoryReportStorage()
    orchestrator = ReviewOrchestrator(
        github_service=FakeGitHubService(),
        jira_service=FakeJiraService(),
        genai_service=FakeGenAIService(),
        storage=storage,
        settings=Settings(),
    )

    report = orchestrator.process_review(
        ReviewJobRequest(
            owner="acme",
            repo="rocket",
            pr_number=11,
            source=ReviewSource.WEBHOOK,
            trigger_event="opened",
        ),
    )

    assert report.version == 1
    assert report.overall_status == ReviewOverallStatus.NEEDS_ATTENTION
    assert report.jira_issue_key == "PROJ-123"
    assert report.context_files == ["src/app.py"]
    assert report.jira_validation is not None
    assert report.jira_validation.status == JiraValidationStatus.PARTIALLY_ALIGNED
    assert report.findings[0].issue_type == ReviewIssueType.SECURITY_VULNERABILITY
    assert report.findings[0].severity_score == 6


def test_review_orchestrator_persists_failures_as_reports() -> None:
    storage = InMemoryReportStorage()
    orchestrator = ReviewOrchestrator(
        github_service=FakeGitHubService(),
        jira_service=FakeJiraService(),
        genai_service=FailingGenAIService(),
        storage=storage,
        settings=Settings(),
    )

    report = orchestrator.process_review(
        ReviewJobRequest(
            owner="acme",
            repo="rocket",
            pr_number=12,
            source=ReviewSource.PROMPT,
            trigger_event="prompt",
        ),
    )

    assert report.version == 1
    assert report.overall_status == ReviewOverallStatus.FAILED
    assert report.findings[0].title == "Review pipeline failure"
    assert report.jira_validation is not None
    assert report.jira_validation.status == JiraValidationStatus.NOT_EVALUATED


def test_review_orchestrator_processes_repository_scan() -> None:
    storage = InMemoryReportStorage()
    orchestrator = ReviewOrchestrator(
        github_service=FakeGitHubService(),
        jira_service=FakeJiraService(),
        genai_service=FakeGenAIService(),
        storage=storage,
        settings=Settings(),
    )

    report = orchestrator.process_repo_scan(
        RepositoryScanJobRequest(
            owner="buildit",
            repo="ai-infusion-survey-ui",
            ref=None,
            folder="src",
            source=ReviewSource.PROMPT,
            trigger_event="prompt",
        ),
    )

    assert report.version == 1
    assert report.mode == ReviewMode.REPOSITORY
    assert report.pr_number == 0
    assert report.scanned_ref == "main"
    assert report.scanned_folder == "src"
    assert report.repository_url == "https://github.com/buildit/ai-infusion-survey-ui"
    assert report.reviewed_commit_sha == "cafebabe"
    assert report.overall_status == ReviewOverallStatus.PASS
    assert report.jira_validation is None
    assert report.context_files == ["src/app.py"]
