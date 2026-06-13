from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from cara.core.dependencies import get_report_storage
from cara.interfaces.report_storage import ReportStorageInterface
from cara.models.api import ErrorResponse
from cara.models.domain import PersistedReviewReport, RepoProviderName

router = APIRouter(tags=["Reports"])


@router.get(
    "/reports/{owner}/{repo}/pulls/{pr_number}",
    response_model=PersistedReviewReport,
    responses={404: {"model": ErrorResponse}},
)
async def get_report(
    owner: str,
    repo: str,
    pr_number: Annotated[int, Path(gt=0)],
    storage: Annotated[ReportStorageInterface, Depends(get_report_storage)],
    version: Annotated[int | None, Query(gt=0)] = None,
    provider: Annotated[RepoProviderName, Query()] = RepoProviderName.GITHUB,
) -> PersistedReviewReport:
    return storage.get_report(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        version=version,
        provider=provider,
    )


@router.get(
    # `ref:path` allows multi-segment branches like `feature/foo` or `release/2026.04`.
    # Without it, FastAPI would only match a single path segment for {ref}.
    "/reports/{owner}/{repo}/scans/{ref:path}",
    response_model=PersistedReviewReport,
    responses={404: {"model": ErrorResponse}},
)
async def get_scan_report(
    owner: str,
    repo: str,
    ref: Annotated[str, Path(min_length=1)],
    storage: Annotated[ReportStorageInterface, Depends(get_report_storage)],
    folder: Annotated[str | None, Query()] = None,
    version: Annotated[int | None, Query(gt=0)] = None,
    provider: Annotated[RepoProviderName, Query()] = RepoProviderName.GITHUB,
) -> PersistedReviewReport:
    return storage.get_scan_report(
        owner=owner,
        repo=repo,
        ref=ref,
        folder=folder,
        version=version,
        provider=provider,
    )
