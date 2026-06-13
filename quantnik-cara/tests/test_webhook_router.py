import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cara.core.config import Settings, get_settings
from cara.core.dependencies import get_review_orchestrator
from cara.models.domain import ReviewJobRequest


class StubOrchestrator:
    def __init__(self) -> None:
        self.jobs: list[ReviewJobRequest] = []

    def process_review(self, job: ReviewJobRequest) -> None:
        self.jobs.append(job)


def build_payload(action: str = "opened") -> dict[str, object]:
    return {
        "action": action,
        "repository": {
            "name": "rocket",
            "owner": {"login": "acme"},
        },
        "pull_request": {
            "number": 11,
            "title": "Implement login flow",
            "body": "Adds the new login workflow.",
            "html_url": "https://github.com/acme/rocket/pull/11",
            "head": {"ref": "feature/login", "sha": "abc123"},
            "base": {"ref": "main", "sha": "base123"},
        },
    }


def test_webhook_endpoint_queues_supported_actions(client: TestClient, test_app: FastAPI) -> None:
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post(
        "/webhook",
        headers={"X-GitHub-Event": "pull_request"},
        json=build_payload(action="opened"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert len(orchestrator.jobs) == 1
    assert orchestrator.jobs[0].model_dump() == {
        "owner": "acme",
        "repo": "rocket",
        "pr_number": 11,
        "source": "webhook",
        "trigger_event": "opened",
        "provider": "github",
    }


def test_webhook_endpoint_ignores_unsupported_actions(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post(
        "/webhook",
        headers={"X-GitHub-Event": "pull_request"},
        json=build_payload(action="closed"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert orchestrator.jobs == []


def test_webhook_endpoint_rejects_invalid_signature(client: TestClient, test_app: FastAPI) -> None:
    orchestrator = StubOrchestrator()
    raw_payload = (
        b'{"action":"opened","repository":{"name":"rocket","owner":{"login":"acme"}},'
        b'"pull_request":{"number":11,"title":"Implement login flow",'
        b'"body":"Adds the new login workflow.",'
        b'"html_url":"https://github.com/acme/rocket/pull/11","head":{"ref":"feature/login","sha":"abc123"},'
        b'"base":{"ref":"main","sha":"base123"}}}'
    )
    secret = "topsecret"
    signature = "sha256=" + hmac.new(secret.encode(), raw_payload, hashlib.sha256).hexdigest()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator
    test_app.dependency_overrides[get_settings] = lambda: Settings(
        github_webhook_secret=SecretStr(secret),
    )

    invalid_response = client.post(
        "/webhook",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalid",
        },
        content=raw_payload,
    )
    valid_response = client.post(
        "/webhook",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
        content=raw_payload,
    )

    assert invalid_response.status_code == 401
    assert valid_response.status_code == 202
