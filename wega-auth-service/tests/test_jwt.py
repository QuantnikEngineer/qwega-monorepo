"""JWT creation and validation test stubs."""

import pytest


@pytest.mark.unit
class TestJWTCreation:
    async def test_access_token_claims(self, jwt_manager):
        token = jwt_manager.create_access_token(
            sub="user-123",
            email="test.user@wipro.com",
            display_name="Test User",
            roles=["developer"],
            capabilities=["stories.read"],
            org_id="org-123",
        )
        decoded = jwt_manager.decode_access_token(token)

        assert decoded["sub"] == "user-123"
        assert decoded["email"] == "test.user@wipro.com"
        assert decoded["roles"] == ["developer"]
        assert decoded["capabilities"] == ["stories.read"]
        assert decoded["org_id"] == "org-123"
        assert decoded["iss"] == "wega-auth"
        assert decoded["aud"] == "wega-api"

    async def test_access_token_is_rs256(self, jwt_manager):
        jwt = pytest.importorskip("jwt")
        token = jwt_manager.create_access_token(
            sub="user-123",
            email="test.user@wipro.com",
            display_name="Test User",
            roles=[],
            capabilities=[],
            org_id="org-123",
        )
        header = jwt.get_unverified_header(token)

        assert header["alg"] == "RS256"
        assert "kid" in header

    async def test_expired_token_rejected(self, jwt_manager):
        """Verify that an expired access token is rejected on decode."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "iss": "wega-auth",
            "aud": "wega-api",
            "sub": "user-expired",
            "email": "expired@wipro.com",
            "name": "Expired User",
            "roles": [],
            "capabilities": [],
            "org_id": "org-123",
            "allowed_agents": [],
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),  # already expired
            "jti": "test-jti",
        }
        expired_token = pyjwt.encode(
            payload, jwt_manager.private_key, algorithm="RS256",
            headers={"kid": jwt_manager.kid},
        )

        with pytest.raises(pyjwt.ExpiredSignatureError):
            jwt_manager.decode_access_token(expired_token)
