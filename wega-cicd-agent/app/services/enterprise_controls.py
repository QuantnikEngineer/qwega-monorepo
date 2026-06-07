from __future__ import annotations

import re

from app.models.requests import GeneratePipelineRequest


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "wega-pipeline"


def resolve_image_repository(request: GeneratePipelineRequest) -> str:
    configured = request.build.image.repository
    if configured:
        return configured.strip()
    return f"registry.example.com/{slugify(request.pipeline_name)}"


def resolve_image_tags(request: GeneratePipelineRequest) -> list[str]:
    configured_tags = list(request.build.image.tags)
    default_tag = request.target.environment
    tags = [tag for tag in configured_tags if tag]

    if default_tag not in tags:
        tags.insert(0, default_tag)

    if request.target.environment == "prod" and "latest" not in tags:
        tags.append("latest")

    return tags or [default_tag]


def resolve_primary_image_tag(request: GeneratePipelineRequest) -> str:
    return resolve_image_tags(request)[0]


def rollout_enabled(request: GeneratePipelineRequest) -> bool:
    return request.target.deployment_target != "none" and (bool(request.target.regions) or request.execution.approvals.enabled)


def build_region_rollout_command(request: GeneratePipelineRequest, region: str) -> str:
    deployment_target = request.target.deployment_target
    environment = request.target.environment
    region_label = region if region != "primary" else f"primary {environment} target"

    if request.build.artifact_type == "container":
        deployable = f"{resolve_image_repository(request)}:{resolve_primary_image_tag(request)}"
    elif request.build.artifact_type == "package":
        deployable = f"package bundle for {request.pipeline_name}"
    elif request.build.artifact_type == "binary":
        deployable = f"release binary for {request.pipeline_name}"
    else:
        deployable = f"validated build output for {request.pipeline_name}"

    if deployment_target == "kubernetes":
        return f'echo "Deploy {deployable} to the {region_label} Kubernetes cluster for {environment}"'
    if deployment_target == "container-apps":
        return f'echo "Promote {deployable} to the {region_label} Container Apps environment for {environment}"'
    if deployment_target == "serverless":
        return f'echo "Deploy {deployable} to the {region_label} serverless target for {environment}"'
    if deployment_target == "vm":
        return f'echo "Roll out {deployable} to the {region_label} VM ring for {environment}"'
    return f'echo "Regional rollout requested for {deployable} in {region_label}"'