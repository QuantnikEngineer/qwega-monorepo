from typing import Any, Literal

from pydantic import BaseModel, Field

from cara.models.domain import ReviewMode, ReviewSource


class PromptReviewRequest(BaseModel):
    command: str = Field(
        min_length=5,
        description=(
            "Natural language command describing which pull request or repository to scan."
        ),
        examples=[
            "Scan PR-11 of owner/xyz repository.",
            "Scan only the src folder of owner/xyz repository.",
        ],
    )


class AcceptedReviewResponse(BaseModel):
    status: Literal["accepted", "ignored"]
    message: str
    owner: str
    repo: str
    pr_number: int = 0
    source: ReviewSource
    mode: ReviewMode = ReviewMode.PULL_REQUEST
    ref: str | None = None
    folder: str | None = None


class ErrorResponse(BaseModel):
    code: str
    detail: str
    errors: list[dict[str, Any]] | None = None


class GitHubRepositoryOwnerPayload(BaseModel):
    login: str


class GitHubRepositoryPayload(BaseModel):
    name: str
    owner: GitHubRepositoryOwnerPayload


class GitHubPullRequestRefPayload(BaseModel):
    ref: str
    sha: str


class GitHubPullRequestPayload(BaseModel):
    number: int = Field(gt=0)
    title: str
    body: str | None = None
    html_url: str
    head: GitHubPullRequestRefPayload
    base: GitHubPullRequestRefPayload


class GitHubPullRequestWebhookPayload(BaseModel):
    action: str
    repository: GitHubRepositoryPayload
    pull_request: GitHubPullRequestPayload
