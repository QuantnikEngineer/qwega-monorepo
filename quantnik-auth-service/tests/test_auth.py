"""Authentication endpoint test stubs."""

import pytest


@pytest.mark.integration
class TestLogin:
    async def test_login_success(self, test_client, seed_user):
        _, password = seed_user
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if response.status_code == 404:
            pytest.skip("Auth login endpoint not yet implemented (Plan 04)")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert "refresh_token" in response.cookies

    async def test_login_domain_rejected(self, test_client):
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "user@gmail.com", "password": "AnyP@ssw0rd1"},
        )
        if response.status_code == 404:
            pytest.skip("Auth login endpoint not yet implemented (Plan 04)")
        assert response.status_code == 422

    async def test_login_wrong_password(self, test_client, seed_user):
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": "WrongP@ssw0rd123"},
        )
        if response.status_code == 404:
            pytest.skip("Auth login endpoint not yet implemented (Plan 04)")
        assert response.status_code == 401


@pytest.mark.integration
class TestRefreshToken:
    async def test_refresh_rotation(self, test_client, seed_user):
        _, password = seed_user
        login = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if login.status_code == 404:
            pytest.skip("Auth login/refresh endpoints not yet implemented (Plan 04)")
        assert login.status_code == 200

        refresh_cookie = login.cookies.get("refresh_token")
        assert refresh_cookie, "Login should set refresh_token cookie"
        refresh = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh.status_code == 200
        data = refresh.json()
        assert "access_token" in data

    async def test_refresh_reuse_detection(self, test_client, seed_user):
        """Verify that reusing an old (rotated) refresh token returns 401."""
        _, password = seed_user
        login = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if login.status_code == 404:
            pytest.skip("Auth login/refresh endpoints not yet implemented")
        assert login.status_code == 200

        old_refresh = login.cookies.get("refresh_token")
        assert old_refresh, "Login should set refresh_token cookie"

        # First refresh — rotates the token (old one is now "rotated")
        refresh1 = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh1.status_code == 200

        # Second refresh with the OLD token — should be detected as reuse
        reuse = await test_client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert reuse.status_code == 401, (
            f"Expected 401 for refresh token reuse, got {reuse.status_code}"
        )


@pytest.mark.integration
class TestFirstLogin:
    async def test_first_login_must_change(self, test_client, seed_first_login_user):
        _, password = seed_first_login_user
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "new.user@wipro.com", "password": password},
        )
        if response.status_code == 404:
            pytest.skip("Auth login endpoint not yet implemented (Plan 04)")

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["must_change_password"] is True
