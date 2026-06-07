"""Session revocation tests — WEGA-1920 / WEGA-1921.

WEGA-1920: role/capability change revokes active refresh sessions.
WEGA-1921: deactivation revokes sessions, /auth/refresh validates user status,
           reactivation forces password reset on next login.
"""

import pytest

from tests.conftest import DEV_PASSWORD, PM_PASSWORD


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(test_client, email: str, password: str):
    """Login helper returning the full response."""
    return await test_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


# ---------------------------------------------------------------------------
# WEGA-1920 — Role / capability change revokes active sessions
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRoleChangeRevokesSessions:
    """WEGA-1920: changing a user's role assignments invalidates refresh tokens."""

    async def test_role_change_revokes_active_refresh_sessions(
        self, test_client, superadmin_token, seed_dev_user, seed_project,
    ):
        """Dev logs in, admin changes their role → old refresh token is rejected."""
        # 1. Dev logs in to obtain a refresh cookie
        login = await _login(test_client, "dev@wipro.com", DEV_PASSWORD)
        assert login.status_code == 200, f"Login failed: {login.text}"
        old_refresh = login.cookies.get("refresh_token")
        assert old_refresh, "Login should set a refresh_token cookie"

        # 2. Admin changes the dev's role (developer → tester)
        update = await test_client.put(
            f"/api/users/{seed_dev_user.id}",
            json={
                "role_assignments": [
                    {
                        "role_name": "tester",
                        "scope_type": "project",
                        "scope_id": seed_project.id,
                    },
                ],
            },
            headers=auth_header(superadmin_token),
        )
        assert update.status_code == 200, f"Role update failed: {update.text}"

        # 3. Old refresh token must be rejected (sessions revoked)
        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh.status_code == 401, (
            f"Expected refresh to be revoked after role change, got {refresh.status_code}"
        )

    async def test_role_change_then_relogin_yields_new_capabilities(
        self, test_client, superadmin_token, seed_dev_user, seed_project,
    ):
        """After role change, re-login yields a JWT with the new role/capabilities."""
        # 1. Dev logs in with old role (developer)
        first_login = await _login(test_client, "dev@wipro.com", DEV_PASSWORD)
        assert first_login.status_code == 200
        first_roles = first_login.json()["user"]["roles"]
        assert "developer" in first_roles

        # 2. Admin changes dev → tester
        update = await test_client.put(
            f"/api/users/{seed_dev_user.id}",
            json={
                "role_assignments": [
                    {
                        "role_name": "tester",
                        "scope_type": "project",
                        "scope_id": seed_project.id,
                    },
                ],
            },
            headers=auth_header(superadmin_token),
        )
        assert update.status_code == 200

        # 3. Re-login → new JWT carries the tester role
        relogin = await _login(test_client, "dev@wipro.com", DEV_PASSWORD)
        assert relogin.status_code == 200
        new_roles = relogin.json()["user"]["roles"]
        assert "tester" in new_roles
        assert "developer" not in new_roles

    async def test_noop_role_update_does_not_revoke_sessions(
        self, test_client, superadmin_token, seed_dev_user,
    ):
        """Updating a user with the same role assignments must NOT revoke sessions."""
        # 1. Dev logs in
        login = await _login(test_client, "dev@wipro.com", DEV_PASSWORD)
        assert login.status_code == 200
        refresh_cookie = login.cookies.get("refresh_token")
        assert refresh_cookie

        # Determine the dev's existing project-scoped developer assignment so
        # we can re-submit the *same* assignment as a no-op update.
        existing = await test_client.get(
            f"/api/users/{seed_dev_user.id}",
            headers=auth_header(superadmin_token),
        )
        assert existing.status_code == 200
        existing_roles = existing.json()["roles"]
        # The dev_user fixture seeds exactly one developer/project assignment
        same_role = next(r for r in existing_roles if r["roleName"] == "developer")

        # 2. Admin "updates" but with identical assignments
        update = await test_client.put(
            f"/api/users/{seed_dev_user.id}",
            json={
                "role_assignments": [
                    {
                        "role_name": same_role["roleName"],
                        "scope_type": same_role["scopeType"],
                        "scope_id": same_role["scopeId"],
                    },
                ],
            },
            headers=auth_header(superadmin_token),
        )
        assert update.status_code == 200

        # 3. Old refresh must STILL work — no-op did not revoke
        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh.status_code == 200, (
            f"No-op update should not revoke refresh sessions, got {refresh.status_code}"
        )

    async def test_display_name_only_update_does_not_revoke_sessions(
        self, test_client, superadmin_token, seed_dev_user,
    ):
        """Updating only display_name (no role_assignments) must NOT revoke sessions."""
        login = await _login(test_client, "dev@wipro.com", DEV_PASSWORD)
        assert login.status_code == 200
        refresh_cookie = login.cookies.get("refresh_token")
        assert refresh_cookie

        update = await test_client.put(
            f"/api/users/{seed_dev_user.id}",
            json={"display_name": "Renamed Dev"},
            headers=auth_header(superadmin_token),
        )
        assert update.status_code == 200

        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh.status_code == 200


# ---------------------------------------------------------------------------
# WEGA-1921 — Deactivation revokes, refresh validates status,
#             reactivation forces password reset
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDeactivationRevokesSessions:
    """WEGA-1921: deactivating a user revokes their refresh sessions."""

    async def test_deactivation_revokes_active_sessions(
        self, test_client, superadmin_token, seed_pm,
    ):
        """PM logs in, admin deactivates them → refresh fails 401."""
        login = await _login(test_client, "pm@wipro.com", PM_PASSWORD)
        assert login.status_code == 200
        refresh_cookie = login.cookies.get("refresh_token")
        assert refresh_cookie

        # SuperAdmin deactivates the PM
        delete_resp = await test_client.delete(
            f"/api/users/{seed_pm.id}",
            headers=auth_header(superadmin_token),
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deactivated"

        # Refresh with the now-deactivated user's old token → 401
        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh.status_code == 401


@pytest.mark.integration
class TestRefreshValidatesUserStatus:
    """WEGA-1921: /auth/refresh rejects tokens for non-ACTIVE users."""

    async def test_refresh_fails_when_user_deactivated(
        self, test_client, superadmin_token, seed_pm, async_session,
    ):
        """Even if a refresh token row survived, status check rejects it."""
        from app.models.user import UserStatus

        login = await _login(test_client, "pm@wipro.com", PM_PASSWORD)
        assert login.status_code == 200
        refresh_cookie = login.cookies.get("refresh_token")
        assert refresh_cookie

        # Force user → DEACTIVATED status directly without going through the
        # delete endpoint (which also revokes sessions).  This isolates the
        # /auth/refresh status check itself.
        seed_pm.status = UserStatus.DEACTIVATED
        await async_session.commit()

        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh.status_code == 401


@pytest.mark.integration
class TestReactivationForcesPasswordReset:
    """WEGA-1921: reactivation flips must_change_password on the auth method."""

    async def test_reactivation_sets_must_change_password(
        self, test_client, superadmin_token, seed_pm, async_session,
    ):
        """Admin deactivates then reactivates a user → next login forces reset."""
        from sqlalchemy import select

        from app.models.auth_method import AuthMethod, AuthMethodType

        # 1. Deactivate the PM
        delete_resp = await test_client.delete(
            f"/api/users/{seed_pm.id}",
            headers=auth_header(superadmin_token),
        )
        assert delete_resp.status_code == 200

        # 2. Reactivate via PUT status=active
        reactivate = await test_client.put(
            f"/api/users/{seed_pm.id}",
            json={"status": "active"},
            headers=auth_header(superadmin_token),
        )
        assert reactivate.status_code == 200

        # 3. The active password auth method must now require a change
        result = await async_session.execute(
            select(AuthMethod).where(
                AuthMethod.user_id == seed_pm.id,
                AuthMethod.method_type == AuthMethodType.PASSWORD,
                AuthMethod.disabled_at.is_(None),
            )
        )
        auth_method = result.scalar_one_or_none()
        assert auth_method is not None
        assert auth_method.must_change_password is True

        # 4. Login response must reflect must_change_password = True
        login = await _login(test_client, "pm@wipro.com", PM_PASSWORD)
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is True

    async def test_status_change_without_deactivation_no_password_reset(
        self, test_client, superadmin_token, seed_pm, async_session,
    ):
        """Updating an already-active user (no deactivation in between)
        must NOT flip must_change_password."""
        from sqlalchemy import select

        from app.models.auth_method import AuthMethod, AuthMethodType

        # PM is already ACTIVE — re-asserting active status is a no-op
        resp = await test_client.put(
            f"/api/users/{seed_pm.id}",
            json={"status": "active"},
            headers=auth_header(superadmin_token),
        )
        assert resp.status_code == 200

        result = await async_session.execute(
            select(AuthMethod).where(
                AuthMethod.user_id == seed_pm.id,
                AuthMethod.method_type == AuthMethodType.PASSWORD,
                AuthMethod.disabled_at.is_(None),
            )
        )
        auth_method = result.scalar_one_or_none()
        assert auth_method is not None
        assert auth_method.must_change_password is False
