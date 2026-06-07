import pytest
from pydantic import ValidationError

from app.main import app
from app.models.requests import GeneratePipelineRequest, create_sample_request


def create_wrapped_ci_payload():
    return {
        "project_name": "CI",
        "repository_url": "https://github.com",
        "branch": "main",
        "language": "node",
        "framework": "react",
        "build_tool": "npm",
        "artifact_type": "package",
        "renderMode": "template",
        "ci_pipeline_request": {
            "schemaVersion": "2.0.0",
            "mode": "guided-ui",
            "prompt": "Generate CI Pipeline",
            "assistantMode": "assistive-prefill",
            "pipelineName": "CI",
            "renderMode": "template",
            "target": {
                "platform": "azure-devops",
                "deploymentTarget": "container-apps",
                "environment": "dev",
            },
            "repository": {
                "url": "https://github.com",
                "branch": "main",
            },
            "build": {
                "language": "node",
                "framework": "react",
                "tool": "npm",
                "artifactType": "package",
            },
            "quality": {
                "coverage": {
                    "enabled": False,
                    "minimum": 75,
                }
            },
            "execution": {
                "triggers": {
                    "push": True,
                    "pullRequest": False,
                },
                "managedAgents": False,
                "caching": False,
                "parallelism": False,
                "failFast": False,
                "timeoutMinutes": 30,
            },
            "tools": [
                {
                    "id": "unit-tests",
                    "name": "Unit Tests",
                    "category": "Build and Validation",
                },
                {
                    "id": "gitleaks",
                    "name": "Gitleaks",
                    "category": "Quality and Security",
                },
                {
                    "id": "artifact-publish",
                    "name": "Artifact Publish",
                    "category": "Packaging and Delivery",
                },
                {
                    "id": "notifications",
                    "name": "Notifications",
                    "category": "Collaboration",
                },
            ],
            "stages": [
                {
                    "order": 1,
                    "stageId": "checkout",
                    "name": "Checkout",
                    "tools": [],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 2,
                    "stageId": "restore",
                    "name": "Restore Dependencies",
                    "tools": ["npm"],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 3,
                    "stageId": "build",
                    "name": "Build",
                    "tools": ["npm"],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 4,
                    "stageId": "publish-artifacts",
                    "name": "Publish Artifacts",
                    "tools": ["package", "Artifact Publish"],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 5,
                    "stageId": "unit-test",
                    "name": "Unit Test",
                    "tools": ["Unit Tests"],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 6,
                    "stageId": "secret-scan",
                    "name": "Secret Scan",
                    "tools": ["Gitleaks"],
                    "orderingMode": "user-defined",
                },
                {
                    "order": 7,
                    "stageId": "notifications",
                    "name": "Notifications",
                    "tools": ["Notifications"],
                    "orderingMode": "user-defined",
                },
            ],
        },
    }


def test_generate_pipeline_request_defaults_nullable_ui_fields():
    payload = create_sample_request().model_dump(by_alias=True, mode="json")
    payload["target"]["deploymentTarget"] = None
    payload["target"]["environment"] = None
    payload["target"]["regions"] = []
    payload["build"]["artifactType"] = None
    payload["execution"]["approvals"] = {
        "enabled": False,
        "approvers": [],
        "timeoutMinutes": 120,
    }

    request = GeneratePipelineRequest.model_validate(payload)

    assert request.target.deployment_target == "none"
    assert request.target.environment == "dev"
    assert request.build.artifact_type == "none"


def test_generate_pipeline_request_accepts_wrapped_ci_payload():
    request = GeneratePipelineRequest.model_validate(create_wrapped_ci_payload())

    assert request.pipeline_name == "CI"
    assert request.repository.url == "https://github.com"
    assert request.render_mode == "template"


def test_generate_pipeline_request_normalizes_enterprise_controls():
    payload = create_sample_request().model_dump(by_alias=True, mode="json")
    payload["target"]["regions"] = "eastus, westeurope\ncentralindia"
    payload["build"]["image"] = {
        "repository": "registry.example.com/wega-app",
        "tags": "qa, latest\nrelease-2026-04",
    }
    payload["execution"]["approvals"] = {
        "enabled": True,
        "approvers": "release-managers@example.com, platform-owners@example.com",
        "timeoutMinutes": 180,
    }

    request = GeneratePipelineRequest.model_validate(payload)

    assert request.target.regions == ["eastus", "westeurope", "centralindia"]
    assert request.build.image.tags == ["qa", "latest", "release-2026-04"]
    assert request.execution.approvals.approvers == ["release-managers@example.com", "platform-owners@example.com"]
    assert request.execution.approvals.timeout_minutes == 180


def test_generate_pipeline_request_requires_approvers_when_approval_gate_enabled():
    payload = create_sample_request().model_dump(by_alias=True, mode="json")
    payload["execution"]["approvals"] = {
        "enabled": True,
        "approvers": [],
        "timeoutMinutes": 120,
    }

    with pytest.raises(ValidationError):
        GeneratePipelineRequest.model_validate(payload)


def test_generate_endpoint_accepts_frontend_style_payload_without_optional_fields():
    from fastapi.testclient import TestClient

    payload = create_sample_request().model_dump(by_alias=True, mode="json")
    payload["target"]["deploymentTarget"] = None
    payload["target"]["environment"] = None
    payload["target"]["regions"] = []
    payload["build"]["artifactType"] = None
    payload["execution"]["approvals"] = {
        "enabled": False,
        "approvers": [],
        "timeoutMinutes": 120,
    }
    payload["tools"] = [tool for tool in payload["tools"] if tool["id"] != "docker-build"]
    payload["tools"] = [tool for tool in payload["tools"] if tool["id"] != "artifact-publish"]
    payload["stages"] = [stage for stage in payload["stages"] if stage["stageId"] != "docker-build"]
    payload["stages"] = [stage for stage in payload["stages"] if stage["stageId"] != "publish-artifacts"]

    client = TestClient(app)
    response = client.post("/v1/pipelines/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["normalizedIntent"]["target"]["deploymentTarget"] == "none"
    assert body["normalizedIntent"]["target"]["environment"] == "dev"
    assert body["normalizedIntent"]["build"]["artifactType"] == "none"


def test_generate_endpoint_accepts_wrapped_ci_payload_with_two_character_name():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/v1/pipelines/generate", json=create_wrapped_ci_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["pipelineName"] == "CI"
    assert body["platform"] == "azure-devops"