from fastapi import FastAPI
from fastapi.testclient import TestClient

from cara.core.dependencies import get_report_storage
from cara.models.domain import (
    ReviewFinding,
    ReviewFindingCategory,
    ReviewIssueType,
    ReviewMode,
    ReviewOverallStatus,
    ReviewReport,
    ReviewSeverity,
    ReviewSource,
)
from cara.services.report_storage import LocalFilesystemReportStorage


def build_review_report(summary: str) -> ReviewReport:
    return ReviewReport(
        owner="acme",
        repo="rocket",
        pr_number=11,
        source=ReviewSource.WEBHOOK,
        trigger_event="opened",
        pull_request_url="https://github.com/acme/rocket/pull/11",
        reviewed_commit_sha="abc123",
        jira_issue_key=None,
        context_files=["src/api.py"],
        overall_status=ReviewOverallStatus.NEEDS_ATTENTION,
        summary=summary,
        strengths=["Good test coverage around the modified endpoint."],
        findings=[
            ReviewFinding(
                title="Missing input sanitization",
                severity=ReviewSeverity.MEDIUM,
                category=ReviewFindingCategory.SECURITY,
                description="User input reaches the shell invocation path without normalization.",
                recommendation=(
                    "Validate and escape user-controlled values before invoking the shell."
                ),
                file_path="src/api.py",
                line_number=42,
                issue_type=ReviewIssueType.SECURITY_VULNERABILITY,
                severity_score=7,
                comment="User input reaches the shell invocation path without normalization.",
                cwe_identifier="CWE-78",
                suggested_remediation_code="escaped_value = shlex.quote(user_value)",
            )
        ],
        jira_validation=None,
    )


def test_reports_endpoint_returns_latest_and_requested_versions(
    client: TestClient,
    test_app: FastAPI,
    tmp_path,
) -> None:
    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    first_report = storage.save_report(build_review_report("First scan summary"))
    second_report = storage.save_report(build_review_report("Second scan summary"))
    test_app.dependency_overrides[get_report_storage] = lambda: storage

    latest_response = client.get("/reports/acme/rocket/pulls/11")
    first_response = client.get("/reports/acme/rocket/pulls/11", params={"version": 1})

    assert latest_response.status_code == 200
    assert latest_response.json()["version"] == second_report.version
    assert latest_response.json()["summary"] == "Second scan summary"
    assert first_response.status_code == 200
    assert first_response.json()["version"] == first_report.version
    assert first_response.json()["summary"] == "First scan summary"


def build_repo_scan_report(summary: str, folder: str | None = "src") -> ReviewReport:
    return ReviewReport(
        owner="buildit",
        repo="ai-infusion-survey-ui",
        pr_number=0,
        source=ReviewSource.PROMPT,
        trigger_event="prompt",
        pull_request_url=None,
        reviewed_commit_sha="cafebabe",
        jira_issue_key=None,
        context_files=["src/app.py"],
        mode=ReviewMode.REPOSITORY,
        scanned_ref="main",
        scanned_folder=folder,
        repository_url="https://github.com/buildit/ai-infusion-survey-ui",
        overall_status=ReviewOverallStatus.PASS,
        summary=summary,
        strengths=[],
        findings=[],
        jira_validation=None,
    )


def test_scan_reports_endpoint_returns_latest_and_filters_by_folder(
    client: TestClient,
    test_app: FastAPI,
    tmp_path,
) -> None:
    storage = LocalFilesystemReportStorage(base_path=tmp_path)
    storage.save_report(build_repo_scan_report("First scan", folder="src"))
    second_report = storage.save_report(build_repo_scan_report("Second scan", folder="src"))
    storage.save_report(build_repo_scan_report("Other folder", folder="tests"))
    test_app.dependency_overrides[get_report_storage] = lambda: storage

    response = client.get(
        "/reports/buildit/ai-infusion-survey-ui/scans/main",
        params={"folder": "src"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == second_report.version
    assert body["summary"] == "Second scan"
    assert body["mode"] == "repository"
    assert body["scanned_folder"] == "src"

    other_response = client.get(
        "/reports/buildit/ai-infusion-survey-ui/scans/main",
        params={"folder": "tests"},
    )
    assert other_response.status_code == 200
    assert other_response.json()["summary"] == "Other folder"

    missing_response = client.get(
        "/reports/buildit/ai-infusion-survey-ui/scans/main",
        params={"folder": "missing"},
    )
    assert missing_response.status_code == 404
