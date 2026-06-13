from app.core.policies import load_policy
from app.models.requests import GeneratePipelineRequest
from app.services.enterprise_controls import resolve_image_repository, resolve_image_tags


def resolve_stage_commands(stage_id: str, request: GeneratePipelineRequest, selected_tool_ids: list[str]) -> list[str]:
    commands_policy = load_policy('commands.json')
    lifecycle_commands = commands_policy['languageCommands'][request.build.language][request.build.tool]

    if stage_id == 'checkout':
        return ['echo "Checkout handled by the platform source connector"']
    if stage_id in {'restore', 'build', 'lint'}:
        return lifecycle_commands[stage_id]
    if stage_id == 'unit-test':
        commands = list(lifecycle_commands['unit-test'])
        if request.quality.coverage.enabled:
            commands.append(f"echo \"Enforce minimum coverage {request.quality.coverage.minimum}%\"")
        return commands
    if stage_id == 'static-analysis':
        return _tool_commands(selected_tool_ids, {'sonarqube', 'semgrep'})
    if stage_id == 'secret-scan':
        return _tool_commands(selected_tool_ids, {'gitleaks'})
    if stage_id == 'dependency-scan':
        return _tool_commands(selected_tool_ids, {'snyk'})
    if stage_id == 'iac-validate':
        return _tool_commands(selected_tool_ids, {'terraform'})
    if stage_id == 'helm-package':
        return _tool_commands(selected_tool_ids, {'helm'})
    if stage_id == 'docker-build':
        image_repository = resolve_image_repository(request)
        image_tags = resolve_image_tags(request)
        tag_flags = ' '.join(f"-t {image_repository}:{tag}" for tag in image_tags)
        return [f"docker build {tag_flags} ."]
    if stage_id == 'publish-artifacts':
        return _artifact_publish_commands(request)
    if stage_id == 'notifications':
        return _tool_commands(selected_tool_ids, {'notifications'})
    return ['echo "No commands defined for stage"']


def _tool_commands(selected_tool_ids: list[str], supported_tool_ids: set[str]) -> list[str]:
    commands_policy = load_policy('commands.json')
    commands = []
    for tool_id in selected_tool_ids:
        if tool_id not in supported_tool_ids:
            continue
        commands.extend(commands_policy['toolCommands'].get(tool_id, []))
    return commands or ['echo "No commands defined for stage"']


def _artifact_publish_commands(request: GeneratePipelineRequest) -> list[str]:
    if request.build.artifact_type == 'container':
        image_repository = resolve_image_repository(request)
        return [f"docker push {image_repository}:{tag}" for tag in resolve_image_tags(request)]
    if request.build.artifact_type == 'package':
        return ['echo "Publish package to registry"']
    if request.build.artifact_type == 'binary':
        return ['echo "Upload binary artifact to storage"']
    return ['echo "No artifact publishing required"']