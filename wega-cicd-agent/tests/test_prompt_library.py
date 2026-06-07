from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.requests import create_sample_request
from app.services.pipeline_context import build_render_context
from app.services.pipeline_renderers import LlmPipelineRenderer, PipelineRenderError
from app.services.prompt_library import PipelinePromptLibrary


@pytest.mark.parametrize(
    ("platform", "expected_snippet"),
    [
        ("azure-devops", "AZURE DEVOPS YAML RULES"),
        ("github-actions", "GITHUB ACTIONS YAML RULES"),
        ("gitlab-ci", "GITLAB CI YAML RULES"),
        ("harness", "HARNESS YAML RULES"),
    ],
)
def test_prompt_library_uses_platform_specific_prompt(platform: str, expected_snippet: str):
    request = create_sample_request()
    request.target.platform = platform
    context = build_render_context(request)

    prompt = PipelinePromptLibrary().render(request, context)

    assert expected_snippet in prompt
    assert context["platform"]["artifactPath"] in prompt
    assert request.pipeline_name in prompt
    assert "Image repository:" in prompt
    assert "Approvals enabled:" in prompt
    assert "RESOLVED ENTERPRISE CONTROL PLAN" in prompt
    assert "ENTERPRISE CONTROLS JSON" in prompt
    assert "Resolved rollout regions: eastus, westeurope" in prompt


def test_render_context_includes_enterprise_controls():
    request = create_sample_request()

    context = build_render_context(request)

    assert context["image"]["repository"] == "registry.example.com/wega-frontend"
    assert context["image"]["tags"] == ["qa", "release-candidate"]
    assert context["rollout"]["enabled"] is True
    assert [region["name"] for region in context["rollout"]["regions"]] == ["eastus", "westeurope"]
    assert context["approvals"]["enabled"] is True
    assert context["approvals"]["approvers"] == ["release-managers@example.com", "platform-owners@example.com"]


def test_prompt_library_uses_resolved_rollout_regions_when_approvals_require_primary_rollout():
    request = create_sample_request()
    request.target.platform = "github-actions"
    request.target.regions = []

    context = build_render_context(request)
    prompt = PipelinePromptLibrary().render(request, context)

    assert context["rollout"]["enabled"] is True
    assert [region["name"] for region in context["rollout"]["regions"]] == ["primary"]
    assert "Requested regions: none" in prompt
    assert "Resolved rollout regions: primary" in prompt


class RecordingPromptLibrary:
    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        self.calls = []

    def render(self, request, context) -> str:
        self.calls.append((request, context))
        return self.prompt


class RecordingClient:
    def __init__(self, response_text: str, finish_reason: str | None = None) -> None:
        self.models = self
        self.response_text = response_text
        self.finish_reason = finish_reason
        self.last_contents = None
        self.last_config = None

    def generate_content(self, model, contents, config):
        self.last_contents = contents
        self.last_config = config
        candidates = None
        if self.finish_reason is not None:
            candidates = [SimpleNamespace(finish_reason=SimpleNamespace(name=self.finish_reason))]
        return SimpleNamespace(text=self.response_text, candidates=candidates)


def test_llm_renderer_builds_prompt_from_prompt_library():
    request = create_sample_request()
    context = build_render_context(request)
    prompt_library = RecordingPromptLibrary("platform-specific prompt")
    client = RecordingClient("name: llm-rendered\njobs: {}\n")

    rendered = LlmPipelineRenderer(client=client, prompt_library=prompt_library).render(request, context)

    assert prompt_library.calls == [(request, context)]
    assert client.last_contents == "platform-specific prompt"
    assert rendered.content == "name: llm-rendered\njobs: {}"
    assert rendered.render_mode_used == "llm"


def test_llm_renderer_disables_thinking_budget_by_default():
    request = create_sample_request()
    context = build_render_context(request)
    client = RecordingClient("name: llm-rendered\njobs: {}\n")

    LlmPipelineRenderer(client=client, prompt_library=RecordingPromptLibrary("platform-specific prompt")).render(request, context)

    assert client.last_config.thinking_config is not None
    assert client.last_config.thinking_config.thinking_budget == settings.llm_thinking_budget
    assert client.last_config.thinking_config.thinking_budget == 0


def test_llm_renderer_rejects_truncated_response():
    request = create_sample_request()
    context = build_render_context(request)
    client = RecordingClient("name: truncated\njobs:\n  build:\n    needs:\n", finish_reason="MAX_TOKENS")

    with pytest.raises(PipelineRenderError) as error:
        LlmPipelineRenderer(client=client, prompt_library=RecordingPromptLibrary("platform-specific prompt")).render(request, context)

    assert 'truncated before the YAML completed' in error.value.detail[0]