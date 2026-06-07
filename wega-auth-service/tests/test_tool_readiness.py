"""
Tests for tool readiness computation and internal secrets endpoint.
=================================================================
Covers:
  A. _compute_tool_ready() — unit tests for all readiness combinations
  B. GET /api/internal/project-secrets/{project_id}/{tool_id} — integration
  C. Ready flag inclusion in GET /api/projects/{id}/settings
"""

import pytest
from httpx import AsyncClient

from app.api.services import (
    REQUIRED_CONFIG_FIELDS,
    REQUIRED_SECRET_KEYS,
    _compute_tool_ready,
    _DEFAULT_REQUIRED_SECRETS,
)

SUPERADMIN_PASSWORD = "SuperAdmin123!@#"


# ── Header / API helpers (mirror test_multitenancy.py) ──────────────────────

def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, token: str, name: str = "Test Project"):
    return await client.post(
        "/api/projects", json={"name": name, "description": "desc"}, headers=_h(token),
    )


async def _create_service(
    client: AsyncClient, token: str, tool_id: str = "github", name: str = "GitHub", **extra,
):
    body = {"tool_id": tool_id, "name": name, **extra}
    return await client.post("/api/services", json=body, headers=_h(token))


# ── Local fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
async def patched_roles(async_session, seed_roles):
    """Add project capabilities to roles for integration tests."""
    seed_roles["superadmin"].capabilities = list(set(
        seed_roles["superadmin"].capabilities
        + ["project:create", "project:manage", "project:manage_members",
           "project:configure_integrations"]
    ))
    await async_session.commit()
    for r in seed_roles.values():
        await async_session.refresh(r)
    return seed_roles


@pytest.fixture
async def sa_token(patched_roles, seed_superadmin, test_client):
    """JWT for SuperAdmin (with project capabilities)."""
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"SA login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
async def internal_key():
    """Return the internal API key from settings."""
    from app.core.config import get_settings
    return get_settings().internal_api_key


@pytest.fixture
async def configured_jira(test_client, sa_token):
    """Create a project + Jira service fully configured with config and secrets.

    Returns (project_id, service_id, tool_id).
    """
    svc = await _create_service(test_client, sa_token, tool_id="jira", name="Jira")
    assert svc.status_code == 201 or svc.status_code == 200, svc.text
    sid = svc.json()["id"]

    proj = await _create_project(test_client, sa_token, name="ReadyProject")
    assert proj.status_code == 201 or proj.status_code == 200, proj.text
    pid = proj.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {
                "url": "https://acme.atlassian.net",
                "projectKey": "ACME",
                "email": "user@acme.com",
            },
            "is_enabled": True,
            "secrets": {"patToken": "jira-secret-pat-123"},
        },
        headers=_h(sa_token),
    )
    assert resp.status_code == 200, resp.text
    return pid, sid, "jira"


# ═════════════════════════════════════════════════════════════════════════════
# A. _compute_tool_ready() — pure unit tests
# ═════════════════════════════════════════════════════════════════════════════


class TestComputeToolReady:
    """Unit tests for _compute_tool_ready() — no DB or HTTP needed."""

    def test_all_conditions_met(self):
        """All conditions met → True."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://x", "projectKey": "PK", "email": "a@b.c"},
            secret_keys=["patToken"],
        ) is True

    def test_platform_disabled(self):
        """Platform disabled → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=False,
            project_enabled=True,
            configured=True,
            config={"url": "https://x", "projectKey": "PK", "email": "a@b.c"},
            secret_keys=["patToken"],
        ) is False

    def test_project_disabled(self):
        """Project disabled → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=False,
            configured=True,
            config={"url": "https://x", "projectKey": "PK", "email": "a@b.c"},
            secret_keys=["patToken"],
        ) is False

    def test_not_configured(self):
        """Not configured → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=True,
            configured=False,
            config={"url": "https://x", "projectKey": "PK", "email": "a@b.c"},
            secret_keys=["patToken"],
        ) is False

    def test_missing_required_config_field(self):
        """Missing required config field (e.g., no email for Jira) → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://x", "projectKey": "PK"},
            secret_keys=["patToken"],
        ) is False

    def test_empty_string_config_field(self):
        """Empty string config field → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://x", "projectKey": "PK", "email": "  "},
            secret_keys=["patToken"],
        ) is False

    def test_missing_required_secret(self):
        """Missing required secret (patToken) → False."""
        assert _compute_tool_ready(
            tool_id="jira",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://x", "projectKey": "PK", "email": "a@b.c"},
            secret_keys=[],
        ) is False

    def test_trivy_no_secrets_required(self):
        """Trivy has empty required secrets → True without secrets."""
        assert _compute_tool_ready(
            tool_id="trivy",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"serverUrl": "https://trivy.local"},
            secret_keys=[],
        ) is True

    def test_unknown_tool_defaults_url_and_pat(self):
        """Unknown tool defaults to requiring 'url' + 'patToken'."""
        # Passes with url in config and patToken in secrets
        assert _compute_tool_ready(
            tool_id="some-new-tool",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://new-tool.io"},
            secret_keys=["patToken"],
        ) is True

        # Fails without url
        assert _compute_tool_ready(
            tool_id="some-new-tool",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={},
            secret_keys=["patToken"],
        ) is False

        # Fails without patToken
        assert _compute_tool_ready(
            tool_id="some-new-tool",
            platform_enabled=True,
            project_enabled=True,
            configured=True,
            config={"url": "https://new-tool.io"},
            secret_keys=[],
        ) is False


# ═════════════════════════════════════════════════════════════════════════════
# B. Internal secrets endpoint — integration tests
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_internal_secrets_returns_decrypted(
    test_client, sa_token, internal_key, configured_jira,
):
    """200: Returns decrypted secrets for a ready tool (email + secrets.patToken)."""
    pid, _sid, tool_id = configured_jira

    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/{tool_id}",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tool_id"] == tool_id
    assert body["auth_type"] == "basic"
    assert body["config"]["email"] == "user@acme.com"
    assert "patToken" in body["secrets"]
    assert body["secrets"]["patToken"] == "jira-secret-pat-123"


@pytest.mark.anyio
async def test_internal_secrets_404_nonexistent_tool(
    test_client, sa_token, internal_key, configured_jira,
):
    """404 for a tool_id that does not exist in the service registry."""
    pid, _sid, _tool_id = configured_jira

    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/nonexistent-tool",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_internal_secrets_404_unconfigured_project(
    test_client, sa_token, internal_key,
):
    """404 for a project/tool combo that hasn't been configured."""
    # Create service but no project settings
    svc = await _create_service(test_client, sa_token, tool_id="sec-gh", name="GH Sec")
    assert svc.status_code in (200, 201), svc.text

    resp = await test_client.get(
        "/api/internal/project-secrets/nonexistent-project-id/sec-gh",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_internal_secrets_424_missing_config_fields(
    test_client, sa_token, internal_key,
):
    """424 for a tool missing required config fields (not ready)."""
    svc = await _create_service(test_client, sa_token, tool_id="jira", name="Jira 424 Cfg")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="MissingCfg")
    pid = proj.json()["id"]

    # Configure Jira WITHOUT required email field
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {"url": "https://acme.atlassian.net", "projectKey": "ACME"},
            "is_enabled": True,
            "secrets": {"patToken": "some-pat"},
        },
        headers=_h(sa_token),
    )

    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/jira",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.status_code == 424


@pytest.mark.anyio
async def test_internal_secrets_424_missing_secrets(
    test_client, sa_token, internal_key,
):
    """424 for a tool missing required secrets (not ready)."""
    svc = await _create_service(test_client, sa_token, tool_id="jira", name="Jira 424 Sec")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="MissingSec")
    pid = proj.json()["id"]

    # Configure Jira with all config but NO secrets
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {
                "url": "https://acme.atlassian.net",
                "projectKey": "ACME",
                "email": "user@acme.com",
            },
            "is_enabled": True,
            "secrets": {},
        },
        headers=_h(sa_token),
    )

    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/jira",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.status_code == 424


@pytest.mark.anyio
async def test_internal_secrets_rejects_without_key(
    test_client, sa_token, configured_jira,
):
    """Rejects request without X-Internal-Key → 403."""
    pid, _sid, tool_id = configured_jira

    # No key at all
    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/{tool_id}",
    )
    assert resp.status_code == 403

    # Wrong key
    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/{tool_id}",
        headers={"X-Internal-Key": "wrong-key"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_internal_secrets_cache_control_header(
    test_client, sa_token, internal_key, configured_jira,
):
    """Response includes Cache-Control: no-store on all responses."""
    pid, _sid, tool_id = configured_jira

    # Success case
    resp = await test_client.get(
        f"/api/internal/project-secrets/{pid}/{tool_id}",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp.headers.get("cache-control") == "no-store"

    # 404 case
    resp_404 = await test_client.get(
        f"/api/internal/project-secrets/{pid}/nonexistent-tool",
        headers={"X-Internal-Key": internal_key},
    )
    assert resp_404.headers.get("cache-control") == "no-store"


@pytest.mark.anyio
async def test_internal_secrets_creates_audit_log(
    test_client, sa_token, internal_key, configured_jira, async_session,
):
    """Audit log entry created on access."""
    from sqlalchemy import select
    from app.models.audit import AuditLog

    pid, _sid, tool_id = configured_jira

    await test_client.get(
        f"/api/internal/project-secrets/{pid}/{tool_id}",
        headers={"X-Internal-Key": internal_key},
    )

    result = await async_session.execute(
        select(AuditLog).where(
            AuditLog.action == "internal_secret_retrieval",
            AuditLog.resource_id == f"{pid}/{tool_id}",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.details["success"] is True


# ═════════════════════════════════════════════════════════════════════════════
# C. Ready flag in project settings response
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_settings_ready_true_for_configured_tool(
    test_client, sa_token, configured_jira,
):
    """GET /api/projects/{id}/settings includes ready: true for fully configured tool."""
    pid, _sid, tool_id = configured_jira

    resp = await test_client.get(
        f"/api/projects/{pid}/settings", headers=_h(sa_token),
    )
    assert resp.status_code == 200
    tool = next(t for t in resp.json()["tools"] if t["toolId"] == tool_id)
    assert tool["ready"] is True


@pytest.mark.anyio
async def test_settings_ready_false_for_missing_secrets(
    test_client, sa_token,
):
    """GET /api/projects/{id}/settings includes ready: false when secrets missing."""
    svc = await _create_service(test_client, sa_token, tool_id="jira", name="Jira NoSec")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="NoSecReady")
    pid = proj.json()["id"]

    # Configure with all config but empty secrets
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {
                "url": "https://acme.atlassian.net",
                "projectKey": "ACME",
                "email": "user@acme.com",
            },
            "is_enabled": True,
            "secrets": {},
        },
        headers=_h(sa_token),
    )

    resp = await test_client.get(
        f"/api/projects/{pid}/settings", headers=_h(sa_token),
    )
    assert resp.status_code == 200
    tool = next(t for t in resp.json()["tools"] if t["toolId"] == "jira")
    assert tool["ready"] is False
