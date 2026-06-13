"""CORS behavior regression tests for auth failures."""

from app.utils.error_codes import MISSING_TOKEN


def test_401_responses_include_cors_headers(gateway_client) -> None:
    """Auth failures include CORS headers because CORS middleware wraps auth middleware."""
    response = gateway_client.get(
        "/protected",
        headers={"Origin": "http://frontend.example"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == MISSING_TOKEN
    assert response.headers.get("access-control-allow-origin") == "http://frontend.example"
    assert response.headers.get("access-control-allow-credentials") == "true"
