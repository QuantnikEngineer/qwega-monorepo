from datetime import UTC, datetime
from pathlib import Path

import pytest

from cara.core.errors import NotFoundError
from cara.models.domain import (
    PersistedReviewReport,
    RepoProviderName,
    ReviewMode,
    ReviewOverallStatus,
    ReviewReport,
    ReviewSource,
)
from cara.services.report_storage import LocalFilesystemReportStorage


def _build_pr_report(provider: RepoProviderName) -> ReviewReport:
    return ReviewReport(
        owner="acme",
        repo="rocket",
        pr_number=11,
        source=ReviewSource.PROMPT,
        provider=provider,
        overall_status=ReviewOverallStatus.PASS,
        summary="ok",
        strengths=[],
        findings=[],
    )


def test_save_writes_under_provider_prefix(tmp_path: Path) -> None:
    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    persisted = storage.save_report(_build_pr_report(RepoProviderName.GITHUB))

    expected = tmp_path / "github" / "acme" / "rocket" / "pulls" / "11" / "report-v1.json"
    assert expected.is_file()
    assert persisted.version == 1


def test_save_keeps_github_and_harness_separate(tmp_path: Path) -> None:
    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    storage.save_report(_build_pr_report(RepoProviderName.GITHUB))
    storage.save_report(_build_pr_report(RepoProviderName.HARNESS))

    gh_path = tmp_path / "github" / "acme" / "rocket" / "pulls" / "11" / "report-v1.json"
    hn_path = tmp_path / "harness" / "acme" / "rocket" / "pulls" / "11" / "report-v1.json"
    assert gh_path.is_file()
    assert hn_path.is_file()


def test_get_report_falls_back_to_legacy_path_for_github(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "acme" / "rocket" / "pulls" / "11"
    legacy_dir.mkdir(parents=True)
    legacy_report = PersistedReviewReport(
        owner="acme",
        repo="rocket",
        pr_number=11,
        source=ReviewSource.WEBHOOK,
        provider=RepoProviderName.GITHUB,
        overall_status=ReviewOverallStatus.PASS,
        summary="legacy",
        strengths=[],
        findings=[],
        version=3,
        created_at=datetime.now(UTC),
    )
    (legacy_dir / "report-v3.json").write_text(
        legacy_report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    fetched = storage.get_report(
        owner="acme",
        repo="rocket",
        pr_number=11,
        provider=RepoProviderName.GITHUB,
    )

    assert fetched.version == 3
    assert fetched.summary == "legacy"


def test_harness_reports_do_not_use_github_legacy_fallback(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "acme" / "rocket" / "pulls" / "11"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "report-v1.json").write_text("{}", encoding="utf-8")

    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    with pytest.raises(NotFoundError):
        storage.get_report(
            owner="acme",
            repo="rocket",
            pr_number=11,
            provider=RepoProviderName.HARNESS,
        )


def test_get_latest_version_walks_provider_path_first(tmp_path: Path) -> None:
    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    storage.save_report(_build_pr_report(RepoProviderName.GITHUB))
    storage.save_report(_build_pr_report(RepoProviderName.GITHUB))

    assert (
        storage.get_latest_version(
            "acme", "rocket", 11, RepoProviderName.GITHUB
        )
        == 2
    )
