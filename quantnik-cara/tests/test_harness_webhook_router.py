import hashlib
import hmac
import json

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


def _payload(trigger: str = "pullreq_created") -> dict[str, object]:
    return {
        "trigger": trigger,
        "repo": {
            "org_identifier": "finance",
            "project_identifier": "api",
            "identifier": "svc",
        },
        "pull_request": {
            "number": 7,
            "title": "Add audit log",
        },
    }


def test_harness_webhook_queues_supported_trigger(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post(
        "/webhook/harness",
        headers={"X-Harness-Trigger": "pullreq_created"},
        json=_payload(trigger="pullreq_created"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert len(orchestrator.jobs) == 1
    job = orchestrator.jobs[0]
    assert job.model_dump() == {
        "owner": "finance/api",
        "repo": "svc",
        "pr_number": 7,
        "source": "webhook",
        "trigger_event": "pullreq_created",
        "provider": "harness",
    }


def test_harness_webhook_ignores_unsupported_trigger(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    orchestrator = StubOrchestrator()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator

    response = client.post(
        "/webhook/harness",
        json=_payload(trigger="pullreq_closed"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert orchestrator.jobs == []


def test_harness_webhook_rejects_invalid_signature(
    client: TestClient,
    test_app: FastAPI,
) -> None:
    orchestrator = StubOrchestrator()
    secret = "topsecret"
    raw_body = json.dumps(_payload()).encode()
    valid_sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    test_app.dependency_overrides[get_review_orchestrator] = lambda: orchestrator
    test_app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        harness_webhook_secret=SecretStr(secret),
    )

    invalid = client.post(
        "/webhook/harness",
        headers={
            "Content-Type": "application/json",
            "X-Harness-Signature": "deadbeef",
        },
        content=raw_body,
    )
    valid = client.post(
        "/webhook/harness",
        headers={
            "Content-Type": "application/json",
            "X-Harness-Signature": valid_sig,
        },
        content=raw_body,
    )

    assert invalid.status_code == 401
    assert valid.status_code == 202
