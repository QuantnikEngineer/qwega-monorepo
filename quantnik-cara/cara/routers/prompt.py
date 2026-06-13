import json
import logging
from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse

from cara.core.dependencies import (
    get_genai_service,
    get_repo_provider_resolver,
    get_review_orchestrator,
)
from cara.interfaces.repo_provider import RepoProvider
from cara.models.api import AcceptedReviewResponse, ErrorResponse, PromptReviewRequest
from cara.models.domain import (
    RepoProviderName,
    RepositoryScanJobRequest,
    ReviewJobRequest,
    ReviewMode,
    ReviewSource,
)
from cara.services.genai_service import GenAIService
from cara.services.review_orchestrator import ReviewOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Prompt"])


def _sse_frame(event: str, data: Any) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_wrapper(generator: Iterator[dict[str, Any]]) -> Iterator[str]:
    """Adapt an orchestrator event generator into SSE-formatted text frames.

    Each yielded dict carries an ``event`` key (``progress`` | ``complete`` |
    ``error``); the remaining keys form the JSON-encoded ``data`` payload sent
    to the client.
    """
    try:
        for item in generator:
            event_type = item.pop("event", "message")
            yield _sse_frame(event_type, item)
    except Exception as exc:
        logger.exception("stream_generator_failed error=%s", exc)
        yield _sse_frame("error", {"detail": str(exc)})


@router.post(
    "/prompt",
    response_model=AcceptedReviewResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_review_from_prompt(
    payload: PromptReviewRequest,
    background_tasks: BackgroundTasks,
    genai_service: Annotated[GenAIService, Depends(get_genai_service)],
    resolve_provider: Annotated[
        Callable[[RepoProviderName], RepoProvider],
        Depends(get_repo_provider_resolver),
    ],
    orchestrator: Annotated[ReviewOrchestrator, Depends(get_review_orchestrator)],
) -> AcceptedReviewResponse:
    reference = genai_service.extract_pull_request_reference(payload.command)
    provider = resolve_provider(reference.provider)

    if reference.pr_number > 0:
        provider.ensure_pull_request_exists(
            reference.owner,
            reference.repo,
            reference.pr_number,
        )
        background_tasks.add_task(
            orchestrator.process_review,
            ReviewJobRequest(
                owner=reference.owner,
                repo=reference.repo,
                pr_number=reference.pr_number,
                source=ReviewSource.PROMPT,
                trigger_event="prompt",
                provider=reference.provider,
            ),
        )
        return AcceptedReviewResponse(
            status="accepted",
            message="Pull request review queued from natural language prompt.",
            owner=reference.owner,
            repo=reference.repo,
            pr_number=reference.pr_number,
            source=ReviewSource.PROMPT,
            mode=ReviewMode.PULL_REQUEST,
        )

    provider.ensure_repository_exists(reference.owner, reference.repo)
    background_tasks.add_task(
        orchestrator.process_repo_scan,
        RepositoryScanJobRequest(
            owner=reference.owner,
            repo=reference.repo,
            ref=reference.ref,
            folder=reference.folder,
            source=ReviewSource.PROMPT,
            trigger_event="prompt",
            provider=reference.provider,
        ),
    )
    return AcceptedReviewResponse(
        status="accepted",
        message="Repository scan queued from natural language prompt.",
        owner=reference.owner,
        repo=reference.repo,
        pr_number=0,
        source=ReviewSource.PROMPT,
        mode=ReviewMode.REPOSITORY,
        ref=reference.ref,
        folder=reference.folder,
    )


@router.post(
    "/prompt/stream",
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def trigger_review_stream_from_prompt(
    payload: PromptReviewRequest,
    genai_service: Annotated[GenAIService, Depends(get_genai_service)],
    resolve_provider: Annotated[
        Callable[[RepoProviderName], RepoProvider],
        Depends(get_repo_provider_resolver),
    ],
    orchestrator: Annotated[ReviewOrchestrator, Depends(get_review_orchestrator)],
) -> StreamingResponse:
    """Stream a review/scan as an SSE event stream.

    Mirrors the body / parsing logic of POST /prompt but instead of queueing the
    job in the background and returning 202, it runs the orchestrator inline
    and yields progress events to the client. The final event is either
    ``event: complete`` (with the persisted report payload) or ``event: error``.
    """
    reference = genai_service.extract_pull_request_reference(payload.command)
    provider = resolve_provider(reference.provider)

    if reference.pr_number > 0:
        provider.ensure_pull_request_exists(
            reference.owner,
            reference.repo,
            reference.pr_number,
        )
        generator = orchestrator.process_review_stream(
            ReviewJobRequest(
                owner=reference.owner,
                repo=reference.repo,
                pr_number=reference.pr_number,
                source=ReviewSource.PROMPT,
                trigger_event="prompt",
                provider=reference.provider,
            ),
        )
    else:
        provider.ensure_repository_exists(reference.owner, reference.repo)
        generator = orchestrator.process_repo_scan_stream(
            RepositoryScanJobRequest(
                owner=reference.owner,
                repo=reference.repo,
                ref=reference.ref,
                folder=reference.folder,
                source=ReviewSource.PROMPT,
                trigger_event="prompt",
                provider=reference.provider,
            ),
        )

    return StreamingResponse(
        _sse_wrapper(generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
