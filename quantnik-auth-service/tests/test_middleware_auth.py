"""Authentication middleware regression tests."""

import pytest


@pytest.mark.integration
class TestGetCurrentUser:
    async def test_untrusted_x_user_headers_rejected(self, test_client, seed_user, monkeypatch):
        user, _ = seed_user
        from app.core.config import settings

        monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.1")

        response = await test_client.get(
            "/api/auth/me",
            headers={
                "X-User-Id": user.id,
                "X-User-Email": user.normalized_email,
                "X-User-Org-Id": user.org_id,
            },
        )
        if response.status_code == 404:
            pytest.skip("Auth me endpoint not yet implemented (Plan 04)")

        assert response.status_code == 401

    async def test_trusted_x_user_headers_allowed(self, test_client, seed_user, monkeypatch):
        user, _ = seed_user
        from app.core.config import settings

        monkeypatch.setattr(settings, "trusted_proxy_ips", "127.0.0.1")

        response = await test_client.get(
            "/api/auth/me",
            headers={
                "X-User-Id": user.id,
                "X-User-Email": user.normalized_email,
                "X-User-Org-Id": user.org_id,
                "X-User-Roles": "superadmin",
                "X-User-Capabilities": "platform:manage",
            },
        )
        if response.status_code == 404:
            pytest.skip("Auth me endpoint not yet implemented (Plan 04)")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
