import re
from datetime import UTC, datetime
from pathlib import Path

from cara.core.errors import NotFoundError
from cara.models.domain import (
    PersistedReviewReport,
    RepoProviderName,
    ReviewMode,
    ReviewReport,
)

VERSION_PATTERN = re.compile(r"report-v(\d+)\.json$")


class LocalFilesystemReportStorage:
    """Filesystem-backed report store with provider-prefixed paths.

    Writes always include the provider prefix
    (``<base>/<provider>/<owner>/<repo>/...``); reads first try the prefixed
    path and, when absent for the GitHub provider, fall back to the legacy
    flat layout (``<base>/<owner>/<repo>/...``) so historical reports persisted
    before this change remain accessible.
    """

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    # ------------------------------------------------------------------
    # Save (always uses provider-prefixed path)
    # ------------------------------------------------------------------

    def save_report(self, report: ReviewReport) -> PersistedReviewReport:
        provider = report.provider or RepoProviderName.GITHUB
        if report.mode is ReviewMode.REPOSITORY:
            report_dir = self._scan_report_directory(
                report.owner,
                report.repo,
                report.scanned_ref or "default",
                report.scanned_folder,
                provider,
            )
            report_dir.mkdir(parents=True, exist_ok=True)
            version = (
                self.get_latest_scan_version(
                    report.owner,
                    report.repo,
                    report.scanned_ref or "default",
                    report.scanned_folder,
                    provider,
                )
                or 0
            ) + 1
            report_path = report_dir / f"report-v{version}.json"
        else:
            report_dir = self._report_directory(
                report.owner, report.repo, report.pr_number, provider
            )
            report_dir.mkdir(parents=True, exist_ok=True)
            version = (
                self.get_latest_version(
                    report.owner, report.repo, report.pr_number, provider
                )
                or 0
            ) + 1
            report_path = self._report_path(
                report.owner, report.repo, report.pr_number, version, provider
            )

        persisted_report = PersistedReviewReport(
            **report.model_dump(),
            version=version,
            created_at=datetime.now(UTC),
        )
        temp_path = report_path.with_suffix(".json.tmp")
        temp_path.write_text(
            persisted_report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(report_path)
        return persisted_report

    # ------------------------------------------------------------------
    # PR-review reads
    # ------------------------------------------------------------------

    def get_report(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        version: int | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> PersistedReviewReport:
        target_version = version or self.get_latest_version(
            owner, repo, pr_number, provider
        )
        if target_version is None:
            raise NotFoundError(
                f"No reports were found for {owner}/{repo} pull request #{pr_number}.",
            )

        for candidate in self._report_path_candidates(
            owner, repo, pr_number, target_version, provider
        ):
            if candidate.exists():
                return PersistedReviewReport.model_validate_json(
                    candidate.read_text(encoding="utf-8"),
                )

        raise NotFoundError(
            "Report version "
            f"{target_version} was not found for {owner}/{repo} pull request #{pr_number}.",
        )

    def get_latest_version(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> int | None:
        for directory in self._report_directory_candidates(
            owner, repo, pr_number, provider
        ):
            if (latest := self._max_version_in_directory(directory)) is not None:
                return latest
        return None

    # ------------------------------------------------------------------
    # Repository-scan reads
    # ------------------------------------------------------------------

    def get_scan_report(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None = None,
        version: int | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> PersistedReviewReport:
        target_version = version or self.get_latest_scan_version(
            owner, repo, ref, folder, provider
        )
        if target_version is None:
            descriptor = self._describe_scan(owner, repo, ref, folder)
            raise NotFoundError(f"No reports were found for {descriptor}.")

        for directory in self._scan_report_directory_candidates(
            owner, repo, ref, folder, provider
        ):
            candidate = directory / f"report-v{target_version}.json"
            if candidate.exists():
                return PersistedReviewReport.model_validate_json(
                    candidate.read_text(encoding="utf-8"),
                )

        descriptor = self._describe_scan(owner, repo, ref, folder)
        raise NotFoundError(
            f"Report version {target_version} was not found for {descriptor}.",
        )

    def get_latest_scan_version(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None = None,
        provider: RepoProviderName = RepoProviderName.GITHUB,
    ) -> int | None:
        for directory in self._scan_report_directory_candidates(
            owner, repo, ref, folder, provider
        ):
            if (latest := self._max_version_in_directory(directory)) is not None:
                return latest
        return None

    # ------------------------------------------------------------------
    # Path resolution helpers
    # ------------------------------------------------------------------

    def _max_version_in_directory(self, report_dir: Path) -> int | None:
        if not report_dir.exists():
            return None
        versions = [
            int(match.group(1))
            for path in report_dir.glob("report-v*.json")
            if (match := VERSION_PATTERN.match(path.name))
        ]
        return max(versions, default=None)

    def _report_directory(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        provider: RepoProviderName,
    ) -> Path:
        return (
            self._base_path
            / provider.value
            / owner
            / repo
            / "pulls"
            / str(pr_number)
        )

    def _report_path(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        version: int,
        provider: RepoProviderName,
    ) -> Path:
        return self._report_directory(owner, repo, pr_number, provider) / (
            f"report-v{version}.json"
        )

    def _report_directory_candidates(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        provider: RepoProviderName,
    ) -> list[Path]:
        primary = self._report_directory(owner, repo, pr_number, provider)
        if provider == RepoProviderName.GITHUB:
            legacy = self._base_path / owner / repo / "pulls" / str(pr_number)
            return [primary, legacy]
        return [primary]

    def _report_path_candidates(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        version: int,
        provider: RepoProviderName,
    ) -> list[Path]:
        return [
            directory / f"report-v{version}.json"
            for directory in self._report_directory_candidates(
                owner, repo, pr_number, provider
            )
        ]

    def _scan_report_directory(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None,
        provider: RepoProviderName,
    ) -> Path:
        safe_ref = self._sanitize_path_component(ref)
        folder_segment = self._sanitize_path_component(folder) if folder else "_root"
        return (
            self._base_path
            / provider.value
            / owner
            / repo
            / "scans"
            / safe_ref
            / folder_segment
        )

    def _scan_report_directory_candidates(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None,
        provider: RepoProviderName,
    ) -> list[Path]:
        primary = self._scan_report_directory(owner, repo, ref, folder, provider)
        if provider == RepoProviderName.GITHUB:
            safe_ref = self._sanitize_path_component(ref)
            folder_segment = (
                self._sanitize_path_component(folder) if folder else "_root"
            )
            legacy = (
                self._base_path
                / owner
                / repo
                / "scans"
                / safe_ref
                / folder_segment
            )
            return [primary, legacy]
        return [primary]

    def _sanitize_path_component(self, value: str) -> str:
        return value.replace("/", "__").replace("\\", "__").strip(".") or "_"

    def _describe_scan(
        self,
        owner: str,
        repo: str,
        ref: str,
        folder: str | None,
    ) -> str:
        suffix = f" folder={folder}" if folder else ""
        return f"{owner}/{repo} scan ref={ref}{suffix}"
