from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    template_count: int
    supported_platforms: list[str]


class CatalogItem(BaseModel):
    value: str
    label: str


class CatalogTool(BaseModel):
    id: str
    name: str
    category: str
    description: str


class CatalogStage(BaseModel):
    id: str
    name: str
    description: str


class CatalogResponse(BaseModel):
    platforms: list[CatalogItem]
    languages: list[CatalogItem]
    artifact_types: list[CatalogItem] = Field(alias="artifactTypes")
    deployment_targets: list[CatalogItem] = Field(alias="deploymentTargets")
    tools: list[CatalogTool]
    stages: list[CatalogStage]

    model_config = {"populate_by_name": True}


class GeneratedArtifact(BaseModel):
    path: str
    content_type: str = Field(alias="contentType")
    content: str

    model_config = {"populate_by_name": True}


class GeneratePipelineResponse(BaseModel):
    status: str
    summary: str
    message: str
    pipeline_name: str = Field(alias="pipelineName")
    platform: str
    artifact: GeneratedArtifact
    normalized_intent: dict[str, Any] = Field(alias="normalizedIntent")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}