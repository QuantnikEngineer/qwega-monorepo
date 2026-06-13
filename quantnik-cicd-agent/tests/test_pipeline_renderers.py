import asyncio

import httpx
import pytest

from app.core.config import settings
from app.models.requests import create_sample_request
from app.services.pipeline_renderers import LlmPipelineRenderer, PipelineRenderError


class StubPromptLibrary:
    def render(self, request, context):
        return 'Return a CI pipeline only.'


def test_llm_renderer_uses_system_ssl_http_clients(monkeypatch):
    from google import genai

    captured: dict = {}

    class DummyClient:
        pass

    def fake_client(**kwargs):
        captured.update(kwargs)
        return DummyClient()

    monkeypatch.setattr(genai, 'Client', fake_client)
    monkeypatch.setattr(settings, 'google_cloud_project', 'digital-rig-poc')
    monkeypatch.setattr(settings, 'google_cloud_location', 'global')
    monkeypatch.setattr(settings, 'google_api_key', None)

    renderer = LlmPipelineRenderer(prompt_library=StubPromptLibrary())
    renderer._get_client()

    http_options = captured['http_options']
    assert isinstance(http_options.httpx_client, httpx.Client)
    assert type(http_options.httpx_client._transport._pool._ssl_context).__name__ == 'SSLContext'
    assert http_options.httpx_client.timeout.connect == settings.llm_timeout_seconds

    http_options.httpx_client.close()
    asyncio.run(http_options.httpx_async_client.aclose())


def test_llm_renderer_wraps_sdk_errors_as_pipeline_render_errors():
    request = create_sample_request()

    class FailingModels:
        def generate_content(self, **kwargs):
            raise httpx.ConnectError('tls failed', request=httpx.Request('POST', 'https://example.com'))

    class FailingClient:
        models = FailingModels()

    renderer = LlmPipelineRenderer(client=FailingClient(), prompt_library=StubPromptLibrary())

    with pytest.raises(PipelineRenderError) as error:
        renderer.render(request, {})

    assert error.value.status_code == 502
    assert 'ConnectError' in error.value.detail[0]
    assert 'tls failed' in error.value.detail[0]
