import asyncio

import httpx

from app.tools.agent_client import AgentClient


def test_call_ci_agent_returns_guardrail_error_shape(monkeypatch):
    client = AgentClient()

    async def fake_post(url, json):
        request = httpx.Request("POST", url, json=json)
        return httpx.Response(400, request=request, json={"detail": ["Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'."]})

    monkeypatch.setattr(client._client, "post", fake_post)

    try:
        result = asyncio.run(client.call_ci_agent("Generate CI pipeline", {"ci_pipeline_request": {"pipelineName": "demo-ci"}}))
    finally:
        asyncio.run(client.close())

    assert result["status"] == "error"
    assert result["message"] == (
        "CI pipeline request failed guardrail validation: "
        "Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'."
    )
    assert result["data"]["error"]["type"] == "guardrail_validation"
    assert result["data"]["error"]["status_code"] == 400
    assert result["data"]["error"]["detail"] == [
        "Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'."
    ]


def test_call_ci_agent_returns_transport_error_shape(monkeypatch):
    client = AgentClient()

    async def fake_post(url, json):
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url, json=json))

    monkeypatch.setattr(client._client, "post", fake_post)

    try:
        result = asyncio.run(client.call_ci_agent("Generate CI pipeline", {"ci_pipeline_request": {"pipelineName": "demo-ci"}}))
    finally:
        asyncio.run(client.close())

    assert result["status"] == "error"
    assert result["message"] == "Unable to reach the CI agent."
    assert result["data"]["error"]["type"] == "transport_error"
    assert result["data"]["error"]["agent"] == "ci"
    assert result["data"]["error"]["detail"]


def test_build_default_ci_request_supports_render_mode_toggle():
    client = AgentClient()

    payload = client._build_default_ci_request("Generate CI pipeline", {"render_mode": "hybrid"})
    llm_payload = client._build_default_ci_request("Generate CI pipeline", {"use_llm_rendering": True})
    template_payload = client._build_default_ci_request("Generate CI pipeline", {"useLlmRendering": False})

    assert payload["renderMode"] == "hybrid"
    assert llm_payload["renderMode"] == "llm"
    assert template_payload["renderMode"] == "template"