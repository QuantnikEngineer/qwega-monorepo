from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.config import settings
from app.core.logging import get_logger
from app.models.requests import GeneratePipelineRequest
from app.models.responses import (
    CatalogResponse,
    GeneratePipelineResponse,
    GeneratedArtifact,
)
from app.services.catalog_registry import build_catalog_response, get_platform_map
from app.services.pipeline_context import build_render_context
from app.services.pipeline_guardrails import PipelineValidationError, validate_generated_artifact, validate_request_guardrails
from app.services.pipeline_renderers import LlmPipelineRenderer, PipelineRenderError, RenderedPipeline, TemplatePipelineRenderer


logger = get_logger(__name__)


class CiPipelineService:
    def __init__(self, template_renderer: TemplatePipelineRenderer | None = None, llm_renderer: LlmPipelineRenderer | None = None) -> None:
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        self._environment = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        platform_map = get_platform_map()
        self.template_count = len(platform_map)
        self.supported_platforms = list(platform_map.keys())
        self._template_renderer = template_renderer or TemplatePipelineRenderer(self._environment)
        self._llm_renderer = llm_renderer or LlmPipelineRenderer()

    def get_catalog(self) -> CatalogResponse:
        return build_catalog_response()

    def generate(self, request: GeneratePipelineRequest) -> GeneratePipelineResponse:
        validate_request_guardrails(request)

        platform_config = get_platform_map()[request.target.platform]
        context = build_render_context(request)
        requested_render_mode = request.render_mode or settings.default_render_mode
        context['normalized_intent']['renderMode'] = requested_render_mode

        normalized_intent = context['normalized_intent']
        artifact_path = platform_config['artifactPath']
        rendered_pipeline = self._render_pipeline(
            request=request,
            template_name=platform_config['template'],
            artifact_path=artifact_path,
            context=context,
            requested_render_mode=requested_render_mode,
        )
        stage_context = context['stages']
        summary = (
            f"Generated {request.target.platform} CI pipeline with "
            f"{len(stage_context)} stages and {len(request.tools)} selected tools."
        )
        metadata = {
            "stage_count": len(stage_context),
            "tool_count": len(request.tools),
            "assistant_mode": request.assistant_mode,
            "mode": request.mode,
            "render_mode_requested": requested_render_mode,
            "render_mode_used": rendered_pipeline.render_mode_used,
        }
        content_type = 'text/x-groovy' if request.target.platform == 'jenkins' else 'text/yaml'
        if rendered_pipeline.fallback_reason:
            metadata['render_fallback_reason'] = rendered_pipeline.fallback_reason

        return GeneratePipelineResponse(
            status="success",
            summary=summary,
            message=summary,
            pipelineName=request.pipeline_name,
            platform=request.target.platform,
            artifact=GeneratedArtifact(path=artifact_path, contentType=content_type, content=rendered_pipeline.content),
            normalizedIntent=normalized_intent,
            metadata=metadata,
        )

    def _render_pipeline(
        self,
        request: GeneratePipelineRequest,
        template_name: str,
        artifact_path: str,
        context: dict,
        requested_render_mode: str,
    ) -> RenderedPipeline:
        if requested_render_mode == 'template':
            return self._render_template(request, template_name, artifact_path, context)

        if requested_render_mode == 'llm':
            return self._render_llm(request, artifact_path, context)

        if requested_render_mode == 'hybrid':
            try:
                return self._render_llm(request, artifact_path, context)
            except (PipelineRenderError, PipelineValidationError) as error:
                logger.warning(
                    'LLM pipeline rendering failed, falling back to template rendering',
                    extra={
                        'pipeline_name': request.pipeline_name,
                        'platform': request.target.platform,
                        'error': str(error),
                    },
                )
                rendered = self._render_template(request, template_name, artifact_path, context)
                rendered.fallback_reason = str(error)
                return rendered

        raise PipelineRenderError(
            [f"Unsupported render mode '{requested_render_mode}'. Supported modes: template, llm, hybrid."],
            status_code=400,
        )

    def _render_template(
        self,
        request: GeneratePipelineRequest,
        template_name: str,
        artifact_path: str,
        context: dict,
    ) -> RenderedPipeline:
        rendered = self._template_renderer.render(template_name, context)
        rendered.content = validate_generated_artifact(request, artifact_path, rendered.content)
        return rendered

    def _render_llm(
        self,
        request: GeneratePipelineRequest,
        artifact_path: str,
        context: dict,
    ) -> RenderedPipeline:
        rendered = self._llm_renderer.render(request, context)
        rendered.content = validate_generated_artifact(request, artifact_path, rendered.content)
        return rendered
