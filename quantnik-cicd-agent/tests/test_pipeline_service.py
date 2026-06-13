import pytest

from app.core.config import settings
from app.models.requests import create_sample_request
from app.services.pipeline_guardrails import PipelineValidationError
from app.services.pipeline_renderers import PipelineRenderError, RenderedPipeline
from app.services.pipeline_service import CiPipelineService


class StubLlmRenderer:
    def __init__(self, content: str) -> None:
        self._content = content

    def render(self, request, context) -> RenderedPipeline:
        return RenderedPipeline(content=self._content, render_mode_used='llm')


class FailingLlmRenderer:
    def render(self, request, context) -> RenderedPipeline:
        raise PipelineRenderError(['Simulated LLM failure.'], status_code=503)


def test_generate_sample_request_returns_expected_artifact_path():
    service = CiPipelineService()
    request = create_sample_request()

    response = service.generate(request)

    assert response.status == 'success'
    assert response.platform == 'github-actions'
    assert response.artifact.path == '.github/workflows/ci.yml'
    assert 'npm ci' in response.artifact.content
    assert 'snyk test --severity-threshold=high' in response.artifact.content


@pytest.mark.parametrize(
    ("platform", "required_snippets"),
    [
        (
            "github-actions",
            [
                'docker build -t registry.example.com/quantnik-frontend:qa -t registry.example.com/quantnik-frontend:release-candidate .',
                'approval_gate:',
                'rollout_eastus:',
                'rollout_westeurope:',
            ],
        ),
        (
            "azure-devops",
            [
                'ManualValidation@0',
                'stage: rollout_eastus',
                'stage: rollout_westeurope',
                'docker push registry.example.com/quantnik-frontend:release-candidate',
            ],
        ),
        (
            "gitlab-ci",
            [
                'when: manual',
                'rollout_eastus:',
                'rollout_westeurope:',
                'docker push registry.example.com/quantnik-frontend:release-candidate',
            ],
        ),
        (
            "harness",
            [
                'type: Approval',
                'identifier: rollout_eastus',
                'identifier: rollout_westeurope',
                'docker push registry.example.com/quantnik-frontend:release-candidate',
            ],
        ),
    ],
)
def test_generate_renders_enterprise_controls_for_all_platforms(platform: str, required_snippets: list[str]):
    service = CiPipelineService()
    request = create_sample_request()
    request.target.platform = platform

    response = service.generate(request)

    assert response.status == 'success'
    assert response.metadata['render_mode_used'] == 'template'
    for snippet in required_snippets:
        assert snippet in response.artifact.content


def test_generate_rejects_publish_without_artifact():
    service = CiPipelineService()
    request = create_sample_request()
    request.build.artifact_type = 'none'

    with pytest.raises(PipelineValidationError) as error:
        service.generate(request)

    assert "Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'." in error.value.violations


def test_generate_with_llm_render_mode_uses_llm_renderer():
    request = create_sample_request()
    request.render_mode = 'llm'
    service = CiPipelineService(llm_renderer=StubLlmRenderer('name: llm-rendered\njobs: {}\n'))

    response = service.generate(request)

    assert response.status == 'success'
    assert response.artifact.content == 'name: llm-rendered\njobs: {}\n'
    assert response.metadata['render_mode_requested'] == 'llm'
    assert response.metadata['render_mode_used'] == 'llm'


def test_generate_with_hybrid_render_mode_falls_back_to_template():
    request = create_sample_request()
    request.render_mode = 'hybrid'
    service = CiPipelineService(llm_renderer=FailingLlmRenderer())

    response = service.generate(request)

    assert response.status == 'success'
    assert response.metadata['render_mode_requested'] == 'hybrid'
    assert response.metadata['render_mode_used'] == 'template'
    assert 'Simulated LLM failure.' in response.metadata['render_fallback_reason']
    assert 'npm ci' in response.artifact.content


def test_generate_preserves_selected_tool_order_within_shared_stage():
    service = CiPipelineService()
    request = type(create_sample_request()).model_validate(
        {
            **create_sample_request().model_dump(by_alias=True),
            'tools': [
                {'id': 'semgrep', 'name': 'Semgrep', 'category': 'Quality and Security'},
                {'id': 'sonarqube', 'name': 'SonarQube', 'category': 'Quality and Security'},
                {'id': 'docker-build', 'name': 'Docker Build', 'category': 'Packaging and Delivery'},
                {'id': 'artifact-publish', 'name': 'Artifact Publish', 'category': 'Packaging and Delivery'},
            ],
            'stages': [
                {'order': 1, 'stageId': 'checkout', 'name': 'Checkout', 'tools': []},
                {'order': 2, 'stageId': 'restore', 'name': 'Restore Dependencies', 'tools': ['npm']},
                {'order': 3, 'stageId': 'build', 'name': 'Build', 'tools': ['npm']},
                {'order': 4, 'stageId': 'static-analysis', 'name': 'Static Analysis', 'tools': ['Semgrep', 'SonarQube']},
                {'order': 5, 'stageId': 'docker-build', 'name': 'Docker Build', 'tools': ['Docker Build']},
                {'order': 6, 'stageId': 'publish-artifacts', 'name': 'Publish Artifacts', 'tools': ['Artifact Publish']},
            ],
        }
    )

    response = service.generate(request)

    assert response.status == 'success'
    assert response.artifact.content.index('semgrep ci') < response.artifact.content.index('sonar-scanner')


def test_generate_with_llm_render_mode_requires_google_configuration(monkeypatch):
    request = create_sample_request()
    request.render_mode = 'llm'
    monkeypatch.setattr(settings, 'google_cloud_project', None)
    monkeypatch.setattr(settings, 'google_api_key', None)

    with pytest.raises(PipelineRenderError) as error:
        CiPipelineService().generate(request)

    assert 'GOOGLE_CLOUD_PROJECT' in error.value.detail[0]