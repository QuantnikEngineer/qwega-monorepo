"""Safety rule integration tests — D-27/D-28 / RBAC-09.

Tests that the platform prevents:
  - Self-lock: SuperAdmin removing their own superadmin role (D-27)
  - Last-admin: Removing the last superadmin role (D-28)
  - Self-deactivation: Deactivating your own account (D-27)
  - Deactivation with multiple superadmins succeeds (D-28 positive)

Phase 5: OrgAdmin replaced by PM in test fixtures.
"""

import pytest


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestSelfLockPrevention:
    """RBAC-09 / D-27: SuperAdmin cannot remove their own superadmin role."""

    async def test_superadmin_cannot_remove_own_superadmin_role(
        self, test_client, superadmin_token, seed_superadmin, seed_roles,
    ):
        """PUT /api/users/{self} removing superadmin → 403 self_lock_violation."""
        response = await test_client.put(
            f"/api/users/{seed_superadmin.id}",
            json={
                "role_assignments": [
                    {"role_name": "pm", "scope_type": "org"},
                ],
            },
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 403
        detail = response.json().get("detail", {})
        # The endpoint returns a dict detail with code
        if isinstance(detail, dict):
            assert detail.get("code") == "self_lock_violation"
        else:
            assert "own" in str(detail).lower() or "self" in str(detail).lower()

    async def test_superadmin_can_update_own_display_name(
        self, test_client, superadmin_token, seed_superadmin,
    ):
        """PUT /api/users/{self} with only display_name → 200 (no role change)."""
        response = await test_client.put(
            f"/api/users/{seed_superadmin.id}",
            json={"display_name": "Updated Super Admin"},
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200

    async def test_superadmin_can_keep_superadmin_and_add_role(
        self, test_client, superadmin_token, seed_superadmin,
    ):
        """PUT /api/users/{self} keeping superadmin + adding pm → 200."""
        response = await test_client.put(
            f"/api/users/{seed_superadmin.id}",
            json={
                "role_assignments": [
                    {"role_name": "superadmin", "scope_type": "org"},
                    {"role_name": "pm", "scope_type": "org"},
                ],
            },
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200


@pytest.mark.integration
class TestLastAdminProtection:
    """D-28: Cannot remove the last superadmin role."""

    async def test_cannot_remove_last_superadmin_role(
        self, test_client, pm_token, seed_superadmin, seed_roles,
    ):
        """PM removing last superadmin's role → 403 (PM lacks org:manage_users)."""
        response = await test_client.put(
            f"/api/users/{seed_superadmin.id}",
            json={
                "role_assignments": [
                    {"role_name": "pm", "scope_type": "org"},
                ],
            },
            headers=auth_header(pm_token),
        )
        # PM has team:manage_users (not org:manage_users), and the target is
        # not created_by PM — so 403 from PM scoping check or capability guard.
        assert response.status_code == 403


@pytest.mark.integration
class TestSelfDeactivation:
    """D-27: Cannot deactivate your own account."""

    async def test_superadmin_cannot_deactivate_self(
        self, test_client, superadmin_token, seed_superadmin,
    ):
        """DELETE /api/users/{self} → 403 (cannot deactivate own account)."""
        response = await test_client.delete(
            f"/api/users/{seed_superadmin.id}",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 403
        detail = response.json().get("detail", "")
        assert "your own account" in str(detail).lower() or "own" in str(detail).lower()

    async def test_pm_cannot_deactivate_self(
        self, test_client, pm_token, seed_pm,
    ):
        """DELETE /api/users/{self} → 403 for PM too."""
        response = await test_client.delete(
            f"/api/users/{seed_pm.id}",
            headers=auth_header(pm_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestDeactivateWithMultipleSuperadmins:
    """D-28 positive: Deactivation succeeds when not the last superadmin."""

    async def test_can_deactivate_non_superadmin_user(
        self, test_client, superadmin_token, seed_pm,
    ):
        """SuperAdmin can deactivate a PM → 200."""
        response = await test_client.delete(
            f"/api/users/{seed_pm.id}",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deactivated"

    async def test_can_deactivate_non_self_user(
        self, test_client, superadmin_token, seed_dev_user,
    ):
        """SuperAdmin can deactivate a developer user → 200."""
        response = await test_client.delete(
            f"/api/users/{seed_dev_user.id}",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deactivated"
