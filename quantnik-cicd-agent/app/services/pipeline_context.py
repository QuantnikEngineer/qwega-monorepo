from app.models.requests import GeneratePipelineRequest
from app.services.catalog_registry import get_platform_map, get_stage_map, get_tool_map
from app.services.command_resolver import resolve_stage_commands
from app.services.enterprise_controls import (
    build_region_rollout_command,
    resolve_image_repository,
    resolve_image_tags,
    resolve_primary_image_tag,
    rollout_enabled,
    slugify,
)


def build_stage_contexts(request: GeneratePipelineRequest) -> list[dict]:
    stage_map = get_stage_map()
    selected_tool_ids = [tool.id for tool in request.tools]
    stage_contexts = []

    for stage in sorted(request.stages, key=lambda item: item.order):
        metadata = stage_map[stage.stage_id]
        stage_contexts.append(
            {
                'id': stage.stage_id,
                'name': metadata['name'],
                'commands': resolve_stage_commands(stage.stage_id, request, selected_tool_ids),
            }
        )

    return stage_contexts


def build_render_context(request: GeneratePipelineRequest) -> dict:
    platform_map = get_platform_map()
    tool_map = get_tool_map()
    normalized_intent = request.model_dump(by_alias=True, mode='json')
    stage_contexts = build_stage_contexts(request)
    image_tags = resolve_image_tags(request)
    rollout_region_names = request.target.regions or (["primary"] if request.execution.approvals.enabled and request.target.deployment_target != 'none' else [])
    rollout_regions = [
        {
            'name': region,
            'identifier': slugify(region),
            'environment_name': f"{request.target.environment}-{slugify(region)}",
            'command': build_region_rollout_command(request, region),
        }
        for region in rollout_region_names
    ]

    harness_target = request.target.harness
    harness_context = {
        'account_identifier': (harness_target.account_identifier or '').strip(),
        'org_identifier': (harness_target.org_identifier or 'default').strip() or 'default',
        'project_identifier': (harness_target.project_identifier or 'default').strip() or 'default',
        'connector_ref': (harness_target.connector_ref or 'account.harnessImage').strip() or 'account.harnessImage',
        'code_connector_ref': (harness_target.code_connector_ref or harness_target.connector_ref or 'account.harnessImage').strip() or 'account.harnessImage',
        'namespace': (harness_target.namespace or 'harness-build').strip() or 'harness-build',
        'runtime': harness_target.runtime or 'cloud',
        'repo_name': (harness_target.repo_name or request.repository.url or request.pipeline_name or '').strip(),
    }

    # Azure Container Apps configuration
    azure_devops_target = request.target.azure_devops
    container_apps_config = azure_devops_target.container_apps if azure_devops_target else None
    azure_container_apps_context = None
    if container_apps_config and request.target.deployment_target == 'container-apps':
        azure_container_apps_context = {
            'enabled': True,
            'service_connection': container_apps_config.service_connection or 'azureconnector',
            'resource_group': container_apps_config.resource_group or '',
            'location': container_apps_config.location or 'eastus',
            'container_app_name': container_apps_config.container_app_name or slugify(request.pipeline_name),
            'container_app_env_prefix': container_apps_config.container_app_env_prefix or 'quantnik-aca',
            'acr_name': container_apps_config.acr_name or '',
            'acr_login_server': container_apps_config.acr_login_server or (f"{container_apps_config.acr_name}.azurecr.io" if container_apps_config.acr_name else ''),
            'deployment_environments': container_apps_config.deployment_environments or ['dev'],
            'trigger_branches': container_apps_config.trigger_branches or ['main'],
            'pr_branches': container_apps_config.pr_branches or ['main'],
            'image_repository': slugify(request.pipeline_name),
        }

    return {
        'request': normalized_intent,
        'pipeline_name': request.pipeline_name,
        'branch': request.repository.branch,
        'repository_url': request.repository.url or 'repository-not-provided',
        'platform': platform_map[request.target.platform],
        'stages': stage_contexts,
        'tool_names': [tool_map.get(tool.id, {'name': tool.name})['name'] for tool in request.tools],
        'triggers': {
            'push': request.execution.triggers.push,
            'pull_request': request.execution.triggers.pull_request,
        },
        'image': {
            'enabled': request.build.artifact_type == 'container',
            'repository': resolve_image_repository(request),
            'tags': image_tags,
            'primary_tag': resolve_primary_image_tag(request),
        },
        'rollout': {
            'enabled': rollout_enabled(request),
            'deployment_target': request.target.deployment_target,
            'environment': request.target.environment,
            'regions': rollout_regions,
        },
        'approvals': {
            'enabled': request.execution.approvals.enabled,
            'approvers': request.execution.approvals.approvers,
            'timeout_minutes': request.execution.approvals.timeout_minutes,
        },
        'harness': harness_context,
        'azure_container_apps': azure_container_apps_context,
        'python_build': _build_python_context(request),
        'normalized_intent': normalized_intent,
    }


def _build_python_context(request) -> dict:
    python_build = getattr(request.build, 'python', None)
    if request.build.language != 'python' or python_build is None:
        return {}
    return {
        'version': python_build.version,
        'package_manager': python_build.package_manager,
        'test_command': python_build.test_command,
        'lint_tool': python_build.lint_tool,
        'coverage_gate': python_build.coverage_gate or 0,
    }