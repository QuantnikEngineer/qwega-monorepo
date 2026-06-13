"""
Tests for Wave 3 multi-tenancy: projects, members, services, settings, secrets.
================================================================================
Covers Project CRUD, membership, service registry, per-project tool
configuration, and Fernet secret encryption.
"""

import pytest
from httpx import AsyncClient

# Passwords matching conftest.py
SUPERADMIN_PASSWORD = "SuperAdmin123!@#"
PM_PASSWORD = "PMUser123!@#"
DEV_PASSWORD = "DevUser123!@#"
FDE_PASSWORD = "FDEUser123!@#"


# ── Local fixtures ──────────────────────────────────────────────────────────
# Patch roles with project capabilities so JWT tokens include them.
# conftest seed_roles has Phase-5-era capabilities only.


@pytest.fixture
async def patched_roles(async_session, seed_roles):
    """Add project capabilities to roles for multi-tenancy tests."""
    seed_roles["superadmin"].capabilities = list(set(
        seed_roles["superadmin"].capabilities
        + ["project:create", "project:manage", "project:manage_members",
           "project:configure_integrations"]
    ))
    seed_roles["pm"].capabilities = list(set(
        seed_roles["pm"].capabilities
        + ["project:create", "project:manage_members"]
    ))
    seed_roles["mlops"].capabilities = list(set(
        seed_roles["mlops"].capabilities
        + ["project:configure_integrations", "integration:configure_tools"]
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
async def pm_tok(patched_roles, seed_pm, test_client):
    """JWT for PM (with project:create, project:manage_members)."""
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "pm@wipro.com", "password": PM_PASSWORD},
    )
    assert resp.status_code == 200, f"PM login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
async def dev_tok(patched_roles, seed_dev_user, test_client):
    """JWT for developer (no project capabilities)."""
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "dev@wipro.com", "password": DEV_PASSWORD},
    )
    assert resp.status_code == 200, f"Dev login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
async def fde_tok(patched_roles, seed_fde_user, test_client):
    """JWT for MLOps / FDE user (integration:configure_tools + project:configure_integrations)."""
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "fde@wipro.com", "password": FDE_PASSWORD},
    )
    assert resp.status_code == 200, f"FDE login failed: {resp.text}"
    return resp.json()["access_token"]


# ── Header helpers ──────────────────────────────────────────────────────────

def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Reusable API helpers ────────────────────────────────────────────────────

async def _create_project(
    client: AsyncClient,
    token: str,
    name: str = "Test Project",
    description: str | None = "desc",
    slug: str | None = None,
) -> dict:
    body: dict = {"name": name, "description": description}
    if slug is not None:
        body["slug"] = slug
    resp = await client.post("/api/projects", json=body, headers=_h(token))
    return resp


async def _create_service(
    client: AsyncClient,
    token: str,
    tool_id: str = "github",
    name: str = "GitHub",
    **extra,
) -> dict:
    body = {"tool_id": tool_id, "name": name, **extra}
    resp = await client.post("/api/services", json=body, headers=_h(token))
    return resp


# ═════════════════════════════════════════════════════════════════════════════
# 1. Project CRUD
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_pm_creates_project(test_client, pm_tok, seed_org):
    """PM with project:create can create a project."""
    resp = await _create_project(test_client, pm_tok, name="Alpha")
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alpha"
    assert data["slug"] == "alpha"
    assert data["orgId"] == seed_org.id
    assert data["isActive"] is True


@pytest.mark.anyio
async def test_superadmin_creates_project(test_client, sa_token, seed_org):
    """SuperAdmin (platform:manage) can create a project."""
    resp = await _create_project(test_client, sa_token, name="Beta Project")
    assert resp.status_code == 201
    assert resp.json()["slug"] == "beta-project"


@pytest.mark.anyio
async def test_dev_cannot_create_project(test_client, dev_tok):
    """Developer without project:create is rejected."""
    resp = await _create_project(test_client, dev_tok, name="Nope")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_slug_auto_generated_from_name(test_client, sa_token):
    """Slug is auto-generated from name when not provided."""
    resp = await _create_project(test_client, sa_token, name="My Cool Project!")
    assert resp.status_code == 201
    assert resp.json()["slug"] == "my-cool-project"


@pytest.mark.anyio
async def test_explicit_slug_used(test_client, sa_token):
    """Explicit slug overrides auto-generation."""
    resp = await _create_project(test_client, sa_token, name="Foo", slug="custom-slug")
    assert resp.status_code == 201
    assert resp.json()["slug"] == "custom-slug"


@pytest.mark.anyio
async def test_duplicate_slug_same_org_rejected(test_client, sa_token):
    """Creating a second project with the same slug in the same org is rejected."""
    resp1 = await _create_project(test_client, sa_token, name="Dup", slug="dup-slug")
    assert resp1.status_code == 201

    resp2 = await _create_project(test_client, sa_token, name="Dup2", slug="dup-slug")
    assert resp2.status_code in (400, 409)
    assert "slug" in resp2.json()["detail"].lower()


@pytest.mark.anyio
async def test_same_slug_different_org_allowed(test_client, sa_token, async_session, seed_org):
    """Same slug in a different org is allowed (create second org + user)."""
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.org import Org
    from app.models.role import Role, UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    # Create first project in seed_org
    resp1 = await _create_project(test_client, sa_token, name="Cross", slug="cross-org")
    assert resp1.status_code == 201

    # Create second org + superadmin user
    org2 = Org(name="Other Corp", slug="other-corp")
    async_session.add(org2)
    await async_session.flush()

    sa_role = (await async_session.execute(
        __import__("sqlalchemy").select(Role).where(Role.name == "superadmin")
    )).scalar_one()

    user2 = User(
        normalized_email="admin2@wipro.com",
        display_name="Admin2",
        org_id=org2.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user2)
    await async_session.flush()
    async_session.add(AuthMethod(
        user_id=user2.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password("Admin2Pass!23"),
        is_primary=True,
        must_change_password=False,
    ))
    async_session.add(UserRole(
        user_id=user2.id, role_id=sa_role.id,
        scope_type="org", scope_id=org2.id, source="admin_assigned",
    ))
    await async_session.commit()

    login = await test_client.post(
        "/api/auth/login",
        json={"email": "admin2@wipro.com", "password": "Admin2Pass!23"},
    )
    assert login.status_code == 200, f"Org2 SA login failed: {login.text}"
    token2 = login.json()["access_token"]

    # Same slug in different org should succeed
    resp2 = await _create_project(test_client, token2, name="Cross", slug="cross-org")
    assert resp2.status_code == 201


@pytest.mark.anyio
async def test_update_project_by_creator(test_client, pm_tok):
    """Creator can update their project."""
    create_resp = await _create_project(test_client, pm_tok, name="Updatable")
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}",
        json={"name": "Updated Name", "description": "new desc"},
        headers=_h(pm_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.anyio
async def test_update_project_by_noncreator_rejected(test_client, sa_token, dev_tok):
    """Non-creator/non-admin cannot update a project."""
    create_resp = await _create_project(test_client, sa_token, name="NoTouch")
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}",
        json={"name": "Hacked"},
        headers=_h(dev_tok),
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_delete_project_by_superadmin(test_client, sa_token):
    """SuperAdmin can soft-delete a project."""
    create_resp = await _create_project(test_client, sa_token, name="Deletable")
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    resp = await test_client.delete(f"/api/projects/{pid}", headers=_h(sa_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "deactivated"

    # Project should no longer appear in list
    listing = await test_client.get("/api/projects", headers=_h(sa_token))
    ids = [p["id"] for p in listing.json()["projects"]]
    assert pid not in ids


@pytest.mark.anyio
async def test_delete_project_by_pm_rejected(test_client, pm_tok):
    """PM cannot delete a project (requires platform:manage)."""
    create_resp = await _create_project(test_client, pm_tok, name="NoDel")
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    resp = await test_client.delete(f"/api/projects/{pid}", headers=_h(pm_tok))
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_list_projects_returns_active_only(test_client, sa_token):
    """GET /api/projects returns only active projects (multi-project model)."""
    r1 = await _create_project(test_client, sa_token, name="Active1", slug="active1")
    assert r1.status_code == 201

    listing = await test_client.get("/api/projects", headers=_h(sa_token))
    assert listing.status_code == 200
    slugs = {p["slug"] for p in listing.json()["projects"]}
    assert "active1" in slugs

    # Deactivate the project — list should be empty
    await test_client.delete(f"/api/projects/{r1.json()['id']}", headers=_h(sa_token))
    listing2 = await test_client.get("/api/projects", headers=_h(sa_token))
    assert listing2.status_code == 200
    assert len(listing2.json()["projects"]) == 0


@pytest.mark.anyio
async def test_get_project_by_id(test_client, sa_token, seed_org):
    """GET /api/projects/{id} returns project details."""
    create_resp = await _create_project(test_client, sa_token, name="Detail")
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    resp = await test_client.get(f"/api/projects/{pid}", headers=_h(sa_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pid
    assert data["name"] == "Detail"
    assert data["orgId"] == seed_org.id


# ═════════════════════════════════════════════════════════════════════════════
# 2. Project Members
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_pm_adds_dev_as_member(test_client, pm_tok, sa_token, seed_dev_user):
    """PM (project:manage_members) can add a user to a project."""
    proj = await _create_project(test_client, pm_tok, name="MemberTest")
    assert proj.status_code == 201
    pid = proj.json()["id"]

    resp = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(pm_tok),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "added"


@pytest.mark.anyio
async def test_superadmin_adds_member(test_client, sa_token, seed_dev_user):
    """SuperAdmin can add members via platform:manage."""
    proj = await _create_project(test_client, sa_token, name="SAMember")
    pid = proj.json()["id"]

    resp = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_list_members(test_client, sa_token, seed_dev_user, seed_pm):
    """GET /api/projects/{id}/members returns correct member data."""
    proj = await _create_project(test_client, sa_token, name="ListMem")
    pid = proj.json()["id"]

    # Add dev as member so SA can list (SA is admin, can always list)
    await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )

    resp = await test_client.get(f"/api/projects/{pid}/members", headers=_h(sa_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    emails = [m["email"] for m in data["members"]]
    assert "dev@wipro.com" in emails


@pytest.mark.anyio
async def test_remove_member(test_client, sa_token, seed_dev_user):
    """Remove a member from a project."""
    proj = await _create_project(test_client, sa_token, name="RemMem")
    pid = proj.json()["id"]

    await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )

    resp = await test_client.delete(
        f"/api/projects/{pid}/members/{seed_dev_user.id}",
        headers=_h(sa_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"


@pytest.mark.anyio
async def test_add_member_cross_org_rejected(
    test_client, sa_token, async_session, seed_org,
):
    """Adding a user from a different org is rejected (400)."""
    from app.models.org import Org
    from app.models.user import User, UserStatus

    # Create user in a different org
    org2 = Org(name="External Corp", slug="ext-corp")
    async_session.add(org2)
    await async_session.flush()

    ext_user = User(
        normalized_email="ext@external.com",
        display_name="External",
        org_id=org2.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(ext_user)
    await async_session.commit()
    await async_session.refresh(ext_user)

    proj = await _create_project(test_client, sa_token, name="NoExternal")
    pid = proj.json()["id"]

    resp = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": ext_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )
    assert resp.status_code == 400
    assert "organization" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_dev_cannot_add_members(test_client, sa_token, dev_tok, seed_dev_user):
    """Developer without project:manage_members cannot add members."""
    proj = await _create_project(test_client, sa_token, name="NoDevAdd")
    pid = proj.json()["id"]

    resp = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(dev_tok),
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_duplicate_role_assignment_rejected(test_client, sa_token, seed_dev_user):
    """Adding the same role twice to a user in a project is rejected."""
    proj = await _create_project(test_client, sa_token, name="DupRole")
    pid = proj.json()["id"]

    r1 = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )
    assert r1.status_code == 201

    r2 = await test_client.post(
        f"/api/projects/{pid}/members",
        json={"user_id": seed_dev_user.id, "role_name": "developer"},
        headers=_h(sa_token),
    )
    assert r2.status_code == 400
    assert "already has role" in r2.json()["detail"].lower()


@pytest.mark.anyio
async def test_remove_nonmember_returns_404(test_client, sa_token, seed_dev_user):
    """Removing a user who is not a member returns 404."""
    proj = await _create_project(test_client, sa_token, name="NoMember")
    pid = proj.json()["id"]

    resp = await test_client.delete(
        f"/api/projects/{pid}/members/{seed_dev_user.id}",
        headers=_h(sa_token),
    )
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 3. Service Registry
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_superadmin_creates_service(test_client, sa_token):
    """SuperAdmin can register a platform service."""
    resp = await _create_service(
        test_client, sa_token,
        tool_id="github", name="GitHub",
        description="GitHub integration", category="vcs",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["toolId"] == "github"
    assert data["enabled"] is True


@pytest.mark.anyio
async def test_list_services(test_client, sa_token, dev_tok):
    """Any authenticated user can list services."""
    await _create_service(test_client, sa_token, tool_id="jira", name="Jira")

    resp = await test_client.get("/api/services", headers=_h(dev_tok))
    assert resp.status_code == 200
    tool_ids = [s["toolId"] for s in resp.json()["services"]]
    assert "jira" in tool_ids


@pytest.mark.anyio
async def test_superadmin_disables_service(test_client, sa_token):
    """SuperAdmin can disable a platform service."""
    create_resp = await _create_service(
        test_client, sa_token, tool_id="sonar", name="SonarQube",
    )
    sid = create_resp.json()["id"]

    resp = await test_client.put(
        f"/api/services/{sid}",
        json={"enabled": False},
        headers=_h(sa_token),
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


@pytest.mark.anyio
async def test_nonadmin_cannot_create_service(test_client, dev_tok):
    """Non-admin cannot create a platform service."""
    resp = await _create_service(
        test_client, dev_tok, tool_id="nope", name="Nope",
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_duplicate_tool_id_rejected(test_client, sa_token):
    """Duplicate tool_id returns 409."""
    r1 = await _create_service(test_client, sa_token, tool_id="dup-tool", name="Dup1")
    assert r1.status_code == 201

    r2 = await _create_service(test_client, sa_token, tool_id="dup-tool", name="Dup2")
    assert r2.status_code == 409


# ═════════════════════════════════════════════════════════════════════════════
# 4. Project Settings / Tool Configuration
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_get_project_settings_returns_services(test_client, sa_token):
    """GET /api/projects/{id}/settings returns platform services with defaults."""
    await _create_service(test_client, sa_token, tool_id="set-gh", name="GitHub")
    proj = await _create_project(test_client, sa_token, name="Settings1")
    pid = proj.json()["id"]

    resp = await test_client.get(
        f"/api/projects/{pid}/settings", headers=_h(sa_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["projectId"] == pid
    assert len(data["tools"]) >= 1
    gh = next(t for t in data["tools"] if t["toolId"] == "set-gh")
    assert gh["platformEnabled"] is True
    assert gh["configured"] is False


@pytest.mark.anyio
async def test_superadmin_configures_tool(test_client, sa_token):
    """SuperAdmin can configure a tool for a project."""
    svc = await _create_service(test_client, sa_token, tool_id="cfg-gh", name="GitHub")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="CfgProj")
    pid = proj.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {"repo_url": "https://github.com/test/repo"},
            "is_enabled": True,
            "secrets": {"pat_token": "ghp_test123"},
        },
        headers=_h(sa_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"
    assert resp.json()["isEnabled"] is True


@pytest.mark.anyio
async def test_mlops_configures_tool(test_client, sa_token, fde_tok):
    """MLOps with integration:configure_tools can configure a tool."""
    svc = await _create_service(test_client, sa_token, tool_id="mlops-gh", name="GH ML")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="MLProj")
    pid = proj.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={"config": {"key": "val"}, "is_enabled": True, "secrets": {}},
        headers=_h(fde_tok),
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_dev_cannot_configure_tool(test_client, sa_token, dev_tok):
    """Developer without integration capabilities cannot configure tools."""
    svc = await _create_service(test_client, sa_token, tool_id="dev-no", name="Blocked")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="NoDevCfg")
    pid = proj.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={"config": {}, "is_enabled": True, "secrets": {}},
        headers=_h(dev_tok),
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_disabled_service_cannot_be_configured(test_client, sa_token):
    """Configuring a platform-disabled service returns 400."""
    svc = await _create_service(test_client, sa_token, tool_id="dis-svc", name="Disabled")
    sid = svc.json()["id"]

    # Disable service
    await test_client.put(
        f"/api/services/{sid}",
        json={"enabled": False},
        headers=_h(sa_token),
    )

    proj = await _create_project(test_client, sa_token, name="DisCfg")
    pid = proj.json()["id"]

    resp = await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={"config": {}, "is_enabled": True, "secrets": {}},
        headers=_h(sa_token),
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_secrets_not_returned_via_get(test_client, sa_token):
    """GET settings returns secretKeys list but not actual secret values."""
    svc = await _create_service(test_client, sa_token, tool_id="sec-gh", name="GH Sec")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="SecProj")
    pid = proj.json()["id"]

    # Store a secret
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {"url": "https://github.com"},
            "is_enabled": True,
            "secrets": {"pat_token": "ghp_supersecret"},
        },
        headers=_h(sa_token),
    )

    # Read back — should have secretKeys but not values
    resp = await test_client.get(
        f"/api/projects/{pid}/settings", headers=_h(sa_token),
    )
    assert resp.status_code == 200
    tool = next(t for t in resp.json()["tools"] if t["toolId"] == "sec-gh")
    assert tool["hasSecrets"] is True
    assert "pat_token" in tool["secretKeys"]
    # The response body should NOT contain the plaintext anywhere
    assert "ghp_supersecret" not in str(resp.json())


@pytest.mark.anyio
async def test_settings_upsert_overwrites(test_client, sa_token):
    """PUT settings twice overwrites config and secrets."""
    svc = await _create_service(test_client, sa_token, tool_id="upsert-t", name="Upsert")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="UpsertProj")
    pid = proj.json()["id"]

    # First write
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={"config": {"v": 1}, "is_enabled": True, "secrets": {"key": "first"}},
        headers=_h(sa_token),
    )

    # Overwrite
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={"config": {"v": 2}, "is_enabled": False, "secrets": {"key": "second"}},
        headers=_h(sa_token),
    )

    resp = await test_client.get(f"/api/projects/{pid}/settings", headers=_h(sa_token))
    tool = next(t for t in resp.json()["tools"] if t["toolId"] == "upsert-t")
    assert tool["config"]["v"] == 2
    assert tool["projectEnabled"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 5. Secret encryption (unit tests)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_encrypt_decrypt_roundtrip():
    """encrypt → decrypt returns the original value."""
    from app.services.secret_service import encrypt_secret, decrypt_secret

    original = "ghp_mysupersecrettoken123"
    encrypted = encrypt_secret(original)
    assert decrypt_secret(encrypted) == original


@pytest.mark.anyio
async def test_encrypted_value_is_not_plaintext():
    """Encrypted output must not contain the plaintext."""
    from app.services.secret_service import encrypt_secret

    original = "sk-live-ABCDEF12345"
    encrypted = encrypt_secret(original)
    assert original not in encrypted
    assert encrypted != original


@pytest.mark.anyio
async def test_different_calls_produce_different_ciphertext():
    """Fernet produces unique ciphertext per call (nonce-based)."""
    from app.services.secret_service import encrypt_secret

    original = "same-input"
    c1 = encrypt_secret(original)
    c2 = encrypt_secret(original)
    assert c1 != c2  # Fernet uses random IV


# ═════════════════════════════════════════════════════════════════════════════
# 6. Sprint 7 — End-to-End Onboarding & Access Control
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_get_settings_requires_use_tools_capability(test_client, dev_tok, sa_token):
    """Developer with integration:use_tools can read settings; someone without cannot."""
    proj = await _create_project(test_client, sa_token, name="AuthTest")
    pid = proj.json()["id"]

    # Developer has integration:use_tools → should succeed
    resp = await test_client.get(f"/api/projects/{pid}/settings", headers=_h(dev_tok))
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_internal_settings_endpoint_requires_api_key(test_client, sa_token):
    """Internal endpoint rejects calls without valid API key."""
    proj = await _create_project(test_client, sa_token, name="IntTest")
    pid = proj.json()["id"]

    # No key → 403
    resp = await test_client.get(f"/api/internal/project-settings/{pid}")
    assert resp.status_code == 403

    # Wrong key → 403
    resp = await test_client.get(
        f"/api/internal/project-settings/{pid}",
        headers={"X-Internal-Key": "wrong-key"},
    )
    assert resp.status_code == 403

    # Correct key → 200
    from app.core.config import get_settings
    resp = await test_client.get(
        f"/api/internal/project-settings/{pid}",
        headers={"X-Internal-Key": get_settings().internal_api_key},
    )
    assert resp.status_code == 200
    assert resp.json()["projectId"] == pid
    assert isinstance(resp.json()["tools"], dict)


@pytest.mark.anyio
async def test_internal_settings_returns_enabled_tools_only(test_client, sa_token):
    """Internal endpoint returns only enabled tool configs (no secrets)."""
    svc = await _create_service(test_client, sa_token, tool_id="int-jira", name="Jira Int")
    sid = svc.json()["id"]
    proj = await _create_project(test_client, sa_token, name="IntTools")
    pid = proj.json()["id"]

    # Configure and enable the tool
    await test_client.put(
        f"/api/projects/{pid}/settings/{sid}",
        json={
            "config": {"url": "https://acme.atlassian.net", "projectKey": "ACME"},
            "is_enabled": True,
            "secrets": {"patToken": "secret-value"},
        },
        headers=_h(sa_token),
    )

    from app.core.config import get_settings
    resp = await test_client.get(
        f"/api/internal/project-settings/{pid}",
        headers={"X-Internal-Key": get_settings().internal_api_key},
    )
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert "int-jira" in tools
    assert tools["int-jira"]["url"] == "https://acme.atlassian.net"
    assert tools["int-jira"]["projectKey"] == "ACME"
    # Secrets must NOT be in the response
    assert "patToken" not in tools["int-jira"]


@pytest.mark.anyio
async def test_onboarding_flow_sa_creates_pm_pm_creates_project(
    test_client, sa_token, seed_org, patched_roles
):
    """Sprint 7.1-7.2: SA creates PM → PM activates → logs in → creates project."""
    # 7.1: SA creates PM user
    create_resp = await test_client.post(
        "/api/users",
        json={
            "email": "pm-flow@wipro.com",
            "display_name": "Flow PM",
            "role_assignments": [{"role_name": "pm", "scope_type": "org"}],
        },
        headers=_h(sa_token),
    )
    assert create_resp.status_code == 201, f"PM creation failed: {create_resp.text}"
    activation_url = create_resp.json().get("activation_url", "")
    assert "token=" in activation_url, "No activation URL returned"
    activation_token = activation_url.split("token=")[-1]

    # Activate the PM user via the activation endpoint
    activate_resp = await test_client.post(
        "/api/auth/activate",
        json={
            "token": activation_token,
            "password": "FlowPM123!@#",
            "confirm_password": "FlowPM123!@#",
        },
    )
    assert activate_resp.status_code == 200, f"Activation failed: {activate_resp.text}"

    # 7.2: PM logs in
    login_resp = await test_client.post(
        "/api/auth/login",
        json={"email": "pm-flow@wipro.com", "password": "FlowPM123!@#"},
    )
    assert login_resp.status_code == 200, f"PM login failed: {login_resp.text}"
    pm_token = login_resp.json()["access_token"]

    # PM creates project
    proj_resp = await _create_project(test_client, pm_token, name="Project Alpha")
    assert proj_resp.status_code == 201
    assert proj_resp.json()["name"] == "Project Alpha"
    assert proj_resp.json()["orgId"] == seed_org.id


@pytest.mark.anyio
async def test_config_defaults_not_leaked_as_config(test_client, sa_token):
    """default_config.fields should not leak into tool.config for unconfigured tools."""
    svc = await _create_service(
        test_client, sa_token, tool_id="leak-test", name="LeakTest",
        default_config={"defaults": {"url": ""}, "fields": [{"key": "url", "label": "URL"}]},
    )
    proj = await _create_project(test_client, sa_token, name="LeakProj")
    pid = proj.json()["id"]

    resp = await test_client.get(f"/api/projects/{pid}/settings", headers=_h(sa_token))
    tool = next(t for t in resp.json()["tools"] if t["toolId"] == "leak-test")
    # config should be defaults (url=""), not the full schema with fields[]
    assert "fields" not in tool["config"]
    assert tool["config"] == {"url": ""}
    # defaultConfig should still have fields for the frontend
    assert "fields" in tool["defaultConfig"]


@pytest.mark.anyio
async def test_multiple_projects_in_same_org(test_client, sa_token):
    """Multiple projects with different names are allowed in the same org."""
    resp1 = await _create_project(test_client, sa_token, name="First")
    assert resp1.status_code == 201

    resp2 = await _create_project(test_client, sa_token, name="Second")
    assert resp2.status_code == 201
    assert resp2.json()["name"] == "Second"
