from typing import Protocol, runtime_checkable

from cara.models.domain import PersistedReviewReport, RepoProviderName, ReviewReport


@runtime_checkable
class ReportStorageInterface(Protocol):
    def save_report(self, report: ReviewReport) -> PersistedReviewReport: ...

    def get_report(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        version: int | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> PersistedReviewReport: ...

    def get_latest_version(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> int | None: ...

    def get_scan_report(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None = None,
        version: int | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> PersistedReviewReport: ...

    def get_latest_scan_version(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> int | None: ...
