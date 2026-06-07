from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import ValidationError

from cara.core.config import Settings, get_settings
from cara.core.dependencies import get_review_orchestrator
from cara.core.errors import BadRequestError
from cara.models.api import AcceptedReviewResponse, ErrorResponse, GitHubPullRequestWebhookPayload
from cara.models.domain import ReviewJobRequest, ReviewSource
from cara.services.github_service import verify_webhook_signature
from cara.services.review_orchestrator import ReviewOrchestrator

SUPPORTED_ACTIONS = {"opened", "synchronize"}

router = APIRouter(tags=["Webhooks"])


@router.post(
    "/webhook",
    response_model=AcceptedReviewResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    status_code=status.HTTP_202_ACCEPTED,
)
async def handle_github_pull_request_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    orchestrator: Annotated[ReviewOrchestrator, Depends(get_review_orchestrator)],
) -> AcceptedReviewResponse:
    raw_body = await request.body()
    verify_webhook_signature(
        settings.github_webhook_secret_value,
        raw_body,
        request.headers.get("X-Hub-Signature-256"),
    )

    if request.headers.get("X-GitHub-Event") != "pull_request":
        raise BadRequestError("Only GitHub pull_request webhooks are supported.")

    try:
        payload = GitHubPullRequestWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise BadRequestError("Invalid GitHub pull request webhook payload.") from exc

    owner = payload.repository.owner.login
    repo = payload.repository.name
    pr_number = payload.pull_request.number

    if payload.action not in SUPPORTED_ACTIONS:
        return AcceptedReviewResponse(
            status="ignored",
            message=f"Pull request action '{payload.action}' is ignored.",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            source=ReviewSource.WEBHOOK,
        )

    background_tasks.add_task(
        orchestrator.process_review,
        ReviewJobRequest(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            source=ReviewSource.WEBHOOK,
            trigger_event=payload.action,
        ),
    )
    return AcceptedReviewResponse(
        status="accepted",
        message="Pull request review queued from webhook.",
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        source=ReviewSource.WEBHOOK,
    )
