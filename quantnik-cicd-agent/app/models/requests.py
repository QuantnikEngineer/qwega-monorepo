from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


PlatformType = Literal["azure-devops", "github-actions", "gitlab-ci", "harness", "jenkins"]
LanguageType = Literal["node", "python", "java", "dotnet", "go"]
ArtifactType = Literal["none", "binary", "container", "package"]
DeploymentTargetType = Literal["none", "kubernetes", "vm", "serverless", "container-apps"]
EnvironmentType = Literal["dev", "qa", "prod"]
AssistantModeType = Literal["assistive-prefill", "manual-only"]
RenderModeType = Literal["template", "llm", "hybrid"]
HarnessRuntimeType = Literal["cloud", "kubernetes-direct"]


def _default_if_blank(value: str | None, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return value


def _none_if_blank(value: str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _normalize_string_list(value: str | list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    if value is None:
        return []

    raw_items = [value] if isinstance(value, str) else list(value)
    normalized: list[str] = []

    for item in raw_items:
        if item is None:
            continue

        text = item if isinstance(item, str) else str(item)
        for part in text.replace("\n", ",").split(","):
            candidate = part.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)

    return normalized


class ImageConfig(BaseModel):
    repository: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)

    @field_validator("repository", mode="before")
    @classmethod
    def default_repository(cls, value: str | None) -> str | None:
        return _none_if_blank(value)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: str | list[str] | None) -> list[str]:
        return _normalize_string_list(value)


class ApprovalConfig(BaseModel):
    enabled: bool = False
    approvers: list[str] = Field(default_factory=list)
    timeout_minutes: int = Field(default=120, ge=15, le=1440, alias="timeoutMinutes")

    model_config = {"populate_by_name": True}

    @field_validator("approvers", mode="before")
    @classmethod
    def normalize_approvers(cls, value: str | list[str] | None) -> list[str]:
        return _normalize_string_list(value)

    @model_validator(mode="after")
    def validate_enabled_approvers(self) -> "ApprovalConfig":
        if self.enabled and not self.approvers:
            raise ValueError("execution.approvals.approvers must contain at least one approver when approvals are enabled.")
        return self


class HarnessTargetConfig(BaseModel):
    """Harness-specific overrides used when the target platform is harness."""

    account_identifier: str | None = Field(default=None, alias="accountIdentifier", max_length=200)
    org_identifier: str | None = Field(default=None, alias="orgIdentifier", max_length=200)
    project_identifier: str | None = Field(default=None, alias="projectIdentifier", max_length=200)
    connector_ref: str | None = Field(default=None, alias="connectorRef", max_length=200)
    code_connector_ref: str | None = Field(default=None, alias="codeConnectorRef", max_length=200)
    namespace: str | None = Field(default=None, max_length=200)
    runtime: HarnessRuntimeType = Field(default="cloud")
    repo_name: str | None = Field(default=None, alias="repoName", max_length=200)

    model_config = {"populate_by_name": True}

    @field_validator("account_identifier", "org_identifier", "project_identifier", "connector_ref", "code_connector_ref", "namespace", "repo_name", mode="before")
    @classmethod
    def trim_optional_strings(cls, value):
        return _none_if_blank(value) if isinstance(value, str) or value is None else value


class AzureContainerAppsConfig(BaseModel):
    """Azure Container Apps deployment configuration for Azure DevOps pipelines."""

    service_connection: str = Field(default="azureconnector", alias="serviceConnection", max_length=200)
    resource_group: str | None = Field(default=None, alias="resourceGroup", max_length=200)
    location: str = Field(default="eastus", max_length=50)
    container_app_name: str | None = Field(default=None, alias="containerAppName", max_length=200)
    container_app_env_prefix: str = Field(default="quantnik-aca", alias="containerAppEnvPrefix", max_length=100)
    acr_name: str | None = Field(default=None, alias="acrName", max_length=200)
    acr_login_server: str | None = Field(default=None, alias="acrLoginServer", max_length=200)
    deployment_environments: list[EnvironmentType] = Field(default_factory=list, alias="deploymentEnvironments")
    trigger_branches: list[str] = Field(default_factory=lambda: ["main"], alias="triggerBranches")
    pr_branches: list[str] = Field(default_factory=lambda: ["main"], alias="prBranches")

    model_config = {"populate_by_name": True}

    @field_validator("resource_group", "container_app_name", "acr_name", "acr_login_server", mode="before")
    @classmethod
    def trim_optional_strings(cls, value):
        return _none_if_blank(value) if isinstance(value, str) or value is None else value

    @field_validator("trigger_branches", "pr_branches", mode="before")
    @classmethod
    def normalize_branches(cls, value: str | list[str] | None) -> list[str]:
        return _normalize_string_list(value) or ["main"]


class AzureDevOpsTargetConfig(BaseModel):
    """Azure DevOps-specific configuration when platform is azure-devops."""

    repository_url: str | None = Field(default=None, alias="repositoryUrl", max_length=500)
    branch: str | None = Field(default=None, max_length=200)
    container_apps: AzureContainerAppsConfig | None = Field(default=None, alias="containerApps")

    model_config = {"populate_by_name": True}

    @field_validator("repository_url", "branch", mode="before")
    @classmethod
    def trim_optional_strings(cls, value):
        return _none_if_blank(value) if isinstance(value, str) or value is None else value


class TargetConfig(BaseModel):
    platform: PlatformType
    deployment_target: DeploymentTargetType = Field(default="none", alias="deploymentTarget")
    environment: EnvironmentType = Field(default="dev")
    regions: list[str] = Field(default_factory=list)
    harness: HarnessTargetConfig = Field(default_factory=HarnessTargetConfig)
    azure_devops: AzureDevOpsTargetConfig | None = Field(default=None, alias="azureDevops")

    model_config = {"populate_by_name": True}

    @field_validator("deployment_target", mode="before")
    @classmethod
    def default_deployment_target(cls, value: str | None) -> str:
        return _default_if_blank(value, "none")

    @field_validator("environment", mode="before")
    @classmethod
    def default_environment(cls, value: str | None) -> str:
        return _default_if_blank(value, "dev")

    @field_validator("regions", mode="before")
    @classmethod
    def normalize_regions(cls, value: str | list[str] | None) -> list[str]:
        return _normalize_string_list(value)


class RepositoryConfig(BaseModel):
    url: str | None = None
    branch: str = Field(default="main", min_length=1, max_length=200)


PythonVersionType = Literal["3.9", "3.10", "3.11", "3.12"]
PythonLintToolType = Literal["ruff", "flake8", "pylint", "black"]


class PythonBuildConfig(BaseModel):
    version: PythonVersionType = Field(default="3.11")
    package_manager: str = Field(default="pip", alias="packageManager", min_length=2, max_length=40)
    test_command: str = Field(default="pytest", alias="testCommand", min_length=1, max_length=400)
    lint_tool: PythonLintToolType = Field(default="ruff", alias="lintTool")
    coverage_gate: int | None = Field(default=None, alias="coverageGate", ge=0, le=100)

    model_config = {"populate_by_name": True}

    @field_validator("test_command", mode="before")
    @classmethod
    def default_test_command(cls, value: str | None) -> str:
        return _default_if_blank(value, "pytest")

    @field_validator("package_manager", mode="before")
    @classmethod
    def default_package_manager(cls, value: str | None) -> str:
        return _default_if_blank(value, "pip")


class BuildConfig(BaseModel):
    language: LanguageType
    framework: str = Field(..., min_length=2, max_length=100)
    tool: str = Field(..., min_length=2, max_length=50)
    artifact_type: ArtifactType = Field(default="none", alias="artifactType")
    image: ImageConfig = Field(default_factory=ImageConfig)
    python: PythonBuildConfig | None = Field(default=None)

    model_config = {"populate_by_name": True}

    @field_validator("artifact_type", mode="before")
    @classmethod
    def default_artifact_type(cls, value: str | None) -> str:
        return _default_if_blank(value, "none")


class CoverageConfig(BaseModel):
    enabled: bool = False
    minimum: int = Field(default=0, ge=0, le=100)


class QualityConfig(BaseModel):
    coverage: CoverageConfig = Field(default_factory=CoverageConfig)


class TriggerConfig(BaseModel):
    push: bool = True
    pull_request: bool = Field(default=True, alias="pullRequest")

    model_config = {"populate_by_name": True}


class ExecutionConfig(BaseModel):
    triggers: TriggerConfig = Field(default_factory=TriggerConfig)
    managed_agents: bool = Field(default=True, alias="managedAgents")
    caching: bool = True
    parallelism: bool = True
    fail_fast: bool = Field(default=True, alias="failFast")
    timeout_minutes: int = Field(default=30, ge=5, le=240, alias="timeoutMinutes")
    approvals: ApprovalConfig = Field(default_factory=ApprovalConfig)

    model_config = {"populate_by_name": True}


class ToolSelection(BaseModel):
    id: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=2, max_length=120)
    category: str = Field(..., min_length=2, max_length=120)


class StageSelection(BaseModel):
    order: int = Field(..., ge=1)
    stage_id: str = Field(..., alias="stageId", min_length=2, max_length=80)
    name: str = Field(..., min_length=2, max_length=120)
    tools: list[str] = Field(default_factory=list)
    ordering_mode: str = Field(default="user-defined", alias="orderingMode")

    model_config = {"populate_by_name": True}


class GeneratePipelineRequest(BaseModel):
    schema_version: str = Field(default="2.0.0", alias="schemaVersion")
    mode: str = Field(default="guided-ui")
    prompt: str | None = Field(default=None, max_length=4000)
    assistant_mode: AssistantModeType = Field(default="assistive-prefill", alias="assistantMode")
    render_mode: RenderModeType | None = Field(default=None, alias="renderMode")
    pipeline_name: str = Field(..., alias="pipelineName", min_length=2, max_length=120)
    target: TargetConfig
    repository: RepositoryConfig
    build: BuildConfig
    quality: QualityConfig = Field(default_factory=QualityConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    tools: list[ToolSelection] = Field(default_factory=list)
    stages: list[StageSelection] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def unwrap_ci_pipeline_request(cls, data):
        if not isinstance(data, dict):
            return data

        nested_request = data.get("ci_pipeline_request")
        if not isinstance(nested_request, dict):
            return data

        payload = dict(nested_request)

        if payload.get("renderMode") is None and data.get("renderMode") is not None:
            payload["renderMode"] = data.get("renderMode")

        if isinstance(payload.get("repository"), dict):
            repository = dict(payload["repository"])
            if repository.get("url") is None and data.get("repository_url") is not None:
                repository["url"] = data.get("repository_url")
            if repository.get("branch") is None and data.get("branch") is not None:
                repository["branch"] = data.get("branch")
            payload["repository"] = repository

        return payload

    @field_validator("stages")
    @classmethod
    def validate_stages_present(cls, value: list[StageSelection]) -> list[StageSelection]:
        if not value:
            raise ValueError("At least one stage must be provided.")
        return value

    @model_validator(mode="after")
    def validate_stage_order(self) -> "GeneratePipelineRequest":
        ordered = sorted(stage.order for stage in self.stages)
        expected = list(range(1, len(self.stages) + 1))
        if ordered != expected:
            raise ValueError("Stages must use sequential ordering starting at 1.")
        return self

    @model_validator(mode="after")
    def validate_enterprise_controls(self) -> "GeneratePipelineRequest":
        if self.target.regions and self.target.deployment_target == "none":
            raise ValueError("target.regions requires target.deploymentTarget to be set.")
        if self.execution.approvals.enabled and self.target.deployment_target == "none":
            raise ValueError("execution.approvals.enabled requires target.deploymentTarget to be set.")
        return self


def create_sample_request() -> GeneratePipelineRequest:
    return GeneratePipelineRequest(
        prompt="Generate GitHub Actions CI for a React app with Snyk, Gitleaks, Docker build, and artifact publish.",
        renderMode="template",
        pipeline_name="quantnik-react-ci",
        target={
            "platform": "github-actions",
            "deploymentTarget": "kubernetes",
            "environment": "qa",
            "regions": ["eastus", "westeurope"],
        },
        repository={
            "url": "https://github.com/example/quantnik-frontend.git",
            "branch": "main",
        },
        build={
            "language": "node",
            "framework": "react",
            "tool": "npm",
            "artifactType": "container",
            "image": {
                "repository": "registry.example.com/quantnik-frontend",
                "tags": ["qa", "release-candidate"],
            },
        },
        quality={"coverage": {"enabled": True, "minimum": 75}},
        execution={
            "triggers": {"push": True, "pullRequest": True},
            "managedAgents": True,
            "caching": True,
            "parallelism": True,
            "failFast": True,
            "timeoutMinutes": 30,
            "approvals": {
                "enabled": True,
                "approvers": ["release-managers@example.com", "platform-owners@example.com"],
                "timeoutMinutes": 120,
            },
        },
        tools=[
            {"id": "unit-tests", "name": "Unit Tests", "category": "Build and Validation"},
            {"id": "linting", "name": "Linting", "category": "Build and Validation"},
            {"id": "gitleaks", "name": "Gitleaks", "category": "Quality and Security"},
            {"id": "snyk", "name": "Snyk", "category": "Quality and Security"},
            {"id": "docker-build", "name": "Docker Build", "category": "Packaging and Delivery"},
            {"id": "artifact-publish", "name": "Artifact Publish", "category": "Packaging and Delivery"},
        ],
        stages=[
            {"order": 1, "stageId": "checkout", "name": "Checkout", "tools": []},
            {"order": 2, "stageId": "restore", "name": "Restore Dependencies", "tools": ["npm"]},
            {"order": 3, "stageId": "build", "name": "Build", "tools": ["npm"]},
            {"order": 4, "stageId": "unit-test", "name": "Unit Test", "tools": ["Unit Tests", "Coverage"]},
            {"order": 5, "stageId": "lint", "name": "Lint", "tools": ["Linting"]},
            {"order": 6, "stageId": "secret-scan", "name": "Secret Scan", "tools": ["Gitleaks"]},
            {"order": 7, "stageId": "dependency-scan", "name": "Dependency Scan", "tools": ["Snyk"]},
            {"order": 8, "stageId": "docker-build", "name": "Docker Build", "tools": ["Docker Build"]},
            {"order": 9, "stageId": "publish-artifacts", "name": "Publish Artifacts", "tools": ["Artifact Publish"]},
        ],
    )