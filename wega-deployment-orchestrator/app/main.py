from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

from app.agents.graph import AgentState, get_orchestrator_graph
from app.agents.streaming_graph import execute_with_streaming
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.security import RepositoryLookupCaller, require_repository_lookup_access
from app.models.repository_operations import (
    AzureDevOpsPipelinePublishRequest,
    AzureDevOpsPipelinePublishResponse,
    HarnessPipelinePublishRequest,
    HarnessPipelinePublishResponse,
    RepositoryFileWriteRequest,
    RepositoryFileWriteResponse,
)
from app.models.requests import ChatRequest
from app.models.responses import ChatResponse, HealthResponse, ResponseStatus, SuggestedAction
from app.tools.agent_client import get_agent_client
from app.tools.repository_lookup import (
    RepositoryLookupError,
    get_repository_lookup_client,
    resolve_repository_context_url,
)

setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_orchestrator_graph()
    yield
    client = get_agent_client()
    await client.close()
    repository_client = get_repository_lookup_client()
    await repository_client.close()


app = FastAPI(
    title="Wega Deployment Orchestrator",
    description="Route deployment workflow requests to CI and CD agents.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    client = get_agent_client()
    ci_health = await client.check_health("ci")
    cd_health = await client.check_health("cd")
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        child_agents={
            "ci": ci_health.get("status", "unknown"),
            "cd": cd_health.get("status", "unknown"),
        },
        timestamp=datetime.utcnow(),
    )


@app.get("/v1/repositories", tags=["Repositories"])
async def list_repositories(
    platform: str = Query(..., min_length=2, max_length=80),
    repository_url: str | None = Query(default=None, alias="repository_url"),
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> dict[str, list[dict[str, str]]]:
    client = get_repository_lookup_client()

    try:
        items = await client.list_repositories(platform=platform, repository_url=repository_url)
    except RepositoryLookupError as exc:
        if exc.log_message:
            logger.warning('Repository lookup failed: %s', exc.log_message)
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    return {
        "items": [
            {"id": item.id, "label": item.label, "url": item.url}
            for item in items
        ]
    }


@app.get("/v1/repositories/context", tags=["Repositories"])
async def get_repository_context(
    platform: str = Query(..., min_length=2, max_length=80),
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> dict[str, str]:
    try:
        return {"repository_url": resolve_repository_context_url(platform)}
    except RepositoryLookupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc


@app.get("/v1/repositories/branches", tags=["Repositories"])
async def list_repository_branches(
    platform: str = Query(..., min_length=2, max_length=80),
    repository_url: str = Query(..., alias="repository_url", min_length=4),
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> dict[str, list[str]]:
    client = get_repository_lookup_client()

    try:
        items = await client.list_branches(platform=platform, repository_url=repository_url)
    except RepositoryLookupError as exc:
        if exc.log_message:
            logger.warning('Repository branch lookup failed: %s', exc.log_message)
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    return {"items": items}


@app.post('/v1/repositories/files', response_model=RepositoryFileWriteResponse, tags=['Repositories'])
async def write_repository_file(
    request: RepositoryFileWriteRequest,
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> RepositoryFileWriteResponse:
    client = get_repository_lookup_client()

    try:
        result = await client.write_file(
            platform=request.platform,
            repository_url=request.repository_url,
            branch=request.branch,
            file_path=request.file_path,
            content=request.content,
            commit_message=request.commit_message,
        )
    except RepositoryLookupError as exc:
        if exc.log_message:
            logger.warning('Repository file push failed: %s', exc.log_message)
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    return RepositoryFileWriteResponse(
        status=result.status,
        repositoryUrl=result.repository_url,
        branch=result.branch,
        filePath=result.file_path,
        commitMessage=result.commit_message,
        commitSha=result.commit_sha,
    )


@app.post('/v1/harness/pipelines', response_model=HarnessPipelinePublishResponse, tags=['Harness'])
async def publish_harness_pipeline(
    request: HarnessPipelinePublishRequest,
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> HarnessPipelinePublishResponse:
    client = get_repository_lookup_client()

    try:
        result = await client.publish_pipeline(
            platform=request.platform,
            repository_url=request.repository_url,
            content=request.content,
        )
    except RepositoryLookupError as exc:
        if exc.log_message:
            logger.warning('Harness pipeline publish failed: %s', exc.log_message)
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    return HarnessPipelinePublishResponse(
        status=result.status,
        pipelineIdentifier=result.pipeline_identifier,
        pipelineName=result.pipeline_name,
        accountIdentifier=result.account_identifier,
        orgIdentifier=result.org_identifier,
        projectIdentifier=result.project_identifier,
    )


@app.post('/v1/azure-devops/pipelines', response_model=AzureDevOpsPipelinePublishResponse, tags=['Azure DevOps'])
async def publish_azure_devops_pipeline(
    request: AzureDevOpsPipelinePublishRequest,
    _: RepositoryLookupCaller = Depends(require_repository_lookup_access),
) -> AzureDevOpsPipelinePublishResponse:
    client = get_repository_lookup_client()

    try:
        result = await client.publish_azure_devops_pipeline(
            repository_url=request.repository_url,
            content=request.content,
            branch=request.branch,
            file_path=request.file_path,
            pipeline_name=request.pipeline_name,
            commit_message=request.commit_message,
        )
    except RepositoryLookupError as exc:
        if exc.log_message:
            logger.warning('Azure DevOps pipeline publish failed: %s', exc.log_message)
        raise HTTPException(status_code=exc.status_code, detail=exc.user_message) from exc

    return AzureDevOpsPipelinePublishResponse(
        status=result.status,
        pipelineId=result.pipeline_id,
        pipelineName=result.pipeline_name,
        repositoryId=result.repository_id,
        repositoryName=result.repository_name,
        branch=result.branch,
        filePath=result.file_path,
        commitSha=result.commit_sha,
        pipelineUrl=result.pipeline_url,
    )


@app.post("/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    graph = get_orchestrator_graph()
    initial_state: AgentState = {
        "session_id": request.session_id,
        "messages": [{"role": message.role, "content": message.content} for message in (request.history or [])],
        "current_message": request.message,
        "intent": None,
        "target_agent": None,
        "entities": request.context.get("entities", {}) if request.context else {},
        "context": request.context or {},
        "pending_actions": [],
        "current_action": None,
        "action_results": [],
        "response": None,
        "error": None,
        "suggested_actions": [],
        "metadata": {"start_time": datetime.utcnow().isoformat()},
        "child_response": None,
    }

    if request.explicit_intent:
        initial_state["context"]["explicit_intent"] = request.explicit_intent
    if request.target_agent:
        initial_state["context"]["target_agent"] = request.target_agent

    config = {"configurable": {"thread_id": request.session_id}}
    final_state = await graph.ainvoke(initial_state, config)

    child_response = final_state.get("child_response") or {}
    child_data = child_response.get("data", {}) or {}
    nextagentflow = child_response.get("nextagentflow")
    routed_to = final_state["target_agent"].value if final_state.get("target_agent") else None
    response_message = child_response.get("message") or final_state.get("response") or "Deployment request processed."
    has_error = bool(final_state.get("error") or child_response.get("status") == "error")

    return ChatResponse(
        session_id=request.session_id,
        message=response_message,
        status=ResponseStatus.ERROR if has_error else ResponseStatus.SUCCESS,
        nextagentflow=nextagentflow,
        data={
            "intent": final_state["intent"].intent.value if final_state.get("intent") else None,
            "entities": final_state.get("entities", {}),
            **({"error": {"type": "orchestrator_error", "detail": [final_state["error"]]}} if final_state.get("error") and "error" not in child_data else {}),
            **child_data,
        },
        suggested_actions=[
            SuggestedAction(
                action=item["action"],
                intent=item.get("intent"),
                agent=item.get("agent"),
            )
            for item in final_state.get("suggested_actions", [])
        ],
        metadata=final_state.get("metadata", {}),
        routed_to=routed_to,
        timestamp=datetime.utcnow(),
    )


@app.post("/v1/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for event in execute_with_streaming(
            session_id=request.session_id,
            message=request.message,
            context=request.context,
            history=[{"role": message.role, "content": message.content} for message in (request.history or [])],
            explicit_intent=request.explicit_intent,
            target_agent=request.target_agent,
        ):
            yield event

    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/chat/simple", response_model=ChatResponse, tags=["Chat"])
async def chat_simple(request: dict) -> ChatResponse:
    session_id = request.get("session_id") or f"deploy_{uuid4().hex[:12]}"
    chat_request = ChatRequest(
        session_id=session_id,
        message=request.get("message", "Generate CI pipeline"),
        context=request.get("context") or {},
        explicit_intent=request.get("explicit_intent"),
        target_agent=request.get("target_agent"),
    )
    return await chat(chat_request)