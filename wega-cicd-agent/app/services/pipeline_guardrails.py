from __future__ import annotations

import re
from typing import Any

from app.core.policies import load_policy
from app.models.requests import GeneratePipelineRequest
from app.services.catalog_registry import get_language_map, get_platform_map, get_stage_map, get_tool_map


_HARNESS_IDENTIFIER_RE = re.compile(r'[^A-Za-z0-9_]')


class PipelineValidationError(ValueError):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__('; '.join(violations))


def validate_request_guardrails(request: GeneratePipelineRequest) -> None:
    guardrails = load_policy('guardrails.json')
    platform_map = get_platform_map()
    language_map = get_language_map()
    stage_map = get_stage_map()
    tool_map = get_tool_map()
    violations = []

    language = language_map[request.build.language]
    selected_stage_ids = [stage.stage_id for stage in request.stages]
    selected_stage_set = set(selected_stage_ids)
    selected_tool_ids = [tool.id for tool in request.tools]
    skip_platform_support_validation = request.target.platform == 'jenkins'

    if request.build.tool not in language['tools']:
        violations.append(
            f"build.tool '{request.build.tool}' is not supported for build.language '{request.build.language}'. Supported tools: {', '.join(language['tools'])}."
        )

    if request.build.artifact_type not in language['artifactTypes']:
        violations.append(
            f"build.artifactType '{request.build.artifact_type}' is not supported for build.language '{request.build.language}'. Supported artifact types: {', '.join(language['artifactTypes'])}."
        )

    if len(selected_stage_ids) != len(selected_stage_set):
        violations.append('Stage IDs must be unique.')

    if len(selected_tool_ids) != len(set(selected_tool_ids)):
        violations.append('Tool IDs must be unique.')

    for required_stage in guardrails['requiredStages']:
        if required_stage not in selected_stage_set:
            violations.append(f"Stage '{required_stage}' is required in every pipeline.")

    for stage_id in selected_stage_ids:
        stage_metadata = stage_map.get(stage_id)
        if stage_metadata is None:
            violations.append(f"Stage '{stage_id}' is not recognized.")
            continue
        if not skip_platform_support_validation and request.target.platform not in stage_metadata['platforms']:
            violations.append(f"Stage '{stage_id}' is not supported on platform '{request.target.platform}'.")

    for tool_id in selected_tool_ids:
        tool_metadata = tool_map.get(tool_id)
        if tool_metadata is None:
            violations.append(f"Tool '{tool_id}' is not recognized.")
            continue
        if not skip_platform_support_validation and request.target.platform not in tool_metadata['platforms']:
            violations.append(f"Tool '{tool_id}' is not supported on platform '{request.target.platform}'.")
        if not selected_stage_set.intersection(tool_metadata['stages']):
            violations.append(
                f"Tool '{tool_id}' was selected without any compatible stage. Expected one of: {', '.join(tool_metadata['stages'])}."
            )

    for rule in guardrails['stageRules']:
        if rule['stageId'] not in selected_stage_set:
            continue
        artifact_types = rule.get('artifactTypes')
        if artifact_types and request.build.artifact_type not in artifact_types:
            violations.append(rule['message'])
        deployment_targets = rule.get('deploymentTargets')
        if deployment_targets and request.target.deployment_target not in deployment_targets:
            violations.append(rule['message'])

    for stage_id, required_tools in guardrails['stageToolRequirements'].items():
        if stage_id not in selected_stage_set:
            continue
        if not selected_stage_set:
            continue
        if not set(required_tools).intersection(selected_tool_ids):
            violations.append(
                f"Stage '{stage_id}' requires at least one compatible tool selection: {', '.join(required_tools)}."
            )

    if request.build.artifact_type == 'container' and 'docker-build' not in selected_stage_set:
        violations.append("build.artifactType 'container' requires stage 'docker-build'.")

    if request.build.artifact_type != 'none' and 'publish-artifacts' not in selected_stage_set:
        violations.append(f"build.artifactType '{request.build.artifact_type}' requires stage 'publish-artifacts'.")

    if request.build.artifact_type == 'none' and 'publish-artifacts' in selected_stage_set:
        violations.append("Stage 'publish-artifacts' cannot be selected when build.artifactType is 'none'.")

    if violations:
        raise PipelineValidationError(violations)


def validate_generated_artifact(request: GeneratePipelineRequest, artifact_path: str, content: str) -> str:
    platform_map = get_platform_map()
    expected_path = platform_map[request.target.platform]['artifactPath']
    violations = []

    if artifact_path != expected_path:
        violations.append(
            f"Generated artifact path '{artifact_path}' does not match the expected path '{expected_path}' for platform '{request.target.platform}'."
        )
    if not content.strip():
        violations.append('Generated artifact content is empty.')

    if violations:
        raise PipelineValidationError(violations)

    if request.target.platform == 'harness':
        content = normalize_harness_pipeline_yaml(request, content)

    return content


def _safe_identifier(value: str, fallback: str) -> str:
    candidate = _HARNESS_IDENTIFIER_RE.sub('_', (value or '').strip())
    candidate = candidate.strip('_') or fallback
    if candidate and not candidate[0].isalpha() and candidate[0] != '_':
        candidate = f'_{candidate}'
    return candidate or fallback


def normalize_harness_pipeline_yaml(request: GeneratePipelineRequest, content: str) -> str:
    """Parse and normalize Harness CI YAML so it satisfies Harness Pipelines schema.

    Best-effort fixes:
    - Replaces the legacy `cloneCodeRepo` field with `cloneCodebase`.
    - Ensures `pipeline.tags` is present.
    - Ensures `pipeline.properties.ci.codebase` is populated when any stage clones code.
    - Overrides `pipeline.projectIdentifier`/`orgIdentifier` with the request's Harness context (when supplied).
    - Replaces `<+input>` connector references with the resolved connector ref.
    - Validates and sanitizes identifiers.
    - Ensures CI stages contain runtime/platform OR infrastructure based on selected runtime.
    """

    try:
        import yaml
    except ImportError as exc:
        raise PipelineValidationError([
            'Harness YAML normalization requires PyYAML. Install pyyaml in the Wega CI Agent environment.',
        ]) from exc

    try:
        document = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise PipelineValidationError([f'Generated Harness YAML is not valid YAML: {exc}.'])

    if not isinstance(document, dict) or 'pipeline' not in document or not isinstance(document['pipeline'], dict):
        raise PipelineValidationError(['Generated Harness YAML must define a top-level `pipeline` mapping.'])

    pipeline = document['pipeline']
    harness_target = request.target.harness
    runtime_mode = (harness_target.runtime or 'cloud').strip().lower()
    if runtime_mode not in {'cloud', 'kubernetes-direct'}:
        runtime_mode = 'cloud'

    connector_ref = (harness_target.connector_ref or 'account.harnessImage').strip() or 'account.harnessImage'
    code_connector_ref = (harness_target.code_connector_ref or connector_ref).strip() or connector_ref
    namespace = (harness_target.namespace or 'harness-build').strip() or 'harness-build'
    org_identifier = (harness_target.org_identifier or pipeline.get('orgIdentifier') or 'default').strip() or 'default'
    project_identifier = (harness_target.project_identifier or pipeline.get('projectIdentifier') or 'default').strip() or 'default'
    repo_name = (harness_target.repo_name or request.repository.url or request.pipeline_name or pipeline.get('name') or '').strip()

    # Pipeline name + identifier
    pipeline_name = str(pipeline.get('name') or request.pipeline_name).strip() or request.pipeline_name
    pipeline['name'] = pipeline_name
    pipeline['identifier'] = _safe_identifier(str(pipeline.get('identifier') or pipeline_name), 'wega_pipeline')
    pipeline['projectIdentifier'] = project_identifier
    pipeline['orgIdentifier'] = org_identifier
    if not isinstance(pipeline.get('tags'), dict):
        pipeline['tags'] = {}

    # Required codebase block
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
    if not codebase.get('connectorRef') or codebase.get('connectorRef') == '<+input>':
        codebase['connectorRef'] = code_connector_ref
    if not codebase.get('repoName') or codebase.get('repoName') == '<+input>':
        codebase['repoName'] = repo_name or pipeline_name
    if not codebase.get('build'):
        codebase['build'] = '<+input>'

    # Stages
    stages = pipeline.get('stages')
    if not isinstance(stages, list) or not stages:
        raise PipelineValidationError(['Generated Harness YAML must include at least one stage.'])

    seen_stage_identifiers: set[str] = set()
    for stage_entry in stages:
        if not isinstance(stage_entry, dict) or not isinstance(stage_entry.get('stage'), dict):
            continue
        stage = stage_entry['stage']
        stage_name = str(stage.get('name') or 'Stage')
        stage_identifier = _safe_identifier(str(stage.get('identifier') or stage_name), 'stage')
        # Make stage identifiers unique
        original_identifier = stage_identifier
        suffix = 2
        while stage_identifier in seen_stage_identifiers:
            stage_identifier = f'{original_identifier}_{suffix}'
            suffix += 1
        seen_stage_identifiers.add(stage_identifier)
        stage['identifier'] = stage_identifier

        spec = stage.setdefault('spec', {})
        if not isinstance(spec, dict):
            spec = {}
            stage['spec'] = spec

        stage_type = stage.get('type')
        if stage_type == 'CI':
            # Replace legacy field name
            if 'cloneCodeRepo' in spec and 'cloneCodebase' not in spec:
                spec['cloneCodebase'] = bool(spec.pop('cloneCodeRepo'))
            spec.pop('cloneCodeRepo', None)
            spec.setdefault('cloneCodebase', True)

            if runtime_mode == 'kubernetes-direct':
                spec.pop('platform', None)
                spec.pop('runtime', None)
                infrastructure = spec.setdefault('infrastructure', {})
                if not isinstance(infrastructure, dict):
                    infrastructure = {}
                    spec['infrastructure'] = infrastructure
                infrastructure['type'] = 'KubernetesDirect'
                infra_spec = infrastructure.setdefault('spec', {})
                if not isinstance(infra_spec, dict):
                    infra_spec = {}
                    infrastructure['spec'] = infra_spec
                if not infra_spec.get('connectorRef') or infra_spec.get('connectorRef') == '<+input>':
                    infra_spec['connectorRef'] = connector_ref
                if not infra_spec.get('namespace') or infra_spec.get('namespace') == '<+input>':
                    infra_spec['namespace'] = namespace
                infra_spec.setdefault('os', 'Linux')
                infra_spec.setdefault('automountServiceAccountToken', True)
            else:
                spec.pop('infrastructure', None)
                spec['platform'] = {'os': 'Linux', 'arch': 'Amd64'}
                spec['runtime'] = {'type': 'Cloud', 'spec': {}}

        # Sanitize step identifiers within execution
        execution = spec.get('execution') if isinstance(spec, dict) else None
        if isinstance(execution, dict):
            steps = execution.get('steps')
            if isinstance(steps, list):
                seen_step_ids: set[str] = set()
                for step_entry in steps:
                    if not isinstance(step_entry, dict) or not isinstance(step_entry.get('step'), dict):
                        continue
                    step = step_entry['step']
                    step_name = str(step.get('name') or step.get('type') or 'step')
                    step_identifier = _safe_identifier(str(step.get('identifier') or f'{stage_identifier}_{step_name}'), f'{stage_identifier}_step')
                    original_step_id = step_identifier
                    suffix = 2
                    while step_identifier in seen_step_ids:
                        step_identifier = f'{original_step_id}_{suffix}'
                        suffix += 1
                    seen_step_ids.add(step_identifier)
                    step['identifier'] = step_identifier

    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False, width=4096)