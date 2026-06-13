from typing import Any

from cara.core.config import Settings
from cara.models.domain import (
    JiraValidationResult,
    JiraValidationStatus,
    PromptScanReference,
    PullRequestContext,
    ReviewFindingCategory,
    ReviewIssueType,
    ReviewOverallStatus,
    ReviewSeverity,
)
from cara.models.schemas import StructuredReviewAssessment, StructuredReviewFinding
from cara.services.genai_service import GenAIService, UploadedContextFile


class FakeResponse:
    def __init__(self, parsed: Any) -> None:
        self.parsed = parsed
        self.text = None


class FakeModelsAPI:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *, model: str, contents: list[Any], config: Any) -> FakeResponse:
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )
        return self._response


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.models = FakeModelsAPI(response)


def test_extract_pull_request_reference_uses_fast_model() -> None:
    client = FakeClient(
        FakeResponse(
            PromptScanReference(owner="facebook", repo="react", pr_number=11),
        )
    )
    service = GenAIService(client=client, settings=Settings())

    reference = service.extract_pull_request_reference("Scan PR-11 of facebook/react.")

    assert reference == PromptScanReference(owner="facebook", repo="react", pr_number=11)
    assert client.models.calls[0]["model"] == service._settings.llm_model_fast
    assert client.models.calls[0]["config"].response_schema is PromptScanReference


def test_extract_pull_request_reference_allows_repo_scan_without_pr_number() -> None:
    client = FakeClient(
        FakeResponse(
            PromptScanReference(
                owner="buildit",
                repo="ai-infusion-survey-ui",
                pr_number=0,
                folder="src",
            ),
        )
    )
    service = GenAIService(client=client, settings=Settings())

    reference = service.extract_pull_request_reference(
        "Scan only the src folder of buildit/ai-infusion-survey-ui repository",
    )

    assert reference.owner == "buildit"
    assert reference.repo == "ai-infusion-survey-ui"
    assert reference.pr_number == 0
    assert reference.folder == "src"


def test_extract_pull_request_reference_rejects_missing_owner_or_repo() -> None:
    from cara.core.errors import BadRequestError

    client = FakeClient(
        FakeResponse(
            PromptScanReference(owner="", repo="", pr_number=0),
        )
    )
    service = GenAIService(client=client, settings=Settings())

    try:
        service.extract_pull_request_reference("Scan something irrelevant.")
    except BadRequestError as exc:
        assert "owner" in exc.detail.lower()
    else:
        raise AssertionError("Expected BadRequestError when owner/repo are missing.")


def test_generate_review_uses_reasoning_model_and_maps_structured_findings() -> None:
    client = FakeClient(
        FakeResponse(
            StructuredReviewAssessment(
                overall_status=ReviewOverallStatus.NEEDS_ATTENTION,
                summary="The pull request introduces an unsanitized command argument.",
                strengths=["The feature has good branch coverage."],
                vulnerabilities_and_bugs=[
                    StructuredReviewFinding(
                        file_path="src/app.py",
                        line_number=17,
                        issue_type=ReviewIssueType.SECURITY_VULNERABILITY,
                        severity_score=8,
                        comment="User-controlled input reaches a shell command without escaping.",
                        cwe_identifier="CWE-78",
                        suggested_remediation_code="safe_arg = shlex.quote(user_arg)",
                    )
                ],
                jira_validation=JiraValidationResult(
                    issue_key="PROJ-123",
                    status=JiraValidationStatus.PARTIALLY_ALIGNED,
                    summary="The core change is present, but one acceptance criterion is missing.",
                    uncovered_requirements=["Add audit logging"],
                ),
            )
        )
    )
    service = GenAIService(client=client, settings=Settings())

    assessment = service.generate_review(
        pull_request=PullRequestContext(
            owner="acme",
            repo="rocket",
            pr_number=11,
            title="Implement login flow",
            body="Adds the login flow.",
            html_url="https://github.com/acme/rocket/pull/11",
            head_sha="abc123",
            head_ref="feature/login",
            base_ref="main",
            diff="diff --git a/src/app.py b/src/app.py\n+print('unsafe')",
            files=[],
        ),
        context_files=[
            UploadedContextFile(
                path="src/app.py",
                uri="gs://context/src-app",
                mime_type="text/plain",
                handle=object(),
            )
        ],
        jira_issue=None,
    )

    assert client.models.calls[0]["model"] == service._settings.llm_model_reasoning
    assert client.models.calls[0]["config"].response_schema is StructuredReviewAssessment
    assert assessment.overall_status == ReviewOverallStatus.NEEDS_ATTENTION
    assert assessment.findings[0].category == ReviewFindingCategory.SECURITY
    assert assessment.findings[0].severity == ReviewSeverity.HIGH
    assert assessment.findings[0].line_number == 17
    assert assessment.findings[0].issue_type == ReviewIssueType.SECURITY_VULNERABILITY
    assert assessment.findings[0].severity_score == 8
    assert assessment.findings[0].cwe_identifier == "CWE-78"


class _RecordingFilesAPI:
    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()
        self.upload_paths: list[str] = []
        self._counter = 0

    def upload(self, *, file: str, config: dict[str, Any]) -> Any:
        with self._lock:
            self._counter += 1
            idx = self._counter
            self.upload_paths.append(file)

        class _Handle:
            uri = f"gs://files/{idx}"
            mime_type = config.get("mime_type", "text/plain")
            name = f"file-{idx}"

        return _Handle()


def test_upload_context_files_calls_upload_per_file_in_order(tmp_path: Any) -> None:
    from pathlib import Path

    repo = Path(tmp_path) / "repo"
    repo.mkdir()
    paths: list[Path] = []
    for i in range(8):
        p = repo / f"f{i}.py"
        p.write_text(f"x = {i}\n")
        paths.append(p)

    files_api = _RecordingFilesAPI()

    class _Client:
        def __init__(self) -> None:
            self.files = files_api
            self.models = FakeModelsAPI(FakeResponse(None))

    settings = Settings(_env_file=None)
    service = GenAIService(client=_Client(), settings=settings)
    uploaded = service.upload_context_files(repository_root=repo, files=paths)

    assert len(uploaded) == len(paths)
    # Every path was uploaded exactly once.
    assert sorted(files_api.upload_paths) == sorted(str(p) for p in paths)
    # Output order matches input order regardless of thread scheduling.
    assert [u.path for u in uploaded] == [p.name for p in paths]


def test_upload_context_files_sequential_when_concurrency_is_one(tmp_path: Any) -> None:
    from pathlib import Path

    repo = Path(tmp_path) / "repo"
    repo.mkdir()
    p1 = repo / "a.py"
    p1.write_text("a = 1\n")
    p2 = repo / "b.py"
    p2.write_text("b = 2\n")

    files_api = _RecordingFilesAPI()

    class _Client:
        def __init__(self) -> None:
            self.files = files_api
            self.models = FakeModelsAPI(FakeResponse(None))

    settings = Settings(_env_file=None, upload_concurrency=1)
    service = GenAIService(client=_Client(), settings=settings)
    uploaded = service.upload_context_files(repository_root=repo, files=[p1, p2])

    assert [u.path for u in uploaded] == ["a.py", "b.py"]
    assert files_api.upload_paths == [str(p1), str(p2)]
