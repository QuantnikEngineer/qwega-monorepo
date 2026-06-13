"""
Quantnik SDLC Orchestrator - Main Application
==========================================
Parent orchestrator that routes requests to Planning and Test orchestrators.
Entry point for frontend React/TSX applications.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse as FastAPIStreamingResponse
import json as json_module
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.requests import ChatRequest, LegacyAnalyzeRequest, OrchestratorType
from app.models.responses import (
    ChatResponse,
    LegacyAnalyzeResponse,
    HealthResponse,
    ErrorResponse,
    ResponseStatus,
    SuggestedAction,
    CapabilitiesResponse,
    OrchestratorCapability
)
from app.agents.graph import get_orchestrator_graph, AgentState
from app.agents.streaming_graph import execute_with_streaming
from app.memory.conversation_memory import get_memory
from app.tools.orchestrator_client import get_orchestrator_client

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(
        "Starting SDLC Orchestrator",
        version=settings.app_version,
        environment=settings.app_env,
        planning_url=settings.planning_orchestrator_url,
        test_url=settings.test_orchestrator_url
    )
    
    get_orchestrator_graph()
    logger.info("Orchestrator graph initialized")
    
    yield
    
    # Cleanup
    client = get_orchestrator_client()
    await client.close()
    logger.info("Shutting down SDLC Orchestrator")


app = FastAPI(
    title="Quantnik SDLC Orchestrator",
    description="""
## SDLC Orchestrator - Unified Entry Point

This is the parent orchestrator for QUANTNIK SDLC workflow automation.
It intelligently routes requests to specialized child orchestrators:

### Architecture

```
Frontend (React/TSX)
        │
        ▼
┌─────────────────────┐
│  SDLC Orchestrator  │  ← You are here
│    (Port 8080)      │
└─────────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────┐
│Plan  │  │Test  │
│Orch  │  │Orch  │
│8000  │  │8001  │
└──────┘  └──────┘
```

### Supported Workflows

| Orchestrator | Intents |
|--------------|---------|
| **Planning** | create_brd, create_user_story, validate_user_story, brd_summary |
| **Test** | generate_test_cases, generate_test_script |

### Conversational Flow

The orchestrator maintains conversation context and handles:
- Intent classification with LLM
- Automatic routing to appropriate child orchestrator
- Confirmation handling (yes, ok, proceed, option 1, etc.)
- Cross-orchestrator context sharing

### Endpoints

- `POST /v1/chat` - Main chat endpoint (recommended)
- `GET /v1/capabilities` - Get all orchestrator capabilities
- `GET /health` - Health check with child orchestrator status
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cache-Control", "Connection", "X-Accel-Buffering", "Content-Type"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Quantnik SDLC Orchestrator",
        version=settings.app_version,
        description=app.description,
        routes=app.routes,
    )
    
    openapi_schema["tags"] = [
        {"name": "Chat", "description": "Conversational interface for frontend applications"},
        {"name": "Capabilities", "description": "Orchestrator capabilities and discovery"},
        {"name": "Legacy", "description": "Backward-compatible endpoints"},
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Memory", "description": "Session memory management"},
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Checks status of SDLC orchestrator and all child orchestrators.
    """
    logger.info("[health_check] Request received")
    client = get_orchestrator_client()
    
    components = {
        "orchestrator": "healthy",
        "memory": "healthy",
        "llm": "unknown"
    }
    
    # Check LLM
    try:
        from app.agents.intent_classifier import get_classifier
        classifier = get_classifier()
        components["llm"] = "healthy" if classifier._llm_type != "fallback" else "degraded"
        logger.debug("[health_check] LLM status checked", llm_type=classifier._llm_type, status=components["llm"])
    except Exception as e:
        components["llm"] = "unhealthy"
        logger.error("[health_check] LLM health check failed", error=str(e), error_type=type(e).__name__)
    
    # Check child orchestrators
    child_status = {}
    
    planning_health = await client.check_health(OrchestratorType.PLANNING)
    child_status["planning"] = planning_health.get("status", "unknown")
    
    test_health = await client.check_health(OrchestratorType.TEST)
    child_status["test"] = test_health.get("status", "unknown")
    
    common_integration_health = await client.check_health(OrchestratorType.COMMON_INTEGRATION)
    child_status["common_integration"] = common_integration_health.get("status", "unknown")
    
    overall = "healthy"
    if any(v == "unhealthy" for v in components.values()):
        overall = "degraded"
    if all(v == "unhealthy" for v in child_status.values()):
        overall = "degraded"
    
    logger.info(
        "[health_check] Health check completed",
        overall_status=overall,
        components=components,
        child_orchestrators=child_status
    )
    
    return HealthResponse(
        status=overall,
        timestamp=datetime.utcnow(),
        service=settings.app_name,
        version=settings.app_version,
        components=components,
        child_orchestrators=child_status
    )


@app.get("/health/connectivity", tags=["Health"])
async def connectivity_check():
    """
    Detailed connectivity check to child orchestrators.
    
    Performs DNS resolution, TCP connection, and HTTP health check tests.
    Useful for diagnosing connection issues in Cloud Run.
    """
    logger.info("[connectivity_check] Request received")
    client = get_orchestrator_client()
    
    results = {
        "planning": await client.verify_connectivity(OrchestratorType.PLANNING),
        "test": await client.verify_connectivity(OrchestratorType.TEST)
    }
    
    overall_success = all(r.get("success", False) for r in results.values())
    
    logger.info(
        "[connectivity_check] Check completed",
        overall_success=overall_success,
        planning_success=results["planning"].get("success"),
        test_success=results["test"].get("success")
    )
    
    return {
        "overall_success": overall_success,
        "timestamp": datetime.utcnow().isoformat(),
        "orchestrators": results
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    logger.info("[root] Request received")
    response = {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "capabilities": "/v1/capabilities"
    }
    logger.info("[root] Response sent", response=response)
    return response


# =============================================================================
# Capabilities Endpoints
# =============================================================================

@app.get("/v1/capabilities", response_model=CapabilitiesResponse, tags=["Capabilities"])
async def get_capabilities():
    """
    Get capabilities of all orchestrators.
    
    Useful for frontend to understand what actions are available.
    """
    logger.info("[get_capabilities] Request received")
    client = get_orchestrator_client()
    caps = client.get_all_capabilities()
    
    # Check health of each
    orchestrators = []
    for cap in caps:
        orch_type = OrchestratorType.PLANNING if cap["name"] == "planning" else OrchestratorType.TEST
        health = await client.check_health(orch_type)
        
        orchestrators.append(OrchestratorCapability(
            name=cap["name"],
            description=cap["description"],
            intents=cap["intents"],
            keywords=cap["keywords"],
            url=cap["url"],
            status=health.get("status", "unknown")
        ))
    
    total_intents = sum(len(o.intents) for o in orchestrators)
    
    response = CapabilitiesResponse(
        orchestrators=orchestrators,
        total_intents=total_intents
    )
    
    logger.info(
        "[get_capabilities] Response sent",
        orchestrator_count=len(orchestrators),
        total_intents=total_intents
    )
    
    return response


# =============================================================================
# Chat Endpoints
# =============================================================================

@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["session_id", "message"],
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Unique session identifier",
                                "example": "sess_abc123"
                            },
                            "message": {
                                "type": "string",
                                "description": "User's natural language message",
                                "example": "Create a BRD from my transcript"
                            },
                            "context": {
                                "type": "object",
                                "description": "Additional context",
                                "example": {}
                            },
                            "history": {
                                "type": "array",
                                "description": "Previous messages",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "role": {"type": "string"},
                                        "content": {"type": "string"}
                                    }
                                }
                            },
                            "explicit_intent": {
                                "type": "string",
                                "description": "Explicit intent override",
                                "example": "create_brd"
                            },
                            "target_orchestrator": {
                                "type": "string",
                                "description": "Force specific orchestrator",
                                "example": "planning"
                            }
                        }
                    }
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["session_id", "message"],
                        "properties": {
                            "session_id": {"type": "string"},
                            "message": {"type": "string"},
                            "context": {"type": "string", "description": "JSON string"},
                            "explicit_intent": {"type": "string"},
                            "file": {"type": "string", "format": "binary"}
                        }
                    }
                }
            }
        }
    }
)
async def chat(request: Request):
    """
    Main chat endpoint for frontend applications.
    
    Supports both JSON and multipart/form-data requests:
    - JSON: Standard chat requests
    - Multipart/form-data: File uploads (e.g., for create_brd with transcript files)
    
    **JSON Request Body:**
    - `session_id` (required): Unique session identifier
    - `message` (required): User's natural language message
    - `context`: Additional context object
    - `history`: Previous conversation messages
    - `explicit_intent`: Override intent classification
    - `target_orchestrator`: Force routing to specific orchestrator
    
    **Multipart Request (for file uploads):**
    - `session_id`, `message`, `context` (as JSON string), `file`
    """
    logger.info("[chat] Request received", content_type=request.headers.get("content-type", ""))
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        return await _handle_multipart_chat(request)
    else:
        body = await request.json()
        chat_request = ChatRequest(**body)
        return await _process_chat(chat_request)


async def _handle_multipart_chat(request: Request):
    """Handle multipart/form-data chat requests with file uploads."""
    form = await request.form()
    
    session_id = form.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")
    message = form.get("message", "")
    context_str = form.get("context", "{}")
    explicit_intent = form.get("explicit_intent")
    target_orchestrator = form.get("target_orchestrator")
    
    # Parse context if provided as string
    try:
        context = json_module.loads(context_str) if isinstance(context_str, str) and context_str else {}
    except json_module.JSONDecodeError:
        context = {}
    
    # Collect uploaded files
    files = []
    for key, value in form.multi_items():
        if hasattr(value, 'file'):  # It's an UploadFile
            file_content = await value.read()
            files.append({
                "filename": value.filename,
                "content_type": value.content_type,
                "content": file_content,
                "field_name": key
            })
            await value.seek(0)  # Reset file position for potential re-read
    
    logger.info(
        "[_handle_multipart_chat] Multipart request received",
        session_id=session_id,
        message_length=len(message) if message else 0,
        file_count=len(files),
        file_names=[f["filename"] for f in files],
        explicit_intent=explicit_intent
    )
    
    # Determine target orchestrator based on explicit_intent
    # context_enrich_upload goes to common_integration, otherwise planning
    if files:
        target_orch = OrchestratorType.PLANNING
        routed_to = "planning"
        if explicit_intent == "context_enrich_upload":
            target_orch = OrchestratorType.COMMON_INTEGRATION
            routed_to = "common_integration"
        
        client = get_orchestrator_client()
        try:
            result = await client.call_chat_multipart(
                orchestrator=target_orch,
                session_id=session_id,
                message=message,
                files=files,
                context=context,
                explicit_intent=explicit_intent
            )
            
            return ChatResponse(
                session_id=session_id,
                message=result.get("message", "Request processed successfully."),
                status=ResponseStatus.SUCCESS if result.get("status") != "error" else ResponseStatus.ERROR,
                data=result.get("data", {}),
                suggested_actions=[
                    SuggestedAction(
                        action=sa["action"],
                        intent=sa.get("intent"),
                        orchestrator=sa.get("orchestrator")
                    )
                    for sa in result.get("suggested_actions", [])
                ],
                metadata=result.get("metadata", {}),
                routed_to=routed_to
            )
        except Exception as e:
            logger.error(
                "[_handle_multipart_chat] Error forwarding multipart request",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return ChatResponse(
                session_id=session_id,
                message=f"Error processing file upload: {str(e)}",
                status=ResponseStatus.ERROR,
                metadata={"error": str(e)}
            )
    
    # No files, process as regular chat
    chat_request = ChatRequest(
        session_id=session_id,
        message=message,
        context=context,
        explicit_intent=explicit_intent,
        target_orchestrator=target_orchestrator
    )
    return await _process_chat(chat_request)


async def _process_chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint for frontend applications.
    
    This endpoint:
    1. Retrieves session memory
    2. Classifies intent using LLM
    3. Routes to appropriate child orchestrator
    4. Returns unified response
    
    **Example Request:**
    ```json
    {
        "session_id": "sess_abc123",
        "message": "Create a BRD from my transcript"
    }
    ```
    
    """
    logger.info(
        "[chat] Request received",
        session_id=request.session_id,
        message_length=len(request.message) if request.message else 0,
        message_preview=request.message[:100] if request.message else "",
        has_context=request.context is not None,
        history_count=len(request.history) if request.history else 0,
        explicit_intent=request.explicit_intent,
        target_orchestrator=request.target_orchestrator,
        request_payload=request.model_dump()
    )
    
    try:
        graph = get_orchestrator_graph()
        
        # Build initial state
        initial_state: AgentState = {
            "session_id": request.session_id,
            "messages": [{"role": m.role, "content": m.content} for m in (request.history or [])],
            "current_message": request.message,
            "intent": None,
            "target_orchestrator": None,
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
        
        # Handle explicit overrides
        if request.explicit_intent:
            initial_state["context"]["explicit_intent"] = request.explicit_intent
            logger.debug("[chat] Explicit intent override set", explicit_intent=request.explicit_intent)
        if request.target_orchestrator:
            initial_state["context"]["target_orchestrator"] = request.target_orchestrator
            logger.debug("[chat] Target orchestrator override set", target_orchestrator=request.target_orchestrator)
        
        logger.debug("[chat] Invoking orchestrator graph", session_id=request.session_id)
        
        # Execute graph
        config = {"configurable": {"thread_id": request.session_id}}
        final_state = await graph.ainvoke(initial_state, config)
        
        # Build response
        routed_to = None
        if final_state.get("target_orchestrator"):
            routed_to = final_state["target_orchestrator"].value
        
        # Extract nextagentflow, job_id, push_results and data from child_response
        nextagentflow = None
        job_id = None
        push_results = None
        child_data = {}
        response_message = final_state.get("response", "I've processed your request.")
        child_response = final_state.get("child_response")
        if child_response:
            nextagentflow = child_response.get("nextagentflow")
            # Include child response data at root level
            child_data = child_response.get("data", {}) or {}
            # Extract job_id from child data
            job_id = child_data.get("job_id")
            # Extract push_results from child data
            push_results = child_data.get("push_results")
            # If message is nested in data, use it
            nested_message = child_data.get("message")
            if nested_message and isinstance(nested_message, str):
                response_message = nested_message
        
        # Merge child data with intent/entities data
        response_data = {
            "intent": final_state["intent"].intent.value if final_state.get("intent") else None,
            "entities": final_state.get("entities", {}),
            "action_results": final_state.get("action_results", []),
            **child_data,  # Include all data from child orchestrator response
        }
        
        response = ChatResponse(
            session_id=request.session_id,
            message=response_message,
            status=ResponseStatus.ERROR if final_state.get("error") else ResponseStatus.SUCCESS,
            job_id=job_id,
            nextagentflow=nextagentflow,
            data=response_data,
            push_results=push_results,
            suggested_actions=[
                SuggestedAction(
                    action=sa["action"],
                    intent=sa.get("intent"),
                    orchestrator=sa.get("orchestrator")
                )
                for sa in final_state.get("suggested_actions", [])
            ],
            metadata=final_state.get("metadata", {}),
            routed_to=routed_to
        )
        
        logger.info(
            "[chat] Response sent",
            session_id=request.session_id,
            status=response.status.value,
            routed_to=routed_to,
            response_message_length=len(response.message),
            suggested_actions_count=len(response.suggested_actions),
            response_payload=response.model_dump()
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "[chat] Processing error",
            session_id=request.session_id,
            error=str(e),
            error_type=type(e).__name__,
            request_message=request.message[:100] if request.message else ""
        )
        return ChatResponse(
            session_id=request.session_id,
            message=f"I encountered an error: {str(e)}",
            status=ResponseStatus.ERROR,
            metadata={"error": str(e)}
        )


@app.post("/v1/chat/simple", tags=["Chat"])
async def simple_chat(message: str = Body(..., embed=True)):
    """Simple chat endpoint with auto-generated session."""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    logger.info(
        "[simple_chat] Request received",
        session_id=session_id,
        message_length=len(message),
        message_preview=message[:100]
    )
    chat_request = ChatRequest(session_id=session_id, message=message)
    response = await _process_chat(chat_request)
    logger.info(
        "[simple_chat] Response sent",
        session_id=session_id,
        status=response.status.value,
        nextagentflow=response.nextagentflow
    )
    return response


@app.post(
    "/v1/chat/stream",
    tags=["Chat"],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["session_id", "message"],
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Unique session identifier",
                                "example": "sess_abc123"
                            },
                            "message": {
                                "type": "string",
                                "description": "User's natural language message",
                                "example": "Create a BRD from my transcript"
                            },
                            "context": {
                                "type": "object",
                                "description": "Additional context",
                                "example": {}
                            },
                            "history": {
                                "type": "array",
                                "description": "Previous messages",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "role": {"type": "string"},
                                        "content": {"type": "string"}
                                    }
                                }
                            },
                            "explicit_intent": {
                                "type": "string",
                                "description": "Explicit intent override",
                                "example": "create_brd"
                            },
                            "target_orchestrator": {
                                "type": "string",
                                "description": "Force specific orchestrator",
                                "example": "planning"
                            }
                        }
                    }
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["session_id", "message"],
                        "properties": {
                            "session_id": {"type": "string"},
                            "message": {"type": "string"},
                            "context": {"type": "string", "description": "JSON string"},
                            "explicit_intent": {"type": "string"},
                            "file": {"type": "string", "format": "binary"}
                        }
                    }
                }
            }
        }
    }
)
async def chat_stream(request: Request):
    """
    Streaming chat endpoint with real-time milestone updates.
    
    Supports both JSON and multipart/form-data requests.
    Returns Server-Sent Events (SSE) stream.
    
    **JSON Request Body:**
    - `session_id` (required): Unique session identifier
    - `message` (required): User's natural language message
    - `context`: Additional context object
    - `history`: Previous conversation messages
    - `explicit_intent`: Override intent classification
    - `target_orchestrator`: Force routing to specific orchestrator
    
    **Multipart Request (for file uploads):**
    - `session_id`, `message`, `context` (as JSON string), `file`
    """
    logger.info("[chat_stream] Request received", content_type=request.headers.get("content-type", ""))
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        return await _handle_multipart_stream(request)
    else:
        body = await request.json()
        chat_request = ChatRequest(**body)
        logger.info(
            "[chat_stream] Starting stream",
            session_id=chat_request.session_id,
            message_length=len(chat_request.message) if chat_request.message else 0
        )
        return await _process_chat_stream(chat_request)


async def _handle_multipart_stream(request: Request):
    """Handle multipart/form-data streaming requests with file uploads."""
    form = await request.form()
    
    session_id = form.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")
    message = form.get("message", "")
    context_str = form.get("context", "{}")
    explicit_intent = form.get("explicit_intent")
    
    try:
        context = json_module.loads(context_str) if isinstance(context_str, str) and context_str else {}
    except json_module.JSONDecodeError:
        context = {}
    
    # Collect uploaded files
    files = []
    for key, value in form.multi_items():
        if hasattr(value, 'file'):
            file_content = await value.read()
            files.append({
                "filename": value.filename,
                "content_type": value.content_type,
                "content": file_content,
                "field_name": key
            })
            await value.seek(0)
    
    logger.info(
        "[_handle_multipart_stream] Multipart stream request received",
        session_id=session_id,
        message_length=len(message) if message else 0,
        file_count=len(files),
        file_names=[f["filename"] for f in files],
        explicit_intent=explicit_intent
    )
    
    # Determine target orchestrator based on explicit_intent
    # context_enrich_upload goes to common_integration, otherwise planning
    if files:
        target_orch = OrchestratorType.PLANNING
        if explicit_intent == "context_enrich_upload":
            target_orch = OrchestratorType.COMMON_INTEGRATION
        
        client = get_orchestrator_client()
        
        async def multipart_event_generator():
            try:
                async for event in client.call_chat_stream_multipart(
                    orchestrator=target_orch,
                    session_id=session_id,
                    message=message,
                    files=files,
                    context=context,
                    explicit_intent=explicit_intent
                ):
                    yield f"data: {json_module.dumps(event)}\n\n"
            except Exception as e:
                logger.error(
                    "[_handle_multipart_stream] Stream error",
                    session_id=session_id,
                    error=str(e)
                )
                yield f"data: {json_module.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return FastAPIStreamingResponse(
            multipart_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # No files, process as regular stream
    chat_request = ChatRequest(
        session_id=session_id,
        message=message,
        context=context,
        explicit_intent=explicit_intent
    )
    return await _process_chat_stream(chat_request)


async def _process_chat_stream(request: ChatRequest):
    """Process streaming chat request."""
    logger.info(
        "[chat_stream] SSE streaming request received",
        session_id=request.session_id,
        message_length=len(request.message) if request.message else 0,
        message_preview=request.message[:100] if request.message else "",
        has_context=request.context is not None,
        history_count=len(request.history) if request.history else 0,
        explicit_intent=request.explicit_intent,
        target_orchestrator=request.target_orchestrator,
        request_payload=request.model_dump()
    )
    
    async def event_generator():
        event_count = 0
        try:
            async for event in execute_with_streaming(
                session_id=request.session_id,
                message=request.message,
                context=request.context,
                history=[{"role": m.role, "content": m.content} for m in (request.history or [])],
                explicit_intent=request.explicit_intent,
                target_orchestrator=request.target_orchestrator
            ):
                event_count += 1
                logger.debug(
                    "[chat_stream] Yielding SSE event",
                    session_id=request.session_id,
                    event_count=event_count,
                    event_preview=event[:200] if event else None
                )
                yield event
            
            logger.info(
                "[chat_stream] SSE stream completed",
                session_id=request.session_id,
                total_events=event_count
            )
        except Exception as e:
            logger.error(
                "[chat_stream] SSE stream error",
                session_id=request.session_id,
                error=str(e),
                error_type=type(e).__name__,
                events_before_error=event_count
            )
            raise
    
    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# =============================================================================
# Legacy Endpoints
# =============================================================================

@app.post("/api/v1/prompt/analyze", response_model=LegacyAnalyzeResponse, tags=["Legacy"])
async def analyze_prompt_legacy(request: LegacyAnalyzeRequest):
    """Legacy analyze endpoint for backward compatibility."""
    logger.info(
        "[analyze_prompt_legacy] Legacy request received",
        query_length=len(request.query_text) if request.query_text else 0,
        query_preview=request.query_text[:100] if request.query_text else "",
        nextagentflow=request.nextagentflow,
        brd_document_uri=request.brd_document_uri,
        framework_type=request.framework_type,
        language=request.language,
        request_payload=request.model_dump()
    )
    
    try:
        session_id = f"legacy_{uuid.uuid4().hex[:12]}"
        
        # Build context
        context = {}
        if request.brd_document_uri:
            context["brd_link"] = request.brd_document_uri
        if request.create_user_story_text:
            context["user_stories"] = request.create_user_story_text
        if request.test_scenarios:
            context["test_scenarios"] = request.test_scenarios
        if request.test_cases:
            context["test_cases"] = request.test_cases
        if request.framework_type:
            context["framework_type"] = request.framework_type
        if request.language:
            context["language"] = request.language
        if request.script_generation_type:
            context["script_generation_type"] = request.script_generation_type
        
        logger.debug(
            "[analyze_prompt_legacy] Built context from legacy request",
            session_id=session_id,
            context=context
        )
        
        chat_request = ChatRequest(
            session_id=session_id,
            message=request.query_text,
            context=context,
            explicit_intent=request.nextagentflow
        )
        
        chat_response = await _process_chat(chat_request)
        
        legacy_response = LegacyAnalyzeResponse(
            success=chat_response.status == ResponseStatus.SUCCESS,
            result=chat_response.data,
            message=chat_response.message,
            error=chat_response.metadata.get("error") if chat_response.metadata else None,
            nextagentflow=_map_intent_to_nextagentflow(
                chat_response.data.get("intent") if chat_response.data else None
            ),
            next_suggested_action=chat_response.suggested_actions[0].action if chat_response.suggested_actions else None,
            routed_to=chat_response.routed_to
        )
        
        logger.info(
            "[analyze_prompt_legacy] Legacy response sent",
            session_id=session_id,
            success=legacy_response.success,
            nextagentflow=legacy_response.nextagentflow,
            routed_to=legacy_response.routed_to,
            response_payload=legacy_response.model_dump()
        )
        
        return legacy_response
        
    except Exception as e:
        logger.error(
            "[analyze_prompt_legacy] Legacy analyze error",
            error=str(e),
            error_type=type(e).__name__,
            query_preview=request.query_text[:100] if request.query_text else ""
        )
        return LegacyAnalyzeResponse(
            success=False,
            error=str(e),
            message=f"Error: {str(e)}"
        )


def _map_intent_to_nextagentflow(intent: Optional[str]) -> Optional[str]:
    """Map intent to legacy nextagentflow."""
    if not intent:
        return None
    
    mapping = {
        "create_brd": "confirmedCreateBrd",
        "create_user_story": "confirmedCreateUserStory",
        "validate_user_story": "confirmedValidateUserStory",
        "create_user_manual": "confirmedCreateUserManual",
        "brd_summary": "confirmedBrdSummary",
        "generate_test_cases": "confirmedUserStoryToTestScenario",
        "generate_test_script": "confirmedTestCaseToTestScript",
        "context_enrich_upload": "confirmedContextEnrichUpload",
        "context_enrich_ingest": "confirmedContextEnrichIngest",
        "context_enrich_feedback": "confirmedContextEnrichFeedback",
        "context_enrich_query": "confirmedContextEnrichQuery",
    }
    
    return mapping.get(intent)


# =============================================================================
# Pass-through Endpoints (Forward to child orchestrators)
# =============================================================================

@app.post(
    "/v1/app/save-validated-user-stories",
    tags=["Chat"],
    summary="Save Validated User Stories via Planning Orchestrator",
    description="""
Forwards the save-validated-user-stories request to the Planning Orchestrator.
Performs bulk Jira operations: update, create, delete stories.

Returns a JSON response with operation results.
    """
)
async def save_validated_user_stories(request: Request):
    """
    Forward save-validated-user-stories to Planning Orchestrator.
    """
    body = await request.json()
    session_id = body.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")

    logger.info(
        "[save_validated_user_stories] Forwarding to planning orchestrator",
        session_id=session_id,
        update_count=len(body.get("update_stories", [])),
        create_count=len(body.get("create_stories", [])),
        delete_count=len(body.get("delete_stories", []))
    )

    client = get_orchestrator_client()
    url = client.get_url(OrchestratorType.PLANNING)
    if not url:
        return JSONResponse(
            status_code=502,
            content={"success": False, "message": "Planning orchestrator URL not configured"}
        )

    fresh_client = client._create_fresh_client()
    try:
        headers = client._get_auth_headers(url)
        response = await fresh_client.post(
            f"{url}/v1/app/save-validated-user-stories",
            json=body,
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        logger.info(
            "[save_validated_user_stories] Response from planning orchestrator",
            session_id=session_id,
            success=result.get("success")
        )
        return JSONResponse(status_code=response.status_code, content=result)
    except Exception as e:
        logger.error(
            "[save_validated_user_stories] Error forwarding request",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__
        )
        return JSONResponse(
            status_code=502,
            content={"success": False, "message": f"Error from planning orchestrator: {str(e)}"}
        )
    finally:
        await fresh_client.aclose()


@app.post(
    "/v1/app/save-validated-user-stories/stream",
    tags=["Chat"],
    summary="Save Validated User Stories with SSE streaming",
    description="""
Forwards the save-validated-user-stories request to the Planning Orchestrator
and streams back SSE milestones for real-time progress tracking.
    """
)
async def save_validated_user_stories_stream(request: Request):
    """
    Forward save-validated-user-stories to Planning Orchestrator with SSE streaming.
    """
    body = await request.json()
    session_id = body.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")

    logger.info(
        "[save_validated_user_stories_stream] Forwarding SSE stream to planning orchestrator",
        session_id=session_id,
        update_count=len(body.get("update_stories", [])),
        create_count=len(body.get("create_stories", [])),
        delete_count=len(body.get("delete_stories", []))
    )

    client = get_orchestrator_client()
    url = client.get_url(OrchestratorType.PLANNING)
    if not url:
        async def error_gen():
            yield f"data: {json_module.dumps({'type': 'error', 'message': 'Planning orchestrator URL not configured'})}\n\n"

        return FastAPIStreamingResponse(
            error_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )

    async def event_generator():
        try:
            async for chunk in client._stream_with_retry(
                url=f"{url}/v1/app/save-validated-user-stories/stream",
                payload=body,
                headers=client._get_auth_headers(url),
                orchestrator_name="planning",
                session_id=session_id
            ):
                yield chunk
        except Exception as e:
            logger.error(
                "[save_validated_user_stories_stream] Stream error",
                session_id=session_id,
                error=str(e)
            )
            yield f"data: {json_module.dumps({'type': 'error', 'stage': 'error', 'title': 'Stream Error', 'message': str(e), 'icon': '❌'})}\n\n"

    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# =============================================================================
# Memory Endpoints
# =============================================================================

@app.get("/v1/memory/{session_id}", tags=["Memory"])
async def get_session_memory(session_id: str):
    """Get session memory state including routing history."""
    logger.info("[get_session_memory] Request received", session_id=session_id)
    memory = get_memory()
    context = await memory.get_full_context(session_id)
    
    result = {
        "session_id": session_id,
        "message_count": len(context.get("history", [])),
        "entities": context.get("entities", {}),
        "last_intent": context.get("last_intent"),
        "last_orchestrator": context.get("last_orchestrator"),
        "suggested_actions": context.get("suggested_actions", []),
        "context": context.get("context", {})
    }
    
    logger.info(
        "[get_session_memory] Response sent",
        session_id=session_id,
        message_count=result["message_count"],
        last_intent=result["last_intent"],
        last_orchestrator=result["last_orchestrator"]
    )
    
    return result


@app.delete("/v1/memory/{session_id}", tags=["Memory"])
async def clear_session_memory(session_id: str):
    """Clear session memory."""
    logger.info("[clear_session_memory] Request received", session_id=session_id)
    memory = get_memory()
    await memory.clear_session(session_id)
    logger.info("[clear_session_memory] Response sent", session_id=session_id, status="cleared")
    return {"status": "cleared", "session_id": session_id}


@app.get("/v1/memory/{session_id}/history", tags=["Memory"])
async def get_conversation_history(session_id: str, limit: int = 20):
    """Get conversation history with routing info."""
    logger.info("[get_conversation_history] Request received", session_id=session_id, limit=limit)
    memory = get_memory()
    history = await memory.get_conversation_history(session_id, limit=limit)
    logger.info(
        "[get_conversation_history] Response sent",
        session_id=session_id,
        message_count=len(history),
        limit=limit
    )
    return {"session_id": session_id, "messages": history, "count": len(history)}


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "[http_exception_handler] HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=str(request.url),
        method=request.method
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            details={"path": str(request.url)}
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "[general_exception_handler] Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An internal error occurred",
            details={"error": str(exc)} if settings.debug else None
        ).model_dump()
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
