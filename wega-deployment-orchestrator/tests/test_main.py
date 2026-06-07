from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.models.requests import ChildAgentType


class _StubGraph:
    async def ainvoke(self, initial_state, config):
        return {
            **initial_state,
            "target_agent": ChildAgentType.CI,
            "response": "CI pipeline request failed guardrail validation.",
            "error": "CI pipeline request failed guardrail validation.",
            "child_response": {
                "status": "error",
                "message": "CI pipeline request failed guardrail validation.",
                "data": {
                    "error": {
                        "type": "guardrail_validation",
                        "agent": "ci",
                        "status_code": 400,
                        "detail": [
                            "Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'."
                        ],
                    }
                },
                "suggested_actions": [
                    {
                        "action": "Revise CI pipeline inputs and retry",
                        "intent": "generate_ci_pipeline",
                        "agent": "ci",
                    }
                ],
            },
            "suggested_actions": [
                {
                    "action": "Revise CI pipeline inputs and retry",
                    "intent": "generate_ci_pipeline",
                    "agent": "ci",
                }
            ],
            "metadata": {},
        }


class _StubRepositoryClient:
    async def close(self):
        return None

    async def list_repositories(self, platform, repository_url=None):
        assert platform == "github-actions"
        assert repository_url is None
        return [
            type("Repository", (), {"id": "repo-1", "label": "demo-repo", "url": "https://github.com/example/demo-repo"})()
        ]

    async def list_branches(self, platform, repository_url):
        assert platform == "github-actions"
        assert repository_url == "https://github.com/example/demo-repo"
        return ["main", "release/1.0"]

    async def write_file(self, platform, repository_url, branch, file_path, content, commit_message):
        assert platform == 'harness'
        assert repository_url == 'https://git.harness.io/acct/default/project/demo-repo.git'
        assert branch == 'main'
        assert file_path == 'harness/pipeline.yaml'
        assert content == 'pipeline:\n  name: demo\n'
        assert commit_message == 'Add generated Harness pipeline'
        return type(
            'RepositoryWriteResult',
            (),
            {
                'status': 'committed',
                'repository_url': repository_url,
                'branch': branch,
                'file_path': file_path,
                'commit_message': commit_message,
                'commit_sha': 'abc123',
            },
        )()


def test_chat_endpoint_preserves_child_guardrail_error(monkeypatch):
    monkeypatch.setattr(main_module, "get_orchestrator_graph", lambda: _StubGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "session_id": "deploy-chat-test",
            "message": "Generate CI pipeline",
            "explicit_intent": "generate_ci_pipeline",
            "target_agent": "ci",
            "context": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "CI pipeline request failed guardrail validation."
    assert body["routed_to"] == "ci"
    assert body["data"]["error"]["type"] == "guardrail_validation"
    assert body["data"]["error"]["detail"] == [
        "Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'."
    ]


def test_list_repositories_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    client = TestClient(app)

    response = client.get("/v1/repositories", params={"platform": "github-actions"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"id": "repo-1", "label": "demo-repo", "url": "https://github.com/example/demo-repo"}
        ]
    }


def test_list_repository_branches_endpoint_returns_items(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    client = TestClient(app)

    response = client.get(
        "/v1/repositories/branches",
        params={
            "platform": "github-actions",
            "repository_url": "https://github.com/example/demo-repo",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"items": ["main", "release/1.0"]}


def test_write_repository_file_endpoint_returns_commit_details(monkeypatch):
    monkeypatch.setattr(main_module, 'get_repository_lookup_client', lambda: _StubRepositoryClient())
    client = TestClient(app)

    response = client.post(
        '/v1/repositories/files',
        json={
            'platform': 'harness',
            'repositoryUrl': 'https://git.harness.io/acct/default/project/demo-repo.git',
            'branch': 'main',
            'filePath': 'harness/pipeline.yaml',
            'content': 'pipeline:\n  name: demo\n',
            'commitMessage': 'Add generated Harness pipeline',
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        'status': 'committed',
        'repositoryUrl': 'https://git.harness.io/acct/default/project/demo-repo.git',
        'branch': 'main',
        'filePath': 'harness/pipeline.yaml',
        'commitMessage': 'Add generated Harness pipeline',
        'commitSha': 'abc123',
    }


def test_repository_context_endpoint_returns_harness_project_url(monkeypatch):
    monkeypatch.setattr(main_module.settings, "harness_base_url", "https://app.harness.io")
    monkeypatch.setattr(main_module.settings, "harness_account_identifier", "acct-1")
    monkeypatch.setattr(main_module.settings, "harness_org_identifier", "default")
    monkeypatch.setattr(main_module.settings, "harness_project_identifier", "wega-build")
    client = TestClient(app)

    response = client.get("/v1/repositories/context", params={"platform": "harness"})

    assert response.status_code == 200
    assert response.json() == {
        "repository_url": "https://app.harness.io/ng/account/acct-1/module/code/orgs/default/projects/wega-build"
    }


def test_repository_context_endpoint_falls_back_to_harness_for_github_actions(monkeypatch):
    monkeypatch.setattr(main_module.settings, "harness_base_url", "https://app.harness.io")
    monkeypatch.setattr(main_module.settings, "harness_account_identifier", "acct-1")
    monkeypatch.setattr(main_module.settings, "harness_org_identifier", "default")
    monkeypatch.setattr(main_module.settings, "harness_project_identifier", "wega-build")
    monkeypatch.setattr(main_module.settings, "github_repository_url", "")
    client = TestClient(app)

    response = client.get("/v1/repositories/context", params={"platform": "github-actions"})

    assert response.status_code == 200
    assert response.json() == {
        "repository_url": "https://app.harness.io/ng/account/acct-1/module/code/orgs/default/projects/wega-build"
    }


def test_repository_context_endpoint_prefers_platform_specific_url(monkeypatch):
    monkeypatch.setattr(main_module.settings, "harness_base_url", "https://app.harness.io")
    monkeypatch.setattr(main_module.settings, "harness_account_identifier", "acct-1")
    monkeypatch.setattr(main_module.settings, "harness_org_identifier", "default")
    monkeypatch.setattr(main_module.settings, "harness_project_identifier", "wega-build")
    monkeypatch.setattr(main_module.settings, "github_repository_url", "https://github.com/example-org")
    client = TestClient(app)

    response = client.get("/v1/repositories/context", params={"platform": "github-actions"})

    assert response.status_code == 200
    assert response.json() == {"repository_url": "https://github.com/example-org"}


def test_repository_endpoint_includes_cors_header(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    client = TestClient(app)

    response = client.get(
        "/v1/repositories",
        params={"platform": "github-actions"},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_repository_endpoint_requires_auth_when_local_bypass_disabled(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    monkeypatch.setattr(main_module.settings, "debug", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_allow_local_debug_bypass", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_users", "")
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_roles", "")
    monkeypatch.setattr(main_module.settings, "repository_lookup_service_token", "")
    monkeypatch.setattr(main_module.settings, "repository_lookup_service_token_secret_name", "")
    client = TestClient(app)

    response = client.get("/v1/repositories", params={"platform": "github-actions"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Repository lookup authentication is required."


def test_repository_endpoint_accepts_authorized_identity_headers(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    monkeypatch.setattr(main_module.settings, "debug", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_allow_local_debug_bypass", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_users", "")
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_roles", "repo-reader")
    client = TestClient(app)

    response = client.get(
        "/v1/repositories",
        params={"platform": "github-actions"},
        headers={
            "X-WEGA-Principal": "user@example.com",
            "X-WEGA-Roles": "repo-reader,viewer",
        },
    )

    assert response.status_code == 200


def test_repository_endpoint_rejects_unauthorized_roles(monkeypatch):
    monkeypatch.setattr(main_module, "get_repository_lookup_client", lambda: _StubRepositoryClient())
    monkeypatch.setattr(main_module.settings, "debug", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_allow_local_debug_bypass", False)
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_users", "")
    monkeypatch.setattr(main_module.settings, "repository_lookup_authorized_roles", "repo-reader")
    client = TestClient(app)

    response = client.get(
        "/v1/repositories",
        params={"platform": "github-actions"},
        headers={
            "X-WEGA-Principal": "user@example.com",
            "X-WEGA-Roles": "viewer",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Repository lookup access is not allowed for this role."