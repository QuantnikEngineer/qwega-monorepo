from __future__ import annotations

from pydantic import BaseModel, Field


class RepositoryFileWriteRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=80)
    repository_url: str = Field(..., alias='repositoryUrl', min_length=4, max_length=500)
    branch: str = Field(..., min_length=1, max_length=200)
    file_path: str = Field(..., alias='filePath', min_length=1, max_length=400)
    content: str = Field(..., min_length=1)
    commit_message: str = Field(..., alias='commitMessage', min_length=3, max_length=300)

    model_config = {'populate_by_name': True}


class RepositoryFileWriteResponse(BaseModel):
    status: str
    repository_url: str = Field(alias='repositoryUrl')
    branch: str
    file_path: str = Field(alias='filePath')
    commit_message: str = Field(alias='commitMessage')
    commit_sha: str | None = Field(default=None, alias='commitSha')

    model_config = {'populate_by_name': True}


class HarnessPipelinePublishRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=80)
    repository_url: str | None = Field(default=None, alias='repositoryUrl', max_length=500)
    content: str = Field(..., min_length=1)

    model_config = {'populate_by_name': True}


class HarnessPipelinePublishResponse(BaseModel):
    status: str
    pipeline_identifier: str = Field(alias='pipelineIdentifier')
    pipeline_name: str = Field(alias='pipelineName')
    account_identifier: str = Field(alias='accountIdentifier')
    org_identifier: str = Field(alias='orgIdentifier')
    project_identifier: str = Field(alias='projectIdentifier')

    model_config = {'populate_by_name': True}


class AzureDevOpsPipelinePublishRequest(BaseModel):
    repository_url: str = Field(..., alias='repositoryUrl', min_length=4, max_length=500)
    branch: str = Field(..., min_length=1, max_length=200)
    file_path: str = Field(default='azure-pipelines.yml', alias='filePath', max_length=400)
    pipeline_name: str | None = Field(default=None, alias='pipelineName', max_length=200)
    commit_message: str | None = Field(default=None, alias='commitMessage', max_length=300)
    content: str = Field(..., min_length=1)

    model_config = {'populate_by_name': True}


class AzureDevOpsPipelinePublishResponse(BaseModel):
    status: str
    pipeline_id: int | None = Field(default=None, alias='pipelineId')
    pipeline_name: str = Field(alias='pipelineName')
    repository_id: str = Field(alias='repositoryId')
    repository_name: str = Field(alias='repositoryName')
    branch: str
    file_path: str = Field(alias='filePath')
    commit_sha: str | None = Field(default=None, alias='commitSha')
    pipeline_url: str | None = Field(default=None, alias='pipelineUrl')

    model_config = {'populate_by_name': True}