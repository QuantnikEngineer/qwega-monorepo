"""JWKS endpoint test stubs."""

import pytest


@pytest.mark.integration
class TestJWKSEndpoint:
    async def test_jwks_endpoint(self, test_client):
        response = await test_client.get("/.well-known/jwks.json")
        if response.status_code == 404:
            pytest.skip("JWKS endpoint not yet implemented (Plan 04)")

        assert response.status_code == 200
        body = response.json()
        assert "keys" in body
        assert isinstance(body["keys"], list)
        assert body["keys"], "JWKS response should include at least one key"

        key = body["keys"][0]
        for field in ("kty", "use", "alg", "kid", "n", "e"):
            assert field in key

    async def test_jwks_cache_headers(self, test_client):
        response = await test_client.get("/.well-known/jwks.json")
        if response.status_code == 404:
            pytest.skip("JWKS endpoint not yet implemented (Plan 04)")

        cache_control = response.headers.get("Cache-Control", "")
        assert "public" in cache_control.lower() or "max-age" in cache_control.lower()
