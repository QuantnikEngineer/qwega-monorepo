from fastapi import FastAPI
from fastapi.testclient import TestClient

from cara.core.dependencies import get_genai_service, get_github_service, get_review_orchestrator
from cara.models.domain import (
    PromptScanReference,
    RepositoryScanJobRequest,
    ReviewJobRequest,
)


class StubPromptParser:
    def __init__(self, reference: PromptScanReference | None = None) -> None:
        self.commands: list[str] = []
        self._reference = reference or PromptScanReference(
            owner="acme", repo="rocket", pr_number=11
        )

    def extract_pull_request_reference(self, command: str) -> PromptScanReference:
        self.commands.append(command)
        return self._reference


class StubGitHubService:
    def __init__(self) -> None:
        self.checked_pull_requests: list[tuple[str, str, int]] = []
        self.checked_repositories: list[tuple[str, str]] = []

    def ensure_pull_request_exists(self, owner: str, repo: str, pr_number: int) -> None:
        self.checked_pull_requests.append((owner, repo, pr_number))

    def ensure_repository_exists(self, owner: str, repo: str) -> None:
        self.checked_repositories.append((owner, repo))


class StubOrchestrator:
    def __init__(self) -> None:
        self.jobs: list[ReviewJobRequest] = []
        self.scan_jobs: list[RepositoryScanJobRequest] = []
        self.stream_jobs: list[ReviewJobRequest] = []
        self.stream_scan_jobs: list[RepositoryScanJobRequest] = []

    def process_review(self, job: ReviewJobRequest) -> None:
        self.jobs.append(job)

    def process_repo_scan(self, job: RepositoryScanJobRequest) -> None:
        self.scan_jobs.append(job)

    def process_review_stream(self, job: ReviewJobRequest):
        self.stream_jobs.append(job)
        yield {"event": "progress", "stage": "resolve_pr", "percent": 5, "message": "Resolving"}
        yield {
            "event": "complete",
            "report": {"owner": job.owner, "repo": job.repo, "pr_number": job.pr_number},
        }

    def process_repo_scan_stream(self, job: RepositoryScanJobRequest):
        self.stream_scan_jobs.append(job)
        yield {"event": "progress", "stage": "resolve_repo", "percent": 5, "message": "Resolving"}
        yield {
            "event": "complete",
            "report": {"owner": job.owner, "repo": job.repo, "ref": job.ref},
        }


def test_prompt_endpoint_queues_review(client: TestClient, test_app: FastAPI) -> None:
    parser = StubPromptParser()
    github_service = StubGitHubService()
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_genai_service] = lambda: parser
    test_app.dependency_overrides[get_github_service] = lambda: github_service
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post("/prompt", json={"command": "Scan PR-11 of acme/rocket repository."})

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message": "Pull request review queued from natural language prompt.",
        "owner": "acme",
        "repo": "rocket",
        "pr_number": 11,
        "source": "prompt",
        "mode": "pull_request",
        "ref": None,
        "folder": None,
    }
    assert parser.commands == ["Scan PR-11 of acme/rocket repository."]
    assert github_service.checked_pull_requests == [("acme", "rocket", 11)]
    assert len(orchestrator.jobs) == 1
    assert orchestrator.jobs[0].model_dump() == {
        "owner": "acme",
        "repo": "rocket",
        "pr_number": 11,
        "source": "prompt",
        "trigger_event": "prompt",
        "provider": "github",
    }
    assert orchestrator.scan_jobs == []


def test_prompt_endpoint_queues_repository_scan(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    parser = StubPromptParser(
        reference=PromptScanReference(
            owner="buildit",
            repo="ai-infusion-survey-ui",
            pr_number=0,
            ref=None,
            folder="src",
        ),
    )
    github_service = StubGitHubService()
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_genai_service] = lambda: parser
    test_app.dependency_overrides[get_github_service] = lambda: github_service
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post(
        "/prompt",
        json={
            "command": (
                "Scan only the src folder of buildit/ai-infusion-survey-ui repository"
            ),
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message": "Repository scan queued from natural language prompt.",
        "owner": "buildit",
        "repo": "ai-infusion-survey-ui",
        "pr_number": 0,
        "source": "prompt",
        "mode": "repository",
        "ref": None,
        "folder": "src",
    }
    assert github_service.checked_repositories == [("buildit", "ai-infusion-survey-ui")]
    assert github_service.checked_pull_requests == []
    assert orchestrator.jobs == []
    assert len(orchestrator.scan_jobs) == 1
    assert orchestrator.scan_jobs[0].model_dump() == {
        "owner": "buildit",
        "repo": "ai-infusion-survey-ui",
        "ref": None,
        "folder": "src",
        "source": "prompt",
        "trigger_event": "prompt",
        "provider": "github",
    }


def test_prompt_stream_endpoint_streams_pull_request_review(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    parser = StubPromptParser()
    github_service = StubGitHubService()
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_genai_service] = lambda: parser
    test_app.dependency_overrides[get_github_service] = lambda: github_service
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    with client.stream(
        "POST",
        "/prompt/stream",
        json={"command": "Review pull request #11 in acme/rocket."},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode()

    assert "event: progress" in body
    assert "\"stage\": \"resolve_pr\"" in body
    assert "event: complete" in body
    assert "\"pr_number\": 11" in body
    assert github_service.checked_pull_requests == [("acme", "rocket", 11)]
    assert len(orchestrator.stream_jobs) == 1
    assert orchestrator.stream_jobs[0].pr_number == 11


def test_prompt_stream_endpoint_streams_repository_scan(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    parser = StubPromptParser(
        reference=PromptScanReference(
            owner="buildit",
            repo="ai-infusion-survey-ui",
            pr_number=0,
            ref=None,
            folder="src",
        ),
    )
    github_service = StubGitHubService()
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_genai_service] = lambda: parser
    test_app.dependency_overrides[get_github_service] = lambda: github_service
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    with client.stream(
        "POST",
        "/prompt/stream",
        json={"command": "Scan the src folder of buildit/ai-infusion-survey-ui."},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode()

    assert "event: progress" in body
    assert "event: complete" in body
    assert github_service.checked_repositories == [("buildit", "ai-infusion-survey-ui")]
    assert len(orchestrator.stream_scan_jobs) == 1
    assert orchestrator.stream_scan_jobs[0].folder == "src"
