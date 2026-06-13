from typing import Any

import pytest

from cara.core.config import Settings
from cara.core.errors import NotFoundError
from cara.services.harness_code_service import HarnessCodeService, _split_owner


class StubResponse:
    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = ""

    def json(self) -> Any:
        return self._payload


class StubHarnessClient:
    def __init__(self, responses: dict[str, StubResponse]) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._responses = responses

    def get(self, url: str, params: dict[str, str] | None = None) -> StubResponse:
        self.calls.append((url, params or {}))
        if url not in self._responses:
            return StubResponse(status_code=404, payload={"message": "not found"})
        return self._responses[url]


def _make_service(client: StubHarnessClient) -> HarnessCodeService:
    settings = Settings(
        _env_file=None,
        harness_account_id="acct1",
        harness_base_url="https://app.harness.io",
    )
    return HarnessCodeService(client=client, token_provider=lambda: "pat", settings=settings)


def test_split_owner_requires_two_segments() -> None:
    assert _split_owner("finance/api") == ("finance", "api")
    with pytest.raises(Exception):
        _split_owner("finance")


def test_ensure_pull_request_exists_passes_when_200() -> None:
    client = StubHarnessClient(
        {
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+/pullreq/7": StubResponse(),
        },
    )
    service = _make_service(client)

    service.ensure_pull_request_exists("finance/api", "svc", 7)

    assert client.calls[0][0].endswith("/pullreq/7")
    assert "/repos/acct1/finance/api/svc/+/" in client.calls[0][0]
    assert client.calls[0][1]["accountIdentifier"] == "acct1"


def test_ensure_pull_request_exists_raises_not_found_on_404() -> None:
    client = StubHarnessClient(
        {
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+/pullreq/7": StubResponse(
                status_code=404,
                payload={"message": "missing"},
            ),
        },
    )
    service = _make_service(client)

    with pytest.raises(NotFoundError):
        service.ensure_pull_request_exists("finance/api", "svc", 7)


def test_get_pull_request_context_assembles_diff_sections() -> None:
    pr_payload = {
        "title": "Add audit log",
        "description": "Add audit logging",
        "url": "https://app.harness.io/code/pr/7",
        "source_sha": "abc123",
        "source_branch": "feature/audit",
        "target_branch": "main",
    }
    files_payload = [
        {
            "path": "src/audit.py",
            "status": "modified",
            "additions": 5,
            "deletions": 1,
            "patch": "@@ -1 +1 @@\n-old\n+new\n",
        },
    ]
    client = StubHarnessClient(
        {
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+/pullreq/7": StubResponse(
                payload=pr_payload,
            ),
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+/pullreq/7/files": StubResponse(
                payload=files_payload,
            ),
        },
    )
    service = _make_service(client)

    context = service.get_pull_request_context("finance/api", "svc", 7)

    assert context.title == "Add audit log"
    assert context.head_sha == "abc123"
    assert context.head_ref == "feature/audit"
    assert context.base_ref == "main"
    assert len(context.files) == 1
    assert "diff --git a/src/audit.py" in context.diff


def test_get_repository_scan_context_uses_default_branch_when_ref_absent() -> None:
    repo_payload = {"default_branch": "main", "html_url": "https://app.harness.io/.../svc"}
    commit_payload = {"sha": "deadbeef"}
    client = StubHarnessClient(
        {
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+": StubResponse(
                payload=repo_payload,
            ),
            "/gateway/code/api/v1/repos/acct1/finance/api/svc/+/commits/main": StubResponse(
                payload=commit_payload,
            ),
        },
    )
    service = _make_service(client)

    ctx = service.get_repository_scan_context("finance/api", "svc")

    assert ctx.ref == "main"
    assert ctx.head_sha == "deadbeef"
    assert ctx.default_branch == "main"


def test_repo_ref_requires_account_id_configured() -> None:
    from cara.core.errors import ConfigurationError

    settings = Settings(_env_file=None, harness_account_id="", harness_base_url="https://app.harness.io")
    service = HarnessCodeService(client=StubHarnessClient({}), token_provider=lambda: "pat", settings=settings)

    with pytest.raises(ConfigurationError):
        service._repo_ref("finance/api", "svc")


def test_collect_context_files_delegates_to_github_walker(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("module.exports={}\n")

    client = StubHarnessClient({})
    service = _make_service(client)

    files = service.collect_context_files(
        repository_root=tmp_path,
        max_files=10,
        max_file_bytes=1024 * 1024,
    )

    paths = {p.name for p in files}
    assert "main.py" in paths
    assert "junk.js" not in paths
