"""Harness Code webhook handler.

Listens for ``pullreq_*`` events from Harness Code and queues a review job
through the same ``ReviewOrchestrator`` used for GitHub. The handler is
explicitly opt-in: when ``HARNESS_WEBHOOK_SECRET`` is unset, signature
verification is skipped (matches GitHub's behaviour).

Harness sends webhook payloads with a top-level ``trigger`` field naming the
event (e.g. ``pullreq_created``, ``pullreq_branch_updated``) and a
``pull_request`` block containing identifiers. The integration is intentionally
defensive about the schema because Harness's webhook payload has been evolving.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from cara.core.config import Settings, get_settings
from cara.core.dependencies import get_review_orchestrator
from cara.core.errors import BadRequestError
from cara.models.api import AcceptedReviewResponse, ErrorResponse
from cara.models.domain import RepoProviderName, ReviewJobRequest, ReviewSource
from cara.services.harness_code_service import verify_webhook_signature
from cara.services.review_orchestrator import ReviewOrchestrator

logger = logging.getLogger(__name__)

SUPPORTED_TRIGGERS = {
    "pullreq_created",
    "pullreq_reopened",
    "pullreq_branch_updated",
    "pullreq_updated",
}

router = APIRouter(tags=["Webhooks"])


def _extract_repo_identifier(payload: dict[str, Any]) -> tuple[str, str]:
    """Return ``(owner, repo)`` derived from a Harness webhook payload.

    Harness identifies repos by ``{org}/{project}/{repo}`` so we pack
    ``org/project`` into ``owner`` and use ``repo_identifier`` as ``repo`` to
    keep the existing CARA model untouched.
    """
    repo_block = payload.get("repo") or payload.get("repository") or {}
    org = (
        repo_block.get("org_identifier")
        or repo_block.get("orgIdentifier")
        or payload.get("org_identifier")
        or payload.get("orgIdentifier")
    )
    project = (
        repo_block.get("project_identifier")
        or repo_block.get("projectIdentifier")
        or payload.get("project_identifier")
        or payload.get("projectIdentifier")
    )
    repo_id = (
        repo_block.get("identifier")
        or repo_block.get("repo_identifier")
        or repo_block.get("name")
    )
    if not org or not project or not repo_id:
        raise BadRequestError(
            "Harness webhook payload is missing org/project/repo identifiers.",
        )
    return f"{org}/{project}", repo_id


def _extract_pr_number(payload: dict[str, Any]) -> int:
    pr_block = payload.get("pull_request") or payload.get("pullreq") or {}
    number = pr_block.get("number") or pr_block.get("id") or payload.get("number")
    if number is None:
        raise BadRequestError("Harness webhook payload is missing pull_request.number.")
    try:
        return int(number)
    except (TypeError, ValueError) as exc:
        raise BadRequestError("Harness pull request number is not an integer.") from exc


@router.post(
    "/webhook/harness",
    response_model=AcceptedReviewResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    status_code=status.HTTP_202_ACCEPTED,
)
async def handle_harness_pullreq_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    orchestrator: Annotated[ReviewOrchestrator, Depends(get_review_orchestrator)],
) -> AcceptedReviewResponse:
    raw_body = await request.body()
    verify_webhook_signature(
        settings.harness_webhook_secret_value,
        raw_body,
        request.headers.get("X-Harness-Signature")
        or request.headers.get("X-Harness-Trigger-Signature"),
    )

    try:
        import json

        payload = json.loads(raw_body or b"{}")
    except ValueError as exc:
        raise BadRequestError("Harness webhook payload is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise BadRequestError("Harness webhook payload must be a JSON object.")

    trigger = (
        payload.get("trigger")
        or payload.get("event")
        or request.headers.get("X-Harness-Trigger")
        or ""
    )
    trigger = str(trigger).lower()

    owner, repo = _extract_repo_identifier(payload)
    pr_number = _extract_pr_number(payload)

    if trigger not in SUPPORTED_TRIGGERS:
        logger.info(
            "harness_webhook_ignored trigger=%s owner=%s repo=%s pr_number=%s",
            trigger,
            owner,
            repo,
            pr_number,
        )
        return AcceptedReviewResponse(
            status="ignored",
            message=f"Harness pull request trigger '{trigger}' is ignored.",
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
            trigger_event=trigger,
            provider=RepoProviderName.HARNESS,
        ),
    )
    return AcceptedReviewResponse(
        status="accepted",
        message="Harness pull request review queued from webhook.",
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        source=ReviewSource.WEBHOOK,
    )
