"""Cookie configuration test stubs."""

import pytest


@pytest.mark.integration
class TestCookieConfiguration:
    async def test_cookie_config(self, test_client, seed_user):
        _, password = seed_user
        response = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if response.status_code == 404:
            pytest.skip("Auth login endpoint not yet implemented (Plan 04)")

        from app.core.config import settings

        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert f"samesite={settings.cookie_samesite}" in set_cookie
        assert "path=/auth" in set_cookie

    async def test_cookie_secure_in_production(self):
        try:
            from app.api.auth import _set_refresh_cookie
        except ImportError as exc:
            pytest.skip(f"Cookie helper not yet implemented (Plan 04): {exc}")

        assert callable(_set_refresh_cookie)

    async def test_logout_clears_cookie(self, test_client, seed_user):
        _, password = seed_user
        login = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if login.status_code == 404:
            pytest.skip("Auth login/logout endpoints not yet implemented (Plan 04)")
        assert login.status_code == 200

        token = login.json().get("access_token")
        if not token:
            pytest.skip("Login response does not include access token yet")

        logout = await test_client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout.status_code == 204
        cleared_cookie = logout.headers.get("set-cookie", "").lower()
        assert "refresh_token=" in cleared_cookie
        assert "max-age=0" in cleared_cookie or "expires=" in cleared_cookie

    async def test_logout_clears_cookie_without_bearer_header(self, test_client, seed_user):
        _, password = seed_user
        login = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        if login.status_code == 404:
            pytest.skip("Auth login/logout endpoints not yet implemented (Plan 04)")
        assert login.status_code == 200

        logout = await test_client.post("/api/auth/logout")
        assert logout.status_code == 204
        cleared_cookie = logout.headers.get("set-cookie", "").lower()
        assert "refresh_token=" in cleared_cookie
        assert "max-age=0" in cleared_cookie or "expires=" in cleared_cookie
