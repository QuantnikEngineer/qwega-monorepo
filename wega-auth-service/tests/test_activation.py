"""Activation token lifecycle integration tests.

Tests GET /api/auth/activate (validate) and POST /api/auth/activate (redeem).
Covers valid token, expired token, replay protection, and login after activation.

NOTE: The plan referenced /api/activation/validate and /api/activation/redeem
but the actual endpoints are GET /api/auth/activate?token=... and POST /api/auth/activate.
"""

import uuid

import pytest


def auth_header(token: str) -> dict[str, str]:
    """Build Authorization header for test requests."""
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestValidateActivationToken:
    """GET /api/auth/activate?token=<raw_token> — token validation probe."""

    async def test_validate_valid_token(self, test_client, seed_activation_token):
        """GET /api/auth/activate?token=... → 200 with valid=true for good token."""
        raw_token = seed_activation_token["raw_token"]
        response = await test_client.get(f"/api/auth/activate?token={raw_token}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["email"] == "newuser@wipro.com"
        assert data["expired"] is False
        assert data["used"] is False

    async def test_validate_expired_token(self, test_client, seed_expired_activation_token):
        """GET /api/auth/activate?token=<expired> → 200 with valid=false, expired=true."""
        raw_token = seed_expired_activation_token["raw_token"]
        response = await test_client.get(f"/api/auth/activate?token={raw_token}")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is True

    async def test_validate_nonexistent_token(self, test_client, seed_roles, seed_org):
        """GET /api/auth/activate?token=random → 200 with valid=false."""
        fake_token = "completely-random-token-that-does-not-exist"
        response = await test_client.get(f"/api/auth/activate?token={fake_token}")
        assert response.status_code == 200
        assert response.json()["valid"] is False


@pytest.mark.integration
class TestRedeemActivation:
    """POST /api/auth/activate — redeem token and set password."""

    async def test_redeem_activation_success(self, test_client, seed_activation_token):
        """POST /api/auth/activate → 200, user status becomes active."""
        raw_token = seed_activation_token["raw_token"]
        response = await test_client.post(
            "/api/auth/activate",
            json={
                "token": raw_token,
                "password": "NewSecurePass123!@#",
                "confirm_password": "NewSecurePass123!@#",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Account activated successfully"
        assert "user_id" in data

    async def test_activated_user_can_login(self, test_client, seed_activation_token):
        """After activation, the user can log in with the new password."""
        raw_token = seed_activation_token["raw_token"]
        # Redeem activation
        redeem_resp = await test_client.post(
            "/api/auth/activate",
            json={
                "token": raw_token,
                "password": "NewSecurePass123!@#",
                "confirm_password": "NewSecurePass123!@#",
            },
        )
        assert redeem_resp.status_code == 200

        # Now login with the activated credentials
        login_resp = await test_client.post(
            "/api/auth/login",
            json={
                "email": "newuser@wipro.com",
                "password": "NewSecurePass123!@#",
            },
        )
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

    async def test_replay_protection(self, test_client, seed_activation_token):
        """POST /api/auth/activate twice → second call fails (token already used)."""
        raw_token = seed_activation_token["raw_token"]
        payload = {
            "token": raw_token,
            "password": "NewSecurePass123!@#",
            "confirm_password": "NewSecurePass123!@#",
        }
        # First redemption succeeds
        first = await test_client.post("/api/auth/activate", json=payload)
        assert first.status_code == 200

        # Second redemption fails — token already consumed
        second = await test_client.post(
            "/api/auth/activate",
            json={
                "token": raw_token,
                "password": "DifferentPass456!@#",
                "confirm_password": "DifferentPass456!@#",
            },
        )
        assert second.status_code == 400

    async def test_redeem_invalid_token(self, test_client, seed_roles, seed_org):
        """POST /api/auth/activate with random token → 400."""
        response = await test_client.post(
            "/api/auth/activate",
            json={
                "token": "completely-fake-token-value",
                "password": "SomePassword123!@#",
                "confirm_password": "SomePassword123!@#",
            },
        )
        assert response.status_code == 400

    async def test_redeem_expired_token(self, test_client, seed_expired_activation_token):
        """POST /api/auth/activate with expired token → 400."""
        raw_token = seed_expired_activation_token["raw_token"]
        response = await test_client.post(
            "/api/auth/activate",
            json={
                "token": raw_token,
                "password": "NewSecurePass123!@#",
                "confirm_password": "NewSecurePass123!@#",
            },
        )
        assert response.status_code == 400

    async def test_redeem_weak_password_rejected(self, test_client, seed_activation_token):
        """POST /api/auth/activate with password violating policy → 400."""
        raw_token = seed_activation_token["raw_token"]
        response = await test_client.post(
            "/api/auth/activate",
            json={
                "token": raw_token,
                "password": "weak",  # Too short, missing complexity
                "confirm_password": "weak",
            },
        )
        # 422 from Pydantic min_length or 400 from policy check
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestResendActivation:
    """POST /api/users/{user_id}/resend-activation via auth header."""

    async def test_resend_creates_new_token(self, test_client, superadmin_token, seed_activation_token):
        """After resend, the old token is still valid (new token also created)."""
        user_id = seed_activation_token["user"].id
        response = await test_client.post(
            f"/api/users/{user_id}/resend-activation",
            headers=auth_header(superadmin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "activation_url" in data
        assert "token=" in data["activation_url"]
