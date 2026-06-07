"""
Wega Common Integration Service - Main Application
===================================================
LangGraph-based orchestrator for context enrichment operations.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
import asyncio

from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse as FastAPIStreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware
import json as json_module

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.requests import (
    ChatRequest,
    LegacyAnalyzeRequest,
    IntentType,
    QueryRequest,
    FeedbackRequest
)
from app.models.responses import (
    ChatResponse,
    LegacyAnalyzeResponse,
    HealthResponse,
    ErrorResponse,
    ResponseStatus,
    SuggestedAction
)
from app.agents.graph import get_orchestrator_graph, AgentState
from app.agents.streaming_graph import execute_with_streaming
from app.memory.conversation_memory import get_memory
from app.tools.rag_client import get_rag_client

setup_logging()
logger = get_logger(__name__)

FILE_NAME = "main.py"


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to add timeout to all requests."""
    
    def __init__(self, app, timeout: int = 600):
        super().__init__(app)
        self.timeout = timeout
        logger.info(
            f"[{FILE_NAME}] TimeoutMiddleware initialized",
            timeout_seconds=timeout,
            timeout_minutes=timeout / 60
        )
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{FILE_NAME}] Request timeout",
                path=str(request.url),
                method=request.method,
                timeout_seconds=self.timeout
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error_code": "REQUEST_TIMEOUT",
                    "message": f"Request timed out after {self.timeout} seconds",
                    "details": {"path": str(request.url), "timeout_seconds": self.timeout}
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(
        f"[{FILE_NAME}] Starting Wega Common Integration Service",
        version=settings.app_version,
        environment=settings.app_env,
        rag_agent_url=settings.rag_agent_url
    )
    
    logger.info(f"[{FILE_NAME}] Orchestrator ready (lazy initialization)")
    
    yield
    
    # Cleanup
    rag_client = get_rag_client()
    await rag_client.close()
    logger.info(f"[{FILE_NAME}] Shutting down Wega Common Integration Service")


app = FastAPI(
    title="Wega Common Integration Service",
    description="""
## Common Integration Service

LangGraph-based orchestrator for context enrichment operations.

### Supported Intents

| Intent | Description |
|--------|-------------|
| `context_enrich_upload` | Upload documents to knowledge base |
| `context_enrich_ingest` | Ingest content from websites, SharePoint, repos |
| `context_enrich_feedback` | Submit feedback (ratings, corrections, preferences) |
| `context_enrich_query` | Query the knowledge base |

### Endpoints

- `/chat` - Non-streaming chat endpoint
- `/chat/stream` - Streaming chat endpoint with SSE

### Optional Parameters

- `selected_model` - Optional model selection passed to downstream APIs
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cache-Control", "Connection", "X-Accel-Buffering", "Content-Type"],
)

app.add_middleware(TimeoutMiddleware, timeout=settings.request_timeout)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Wega Common Integration Service",
        version=settings.app_version,
        description=app.description,
        routes=app.routes,
    )
    
    openapi_schema["tags"] = [
        {"name": "Chat", "description": "Conversational interface endpoints"},
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

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint for GCP startup probe."""
    logger.info(f"[{FILE_NAME}] health_check: ENTRY")
    response = {"status": "healthy", "service": settings.app_name}
    logger.info(f"[{FILE_NAME}] health_check: EXIT", status="healthy")
    return response


@app.get("/health/detailed", response_model=HealthResponse, tags=["Health"])
async def health_check_detailed():
    """Detailed health check with RAG Agent status."""
    logger.info(f"[{FILE_NAME}] health_check_detailed: ENTRY")
    
    components = {
        "orchestrator": "healthy",
        "memory": "healthy",
        "llm": "unknown",
        "rag_agent": "unknown"
    }
    
    try:
        from app.agents.intent_classifier import get_classifier
        classifier = get_classifier()
        components["llm"] = "healthy" if classifier._llm_type != "fallback" else "degraded"
    except Exception as e:
        logger.error(f"[{FILE_NAME}] LLM health check failed", error=str(e))
        components["llm"] = "unhealthy"
    
    try:
        rag_client = get_rag_client()
        rag_health = await rag_client.check_health()
        components["rag_agent"] = rag_health.get("status", "unknown")
    except Exception as e:
        logger.error(f"[{FILE_NAME}] RAG Agent health check failed", error=str(e))
        components["rag_agent"] = "unhealthy"
    
    overall_status = "healthy"
    if any(v == "unhealthy" for v in components.values()):
        overall_status = "degraded"
    
    response = HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        service=settings.app_name,
        version=settings.app_version,
        components=components
    )
    
    logger.info(f"[{FILE_NAME}] health_check_detailed: EXIT", status=overall_status, components=components)
    return response


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    logger.info(f"[{FILE_NAME}] root: ENTRY")
    response = {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }
    logger.info(f"[{FILE_NAME}] root: EXIT")
    return response


# =============================================================================
# Chat Endpoints
# =============================================================================

@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Non-streaming chat endpoint",
    description="""
Process context enrichment requests without streaming.

Supports both JSON and multipart/form-data requests:
- JSON: Standard chat requests
- Multipart/form-data: File uploads for context_enrich_upload

**Request Body:**
- `session_id` (required): Unique session identifier
- `message` (required): User's natural language message
- `context`: Additional context (files, source info, query params)
- `history`: Previous conversation messages
- `explicit_intent`: Override intent classification
- `selected_model`: Optional model selection for downstream APIs
    """
)
async def chat(request: Request):
    """Main chat endpoint for context enrichment operations."""
    logger.info(f"[{FILE_NAME}] chat: ENTRY", content_type=request.headers.get("content-type", ""))
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        return await _handle_multipart_chat(request)
    else:
        body = await request.json()
        chat_request = ChatRequest(**body)
        return await _process_chat(chat_request)


async def _handle_multipart_chat(request: Request):
    """Handle multipart/form-data chat requests with file uploads."""
    logger.info(f"[{FILE_NAME}] _handle_multipart_chat: ENTRY")
    
    form = await request.form()
    
    session_id = form.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")
    message = form.get("message", "")
    context_str = form.get("context", "{}")
    explicit_intent = form.get("explicit_intent")
    selected_model = form.get("selected_model")
    
    try:
        context = json_module.loads(context_str) if isinstance(context_str, str) and context_str else {}
    except json_module.JSONDecodeError:
        context = {}
    
    if selected_model:
        context["selected_model"] = selected_model
    
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
        f"[{FILE_NAME}] _handle_multipart_chat: Files collected",
        session_id=session_id,
        file_count=len(files),
        file_names=[f["filename"] for f in files]
    )
    
    if files:
        context["files"] = files
        if not explicit_intent:
            explicit_intent = "context_enrich_upload"
    
    chat_request = ChatRequest(
        session_id=session_id,
        message=message or "Upload files to knowledge base",
        context=context,
        explicit_intent=explicit_intent,
        selected_model=selected_model
    )
    
    logger.info(f"[{FILE_NAME}] _handle_multipart_chat: EXIT")
    return await _process_chat(chat_request)


async def _process_chat(request: ChatRequest) -> ChatResponse:
    """Process chat request."""
    logger.info(
        f"[{FILE_NAME}] _process_chat: ENTRY",
        session_id=request.session_id,
        message_preview=request.message[:50] if request.message else "",
        explicit_intent=request.explicit_intent,
        selected_model=request.selected_model
    )
    
    try:
        graph = get_orchestrator_graph()
        
        context = request.context or {}
        if request.selected_model:
            context["selected_model"] = request.selected_model
        
        initial_state: AgentState = {
            "session_id": request.session_id,
            "messages": [{"role": m.role, "content": m.content} for m in (request.history or [])],
            "current_message": request.message,
            "intent": None,
            "entities": context.get("entities", {}),
            "context": context,
            "pending_actions": [],
            "current_action": None,
            "action_results": [],
            "response": None,
            "error": None,
            "suggested_actions": [],
            "metadata": {
                "start_time": datetime.utcnow().isoformat(),
                "explicit_intent": request.explicit_intent,
                "selected_model": request.selected_model
            }
        }
        
        if request.explicit_intent:
            initial_state["context"]["explicit_intent"] = request.explicit_intent
        
        config = {"configurable": {"thread_id": request.session_id}}
        final_state = await graph.ainvoke(initial_state, config)
        
        response = ChatResponse(
            session_id=request.session_id,
            message=final_state.get("response", "Request processed."),
            status=ResponseStatus.ERROR if final_state.get("error") else ResponseStatus.SUCCESS,
            nextagentflow=_map_intent_to_nextagentflow(
                final_state["intent"].intent.value if final_state.get("intent") else None
            ),
            data={
                "intent": final_state["intent"].intent.value if final_state.get("intent") else None,
                "entities": final_state.get("entities", {}),
                "action_results": final_state.get("action_results", []),
            },
            suggested_actions=[
                SuggestedAction(action=sa["action"], intent=sa.get("intent"))
                for sa in final_state.get("suggested_actions", [])
            ],
            metadata=final_state.get("metadata", {})
        )
        
        logger.info(
            f"[{FILE_NAME}] _process_chat: EXIT",
            session_id=request.session_id,
            status=response.status.value,
            intent=final_state["intent"].intent.value if final_state.get("intent") else None
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"[{FILE_NAME}] _process_chat: ERROR",
            session_id=request.session_id,
            error=str(e),
            error_type=type(e).__name__
        )
        return ChatResponse(
            session_id=request.session_id,
            message=f"Error processing request: {str(e)}",
            status=ResponseStatus.ERROR,
            metadata={"error": str(e)}
        )


@app.post("/v1/chat/simple", tags=["Chat"])
async def simple_chat(message: str = Body(..., embed=True)):
    """Simple chat endpoint with auto-generated session."""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{FILE_NAME}] simple_chat: ENTRY", session_id=session_id, message_preview=message[:50] if message else "")
    request = ChatRequest(session_id=session_id, message=message)
    response = await _process_chat(request)
    logger.info(f"[{FILE_NAME}] simple_chat: EXIT", session_id=session_id, status=response.status.value)
    return response


@app.post(
    "/v1/chat/stream",
    tags=["Chat"],
    summary="Streaming chat endpoint",
    description="""
Process context enrichment requests with SSE streaming progress updates.

Supports both JSON and multipart/form-data requests:
- JSON: Standard chat requests
- Multipart/form-data: File uploads for context_enrich_upload

Returns Server-Sent Events showing progress stages:
- received, thinking, analyzing, executing, complete

**Request Body:**
- `session_id` (required): Unique session identifier
- `message` (required): User's natural language message
- `context`: Additional context (files, source info, query params)
- `history`: Previous conversation messages
- `explicit_intent`: Override intent classification
- `selected_model`: Optional model selection for downstream APIs
    """
)
async def chat_stream(request: Request):
    """Streaming chat endpoint with real-time milestone updates."""
    logger.info(f"[{FILE_NAME}] chat_stream: ENTRY", content_type=request.headers.get("content-type", ""))
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        return await _handle_multipart_stream(request)
    else:
        body = await request.json()
        chat_request = ChatRequest(**body)
        print(f"\n{'='*60}\n[CHAT_STREAM] Request received: session={chat_request.session_id}, intent={chat_request.explicit_intent}\n{'='*60}\n", flush=True)
        return await _process_chat_stream(chat_request)


async def _handle_multipart_stream(request: Request):
    """Handle multipart/form-data streaming requests."""
    logger.info(f"[{FILE_NAME}] _handle_multipart_stream: ENTRY")
    
    form = await request.form()
    
    session_id = form.get("session_id", f"sess_{uuid.uuid4().hex[:12]}")
    message = form.get("message", "")
    context_str = form.get("context", "{}")
    explicit_intent = form.get("explicit_intent")
    selected_model = form.get("selected_model")
    
    try:
        context = json_module.loads(context_str) if isinstance(context_str, str) and context_str else {}
    except json_module.JSONDecodeError:
        context = {}
    
    if selected_model:
        context["selected_model"] = selected_model
    
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
    
    if files:
        context["files"] = files
        if not explicit_intent:
            explicit_intent = "context_enrich_upload"
    
    chat_request = ChatRequest(
        session_id=session_id,
        message=message or "Upload files to knowledge base",
        context=context,
        explicit_intent=explicit_intent,
        selected_model=selected_model
    )
    
    logger.info(f"[{FILE_NAME}] _handle_multipart_stream: EXIT")
    return await _process_chat_stream(chat_request)


async def _process_chat_stream(request: ChatRequest):
    """Process streaming chat request."""
    logger.info(
        f"[{FILE_NAME}] _process_chat_stream: ENTRY",
        session_id=request.session_id,
        message_preview=request.message[:50] if request.message else "",
        selected_model=request.selected_model
    )
    
    context = request.context or {}
    if request.selected_model:
        context["selected_model"] = request.selected_model
    
    async def event_generator():
        event_count = 0
        try:
            async for event in execute_with_streaming(
                session_id=request.session_id,
                message=request.message,
                context=context,
                history=[{"role": m.role, "content": m.content} for m in (request.history or [])],
                explicit_intent=request.explicit_intent
            ):
                event_count += 1
                logger.debug(
                    f"[{FILE_NAME}] SSE event emitted",
                    session_id=request.session_id,
                    event_number=event_count
                )
                yield event
            
            logger.info(
                f"[{FILE_NAME}] _process_chat_stream: EXIT - streaming completed",
                session_id=request.session_id,
                total_events=event_count
            )
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] SSE streaming error",
                session_id=request.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def _map_intent_to_nextagentflow(intent: Optional[str]) -> Optional[str]:
    """Map intent types to nextagentflow values."""
    if not intent:
        return None
    
    mapping = {
        "context_enrich_upload": "confirmedContextEnrichUpload",
        "context_enrich_ingest": "confirmedContextEnrichIngest",
        "context_enrich_feedback": "confirmedContextEnrichFeedback",
        "context_enrich_query": "confirmedContextEnrichQuery",
    }
    
    return mapping.get(intent)


# =============================================================================
# Legacy Endpoints
# =============================================================================

@app.post("/api/v1/prompt/analyze", response_model=LegacyAnalyzeResponse, tags=["Legacy"])
async def analyze_prompt_legacy(request: LegacyAnalyzeRequest):
    """Legacy analyze endpoint for backward compatibility."""
    logger.info(
        f"[{FILE_NAME}] analyze_prompt_legacy: ENTRY",
        query_preview=request.query_text[:50] if request.query_text else "",
        nextagentflow=request.nextagentflow,
        selected_model=request.selected_model
    )
    
    try:
        session_id = f"legacy_{uuid.uuid4().hex[:12]}"
        
        context = {}
        if request.selected_model:
            context["selected_model"] = request.selected_model
        
        chat_request = ChatRequest(
            session_id=session_id,
            message=request.query_text,
            context=context,
            explicit_intent=request.nextagentflow,
            selected_model=request.selected_model
        )
        
        chat_response = await _process_chat(chat_request)
        
        response = LegacyAnalyzeResponse(
            success=chat_response.status == ResponseStatus.SUCCESS,
            result=chat_response.data,
            message=chat_response.message,
            error=chat_response.metadata.get("error") if chat_response.metadata else None,
            nextagentflow=chat_response.nextagentflow,
            next_suggested_action=chat_response.suggested_actions[0].action if chat_response.suggested_actions else None
        )
        
        logger.info(
            f"[{FILE_NAME}] analyze_prompt_legacy: EXIT",
            session_id=session_id,
            success=response.success,
            nextagentflow=response.nextagentflow
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"[{FILE_NAME}] analyze_prompt_legacy: ERROR",
            error=str(e),
            error_type=type(e).__name__
        )
        return LegacyAnalyzeResponse(
            success=False,
            error=str(e),
            message=f"Error: {str(e)}"
        )


# =============================================================================
# Memory Endpoints
# =============================================================================

@app.get("/v1/memory/{session_id}", tags=["Memory"])
async def get_session_memory(session_id: str):
    """Get session memory state."""
    logger.info(f"[{FILE_NAME}] get_session_memory: ENTRY", session_id=session_id)
    
    memory = get_memory()
    context = await memory.get_full_context(session_id)
    
    response = {
        "session_id": session_id,
        "message_count": len(context.get("history", [])),
        "entities": context.get("entities", {}),
        "last_intent": context.get("last_intent"),
        "context": context.get("context", {})
    }
    
    logger.info(f"[{FILE_NAME}] get_session_memory: EXIT", session_id=session_id)
    return response


@app.delete("/v1/memory/{session_id}", tags=["Memory"])
async def clear_session_memory(session_id: str):
    """Clear session memory."""
    logger.info(f"[{FILE_NAME}] clear_session_memory: ENTRY", session_id=session_id)
    
    memory = get_memory()
    await memory.clear_session(session_id)
    
    logger.info(f"[{FILE_NAME}] clear_session_memory: EXIT", session_id=session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/v1/memory/{session_id}/history", tags=["Memory"])
async def get_conversation_history(session_id: str, limit: int = 20):
    """Get conversation history."""
    logger.info(f"[{FILE_NAME}] get_conversation_history: ENTRY", session_id=session_id, limit=limit)
    
    memory = get_memory()
    history = await memory.get_conversation_history(session_id, limit=limit)
    
    logger.info(f"[{FILE_NAME}] get_conversation_history: EXIT", session_id=session_id, count=len(history))
    return {"session_id": session_id, "messages": history, "count": len(history)}


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        f"[{FILE_NAME}] http_exception_handler",
        status_code=exc.status_code,
        detail=exc.detail,
        path=str(request.url)
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
    """Handle general exceptions."""
    logger.error(
        f"[{FILE_NAME}] general_exception_handler",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url)
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
