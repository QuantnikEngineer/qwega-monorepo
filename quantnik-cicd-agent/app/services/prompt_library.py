from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.models.requests import GeneratePipelineRequest


class PipelinePromptLibrary:
    def __init__(self, environment: Environment | None = None) -> None:
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        self._environment = environment or Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, request: GeneratePipelineRequest, context: dict[str, Any]) -> str:
        template = self._environment.get_template(f"{request.target.platform}.prompt.txt.j2")
        return template.render(**self._build_template_context(request, context))

    def _build_template_context(self, request: GeneratePipelineRequest, context: dict[str, Any]) -> dict[str, Any]:
        requested_regions = list(request.target.regions)
        resolved_rollout_regions = [region["name"] for region in context["rollout"]["regions"]]
        stage_identifiers = [stage["id"] for stage in context["stages"]]
        enterprise_controls = {
            "image": context["image"],
            "rollout": context["rollout"],
            "approvals": context["approvals"],
        }

        harness = context.get("harness") or {}
        python_build = context.get("python_build") or {}
        azure_container_apps = context.get("azure_container_apps") or {}

        return {
            "user_prompt": request.prompt or "prompt-not-provided",
            "target_platform": request.target.platform,
            "expected_output_path": context["platform"]["artifactPath"],
            "pipeline_name": request.pipeline_name,
            "repository_url": request.repository.url or "repository-not-provided",
            "branch": request.repository.branch,
            "push_trigger_enabled": context["triggers"]["push"],
            "pull_request_trigger_enabled": context["triggers"]["pull_request"],
            "deployment_target": request.target.deployment_target,
            "target_environment": request.target.environment,
            "selected_regions": ", ".join(requested_regions) or "none",
            "selected_regions_json": json.dumps(requested_regions, indent=2),
            "rollout_enabled": context["rollout"]["enabled"],
            "resolved_rollout_regions": ", ".join(resolved_rollout_regions) or "none",
            "resolved_rollout_regions_json": json.dumps(resolved_rollout_regions, indent=2),
            "selected_tools": ", ".join(context["tool_names"]) or "none",
            "tool_count": len(context["tool_names"]),
            "stage_count": len(context["stages"]),
            "stage_identifiers": ", ".join(stage_identifiers) or "none",
            "stage_identifiers_json": json.dumps(stage_identifiers, indent=2),
            "image_enabled": context["image"]["enabled"],
            "image_repository": context["image"]["repository"],
            "image_tags": ", ".join(context["image"]["tags"]) if context["image"]["enabled"] else "none",
            "image_tags_json": json.dumps(context["image"]["tags"], indent=2),
            "approvals_enabled": context["approvals"]["enabled"],
            "approval_approvers": ", ".join(context["approvals"]["approvers"]) or "none",
            "approval_timeout_minutes": context["approvals"]["timeout_minutes"],
            "approval_config_json": json.dumps(context["approvals"], indent=2),
            "enterprise_controls_json": json.dumps(enterprise_controls, indent=2),
            "stage_context_json": json.dumps(context["stages"], indent=2),
            "normalized_intent_json": json.dumps(context["normalized_intent"], indent=2),
            "connector_ref": harness.get("connector_ref", "account.harnessImage"),
            "code_connector_ref": harness.get("code_connector_ref", "account.harnessImage"),
            "harness_account_identifier": harness.get("account_identifier", ""),
            "harness_org_identifier": harness.get("org_identifier", "default"),
            "harness_project_identifier": harness.get("project_identifier", "default"),
            "harness_namespace": harness.get("namespace", "harness-build"),
            "harness_runtime": harness.get("runtime", "cloud"),
            "harness_repo_name": harness.get("repo_name", request.repository.url or request.pipeline_name),
            "python_version": python_build.get("version", "3.11"),
            "python_package_manager": python_build.get("package_manager", "pip"),
            "python_test_command": python_build.get("test_command", "pytest"),
            "python_lint_tool": python_build.get("lint_tool", "ruff"),
            "python_coverage_gate": python_build.get("coverage_gate", 0),
            "python_build_json": json.dumps(python_build, indent=2),
            "azure_container_apps": azure_container_apps,
            "azure_container_apps_json": json.dumps(azure_container_apps, indent=2),
        }