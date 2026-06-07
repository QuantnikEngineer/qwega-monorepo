from __future__ import annotations

from dataclasses import dataclass
import re
import ssl
from typing import Any

import httpx
from jinja2 import Environment, TemplateNotFound

from app.core.config import settings
from app.models.requests import GeneratePipelineRequest
from app.services.prompt_library import PipelinePromptLibrary


class PipelineRenderError(RuntimeError):
    def __init__(self, detail: list[str], status_code: int = 503):
        self.detail = detail
        self.status_code = status_code
        super().__init__('; '.join(detail))


@dataclass
class RenderedPipeline:
    content: str
    render_mode_used: str
    fallback_reason: str | None = None


class TemplatePipelineRenderer:
    def __init__(self, environment: Environment) -> None:
        self._environment = environment

    def render(self, template_name: str, context: dict[str, Any]) -> RenderedPipeline:
        template = self._environment.get_template(template_name)
        return RenderedPipeline(
            content=template.render(**context),
            render_mode_used='template',
        )


class LlmPipelineRenderer:
    def __init__(self, client: Any | None = None, prompt_library: PipelinePromptLibrary | None = None) -> None:
        self._client = client
        self._client_type: str | None = None
        self._prompt_library = prompt_library or PipelinePromptLibrary()

    def render(self, request: GeneratePipelineRequest, context: dict[str, Any]) -> RenderedPipeline:
        client = self._get_client()
        prompt = self._build_prompt(request, context)
        try:
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=self._build_generation_config(),
            )
        except PipelineRenderError:
            raise
        except Exception as error:
            raise PipelineRenderError(
                [f"LLM renderer request failed: {type(error).__name__}: {error}"],
                status_code=502,
            ) from error
        self._ensure_complete_response(response)
        content = self._extract_content(response)
        content = self._strip_markdown_fences(content)
        if not content.strip():
            raise PipelineRenderError(['LLM renderer returned empty pipeline content.'], status_code=502)
        return RenderedPipeline(content=content, render_mode_used='llm')

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from google import genai
        except ImportError as error:
            raise PipelineRenderError(
                ['LLM render mode was requested, but the google-genai package is not installed in Wega CI Agent.'],
                status_code=503,
            ) from error

        if settings.google_cloud_project:
            self._client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
                http_options=self._build_http_options(),
            )
            self._client_type = 'vertexai'
            return self._client

        if settings.google_api_key:
            self._client = genai.Client(
                api_key=settings.google_api_key,
                http_options=self._build_http_options(),
            )
            self._client_type = 'google-api'
            return self._client

        raise PipelineRenderError(
            ['LLM render mode was requested, but neither GOOGLE_CLOUD_PROJECT nor GOOGLE_API_KEY is configured for Wega CI Agent.'],
            status_code=503,
        )

    def _build_generation_config(self):
        try:
            from google.genai import types
        except ImportError as error:
            raise PipelineRenderError(
                ['LLM render mode was requested, but Google GenAI configuration types are unavailable.'],
                status_code=503,
            ) from error

        return types.GenerateContentConfig(
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_tokens,
            response_mime_type='text/plain',
            thinking_config=types.ThinkingConfig(
                thinking_budget=settings.llm_thinking_budget,
            ),
        )

    def _build_http_options(self):
        try:
            from google.genai import types
        except ImportError as error:
            raise PipelineRenderError(
                ['LLM render mode was requested, but Google GenAI HTTP options are unavailable.'],
                status_code=503,
            ) from error

        verify = ssl.create_default_context()

        timeout = httpx.Timeout(settings.llm_timeout_seconds)

        return types.HttpOptions(
            httpx_client=httpx.Client(verify=verify, timeout=timeout),
            httpx_async_client=httpx.AsyncClient(verify=verify, timeout=timeout),
        )

    def _build_prompt(self, request: GeneratePipelineRequest, context: dict[str, Any]) -> str:
        try:
            return self._prompt_library.render(request, context)
        except TemplateNotFound as error:
            raise PipelineRenderError(
                [f"No LLM prompt template is configured for platform '{request.target.platform}'."],
                status_code=500,
            ) from error

    def _extract_content(self, response: Any) -> str:
        return str(getattr(response, 'text', '') or '')

    def _ensure_complete_response(self, response: Any) -> None:
        finish_reason = self._get_finish_reason(response)
        if finish_reason in {None, 'STOP', 'FINISH_REASON_UNSPECIFIED'}:
            return
        if finish_reason == 'MAX_TOKENS':
            raise PipelineRenderError(
                ['LLM renderer response was truncated before the YAML completed. Reduce prompt overhead or increase the effective output budget.'],
                status_code=502,
            )
        raise PipelineRenderError(
            [f"LLM renderer did not complete the YAML response (finish_reason={finish_reason})."],
            status_code=502,
        )

    def _get_finish_reason(self, response: Any) -> str | None:
        candidates = getattr(response, 'candidates', None) or []
        if not candidates:
            return None

        finish_reason = getattr(candidates[0], 'finish_reason', None)
        if finish_reason is None:
            return None

        normalized = getattr(finish_reason, 'name', None) or str(finish_reason)
        return normalized.rsplit('.', 1)[-1]

    def _strip_markdown_fences(self, content: str) -> str:
        fenced = re.match(r'^```[a-zA-Z0-9_-]*\s*(.*?)```\s*$', content.strip(), re.DOTALL)
        return fenced.group(1).strip() if fenced else content.strip()