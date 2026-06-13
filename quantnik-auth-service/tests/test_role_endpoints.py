"""Role endpoint integration tests.

Tests GET /api/roles and GET /api/roles/capabilities.
Validates all 6 roles are returned with correct capability counts (6-role model).
"""

import pytest


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListRoles:
    """GET /api/roles — list all system roles."""

    async def test_list_roles_returns_six(self, test_client, superadmin_token, seed_roles):
        """GET /api/roles → 200, returns all 6 roles (6-role model)."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        roles = response.json()["roles"]
        assert len(roles) == 6
        role_names = {r["name"] for r in roles}
        assert role_names == {"superadmin", "pm", "po_sm_ba", "developer", "tester", "mlops"}

    async def test_no_orgadmin_role(self, test_client, superadmin_token, seed_roles):
        """D-01: OrgAdmin role dropped in Phase 5."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        role_names = [r["name"] for r in response.json()["roles"]]
        assert "orgadmin" not in role_names
        assert set(role_names) == {"superadmin", "pm", "po_sm_ba", "developer", "tester", "mlops"}

    async def test_role_descriptions(self, test_client, superadmin_token, seed_roles):
        """Roles have human-readable descriptions (6-role model)."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        roles = {r["name"]: r["description"] for r in response.json()["roles"]}
        assert roles["pm"] == "Project manager — creates and manages team members"
        assert roles["mlops"] == "ML/AI operations — testing, code analysis, validation"

    async def test_list_roles_includes_capabilities(self, test_client, superadmin_token, seed_roles):
        """GET /api/roles → each role has capabilities list."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        for role in response.json()["roles"]:
            assert "capabilities" in role
            assert isinstance(role["capabilities"], list)

    async def test_superadmin_has_10_capabilities(self, test_client, superadmin_token, seed_roles):
        """SuperAdmin role should have exactly 10 capabilities (Phase 5 simplified)."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        roles = response.json()["roles"]
        sa = next(r for r in roles if r["name"] == "superadmin")
        assert len(sa["capabilities"]) == 10
        # Verify key capabilities are present
        assert "platform:manage" in sa["capabilities"]
        assert "org:manage_users" in sa["capabilities"]
        assert "admin:manage_sessions" in sa["capabilities"]

    async def test_developer_has_4_capabilities(self, test_client, superadmin_token, seed_roles):
        """developer role should have exactly 4 capabilities (6-role model)."""
        response = await test_client.get(
            "/api/roles",
            headers=auth_header(superadmin_token),
        )
        roles = response.json()["roles"]
        dev = next(r for r in roles if r["name"] == "developer")
        assert len(dev["capabilities"]) == 4
        assert "platform:manage" not in dev["capabilities"]
        assert "org:manage_users" not in dev["capabilities"]

    async def test_roles_require_auth(self, test_client, seed_roles, seed_org):
        """GET /api/roles without token → 401."""
        response = await test_client.get("/api/roles")
        assert response.status_code == 401


@pytest.mark.integration
class TestCapabilityMatrix:
    """GET /api/roles/capabilities — categorized capability matrix."""

    async def test_capability_matrix(self, test_client, superadmin_token, seed_roles):
        """GET /api/roles/capabilities → 200, returns categorized structure."""
        response = await test_client.get(
            "/api/roles/capabilities",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        # Should have categories from known prefixes
        category_names = set(data["categories"].keys())
        assert "Platform" in category_names

    async def test_capability_matrix_platform_manage(self, test_client, superadmin_token, seed_roles):
        """platform:manage should list only superadmin."""
        response = await test_client.get(
            "/api/roles/capabilities",
            headers=auth_header(superadmin_token),
        )
        categories = response.json()["categories"]
        platform_caps = categories.get("Platform", [])
        pm_cap = next((c for c in platform_caps if c["name"] == "platform:manage"), None)
        assert pm_cap is not None
        assert "superadmin" in pm_cap["roles"]
        assert len(pm_cap["roles"]) == 1  # Only superadmin has platform:manage


@pytest.mark.integration
class TestListProjects:
    """GET /api/projects — project listing for scope selection."""

    async def test_list_projects(self, test_client, superadmin_token):
        """GET /api/projects → 200, returns projects list (may be empty)."""
        response = await test_client.get(
            "/api/projects",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        assert "projects" in response.json()

    async def test_projects_require_auth(self, test_client, seed_roles, seed_org):
        """GET /api/projects without token → 401."""
        response = await test_client.get("/api/projects")
        assert response.status_code == 401
