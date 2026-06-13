"""Scoped capability check integration tests — D-17.

Tests that login and /me return scoped capability claims
(platform_capabilities, org_capabilities, project_roles, self_capabilities).
Phase 5: PM replaces OrgAdmin; capabilities simplified.
"""

import pytest

# Match conftest.py password constants
SUPERADMIN_PASSWORD = "SuperAdmin123!@#"
PM_PASSWORD = "PMUser123!@#"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestLoginScopedCapabilities:
    """POST /api/auth/login — JWT response includes scoped capability claims."""

    async def test_superadmin_login_returns_scoped_capabilities(
        self, test_client, seed_superadmin,
    ):
        """SuperAdmin login → response includes platform_capabilities with platform:manage."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
        )
        assert response.status_code == 200
        user_data = response.json().get("user", {})

        # SuperAdmin has org-scoped role, so capabilities appear in org_capabilities
        # (platform_capabilities only populated for scope_type="platform")
        all_caps = (
            user_data.get("platform_capabilities", [])
            + user_data.get("org_capabilities", [])
        )
        assert "platform:manage" in all_caps
        assert "org:manage_users" in all_caps

        # Flat capabilities always present for backward compat
        assert "capabilities" in user_data
        assert "platform:manage" in user_data["capabilities"]

    async def test_superadmin_login_returns_flat_roles(
        self, test_client, seed_superadmin,
    ):
        """SuperAdmin login → user.roles includes 'superadmin'."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
        )
        user_data = response.json()["user"]
        assert "superadmin" in user_data["roles"]

    async def test_pm_has_no_platform_manage(
        self, test_client, seed_pm,
    ):
        """PM login → does NOT have platform:manage in any scope."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "pm@wipro.com", "password": PM_PASSWORD},
        )
        assert response.status_code == 200
        user_data = response.json()["user"]
        all_caps = (
            user_data.get("platform_capabilities", [])
            + user_data.get("org_capabilities", [])
            + user_data.get("self_capabilities", [])
        )
        assert "platform:manage" not in all_caps
        assert "platform:manage" not in user_data.get("capabilities", [])

    async def test_pm_has_team_capabilities(
        self, test_client, seed_pm,
    ):
        """PM login → has team:manage_users in flat capabilities."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "pm@wipro.com", "password": PM_PASSWORD},
        )
        user_data = response.json()["user"]
        all_caps = (
            user_data.get("org_capabilities", [])
            + user_data.get("capabilities", [])
        )
        assert "team:manage_users" in all_caps

    async def test_self_capabilities_always_present(
        self, test_client, seed_superadmin,
    ):
        """Every user gets settings:manage_own in self_capabilities."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
        )
        user_data = response.json()["user"]
        assert "settings:manage_own" in user_data.get("self_capabilities", [])


@pytest.mark.integration
class TestMeEndpointScopedCapabilities:
    """GET /api/auth/me — returns scoped capability claims."""

    async def test_me_returns_scoped_capabilities(
        self, test_client, superadmin_token, seed_superadmin,
    ):
        """GET /api/auth/me → response includes scoped capability fields."""
        response = await test_client.get(
            "/api/auth/me",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        data = response.json()

        # Verify scoped capability fields exist
        assert "platform_capabilities" in data
        assert "org_capabilities" in data
        assert "project_roles" in data
        assert "self_capabilities" in data

        # Flat capabilities for backward compat
        assert "capabilities" in data
        assert "roles" in data
        assert "superadmin" in data["roles"]

    async def test_me_returns_self_manage_own(
        self, test_client, superadmin_token, seed_superadmin,
    ):
        """GET /api/auth/me → self_capabilities always includes settings:manage_own."""
        response = await test_client.get(
            "/api/auth/me",
            headers=auth_header(superadmin_token),
        )
        assert "settings:manage_own" in response.json().get("self_capabilities", [])

    async def test_me_without_auth(self, test_client, seed_roles, seed_org):
        """GET /api/auth/me without token → 401."""
        response = await test_client.get("/api/auth/me")
        assert response.status_code == 401


@pytest.mark.integration
class TestAccessTokenClaims:
    """Verify JWT access token encodes correct claims."""

    async def test_access_token_has_correct_structure(
        self, test_client, seed_superadmin,
    ):
        """Login response has access_token, token_type, expires_in."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_refresh_cookie_set(
        self, test_client, seed_superadmin,
    ):
        """Login sets refresh_token cookie."""
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
        )
        assert response.status_code == 200
        assert "refresh_token" in response.cookies
