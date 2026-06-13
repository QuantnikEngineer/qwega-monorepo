from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewSource(StrEnum):
    WEBHOOK = "webhook"
    PROMPT = "prompt"


class ReviewMode(StrEnum):
    PULL_REQUEST = "pull_request"
    REPOSITORY = "repository"


class ReviewOverallStatus(StrEnum):
    PASS = "pass"
    NEEDS_ATTENTION = "needs_attention"
    FAILED = "failed"


class ReviewSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewIssueType(StrEnum):
    SECURITY_VULNERABILITY = "Security_Vulnerability"
    BUG = "Bug"
    MISSING_BEST_PRACTICE = "Missing_Best_Practice"


class ReviewFindingCategory(StrEnum):
    SECURITY = "security"
    QUALITY = "quality"
    BEST_PRACTICE = "best_practice"
    JIRA_ALIGNMENT = "jira_alignment"
    OPERATIONAL = "operational"


class JiraValidationStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIALLY_ALIGNED = "partially_aligned"
    NOT_ALIGNED = "not_aligned"
    NOT_EVALUATED = "not_evaluated"


class RepoProviderName(StrEnum):
    """SCM provider hosting the repository under review.

    The default is ``github`` so older clients, persisted reports, and tests
    that pre-date Harness Code support continue to work unchanged.
    """

    GITHUB = "github"
    HARNESS = "harness"


class PromptScanReference(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    owner: str
    repo: str
    pr_number: int = 0
    ref: str | None = None
    folder: str | None = None
    provider: RepoProviderName = RepoProviderName.GITHUB


class ReviewFinding(BaseModel):
    title: str = Field(min_length=1)
    severity: ReviewSeverity
    category: ReviewFindingCategory
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    file_path: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    issue_type: ReviewIssueType | None = None
    severity_score: int | None = Field(default=None, ge=1, le=10)
    comment: str | None = None
    cwe_identifier: str | None = None
    suggested_remediation_code: str | None = None


class JiraValidationResult(BaseModel):
    issue_key: str
    status: JiraValidationStatus
    summary: str
    uncovered_requirements: list[str] = Field(default_factory=list)


class ReviewAssessment(BaseModel):
    overall_status: ReviewOverallStatus
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    jira_validation: JiraValidationResult | None = None


class ReviewReport(ReviewAssessment):
    owner: str
    repo: str
    pr_number: int = Field(default=0, ge=0)
    source: ReviewSource
    trigger_event: str | None = None
    pull_request_url: str | None = None
    reviewed_commit_sha: str | None = None
    jira_issue_key: str | None = None
    context_files: list[str] = Field(default_factory=list)
    mode: ReviewMode = ReviewMode.PULL_REQUEST
    scanned_ref: str | None = None
    scanned_folder: str | None = None
    repository_url: str | None = None
    provider: RepoProviderName = RepoProviderName.GITHUB


class PersistedReviewReport(ReviewReport):
    version: int = Field(gt=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewJobRequest(BaseModel):
    owner: str
    repo: str
    pr_number: int = Field(gt=0)
    source: ReviewSource
    trigger_event: str | None = None
    provider: RepoProviderName = RepoProviderName.GITHUB


class RepositoryScanJobRequest(BaseModel):
    owner: str
    repo: str
    ref: str | None = None
    folder: str | None = None
    source: ReviewSource
    trigger_event: str | None = None
    provider: RepoProviderName = RepoProviderName.GITHUB


class PullRequestFileChange(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None


class PullRequestContext(BaseModel):
    owner: str
    repo: str
    pr_number: int
    title: str
    body: str | None = None
    html_url: str
    head_sha: str
    head_ref: str
    base_ref: str
    diff: str
    files: list[PullRequestFileChange] = Field(default_factory=list)


class JiraIssueContext(BaseModel):
    issue_key: str
    summary: str
    description: str | None = None
    status: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class RepositoryScanContext(BaseModel):
    owner: str
    repo: str
    ref: str
    folder: str | None = None
    head_sha: str
    html_url: str
    default_branch: str | None = None
