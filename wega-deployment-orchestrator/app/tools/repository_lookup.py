from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.secret_manager import SecretManagerError, resolve_optional_secret

logger = get_logger(__name__)


class RepositoryLookupError(ValueError):
    def __init__(self, user_message: str, *, log_message: str | None = None, status_code: int = 400) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.log_message = log_message
        self.status_code = status_code


@dataclass(frozen=True)
class RepositoryOption:
    id: str
    label: str
    url: str


@dataclass(frozen=True)
class RepositoryWriteResult:
    status: str
    repository_url: str
    branch: str
    file_path: str
    commit_message: str
    commit_sha: str | None


@dataclass(frozen=True)
class HarnessPipelinePublishResult:
    status: str
    pipeline_identifier: str
    pipeline_name: str
    account_identifier: str
    org_identifier: str
    project_identifier: str


@dataclass(frozen=True)
class HarnessProjectContext:
    api_base_url: str
    account_identifier: str
    org_identifier: str
    project_identifier: str
    api_key: str


@dataclass(frozen=True)
class AzureDevOpsPipelinePublishResult:
    status: str
    pipeline_id: int | None
    pipeline_name: str
    repository_id: str
    repository_name: str
    branch: str
    file_path: str
    commit_sha: str | None
    pipeline_url: str | None


@dataclass(frozen=True)
class AzureDevOpsContext:
    organization_url: str  # https://dev.azure.com/{org}
    project: str
    repository_id: str
    repository_name: str
    default_branch: str
    pat_token: str


def _trim_git_suffix(value: str) -> str:
    return value.removesuffix('.git') if value.endswith('.git') else value


def _sort_branch_names(branches: list[str]) -> list[str]:
    priority = ['main', 'master', 'develop', 'development', 'release']

    def sort_key(branch: str) -> tuple[int, int, str]:
        for index, prefix in enumerate(priority):
            if branch == prefix or branch.startswith(f'{prefix}/'):
                return (0, index, branch)
        return (1, len(priority), branch)

    return sorted({branch for branch in branches if branch}, key=sort_key)


def _sort_repository_options(repositories: list[RepositoryOption]) -> list[RepositoryOption]:
    return sorted((repository for repository in repositories if repository.url), key=lambda repository: repository.label.lower())


def _build_url_origin(parsed_url: httpx.URL) -> str:
    port = f':{parsed_url.port}' if parsed_url.port is not None else ''
    return f'{parsed_url.scheme}://{parsed_url.host}{port}'


def _build_query_string(params: dict[str, str | int]) -> str:
    return '&'.join(f'{key}={quote(str(value), safe="")}' for key, value in params.items())


def _host_matches_pattern(host: str, pattern: str) -> bool:
    return host == pattern or (pattern.startswith('*.') and host.endswith(pattern[1:]))


_HARNESS_BACKED_PLATFORMS = {'github-actions', 'gitlab-ci', 'azure-devops', 'harness', 'jenkins'}


def _configured_repository_url_for_platform(platform: str) -> str:
    if platform == 'github-actions':
        return settings.github_repository_url.strip()
    if platform == 'gitlab-ci':
        return settings.gitlab_repository_url.strip()
    if platform == 'azure-devops':
        return settings.azure_devops_repository_url.strip()
    if platform in {'harness', 'jenkins'}:
        return settings.harness_repository_url.strip()
    return ''


def resolve_repository_context_url(platform: str) -> str:
    normalized_platform = platform.strip().lower()
    configured_url = _configured_repository_url_for_platform(normalized_platform)
    if configured_url:
        return configured_url

    if normalized_platform in _HARNESS_BACKED_PLATFORMS:
        return settings.harness_repository_url.strip()

    raise RepositoryLookupError(f'Unsupported platform {platform!r} for repository context lookup.')


class RepositoryLookupClient:
    def __init__(self) -> None:
        timeout = httpx.Timeout(settings.repository_lookup_timeout_seconds, connect=min(settings.repository_lookup_timeout_seconds, 10.0))
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def list_repositories(self, platform: str, repository_url: str | None = None) -> list[RepositoryOption]:
        effective_platform = self._resolve_repository_provider(platform, repository_url)

        if effective_platform == 'github-actions':
            return await self._list_github_repositories(repository_url)
        if effective_platform == 'gitlab-ci':
            return await self._list_gitlab_repositories(repository_url)
        if effective_platform == 'azure-devops':
            return await self._list_azure_devops_repositories(repository_url)
        if effective_platform == 'harness':
            return await self._list_harness_repositories(repository_url)
        raise RepositoryLookupError(f'Unsupported platform {platform!r} for repository lookup.')

    async def list_branches(self, platform: str, repository_url: str) -> list[str]:
        effective_platform = self._resolve_repository_provider(platform, repository_url)

        if effective_platform == 'github-actions':
            return await self._list_github_branches(repository_url)
        if effective_platform == 'gitlab-ci':
            return await self._list_gitlab_branches(repository_url)
        if effective_platform == 'azure-devops':
            return await self._list_azure_devops_branches(repository_url)
        if effective_platform == 'harness':
            return await self._list_harness_branches(repository_url)
        raise RepositoryLookupError(f'Unsupported platform {platform!r} for branch lookup.')

    async def write_file(
        self,
        platform: str,
        repository_url: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> RepositoryWriteResult:
        effective_platform = self._resolve_repository_provider(platform, repository_url)
        if effective_platform not in {'harness', 'azure-devops'}:
            raise RepositoryLookupError('Repository push is currently supported only for Harness and Azure DevOps repositories.')

        normalized_branch = branch.strip()
        if not normalized_branch:
            raise RepositoryLookupError('Branch is required to push the generated pipeline.')

        normalized_commit_message = commit_message.strip()
        if not normalized_commit_message:
            raise RepositoryLookupError('Commit message is required to push the generated pipeline.')

        normalized_file_path = self._normalize_repository_file_path(file_path)
        if not content.strip():
            raise RepositoryLookupError('Pipeline content is empty and cannot be pushed to the repository.')

        if effective_platform == 'azure-devops':
            return await self._push_file_to_azure_devops(
                repository_url=repository_url,
                branch=normalized_branch,
                file_path=normalized_file_path,
                content=content,
                commit_message=normalized_commit_message,
            )

        remote_url, api_key = self._resolve_platform_settings(effective_platform, repository_url)
        git_env = self._build_git_environment(effective_platform, api_key)

        return await asyncio.to_thread(
            self._push_file_with_git,
            remote_url,
            normalized_branch,
            normalized_file_path,
            content,
            normalized_commit_message,
            git_env,
        )

    async def publish_azure_devops_pipeline(
        self,
        repository_url: str,
        content: str,
        branch: str,
        file_path: str,
        pipeline_name: str | None = None,
        commit_message: str | None = None,
    ) -> AzureDevOpsPipelinePublishResult:
        normalized_content = content.strip()
        if not normalized_content:
            raise RepositoryLookupError('Pipeline content is empty and cannot be published to Azure DevOps.')

        normalized_branch = (branch or '').strip()
        if not normalized_branch:
            raise RepositoryLookupError('Branch is required to publish the generated pipeline to Azure DevOps.')

        normalized_file_path = self._normalize_repository_file_path(file_path or 'azure-pipelines.yml')
        normalized_pipeline_name = (pipeline_name or '').strip() or self._derive_pipeline_name_from_path(normalized_file_path)
        normalized_commit_message = (commit_message or '').strip() or f'Update {normalized_file_path} pipeline definition'

        # Step 1: ensure the YAML file is committed on the selected branch.
        write_result = await self._push_file_to_azure_devops(
            repository_url=repository_url,
            branch=normalized_branch,
            file_path=normalized_file_path,
            content=normalized_content,
            commit_message=normalized_commit_message,
        )

        # Step 2: register or update the pipeline definition that points at the file.
        context = await self._resolve_azure_devops_context(repository_url)
        registration = await self._upsert_azure_devops_pipeline_definition(
            context=context,
            pipeline_name=normalized_pipeline_name,
            branch=normalized_branch,
            file_path=normalized_file_path,
        )

        return AzureDevOpsPipelinePublishResult(
            status=registration['status'],
            pipeline_id=registration.get('id'),
            pipeline_name=normalized_pipeline_name,
            repository_id=context.repository_id,
            repository_name=context.repository_name,
            branch=normalized_branch,
            file_path=normalized_file_path,
            commit_sha=write_result.commit_sha,
            pipeline_url=registration.get('url'),
        )

    @staticmethod
    def _derive_pipeline_name_from_path(file_path: str) -> str:
        stem = PurePosixPath(file_path).stem or 'azure-pipeline'
        return stem if stem != 'azure-pipelines' else 'wega-azure-ci-pipeline'

    async def publish_pipeline(
        self,
        platform: str,
        repository_url: str | None,
        content: str,
    ) -> HarnessPipelinePublishResult:
        if platform != 'harness':
            raise RepositoryLookupError('Direct pipeline publish is currently supported only for Harness pipelines.')

        normalized_content = content.strip()
        if not normalized_content:
            raise RepositoryLookupError('Pipeline content is empty and cannot be published directly to Harness.')

        context = self._resolve_harness_context(repository_url)
        normalized_content = self._normalize_harness_pipeline_yaml(normalized_content, context)
        pipeline_name, pipeline_identifier = self._parse_harness_pipeline_metadata(normalized_content)
        status = await self._upsert_harness_pipeline(context, pipeline_name, pipeline_identifier, normalized_content)

        return HarnessPipelinePublishResult(
            status=status,
            pipeline_identifier=pipeline_identifier,
            pipeline_name=pipeline_name,
            account_identifier=context.account_identifier,
            org_identifier=context.org_identifier,
            project_identifier=context.project_identifier,
        )

    def _normalize_harness_pipeline_yaml(self, content: str, context: HarnessProjectContext) -> str:
        """Best-effort normalization to make LLM-generated Harness YAML publish-safe.

        - Overwrites pipeline.orgIdentifier/projectIdentifier with the resolved Harness context.
        - Ensures pipeline.tags is present.
        - Ensures pipeline.properties.ci.codebase has connectorRef/repoName/build.
        - Renames legacy `cloneCodeRepo` to `cloneCodebase` on CI stages.
        - Sanitizes pipeline + stage + step identifiers.
        """

        try:
            import yaml
        except ImportError as exc:
            raise RepositoryLookupError(
                'Harness pipeline publishing requires PyYAML on the deployment orchestrator host.',
                status_code=503,
            ) from exc

        try:
            document = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise RepositoryLookupError(
                'Generated Harness YAML is invalid and cannot be published directly to Harness Pipelines.',
                log_message=f'Failed to parse generated Harness YAML: {exc}',
            ) from exc

        if not isinstance(document, dict) or not isinstance(document.get('pipeline'), dict):
            raise RepositoryLookupError('Generated Harness YAML must contain a top-level pipeline object.')

        pipeline = document['pipeline']
        pipeline['orgIdentifier'] = context.org_identifier
        pipeline['projectIdentifier'] = context.project_identifier

        if not isinstance(pipeline.get('tags'), dict):
            pipeline['tags'] = {}

        pipeline_name = str(pipeline.get('name') or '').strip() or 'wega-ci-pipeline'
        pipeline['name'] = pipeline_name
        pipeline['identifier'] = self._sanitize_harness_identifier(
            str(pipeline.get('identifier') or pipeline_name),
            'wega_ci_pipeline',
        )

        properties = pipeline.setdefault('properties', {})
        if not isinstance(properties, dict):
            properties = {}
            pipeline['properties'] = properties
        ci = properties.setdefault('ci', {})
        if not isinstance(ci, dict):
            ci = {}
            properties['ci'] = ci
        codebase = ci.setdefault('codebase', {})
        if not isinstance(codebase, dict):
            codebase = {}
            ci['codebase'] = codebase
        if not codebase.get('build'):
            codebase['build'] = '<+input>'
        if not codebase.get('repoName'):
            codebase['repoName'] = pipeline_name
        # connectorRef left as-is unless missing; replaced with placeholder if needed
        if not codebase.get('connectorRef'):
            codebase['connectorRef'] = 'account.harnessImage'

        stages = pipeline.get('stages') or []
        if isinstance(stages, list):
            seen_stage_ids: set[str] = set()
            for stage_entry in stages:
                if not isinstance(stage_entry, dict) or not isinstance(stage_entry.get('stage'), dict):
                    continue
                stage = stage_entry['stage']
                stage_name = str(stage.get('name') or 'Stage')
                stage_identifier = self._sanitize_harness_identifier(
                    str(stage.get('identifier') or stage_name),
                    'stage',
                )
                base_id = stage_identifier
                suffix = 2
                while stage_identifier in seen_stage_ids:
                    stage_identifier = f'{base_id}_{suffix}'
                    suffix += 1
                seen_stage_ids.add(stage_identifier)
                stage['identifier'] = stage_identifier

                spec = stage.get('spec')
                if isinstance(spec, dict):
                    if 'cloneCodeRepo' in spec and 'cloneCodebase' not in spec:
                        spec['cloneCodebase'] = bool(spec.pop('cloneCodeRepo'))
                    spec.pop('cloneCodeRepo', None)
                    execution = spec.get('execution') if isinstance(spec, dict) else None
                    if isinstance(execution, dict):
                        steps = execution.get('steps') or []
                        if isinstance(steps, list):
                            seen_step_ids: set[str] = set()
                            for step_entry in steps:
                                if not isinstance(step_entry, dict) or not isinstance(step_entry.get('step'), dict):
                                    continue
                                step = step_entry['step']
                                step_name = str(step.get('name') or step.get('type') or 'step')
                                step_identifier = self._sanitize_harness_identifier(
                                    str(step.get('identifier') or f'{stage_identifier}_{step_name}'),
                                    f'{stage_identifier}_step',
                                )
                                base_step_id = step_identifier
                                suffix = 2
                                while step_identifier in seen_step_ids:
                                    step_identifier = f'{base_step_id}_{suffix}'
                                    suffix += 1
                                seen_step_ids.add(step_identifier)
                                step['identifier'] = step_identifier

        return yaml.safe_dump(document, sort_keys=False, default_flow_style=False, width=4096)

    @staticmethod
    def _sanitize_harness_identifier(value: str, fallback: str) -> str:
        import re

        candidate = re.sub(r'[^A-Za-z0-9_]', '_', (value or '').strip()).strip('_')
        if not candidate:
            candidate = fallback
        if candidate and not (candidate[0].isalpha() or candidate[0] == '_'):
            candidate = f'_{candidate}'
        return candidate or fallback

    async def _fetch_json(self, url: str, headers: dict[str, str], provider: str) -> object:
        try:
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            request_url = exc.request.url if exc.request is not None else httpx.URL(url)
            response_body = (exc.response.text or '')[:2000]
            logger.warning(
                'Repository lookup provider error: provider=%s status=%s host=%s path=%s body=%s',
                provider,
                exc.response.status_code,
                request_url.host,
                request_url.path,
                response_body,
            )
            raise RepositoryLookupError(
                'Repository lookup failed at the provider. Verify repository access and provider configuration.',
                log_message=f'{provider} provider error status={exc.response.status_code} host={request_url.host} path={request_url.path}',
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning('Repository lookup transport error: provider=%s detail=%s', provider, str(exc))
            raise RepositoryLookupError(
                'Repository lookup could not reach the provider. Verify provider connectivity and try again.',
                log_message=f'{provider} transport error: {exc}',
                status_code=502,
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            logger.warning(
                'Repository lookup returned non-JSON content: provider=%s host=%s path=%s body=%s',
                provider,
                response.request.url.host,
                response.request.url.path,
                response.text[:1000],
            )
            raise RepositoryLookupError(
                'Repository lookup returned an invalid provider response.',
                log_message=f'{provider} returned non-JSON content',
                status_code=502,
            ) from exc

    def _resolve_platform_settings(self, platform: str, repository_url: str | None = None) -> tuple[str, str]:
        normalized_repository_url = (repository_url or '').strip()

        if platform == 'github-actions':
            base_url = normalized_repository_url or settings.github_repository_url.strip()
            if not base_url:
                raise RepositoryLookupError('GITHUB_REPOSITORY_URL is not configured.')
            validated_url = self._validate_repository_url(platform, base_url)
            return str(validated_url), settings.github_pat_token.strip()

        if platform == 'gitlab-ci':
            base_url = normalized_repository_url or settings.gitlab_repository_url.strip()
            if not base_url:
                raise RepositoryLookupError('GITLAB_REPOSITORY_URL is not configured.')
            validated_url = self._validate_repository_url(platform, base_url)
            return str(validated_url), settings.gitlab_pat_token.strip()

        if platform == 'azure-devops':
            base_url = normalized_repository_url or settings.azure_devops_repository_url.strip() or settings.azure_devops_organization_url.strip()
            if not base_url:
                raise RepositoryLookupError('AZURE_DEVOPS_REPOSITORY_URL or AZURE_DEVOPS_ORGANIZATION_URL is not configured.')
            pat_token = self._resolve_azure_devops_pat_token()
            validated_url = self._validate_repository_url(platform, base_url)
            return str(validated_url), pat_token

        if platform == 'harness':
            base_url = normalized_repository_url or settings.harness_repository_url.strip()
            if not base_url:
                raise RepositoryLookupError(
                    'HARNESS_BASE_URL, HARNESS_ACCOUNT_IDENTIFIER, HARNESS_ORG_IDENTIFIER, and HARNESS_PROJECT_IDENTIFIER must be configured.'
                )
            validated_url = self._validate_repository_url(platform, base_url)
            return str(validated_url), self._resolve_harness_api_key()

        raise RepositoryLookupError(f'Unsupported platform {platform!r}.')

    def _resolve_repository_provider(self, platform: str, repository_url: str | None = None) -> str:
        normalized_platform = platform.strip().lower()
        normalized_repository_url = (repository_url or '').strip()
        if normalized_platform == 'jenkins':
            return 'harness'

        detected_provider = self._detect_repository_provider(repository_url)
        if detected_provider is not None:
            return detected_provider

        if normalized_repository_url:
            return normalized_platform

        if _configured_repository_url_for_platform(normalized_platform):
            return normalized_platform

        if normalized_platform in _HARNESS_BACKED_PLATFORMS:
            return 'harness'

        return normalized_platform

    def _detect_repository_provider(self, repository_url: str | None) -> str | None:
        normalized_repository_url = (repository_url or '').strip()
        if not normalized_repository_url:
            return None

        try:
            parsed_url = self._parse_url(normalized_repository_url)
        except RepositoryLookupError:
            return None

        host = (parsed_url.host or '').lower()
        for candidate in ('harness', 'github-actions', 'gitlab-ci', 'azure-devops'):
            if any(_host_matches_pattern(host, pattern) for pattern in self._allowed_hosts_for_platform(candidate)):
                return candidate

        return None

    def _parse_url(self, repository_url: str) -> httpx.URL:
        try:
            return httpx.URL(repository_url.strip())
        except Exception as exc:  # noqa: BLE001
            raise RepositoryLookupError('Repository URL is invalid.') from exc

    def _parse_harness_pipeline_metadata(self, content: str) -> tuple[str, str]:
        try:
            import yaml
        except ImportError as exc:
            raise RepositoryLookupError(
                'Harness pipeline publishing requires PyYAML on the deployment orchestrator host.',
                status_code=503,
            ) from exc

        try:
            document = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise RepositoryLookupError(
                'Generated Harness YAML is invalid and cannot be published directly to Harness Pipelines.',
                log_message=f'Failed to parse generated Harness YAML: {exc}',
            ) from exc

        if not isinstance(document, dict):
            raise RepositoryLookupError('Generated Harness YAML must contain a top-level pipeline object.')

        pipeline = document.get('pipeline')
        if not isinstance(pipeline, dict):
            raise RepositoryLookupError('Generated Harness YAML must define pipeline.name and pipeline.identifier.')

        pipeline_name = str(pipeline.get('name') or '').strip()
        pipeline_identifier = str(pipeline.get('identifier') or '').strip()

        if not pipeline_name or not pipeline_identifier:
            raise RepositoryLookupError('Generated Harness YAML must include pipeline.name and pipeline.identifier.')

        return pipeline_name, pipeline_identifier

    def _normalize_repository_file_path(self, file_path: str) -> str:
        normalized_value = file_path.strip().replace('\\', '/')
        if not normalized_value:
            raise RepositoryLookupError('Repository file path is required.')

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or any(part in {'', '.', '..'} for part in normalized_path.parts):
            raise RepositoryLookupError('Repository file path is invalid.')

        return str(normalized_path)

    def _build_git_environment(self, platform: str, token: str) -> dict[str, str]:
        if platform != 'harness':
            raise RepositoryLookupError(f'Repository push is not supported for {platform!r}.')

        if not token.strip():
            raise RepositoryLookupError('Harness repository push credentials are not configured.', status_code=503)

        return {
            'GIT_TERMINAL_PROMPT': '0',
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'http.extraHeader',
            'GIT_CONFIG_VALUE_0': f'x-api-key: {token}',
        }

    async def _upsert_harness_pipeline(
        self,
        context: HarnessProjectContext,
        pipeline_name: str,
        pipeline_identifier: str,
        content: str,
    ) -> str:
        # Modern Harness Pipelines API expects the YAML body and the legacy JSON
        # envelope as a fallback for older Harness installations.
        json_payload = {
            'name': pipeline_name,
            'identifier': pipeline_identifier,
            'orgIdentifier': context.org_identifier,
            'projectIdentifier': context.project_identifier,
            'tags': {},
            'yaml': content,
            'pipeline_yaml': content,
        }
        update_url = self._build_harness_pipeline_url(context, pipeline_identifier)
        create_url = self._build_harness_pipeline_url(context)
        missing_response = await self._send_harness_pipeline_request(
            'PUT',
            update_url,
            context.api_key,
            json_payload,
            content,
            allow_missing=True,
        )
        if missing_response is None:
            await self._send_harness_pipeline_request('POST', create_url, context.api_key, json_payload, content)
            return 'created'
        return 'updated'

    async def _send_harness_pipeline_request(
        self,
        method: str,
        url: str,
        api_key: str,
        payload: dict[str, object],
        content: str,
        *,
        allow_missing: bool = False,
    ) -> httpx.Response | None:
        url_candidates = url if isinstance(url, list) else [url]
        # Modern Harness Pipelines REST API accepts raw YAML with
        # Content-Type: application/yaml. Older variants accept a JSON
        # envelope; we try YAML first and fall back to JSON for compatibility.
        request_variants = [
            {
                'headers': {
                    **self._build_harness_headers(api_key),
                    'Content-Type': 'application/yaml',
                },
                'json': None,
                'content': content,
            },
            {
                'headers': {
                    **self._build_harness_headers(api_key),
                    'Content-Type': 'application/json',
                },
                'json': payload,
                'content': None,
            },
        ]
        last_http_error: httpx.HTTPStatusError | None = None

        for candidate_url in url_candidates:
            for index, variant in enumerate(request_variants):
                try:
                    response = await self._client.request(
                        method,
                        candidate_url,
                        headers=variant['headers'],
                        json=variant['json'],
                        content=variant['content'],
                    )
                    if allow_missing and self._is_harness_pipeline_missing_response(response):
                        return None
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as exc:
                    if allow_missing and self._is_harness_pipeline_missing_response(exc.response):
                        return None

                    # Try the next content-type variant, then the next URL.
                    if exc.response.status_code in {400, 404, 415, 422}:
                        last_http_error = exc
                        continue

                    raise self._build_harness_pipeline_error(exc) from exc
                except httpx.HTTPError as exc:
                    raise RepositoryLookupError(
                        'Harness pipeline publish could not reach the provider. Verify provider connectivity and try again.',
                        log_message=f'Harness pipeline publish transport error: {exc}',
                        status_code=502,
                    ) from exc

        if last_http_error is not None:
            raise self._build_harness_pipeline_error(last_http_error) from last_http_error

        raise RepositoryLookupError('Harness pipeline publish failed before the provider request completed.')

    def _build_harness_pipeline_error(self, exc: httpx.HTTPStatusError) -> RepositoryLookupError:
        request_url = exc.request.url if exc.request is not None else httpx.URL('https://app.harness.io/pipeline/api/pipelines/v2')
        response_body = (exc.response.text or '')[:2000]
        logger.warning(
            'Harness pipeline provider error: status=%s host=%s path=%s body=%s',
            exc.response.status_code,
            request_url.host,
            request_url.path,
            response_body,
        )
        upstream_summary = self._summarize_harness_error_body(response_body)
        user_message = (
            'Harness pipeline publish failed. Verify the generated YAML, connector references, and Harness project configuration.'
        )
        if upstream_summary:
            user_message = f'{user_message} Upstream: {upstream_summary}'
        return RepositoryLookupError(
            user_message,
            log_message=f'harness pipeline publish error status={exc.response.status_code} host={request_url.host} path={request_url.path}',
            status_code=502,
        )

    @staticmethod
    def _summarize_harness_error_body(body: str) -> str:
        if not body:
            return ''
        try:
            import json

            parsed = json.loads(body)
        except ValueError:
            return body.strip()[:300]
        if isinstance(parsed, dict):
            for key in ('message', 'error', 'detailedMessage', 'responseMessages'):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:300]
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, dict):
                        for inner_key in ('message', 'detailedMessage'):
                            inner = first.get(inner_key)
                            if isinstance(inner, str) and inner.strip():
                                return inner.strip()[:300]
                    elif isinstance(first, str) and first.strip():
                        return first.strip()[:300]
        return body.strip()[:300]

    def _is_harness_pipeline_missing_response(self, response: httpx.Response) -> bool:
        if response.status_code == 404:
            return True

        if response.status_code != 400:
            return False

        body = (response.text or '').lower()
        return any(token in body for token in ['not found', 'does not exist', 'not exist', 'entity not found'])

    def _build_harness_pipeline_url(
        self,
        context: HarnessProjectContext,
        pipeline_identifier: str | None = None,
    ) -> list[str]:
        """Return Harness Pipelines API URL candidates in priority order.

        The modern endpoint is `/pipeline/api/pipelines/v2`. We also try the
        legacy `/pipeline/api/pipelines` and `/ng/api/pipelines` paths so that
        older Harness installations remain supported.
        """

        query = self._build_harness_query(context)
        modern_paths = ['/pipeline/api/pipelines/v2', '/pipeline/api/pipelines']
        legacy_paths = ['/ng/api/pipelines']

        urls: list[str] = []
        for base_path in [*modern_paths, *legacy_paths]:
            path = base_path
            if pipeline_identifier:
                path = f'{path}/{quote(pipeline_identifier, safe="")}'
            urls.append(f'{context.api_base_url}{path}?{query}')
        return urls

    def _push_file_with_git(
        self,
        remote_url: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
        git_env: dict[str, str] | None = None,
    ) -> RepositoryWriteResult:
        with tempfile.TemporaryDirectory(prefix='wega-repo-push-') as temp_dir:
            working_tree = Path(temp_dir) / 'repo'

            self._run_git_command(
                ['clone', '--depth', '1', '--branch', branch, '--single-branch', remote_url, str(working_tree)],
                env=git_env,
                error_message='Unable to clone the selected repository and branch. Verify repository access and branch selection.',
            )
            self._run_git_command(
                ['config', 'user.name', settings.repository_push_author_name],
                cwd=working_tree,
                error_message='Unable to configure the repository commit author name.',
            )
            self._run_git_command(
                ['config', 'user.email', settings.repository_push_author_email],
                cwd=working_tree,
                error_message='Unable to configure the repository commit author email.',
            )

            target_path = working_tree.joinpath(*PurePosixPath(file_path).parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding='utf-8', newline='\n')

            self._run_git_command(
                ['add', '--', file_path],
                cwd=working_tree,
                error_message='Unable to stage the generated pipeline file for commit.',
            )
            status_result = self._run_git_command(
                ['status', '--porcelain', '--', file_path],
                cwd=working_tree,
                error_message='Unable to inspect repository changes before commit.',
            )

            if not status_result.stdout.strip():
                commit_sha = self._run_git_command(
                    ['rev-parse', 'HEAD'],
                    cwd=working_tree,
                    error_message='Unable to resolve the current repository revision.',
                ).stdout.strip() or None
                return RepositoryWriteResult(
                    status='noop',
                    repository_url=remote_url,
                    branch=branch,
                    file_path=file_path,
                    commit_message=commit_message,
                    commit_sha=commit_sha,
                )

            self._run_git_command(
                ['commit', '-m', commit_message],
                cwd=working_tree,
                error_message='Unable to create a commit for the generated pipeline file.',
            )
            commit_sha = self._run_git_command(
                ['rev-parse', 'HEAD'],
                cwd=working_tree,
                error_message='Unable to resolve the new repository revision after commit.',
            ).stdout.strip() or None
            self._run_git_command(
                ['push', 'origin', f'HEAD:{branch}'],
                cwd=working_tree,
                env=git_env,
                error_message='Unable to push the generated pipeline commit to the selected repository branch.',
            )

            return RepositoryWriteResult(
                status='committed',
                repository_url=remote_url,
                branch=branch,
                file_path=file_path,
                commit_message=commit_message,
                commit_sha=commit_sha,
            )

    def _run_git_command(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        error_message: str,
    ) -> subprocess.CompletedProcess[str]:
        command_env = os.environ.copy()
        if env:
            command_env.update(env)

        try:
            return subprocess.run(
                ['git', *args],
                cwd=str(cwd) if cwd is not None else None,
                env=command_env,
                capture_output=True,
                text=True,
                timeout=settings.repository_push_timeout_seconds,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RepositoryLookupError(
                'Git is not available on the deployment orchestrator host.',
                log_message='git executable was not found while attempting to push a repository file',
                status_code=503,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            stderr = (exc.stderr or '')[:1000]
            raise RepositoryLookupError(
                error_message,
                log_message=f'git command timed out args={args!r} stderr={stderr}',
                status_code=504,
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or '')[:1000]
            stdout = (exc.stdout or '')[:1000]
            raise RepositoryLookupError(
                error_message,
                log_message=f'git command failed args={args!r} exit={exc.returncode} stdout={stdout} stderr={stderr}',
                status_code=502,
            ) from exc

    async def _list_github_repositories(self, repository_url: str | None = None) -> list[RepositoryOption]:
        base_url, pat_token = self._resolve_platform_settings('github-actions', repository_url)
        parsed_url = self._parse_url(base_url)
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if not segments:
            raise RepositoryLookupError('Use a GitHub organization or repository URL such as https://github.com/org or https://github.com/org/repository.git.')

        api_base_url = 'https://api.github.com' if parsed_url.host == 'github.com' else f'{parsed_url.scheme}://{parsed_url.host}/api/v3'
        owner = segments[0]
        if len(segments) > 1:
            repository_name = _trim_git_suffix(segments[1])
            return [RepositoryOption(id=repository_name, label=repository_name, url=f'{parsed_url.scheme}://{parsed_url.host}/{owner}/{repository_name}')]

        headers = {
            'Accept': 'application/vnd.github+json',
            **({'Authorization': f'Bearer {pat_token}'} if pat_token else {}),
        }

        try:
            payload = await self._fetch_json(f'{api_base_url}/orgs/{owner}/repos?per_page=100&sort=full_name', headers, 'github-actions')
        except RepositoryLookupError:
            payload = await self._fetch_json(f'{api_base_url}/users/{owner}/repos?per_page=100&sort=full_name', headers, 'github-actions')

        repositories = [
            RepositoryOption(
                id=str(item.get('id') or item.get('name') or ''),
                label=str(item.get('name') or 'Repository'),
                url=str(item.get('html_url') or ''),
            )
            for item in payload if isinstance(item, dict)
        ]
        return _sort_repository_options(repositories)

    async def _list_github_branches(self, repository_url: str) -> list[str]:
        base_url, pat_token = self._resolve_platform_settings('github-actions', repository_url)
        parsed_url = self._parse_url(base_url)
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if len(segments) < 2:
            raise RepositoryLookupError('Use a repository-level GitHub URL such as https://github.com/org/repository.git.')

        api_base_url = 'https://api.github.com' if parsed_url.host == 'github.com' else f'{parsed_url.scheme}://{parsed_url.host}/api/v3'
        headers = {
            'Accept': 'application/vnd.github+json',
            **({'Authorization': f'Bearer {pat_token}'} if pat_token else {}),
        }
        payload = await self._fetch_json(
            f'{api_base_url}/repos/{segments[0]}/{_trim_git_suffix(segments[1])}/branches?per_page=100',
            headers,
            'github-actions',
        )
        branches = [str(item.get('name') or '') for item in payload if isinstance(item, dict)]
        return _sort_branch_names(branches)

    async def _list_gitlab_repositories(self, repository_url: str | None = None) -> list[RepositoryOption]:
        base_url, pat_token = self._resolve_platform_settings('gitlab-ci', repository_url)
        parsed_url = self._parse_url(base_url)
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if not segments:
            raise RepositoryLookupError('Use a GitLab group or repository URL such as https://gitlab.com/group or https://gitlab.com/group/project.git.')

        api_base_url = f'{parsed_url.scheme}://{parsed_url.host}/api/v4'
        if len(segments) > 1:
            project_path = _trim_git_suffix('/'.join(segments))
            return [RepositoryOption(id=project_path, label=_trim_git_suffix(segments[-1]), url=_trim_git_suffix(base_url))]

        payload = await self._fetch_json(
            f'{api_base_url}/groups/{segments[0]}/projects?per_page=100&simple=true',
            {
                'Accept': 'application/json',
                **({'PRIVATE-TOKEN': pat_token} if pat_token else {}),
            },
            'gitlab-ci',
        )
        repositories = [
            RepositoryOption(
                id=str(item.get('id') or item.get('name') or ''),
                label=str(item.get('name') or 'Repository'),
                url=str(item.get('web_url') or ''),
            )
            for item in payload if isinstance(item, dict)
        ]
        return _sort_repository_options(repositories)

    async def _list_gitlab_branches(self, repository_url: str) -> list[str]:
        base_url, pat_token = self._resolve_platform_settings('gitlab-ci', repository_url)
        parsed_url = self._parse_url(base_url)
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if len(segments) < 2:
            raise RepositoryLookupError('Use a repository-level GitLab URL such as https://gitlab.com/group/project.git.')

        project_path = quote(_trim_git_suffix('/'.join(segments)), safe='')
        payload = await self._fetch_json(
            f'{parsed_url.scheme}://{parsed_url.host}/api/v4/projects/{project_path}/repository/branches?per_page=100',
            {
                'Accept': 'application/json',
                **({'PRIVATE-TOKEN': pat_token} if pat_token else {}),
            },
            'gitlab-ci',
        )
        branches = [str(item.get('name') or '') for item in payload if isinstance(item, dict)]
        return _sort_branch_names(branches)

    def _resolve_azure_devops_pat_token(self) -> str:
        secret_name = settings.azure_devops_secret_name.strip()
        if secret_name:
            try:
                secret_value = resolve_optional_secret(secret_name)
            except SecretManagerError as exc:
                logger.error('Failed to resolve Azure DevOps secret %r: %s', secret_name, exc)
                raise RepositoryLookupError(
                    'Azure DevOps secret configuration is unavailable. Verify the configured secret exists in Google Secret Manager.',
                    log_message=f'Failed to resolve Azure DevOps secret {secret_name!r}',
                    status_code=503,
                ) from exc
            if secret_value:
                return secret_value

        if settings.azure_devops_pat_token.strip():
            return settings.azure_devops_pat_token.strip()

        raise RepositoryLookupError('AZURE_DEVOPS_SECRET_NAME or AZURE_DEVOPS_PAT_TOKEN is not configured.', status_code=503)

    async def _resolve_azure_devops_context(self, repository_url: str | None) -> AzureDevOpsContext:
        base_url, pat_token = self._resolve_platform_settings('azure-devops', repository_url)
        parsed_url = self._parse_url(base_url)
        organization_url, project, configured_repository_name = self._extract_azure_devops_org_project(parsed_url)

        # Fetch repository metadata so we have repository_id (required for Pushes API).
        repositories_payload = await self._fetch_json(
            f'{organization_url}/{quote(project, safe="")}/_apis/git/repositories?api-version=7.1-preview.1',
            {
                'Accept': 'application/json',
                'Authorization': self._build_azure_basic_auth(pat_token),
            },
            'azure-devops',
        )

        repositories = repositories_payload.get('value') if isinstance(repositories_payload, dict) else None
        if not isinstance(repositories, list) or not repositories:
            raise RepositoryLookupError('No Azure DevOps repositories were returned for the configured project.')

        repository_name = configured_repository_name
        repository_match: dict | None = None
        if repository_name:
            repository_match = next(
                (
                    repository
                    for repository in repositories
                    if isinstance(repository, dict) and str(repository.get('name') or '').lower() == repository_name.lower()
                ),
                None,
            )
        if repository_match is None:
            # Default to the first repository in the project when no name was supplied.
            repository_match = next((repository for repository in repositories if isinstance(repository, dict)), None)

        if repository_match is None or not repository_match.get('id'):
            raise RepositoryLookupError(
                'Unable to resolve an Azure DevOps repository for the supplied URL. Provide a repository-level URL or set AZURE_DEVOPS_REPOSITORY_URL.'
            )

        repository_id = str(repository_match.get('id'))
        repository_name = str(repository_match.get('name') or repository_name or 'repository')
        default_branch = str(repository_match.get('defaultBranch') or '').removeprefix('refs/heads/') or 'main'

        return AzureDevOpsContext(
            organization_url=organization_url,
            project=project,
            repository_id=repository_id,
            repository_name=repository_name,
            default_branch=default_branch,
            pat_token=pat_token,
        )

    def _extract_azure_devops_org_project(self, parsed_url: httpx.URL) -> tuple[str, str, str | None]:
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        host = (parsed_url.host or '').lower()

        if host == 'dev.azure.com':
            if len(segments) < 2:
                raise RepositoryLookupError(
                    'Azure DevOps URL must include the organization and project, e.g., https://dev.azure.com/<org>/<project>.'
                )
            organization, project = segments[0], segments[1]
            repository_name = _trim_git_suffix(segments[3]) if len(segments) > 3 and segments[2] == '_git' else None
            return f'{parsed_url.scheme}://{parsed_url.host}/{organization}', project, repository_name

        if host.endswith('.visualstudio.com'):
            if not segments:
                raise RepositoryLookupError(
                    'Azure DevOps URL must include the project, e.g., https://<org>.visualstudio.com/<project>.'
                )
            project = segments[0]
            repository_name = _trim_git_suffix(segments[2]) if len(segments) > 2 and segments[1] == '_git' else None
            return f'{parsed_url.scheme}://{parsed_url.host}', project, repository_name

        raise RepositoryLookupError('Azure DevOps URL host must be dev.azure.com or *.visualstudio.com.')

    async def _push_file_to_azure_devops(
        self,
        repository_url: str | None,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> RepositoryWriteResult:
        context = await self._resolve_azure_devops_context(repository_url)

        # Resolve the latest commit (oldObjectId) on the target branch.
        ref_url = (
            f'{context.organization_url}/{quote(context.project, safe="")}/_apis/git/repositories/'
            f'{quote(context.repository_id, safe="")}/refs?filter=heads/{quote(branch, safe="")}&api-version=7.1-preview.1'
        )
        ref_payload = await self._fetch_json(
            ref_url,
            {
                'Accept': 'application/json',
                'Authorization': self._build_azure_basic_auth(context.pat_token),
            },
            'azure-devops',
        )
        ref_values = ref_payload.get('value') if isinstance(ref_payload, dict) else None
        if not isinstance(ref_values, list) or not ref_values:
            raise RepositoryLookupError(
                f"Branch '{branch}' was not found in the Azure DevOps repository.",
                log_message=f'Azure DevOps ref lookup empty for branch {branch!r}',
            )
        old_object_id = str(ref_values[0].get('objectId') or '')
        if not old_object_id:
            raise RepositoryLookupError(f"Unable to resolve the head commit for branch '{branch}'.")

        # Detect whether the file already exists on this branch to decide between add/edit.
        item_url = (
            f'{context.organization_url}/{quote(context.project, safe="")}/_apis/git/repositories/'
            f'{quote(context.repository_id, safe="")}/items?path={quote(file_path, safe="/")}&versionDescriptor.version='
            f'{quote(branch, safe="")}&versionDescriptor.versionType=branch&api-version=7.1-preview.1'
        )
        change_type = 'add'
        try:
            await self._fetch_json(
                item_url,
                {
                    'Accept': 'application/json',
                    'Authorization': self._build_azure_basic_auth(context.pat_token),
                },
                'azure-devops',
            )
            change_type = 'edit'
        except RepositoryLookupError:
            change_type = 'add'

        push_payload = {
            'refUpdates': [
                {
                    'name': f'refs/heads/{branch}',
                    'oldObjectId': old_object_id,
                }
            ],
            'commits': [
                {
                    'comment': commit_message,
                    'changes': [
                        {
                            'changeType': change_type,
                            'item': {'path': f'/{file_path}'},
                            'newContent': {
                                'content': content,
                                'contentType': 'rawtext',
                            },
                        }
                    ],
                }
            ],
        }
        push_url = (
            f'{context.organization_url}/{quote(context.project, safe="")}/_apis/git/repositories/'
            f'{quote(context.repository_id, safe="")}/pushes?api-version=7.1-preview.2'
        )
        try:
            response = await self._client.post(
                push_url,
                json=push_payload,
                headers={
                    'Accept': 'application/json',
                    'Authorization': self._build_azure_basic_auth(context.pat_token),
                    'Content-Type': 'application/json',
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_body = (exc.response.text or '')[:2000]
            logger.warning(
                'Azure DevOps push failed: status=%s host=%s path=%s body=%s',
                exc.response.status_code,
                exc.request.url.host if exc.request is not None else '',
                exc.request.url.path if exc.request is not None else '',
                response_body,
            )
            raise RepositoryLookupError(
                f'Azure DevOps push failed: {self._summarize_azure_devops_error_body(response_body)}',
                log_message=f'azure-devops push status={exc.response.status_code} body={response_body[:500]}',
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise RepositoryLookupError(
                'Azure DevOps push could not reach the provider. Verify provider connectivity and try again.',
                log_message=f'azure-devops push transport error: {exc}',
                status_code=502,
            ) from exc

        try:
            push_response = response.json()
        except ValueError:
            push_response = None

        logger.info(
            'Azure DevOps push response: status=%s body=%s',
            response.status_code,
            json.dumps(push_response, default=str)[:1500] if push_response is not None else (response.text or '')[:1500],
        )

        commit_sha: str | None = None
        if isinstance(push_response, dict):
            ref_updates = push_response.get('refUpdates') or []
            if isinstance(ref_updates, list) and ref_updates and isinstance(ref_updates[0], dict):
                candidate = str(ref_updates[0].get('newObjectId') or '')
                # Skip the all-zero SHA which means "no update applied".
                if candidate and not all(ch == '0' for ch in candidate):
                    commit_sha = candidate
            commits = push_response.get('commits') or []
            if not commit_sha and isinstance(commits, list) and commits and isinstance(commits[0], dict):
                candidate = str(commits[0].get('commitId') or '')
                if candidate and not all(ch == '0' for ch in candidate):
                    commit_sha = candidate

        if not commit_sha:
            logger.warning(
                'Azure DevOps push returned 2xx but no usable commit SHA. Treating as failed push. body=%s',
                json.dumps(push_response, default=str)[:1500] if push_response is not None else '<non-json>',
            )
            raise RepositoryLookupError(
                'Azure DevOps push completed without producing a commit. Check branch protection policies (PR-only) and retry.',
                status_code=502,
            )

        # Verify the file is actually present at the expected path/branch after push.
        verify_url = (
            f'{context.organization_url}/{quote(context.project, safe="")}/_apis/git/repositories/'
            f'{quote(context.repository_id, safe="")}/items?path={quote(file_path, safe="/")}&versionDescriptor.version='
            f'{quote(branch, safe="")}&versionDescriptor.versionType=branch&includeContent=false&api-version=7.1-preview.1'
        )
        try:
            verify_response = await self._client.get(
                verify_url,
                headers={
                    'Accept': 'application/json',
                    'Authorization': self._build_azure_basic_auth(context.pat_token),
                },
            )
        except httpx.HTTPError as exc:
            logger.warning('Azure DevOps post-push verification transport error: %s', exc)
            verify_response = None

        if verify_response is not None and verify_response.status_code != 200:
            verify_body = (verify_response.text or '')[:1000]
            logger.warning(
                'Azure DevOps post-push verification did not find the file: status=%s url=%s body=%s',
                verify_response.status_code,
                verify_url,
                verify_body,
            )
            raise RepositoryLookupError(
                f'Azure DevOps reported the push succeeded (commit {commit_sha[:7]}), but the file was not found at '
                f'{file_path!r} on branch {branch!r} (verification status {verify_response.status_code}). '
                f'Verify the branch is not redirecting commits via a policy and that the file path has no leading slash duplication.',
                status_code=502,
            )

        return RepositoryWriteResult(
            status='committed',
            repository_url=f'{context.organization_url}/{context.project}/_git/{context.repository_name}',
            branch=branch,
            file_path=file_path,
            commit_message=commit_message,
            commit_sha=commit_sha,
        )

    async def _upsert_azure_devops_pipeline_definition(
        self,
        context: AzureDevOpsContext,
        pipeline_name: str,
        branch: str,
        file_path: str,
    ) -> dict[str, object]:
        list_url = (
            f'{context.organization_url}/{quote(context.project, safe="")}/_apis/pipelines'
            f'?api-version=7.1-preview.1&queryOrder=name&top=200'
        )
        existing_pipeline_id: int | None = None
        try:
            list_payload = await self._fetch_json(
                list_url,
                {
                    'Accept': 'application/json',
                    'Authorization': self._build_azure_basic_auth(context.pat_token),
                },
                'azure-devops',
            )
            entries = list_payload.get('value') if isinstance(list_payload, dict) else []
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get('name') or '').strip().lower() == pipeline_name.strip().lower():
                        identifier = entry.get('id')
                        if isinstance(identifier, int):
                            existing_pipeline_id = identifier
                            break
        except RepositoryLookupError:
            existing_pipeline_id = None

        payload = {
            'name': pipeline_name,
            'folder': settings.azure_devops_default_pipeline_folder.strip() or None,
            'configuration': {
                'type': 'yaml',
                'path': file_path if file_path.startswith('/') else f'/{file_path}',
                'repository': {
                    'id': context.repository_id,
                    'name': context.repository_name,
                    'type': 'azureReposGit',
                },
                'branch': branch,
            },
        }
        # Drop folder=None to avoid Azure rejecting the field.
        if payload.get('folder') is None:
            payload.pop('folder', None)

        headers = {
            'Accept': 'application/json',
            'Authorization': self._build_azure_basic_auth(context.pat_token),
            'Content-Type': 'application/json',
        }
        if existing_pipeline_id is not None:
            update_url = (
                f'{context.organization_url}/{quote(context.project, safe="")}/_apis/pipelines/'
                f'{existing_pipeline_id}?api-version=7.1-preview.1'
            )
            try:
                response = await self._client.put(update_url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                response_body = (exc.response.text or '')[:2000]
                logger.warning(
                    'Azure DevOps pipeline update failed: status=%s body=%s',
                    exc.response.status_code,
                    response_body,
                )
                # Fall through to create as a recovery path.
                existing_pipeline_id = None
            except httpx.HTTPError as exc:
                raise RepositoryLookupError(
                    'Azure DevOps pipeline update could not reach the provider.',
                    log_message=f'azure-devops pipeline update transport error: {exc}',
                    status_code=502,
                ) from exc

        if existing_pipeline_id is None:
            create_url = (
                f'{context.organization_url}/{quote(context.project, safe="")}/_apis/pipelines?api-version=7.1-preview.1'
            )
            try:
                response = await self._client.post(create_url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                response_body = (exc.response.text or '')[:2000]
                logger.warning(
                    'Azure DevOps pipeline create failed: status=%s body=%s',
                    exc.response.status_code,
                    response_body,
                )
                raise RepositoryLookupError(
                    f'Azure DevOps pipeline registration failed: {self._summarize_azure_devops_error_body(response_body)}',
                    log_message=f'azure-devops pipeline create status={exc.response.status_code} body={response_body[:500]}',
                    status_code=502,
                ) from exc
            except httpx.HTTPError as exc:
                raise RepositoryLookupError(
                    'Azure DevOps pipeline create could not reach the provider.',
                    log_message=f'azure-devops pipeline create transport error: {exc}',
                    status_code=502,
                ) from exc

        registration = response.json() if response.content else {}
        if not isinstance(registration, dict):
            registration = {}

        return {
            'status': 'updated' if existing_pipeline_id is not None else 'created',
            'id': registration.get('id'),
            'url': self._extract_azure_devops_pipeline_web_url(registration, context),
        }

    @staticmethod
    def _extract_azure_devops_pipeline_web_url(payload: dict, context: AzureDevOpsContext) -> str | None:
        links = payload.get('_links') if isinstance(payload, dict) else None
        if isinstance(links, dict):
            web = links.get('web') if isinstance(links.get('web'), dict) else None
            if isinstance(web, dict):
                href = web.get('href')
                if isinstance(href, str) and href.strip():
                    return href.strip()
        identifier = payload.get('id') if isinstance(payload, dict) else None
        if isinstance(identifier, int):
            return f'{context.organization_url}/{context.project}/_build?definitionId={identifier}'
        return None

    @staticmethod
    def _summarize_azure_devops_error_body(body: str) -> str:
        if not body:
            return 'no response body'
        try:
            import json

            parsed = json.loads(body)
        except ValueError:
            return body.strip()[:300]
        if isinstance(parsed, dict):
            for key in ('message', 'value', 'typeKey'):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:300]
        return body.strip()[:300]

    async def _list_azure_devops_repositories(self, repository_url: str | None = None) -> list[RepositoryOption]:
        base_url, pat_token = self._resolve_platform_settings('azure-devops', repository_url)
        parsed_url = self._parse_url(base_url)
        api_url, repository_name = self._build_azure_project_api(parsed_url)
        if repository_name:
            return [RepositoryOption(id=repository_name, label=repository_name, url=base_url)]

        payload = await self._fetch_json(
            api_url,
            {
                'Accept': 'application/json',
                'Authorization': self._build_azure_basic_auth(pat_token),
            },
            'azure-devops',
        )
        repositories = [
            RepositoryOption(
                id=str(item.get('id') or item.get('name') or ''),
                label=str(item.get('name') or 'Repository'),
                url=str(item.get('webUrl') or ''),
            )
            for item in payload.get('value', []) if isinstance(item, dict)
        ]
        return _sort_repository_options(repositories)

    async def _resolve_azure_devops_repository_id(
        self,
        project_origin: str,
        project: str,
        repository_name: str,
        headers: dict[str, str],
    ) -> str:
        """Resolve the GUID for the given repository using the most direct API path possible.

        Tries `/_apis/git/repositories/{name}` first (single-repo lookup) so any auth/permission
        problem fails loudly with a real status code. Falls back to listing repositories if the
        single-repo endpoint isn't available on the install.
        """

        async def _diagnose_response(response: httpx.Response, *, label: str) -> str:
            content_type = (response.headers.get('content-type') or '').lower()
            body = (response.text or '')[:2000]
            if 'text/html' in content_type:
                return (
                    f'{label} returned HTML (status {response.status_code}, content-type={content_type}). '
                    'Azure DevOps redirected to a sign-in page, which means the PAT was rejected. '
                    'Confirm the PAT belongs to organization {org} and has Code: Read scope.'
                ).format(org=project_origin.rsplit('/', 1)[0])
            return (
                f'{label} returned status {response.status_code} with content-type {content_type or "unknown"}. '
                f'Body: {body[:300] or "<empty>"}'
            )

        # 1) Direct single-repo lookup by name. This call is what fails clearly when auth or scope is wrong.
        single_repo_url = (
            f'{project_origin}/_apis/git/repositories/{quote(repository_name, safe="")}?api-version=7.1-preview.1'
        )
        try:
            response = await self._client.get(single_repo_url, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning('Azure DevOps single-repo lookup transport error: %s', exc)
            raise RepositoryLookupError(
                'Azure DevOps could not be reached for repository lookup. Verify provider connectivity.',
                log_message=f'azure-devops single-repo transport error: {exc}',
                status_code=502,
            ) from exc

        content_type = (response.headers.get('content-type') or '').lower()

        if response.status_code == 200 and 'application/json' in content_type:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                repository_id = str(payload.get('id') or '').strip()
                if repository_id:
                    return repository_id

        if response.status_code in (401, 403) or 'text/html' in content_type:
            diagnosis = await _diagnose_response(response, label='Azure DevOps repository lookup')
            logger.warning(diagnosis)
            raise RepositoryLookupError(
                f'Azure DevOps rejected the request. {diagnosis}',
                log_message=diagnosis,
                status_code=502,
            )

        # Log the body so the operator can see exactly what came back.
        logger.warning(
            'Azure DevOps single-repo lookup did not return a usable JSON repository: status=%s content-type=%s body=%s',
            response.status_code,
            content_type,
            (response.text or '')[:1000],
        )

        # 2) Fall back to listing repositories at the **organization** level. The project-scoped
        # endpoint can return an empty result on some Azure DevOps configurations even when the
        # repository exists, while the org-wide endpoint reliably returns every repo the PAT can see.
        organization_origin = project_origin.rsplit('/', 1)[0]
        repositories_url = f'{organization_origin}/_apis/git/repositories?api-version=7.1-preview.1'
        try:
            list_response = await self._client.get(repositories_url, headers=headers)
        except httpx.HTTPError as exc:
            raise RepositoryLookupError(
                'Azure DevOps repositories listing failed during branch lookup. Verify provider connectivity.',
                log_message=f'azure-devops repositories listing error: {exc}',
                status_code=502,
            ) from exc

        list_content_type = (list_response.headers.get('content-type') or '').lower()
        if list_response.status_code in (401, 403) or 'text/html' in list_content_type:
            diagnosis = await _diagnose_response(list_response, label='Azure DevOps repositories listing')
            logger.warning(diagnosis)
            raise RepositoryLookupError(
                f'Azure DevOps rejected the request. {diagnosis}',
                log_message=diagnosis,
                status_code=502,
            )

        try:
            list_payload = list_response.json()
        except ValueError:
            body = (list_response.text or '')[:1000]
            logger.warning('Azure DevOps repositories listing returned non-JSON: status=%s body=%s', list_response.status_code, body)
            raise RepositoryLookupError(
                f'Azure DevOps repositories listing returned a non-JSON response (status {list_response.status_code}). '
                f'Body preview: {body[:300]}',
                status_code=502,
            )

        repositories = list_payload.get('value') if isinstance(list_payload, dict) else None
        if not isinstance(repositories, list) or not repositories:
            count = list_payload.get('count') if isinstance(list_payload, dict) else None
            raise RepositoryLookupError(
                f'Azure DevOps returned no repositories at organization scope (status {list_response.status_code}, count={count}). '
                'Most common causes: the PAT was issued in a different organization, the PAT lacks Code: Read scope, '
                'or conditional access policies are blocking the PAT.',
                status_code=502,
            )

        # Filter by project + repository name (case-insensitive on both sides).
        normalized_project = project.strip().lower()
        normalized_repository = repository_name.strip().lower()

        def _project_name_for(repo: dict) -> str:
            project_obj = repo.get('project')
            if isinstance(project_obj, dict):
                return str(project_obj.get('name') or '').strip().lower()
            return ''

        repository_match = next(
            (
                repo
                for repo in repositories
                if isinstance(repo, dict)
                and str(repo.get('name') or '').strip().lower() == normalized_repository
                and _project_name_for(repo) == normalized_project
            ),
            None,
        )

        # If no exact project+name match, try matching just the repo name across all projects.
        if repository_match is None:
            repository_match = next(
                (
                    repo
                    for repo in repositories
                    if isinstance(repo, dict)
                    and str(repo.get('name') or '').strip().lower() == normalized_repository
                ),
                None,
            )

        if repository_match is None:
            available = ', '.join(sorted({
                f"{(_project_name_for(repo) or '?')}/{repo.get('name') or '?'}"
                for repo in repositories
                if isinstance(repo, dict)
            }))
            raise RepositoryLookupError(
                f'Azure DevOps repository {repository_name!r} was not found in organization scope. '
                f'Available repositories (project/name): {available or "none"}.',
                status_code=404,
            )

        repository_id = str(repository_match.get('id') or '').strip()
        if not repository_id:
            raise RepositoryLookupError(
                f'Azure DevOps did not return an ID for repository {repository_name!r}.',
                status_code=502,
            )
        return repository_id

    async def _list_azure_devops_branches(self, repository_url: str) -> list[str]:
        base_url, pat_token = self._resolve_platform_settings('azure-devops', repository_url)
        parsed_url = self._parse_url(base_url)

        segments = [segment for segment in parsed_url.path.split('/') if segment]
        host = (parsed_url.host or '').lower()

        if host == 'dev.azure.com':
            if len(segments) < 4 or segments[2] != '_git':
                raise RepositoryLookupError(
                    'Use an Azure DevOps repository URL such as https://dev.azure.com/org/project/_git/repository.'
                )
            organization, project, _, repository_name = segments[:4]
            organization_origin = f'{parsed_url.scheme}://{parsed_url.host}/{organization}'
            project_origin = f'{organization_origin}/{project}'
        elif host.endswith('.visualstudio.com'):
            if len(segments) < 3 or segments[1] != '_git':
                raise RepositoryLookupError(
                    'Use an Azure DevOps repository URL such as https://org.visualstudio.com/project/_git/repository.'
                )
            project, _, repository_name = segments[:3]
            organization_origin = f'{parsed_url.scheme}://{parsed_url.host}'
            project_origin = f'{organization_origin}/{project}'
        else:
            raise RepositoryLookupError('Azure DevOps branch lookup requires a dev.azure.com or visualstudio.com repository URL.')

        repository_name = _trim_git_suffix(repository_name)
        headers = {
            'Accept': 'application/json',
            'Authorization': self._build_azure_basic_auth(pat_token),
            'X-TFS-FedAuthRedirect': 'Suppress',
        }

        repository_id = await self._resolve_azure_devops_repository_id(
            project_origin=project_origin,
            project=project,
            repository_name=repository_name,
            headers=headers,
        )

        # Step 2: Fetch refs using the repository GUID. Try a couple of common URL variants for
        # backward compatibility with older Azure DevOps Server installations.
        repository_segment = quote(repository_id, safe='')
        candidate_urls = [
            f'{project_origin}/_apis/git/repositories/{repository_segment}/refs?filter=heads/&api-version=7.1-preview.1',
            f'{organization_origin}/_apis/git/repositories/{repository_segment}/refs?filter=heads/&api-version=7.1-preview.1',
            f'{project_origin}/_apis/git/repositories/{repository_segment}/refs?filter=heads&api-version=7.1-preview.1',
            f'{project_origin}/_apis/git/repositories/{repository_segment}/refs?filter=heads/&api-version=6.0',
        ]

        last_status: int | None = None
        last_error_summary: str | None = None
        for candidate_url in candidate_urls:
            try:
                response = await self._client.get(candidate_url, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_status = exc.response.status_code
                response_body = (exc.response.text or '')[:2000]
                last_error_summary = self._summarize_azure_devops_error_body(response_body)
                logger.warning(
                    'Azure DevOps branch lookup failed: status=%s url=%s body=%s',
                    last_status,
                    candidate_url,
                    response_body,
                )
                if last_status in (401, 403):
                    raise RepositoryLookupError(
                        f'Azure DevOps rejected the branch lookup ({last_status}): {last_error_summary or "verify the PAT has Code: Read scope on this repository."}',
                        log_message=f'azure-devops branch status={last_status} body={response_body[:500]}',
                        status_code=502,
                    ) from exc
                continue
            except httpx.HTTPError as exc:
                last_error_summary = str(exc)
                logger.warning('Azure DevOps branch lookup transport error: %s', exc)
                continue

            try:
                payload = response.json()
            except ValueError:
                last_error_summary = 'response was not JSON'
                continue

            if not isinstance(payload, dict):
                last_error_summary = 'unexpected response shape'
                continue

            branches = [
                str(item.get('name') or '').removeprefix('refs/heads/')
                for item in (payload.get('value') or [])
                if isinstance(item, dict)
            ]
            return _sort_branch_names(branches)

        raise RepositoryLookupError(
            f'Azure DevOps branch lookup failed for repository {repository_name!r}'
            f'{f" ({last_status})" if last_status else ""}: {last_error_summary or "verify the PAT has Code: Read scope."}',
            log_message=f'azure-devops branch lookup exhausted candidates repo_id={repository_id} last_status={last_status}',
            status_code=502,
        )

    async def _list_harness_repositories(self, repository_url: str | None = None) -> list[RepositoryOption]:
        context = self._resolve_harness_context(repository_url)
        payload = await self._fetch_harness_collection('/gateway/code/api/v1/repos', context)
        repositories = [
            RepositoryOption(
                id=str(item.get('identifier') or item.get('uid') or item.get('id') or ''),
                label=str(item.get('identifier') or item.get('path') or item.get('uid') or 'Repository'),
                url=str(item.get('git_url') or item.get('path') or item.get('identifier') or ''),
            )
            for item in payload if isinstance(item, dict)
        ]
        return _sort_repository_options(repositories)

    async def _list_harness_branches(self, repository_url: str) -> list[str]:
        context = self._resolve_harness_context(repository_url)
        repository_identifier = self._extract_harness_repository_identifier(repository_url)
        payload = await self._fetch_harness_collection(
            f'/gateway/code/api/v1/repos/{quote(repository_identifier, safe="")}/branches',
            context,
        )
        branches = [str(item.get('name') or '') for item in payload if isinstance(item, dict)]
        return _sort_branch_names(branches)

    async def _fetch_harness_collection(
        self,
        path: str,
        context: HarnessProjectContext,
        *,
        page_size: int = 100,
    ) -> list[object]:
        headers = self._build_harness_headers(context.api_key)
        items: list[object] = []
        page = 1

        while True:
            payload = await self._fetch_json(
                f'{context.api_base_url}{path}?{self._build_harness_query(context, page=page, limit=page_size)}',
                headers,
                'harness',
            )
            batch = payload if isinstance(payload, list) else []
            items.extend(batch)
            if len(batch) < page_size:
                return items
            page += 1

    def _resolve_harness_api_key(self) -> str:
        secret_name = settings.harness_secret_name.strip()
        if secret_name:
            try:
                secret_value = resolve_optional_secret(secret_name)
            except SecretManagerError as exc:
                logger.error('Failed to resolve Harness secret %r: %s', secret_name, exc)
                raise RepositoryLookupError(
                    'Harness secret configuration is unavailable. Verify that the configured secret exists in Google Secret Manager.',
                    log_message=f'Failed to resolve Harness secret {secret_name!r}',
                    status_code=503,
                ) from exc

            if secret_value:
                return secret_value

        if settings.harness_pat_token.strip():
            return settings.harness_pat_token.strip()

        raise RepositoryLookupError('HARNESS_SECRET_NAME or HARNESS_PAT_TOKEN is not configured.', status_code=503)

    def _build_harness_headers(self, api_key: str) -> dict[str, str]:
        return {
            'Accept': 'application/json',
            'x-api-key': api_key,
        }

    def _build_harness_query(
        self,
        context: HarnessProjectContext,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> str:
        params: dict[str, str | int] = {
            'accountIdentifier': context.account_identifier,
            'orgIdentifier': context.org_identifier,
            'projectIdentifier': context.project_identifier,
        }
        if page is not None:
            params['page'] = page
        if limit is not None:
            params['limit'] = limit
        return _build_query_string(params)

    def _resolve_harness_context(self, repository_url: str | None = None) -> HarnessProjectContext:
        _, api_key = self._resolve_platform_settings('harness', repository_url)

        configured_context = self._resolve_configured_harness_context(api_key)
        if configured_context is not None:
            return configured_context

        base_url, _ = self._resolve_platform_settings('harness', repository_url)
        parsed_url = self._parse_url(base_url)
        segments = [segment for segment in parsed_url.path.split('/') if segment]

        if parsed_url.host == 'git.harness.io':
            if len(segments) < 3:
                raise RepositoryLookupError(
                    'Use a Harness Code project URL or Harness git URL such as https://git.harness.io/<account>/<org>/<project>/<repository>.git.'
                )
            account_identifier, org_identifier, project_identifier = segments[:3]
            api_base_url = self._resolve_harness_api_base_url()
        else:
            try:
                account_identifier = segments[segments.index('account') + 1]
                org_identifier = segments[segments.index('orgs') + 1]
                project_identifier = segments[segments.index('projects') + 1]
            except (ValueError, IndexError) as exc:
                raise RepositoryLookupError(
                    'Use a Harness Code project URL such as https://app.harness.io/ng/account/<account>/module/code/orgs/<org>/projects/<project>.'
                ) from exc
            api_base_url = _build_url_origin(parsed_url)

        return HarnessProjectContext(
            api_base_url=api_base_url,
            account_identifier=account_identifier,
            org_identifier=org_identifier,
            project_identifier=project_identifier,
            api_key=api_key,
        )

    def _resolve_configured_harness_context(self, api_key: str) -> HarnessProjectContext | None:
        base_url = settings.harness_base_url_normalized
        account_identifier = settings.harness_account_identifier.strip()
        org_identifier = settings.harness_org_identifier.strip()
        project_identifier = settings.harness_project_identifier.strip()

        if not base_url or not account_identifier or not org_identifier or not project_identifier:
            return None

        parsed_url = self._validate_repository_url('harness', base_url)
        return HarnessProjectContext(
            api_base_url=_build_url_origin(parsed_url),
            account_identifier=account_identifier,
            org_identifier=org_identifier,
            project_identifier=project_identifier,
            api_key=api_key,
        )

    def _resolve_harness_api_base_url(self) -> str:
        configured_url = settings.harness_base_url_normalized or settings.harness_repository_url.strip()
        if configured_url:
            try:
                parsed_url = self._validate_repository_url('harness', configured_url)
            except RepositoryLookupError:
                return 'https://app.harness.io'

            if parsed_url.host != 'git.harness.io':
                return _build_url_origin(parsed_url)

        return 'https://app.harness.io'

    def _extract_harness_repository_identifier(self, repository_url: str) -> str:
        normalized_repository_url = repository_url.strip()
        if not normalized_repository_url:
            raise RepositoryLookupError('Harness branch lookup requires a repository selection.')

        try:
            parsed_url = self._parse_url(normalized_repository_url)
        except RepositoryLookupError:
            if '/' not in normalized_repository_url and ' ' not in normalized_repository_url:
                return _trim_git_suffix(normalized_repository_url)
            raise

        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if parsed_url.host == 'git.harness.io':
            if len(segments) < 4:
                raise RepositoryLookupError('Harness branch lookup requires a repository git URL or identifier. Select a repository from the loaded list first.')
            return _trim_git_suffix(segments[-1])

        if 'projects' in segments:
            project_index = segments.index('projects')
            if len(segments) <= project_index + 2:
                raise RepositoryLookupError('Harness branch lookup requires a repository selection. Select a repository from the loaded list first.')

        candidate = _trim_git_suffix(segments[-1]) if segments else ''
        if candidate:
            return candidate

        raise RepositoryLookupError('Harness branch lookup requires a repository identifier.')

    def _validate_repository_url(self, platform: str, repository_url: str) -> httpx.URL:
        parsed_url = self._parse_url(repository_url)
        provider_name = self._provider_display_name(platform)
        host = (parsed_url.host or '').lower()
        scheme = (parsed_url.scheme or '').lower()

        if scheme != 'https':
            raise RepositoryLookupError(f'{provider_name} repository URL must use https.')

        if not host:
            raise RepositoryLookupError(f'{provider_name} repository URL host is missing.')

        if not any(_host_matches_pattern(host, pattern) for pattern in self._allowed_hosts_for_platform(platform)):
            raise RepositoryLookupError(
                f'{provider_name} repository URL host is not allowed.',
                log_message=f'{provider_name} host {host!r} is not in the configured allowlist',
            )

        return parsed_url

    def _allowed_hosts_for_platform(self, platform: str) -> list[str]:
        if platform == 'github-actions':
            return settings.github_allowed_hosts_list
        if platform == 'gitlab-ci':
            return settings.gitlab_allowed_hosts_list
        if platform == 'azure-devops':
            return settings.azure_devops_allowed_hosts_list
        if platform == 'harness':
            return settings.harness_allowed_hosts_list
        return []

    def _provider_display_name(self, platform: str) -> str:
        if platform == 'github-actions':
            return 'GitHub'
        if platform == 'gitlab-ci':
            return 'GitLab'
        if platform == 'azure-devops':
            return 'Azure DevOps'
        if platform == 'harness':
            return 'Harness'
        return platform

    def _build_azure_basic_auth(self, pat_token: str) -> str:
        encoded = base64.b64encode(f':{pat_token}'.encode('utf-8')).decode('utf-8')
        return f'Basic {encoded}'

    def _build_azure_project_api(self, parsed_url: httpx.URL) -> tuple[str, str | None]:
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if parsed_url.host == 'dev.azure.com':
            if len(segments) < 2:
                raise RepositoryLookupError('Use an Azure DevOps project or repository URL such as https://dev.azure.com/org/project or https://dev.azure.com/org/project/_git/repository.')
            organization, project = segments[0], segments[1]
            repository_name = _trim_git_suffix(segments[3]) if len(segments) > 3 and segments[2] == '_git' else None
            return (
                f'{parsed_url.scheme}://{parsed_url.host}/{organization}/{project}/_apis/git/repositories?api-version=7.1-preview.1',
                repository_name,
            )

        if parsed_url.host.endswith('.visualstudio.com'):
            if not segments:
                raise RepositoryLookupError('Use an Azure DevOps project or repository URL such as https://org.visualstudio.com/project or https://org.visualstudio.com/project/_git/repository.')
            project = segments[0]
            repository_name = _trim_git_suffix(segments[2]) if len(segments) > 2 and segments[1] == '_git' else None
            return (
                f'{parsed_url.scheme}://{parsed_url.host}/{project}/_apis/git/repositories?api-version=7.1-preview.1',
                repository_name,
            )

        raise RepositoryLookupError('Azure DevOps repository lookup requires a dev.azure.com or visualstudio.com URL.')

    def _build_azure_repository_api(self, parsed_url: httpx.URL) -> str:
        segments = [segment for segment in parsed_url.path.split('/') if segment]
        if parsed_url.host == 'dev.azure.com':
            if len(segments) < 4 or segments[2] != '_git':
                raise RepositoryLookupError('Use an Azure DevOps repository URL such as https://dev.azure.com/org/project/_git/repository.')
            organization, project, _, repository = segments[:4]
            return f'{parsed_url.scheme}://{parsed_url.host}/{organization}/{project}/_apis/git/repositories/{_trim_git_suffix(repository)}/refs?filter=heads/&api-version=7.1-preview.1'

        if parsed_url.host.endswith('.visualstudio.com'):
            if len(segments) < 3 or segments[1] != '_git':
                raise RepositoryLookupError('Use an Azure DevOps repository URL such as https://org.visualstudio.com/project/_git/repository.')
            project, _, repository = segments[:3]
            return f'{parsed_url.scheme}://{parsed_url.host}/{project}/_apis/git/repositories/{_trim_git_suffix(repository)}/refs?filter=heads/&api-version=7.1-preview.1'

        raise RepositoryLookupError('Azure DevOps branch lookup requires a dev.azure.com or visualstudio.com repository URL.')


_repository_lookup_client: RepositoryLookupClient | None = None


def get_repository_lookup_client() -> RepositoryLookupClient:
    global _repository_lookup_client
    if _repository_lookup_client is None:
        _repository_lookup_client = RepositoryLookupClient()
    return _repository_lookup_client