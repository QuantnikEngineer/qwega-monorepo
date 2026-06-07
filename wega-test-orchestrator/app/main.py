"""
Wega Test Orchestrator - Main Application
==========================================
LangGraph-based orchestrator for test automation workflows.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any
import uuid
import asyncio

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse as FastAPIStreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.requests import (ChatRequest, LegacyAnalyzeRequest,IntentType)
from app.models.responses import (ChatResponse,LegacyAnalyzeResponse,HealthResponse,ErrorResponse,ResponseStatus,SuggestedAction)
from app.agents.graph import get_orchestrator_graph, AgentState
from app.agents.streaming_graph import execute_with_streaming
from app.memory.conversation_memory import get_memory

setup_logging()
logger = get_logger(__name__)

class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to add timeout to all requests."""
    
    def __init__(self, app, timeout: int = 600):
        super().__init__(app)
        self.timeout = timeout
        logger.info("TimeoutMiddleware initialized",timeout_seconds=timeout,timeout_minutes=timeout / 60)
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request),timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error(
                "Request timeout",
                path=str(request.url),
                method=request.method,
                timeout_seconds=self.timeout
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error_code": "REQUEST_TIMEOUT",
                    "message": f"Request timed out after {self.timeout} seconds ({self.timeout // 60} minutes)",
                    "details": {"path": str(request.url), "timeout_seconds": self.timeout}
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(
        "Starting Wega Test Orchestrator",
        version=settings.app_version,
        environment=settings.app_env,
        request_timeout_seconds=settings.request_timeout,
        agent_call_timeout_seconds=settings.agent_call_timeout,
        child_agent_streaming=settings.enable_child_agent_streaming
    )
    
    # Lazy initialization - don't block startup
    # Graph will be initialized on first request
    logger.info("Orchestrator ready (lazy initialization)")
    
    yield
    
    logger.info("Shutting down Wega Test Orchestrator")


app = FastAPI(title="Wega Test Orchestrator",
    description="""
## Test Automation Orchestrator

LangGraph-based orchestrator for test scenario and script generation.

### Supported Intents

| Intent | Description |
|--------|-------------|
| `generate_test_cases`  | Create test cases from user stories |
| `generate_test_script` | Create automation scripts from test cases |
| `generate_test_data`   | Generate test data for test cases |

### Endpoints

- `/v1/chat` - Conversational interface (recommended)
- `/api/v1/prompt/analyze` - Legacy compatibility endpoint
    """,
    version=settings.app_version,docs_url="/docs",redoc_url="/redoc",openapi_url="/openapi.json",lifespan=lifespan)

app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],expose_headers=["Cache-Control", "Connection", "X-Accel-Buffering", "Content-Type"],)
# Add timeout middleware (10 minutes default)
app.add_middleware(TimeoutMiddleware, timeout=settings.request_timeout)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(title="Wega Test Orchestrator",version=settings.app_version,description=app.description,routes=app.routes)
    openapi_schema["tags"] = [
        {"name": "Chat", "description": "Conversational interface endpoints"},
        {"name": "Legacy", "description": "Backward-compatible endpoints"},
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Memory", "description": "Session memory management"},
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema
app.openapi = custom_openapi


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint for GCP startup probe."""
    logger.info("health_check: Request received")
    response = {"status": "healthy", "service": settings.app_name}
    logger.info("health_check: Response sent", status="healthy")
    return response

@app.get("/health/detailed", response_model=HealthResponse, tags=["Health"])
async def health_check_detailed():
    """Detailed health check endpoint with component status."""
    logger.info("health_check_detailed: Request received")
    components = {
        "orchestrator": "healthy",
        "memory": "healthy",
        "llm": "unknown"
    }
    
    try:
        from app.agents.intent_classifier import get_classifier
        classifier = get_classifier()
        components["llm"] = "healthy" if classifier._llm_type != "fallback" else "degraded"
    except Exception as e:
        logger.error("LLM health check failed", error=str(e), error_type=type(e).__name__)
        components["llm"] = "unhealthy"
    
    response = HealthResponse(
        status="healthy" if all(v != "unhealthy" for v in components.values()) else "degraded",
        timestamp=datetime.utcnow(),
        service=settings.app_name,
        version=settings.app_version,
        components=components
    )
    logger.info("health_check_detailed: Response sent", status=response.status, components=components)
    return response


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    logger.info("root: Request received")
    response = {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }
    logger.info("root: Response sent", service=settings.app_name)
    return response


@app.post("/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """Main chat endpoint for test orchestration."""
    logger.info("Chat request received",session_id=request.session_id,message_preview=request.message[:50] if request.message else "")
    logger.debug(
        "Chat request payload",
        session_id=request.session_id,
        message=request.message,
        context=request.context,
        explicit_intent=request.explicit_intent,
        history_count=len(request.history) if request.history else 0)

    try:
        graph = get_orchestrator_graph()
        
        initial_state: AgentState = {
            "session_id": request.session_id,
            "messages": [{"role": m.role, "content": m.content} for m in (request.history or [])],
            "current_message": request.message,
            "intent": None,
            "entities": request.context.get("entities", {}) if request.context else {},
            "context": request.context or {},
            "pending_actions": [],
            "current_action": None,
            "action_results": [],
            "response": None,
            "error": None,
            "suggested_actions": [],
            "metadata": {
                "start_time": datetime.utcnow().isoformat(),
                "explicit_intent": request.explicit_intent
            }
        }
        
        logger.debug("Initial state prepared", session_id=request.session_id, initial_state=initial_state)
        
        if request.explicit_intent:
            initial_state["context"]["explicit_intent"] = request.explicit_intent
        
        config = {"configurable": {"thread_id": request.session_id}}
        logger.debug("Invoking graph", session_id=request.session_id, config=config)
        final_state = await graph.ainvoke(initial_state, config)
        logger.debug("Graph execution completed", session_id=request.session_id, final_state=final_state)
        
        # Check if validation is required (missing required inputs)
        metadata = final_state.get("metadata", {})
        if metadata.get("validation_required"):
            # Return validation response with nextagentflow at root level
            response = ChatResponse(
                session_id=request.session_id,
                message=metadata.get("validation_message", "Please provide required inputs"),
                status=ResponseStatus.SUCCESS,  # Not an error, just needs more input
                nextagentflow=metadata.get("nextagentflow"),
                data={
                    "intent": final_state["intent"].intent.value if final_state.get("intent") else None,
                    "entities": final_state.get("entities", {}),
                    "validation_required": True,
                    "missing_fields": metadata.get("missing_fields", [])
                },
                suggested_actions=[],
                metadata={k: v for k, v in metadata.items() if k != "nextagentflow"}
            )
        else:
            # Extract test_scripts and push_results from action_results
            test_scripts = None
            push_results = None
            for action_result in final_state.get("action_results", []):
                if action_result.get("success") and action_result.get("result"):
                    result_data = action_result["result"]
                    test_scripts = result_data.get("test_scripts") or test_scripts
                    push_results = result_data.get("push_results") or push_results
            
            # Build normal response
            response = ChatResponse(
                session_id=request.session_id,
                message=final_state.get("response", "I've processed your request."),
                status=ResponseStatus.ERROR if final_state.get("error") else ResponseStatus.SUCCESS,
                nextagentflow=None,
                data={
                    "intent": final_state["intent"].intent.value if final_state.get("intent") else None,
                    "entities": final_state.get("entities", {}),
                    "action_results": final_state.get("action_results", []),
                    "test_scripts": test_scripts,
                    "push_results": push_results,
                },
                suggested_actions=[
                    SuggestedAction(action=sa["action"], intent=sa.get("intent"))
                    for sa in final_state.get("suggested_actions", [])
                ],
                metadata=metadata
            )
        
        logger.info(
            "Chat response sent",
            session_id=request.session_id,
            status=response.status.value,
            intent=final_state["intent"].intent.value if final_state.get("intent") else None
        )
        logger.debug(
            "Chat response payload",
            session_id=request.session_id,
            response_message=response.message,
            response_data=response.data,
            suggested_actions=[sa.action for sa in response.suggested_actions]
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "Chat processing error",
            error=str(e),
            error_type=type(e).__name__,
            session_id=request.session_id,
            exc_info=True
        )
        error_response = ChatResponse(
            session_id=request.session_id,
            message=f"I encountered an error: {str(e)}",
            status=ResponseStatus.ERROR,
            metadata={"error": str(e)}
        )
        logger.debug("Error response payload", session_id=request.session_id, error_response=error_response.model_dump())
        return error_response


@app.post("/v1/chat/simple", tags=["Chat"])
async def simple_chat(message: str = Body(..., embed=True)):
    """Simple chat endpoint with auto-generated session."""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    logger.info("simple_chat: Request received", session_id=session_id, message_preview=message[:50] if message else "")
    request = ChatRequest(session_id=session_id, message=message)
    response = await chat(request)
    logger.info("simple_chat: Response sent", session_id=session_id, status=response.status.value)
    return response


@app.post("/v1/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint with real-time milestone updates.
    
    Returns Server-Sent Events showing progress stages:
    - thinking, analyzing, planning, executing, complete
    """
    logger.info(
        "chat_stream: Request received",
        session_id=request.session_id,
        message_preview=request.message[:50] if request.message else ""
    )
    logger.debug(
        "Streaming chat request payload",
        session_id=request.session_id,
        message=request.message,
        context=request.context,
        explicit_intent=request.explicit_intent,
        history_count=len(request.history) if request.history else 0
    )
    
    async def event_generator():
        event_count = 0
        try:
            async for event in execute_with_streaming(
                session_id=request.session_id,
                message=request.message,
                context=request.context,
                history=[{"role": m.role, "content": m.content} for m in (request.history or [])],
                explicit_intent=request.explicit_intent
            ):
                event_count += 1
                logger.debug(
                    "SSE event emitted",
                    session_id=request.session_id,
                    event_number=event_count,
                    event_preview=event[:200] if event else ""
                )
                yield event
            logger.info(
                "chat_stream: Response sent - streaming completed",
                session_id=request.session_id,
                total_events=event_count
            )
        except Exception as e:
            logger.error(
                "SSE streaming error",
                session_id=request.session_id,
                error=str(e),
                error_type=type(e).__name__,
                events_emitted=event_count,
                exc_info=True
            )
            raise
    
    logger.debug("Starting SSE stream", session_id=request.session_id)
    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/prompt/analyze", response_model=LegacyAnalyzeResponse, tags=["Legacy"])
async def analyze_prompt_legacy(request: LegacyAnalyzeRequest):
    """Legacy analyze endpoint for backward compatibility."""
    logger.info(
        "Legacy analyze request received",
        query=request.query_text[:50] if request.query_text else "",
        nextagentflow=request.nextagentflow
    )
    logger.debug(
        "Legacy analyze request payload",
        query_text=request.query_text,
        nextagentflow=request.nextagentflow,
        create_user_story_text=request.create_user_story_text,
        test_scenarios=request.test_scenarios,
        test_cases=request.test_cases,
        framework_type=request.framework_type,
        language=request.language,
        script_generation_type=request.script_generation_type,
        scenario_types=request.scenario_types
    )
    
    try:
        session_id = f"legacy_{uuid.uuid4().hex[:12]}"
        context = {}
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
        if request.scenario_types:
            context["scenario_types"] = request.scenario_types
        logger.debug("Built context for legacy request", session_id=session_id, context=context)
        chat_request = ChatRequest(
            session_id=session_id,
            message=request.query_text,
            context=context,
            explicit_intent=request.nextagentflow
        )
        chat_response = await chat(chat_request)
        intent = chat_response.data.get("intent") if chat_response.data else None
        response = LegacyAnalyzeResponse(
            success=chat_response.status == ResponseStatus.SUCCESS,
            result=chat_response.data,
            message=chat_response.message,
            error=chat_response.metadata.get("error") if chat_response.metadata else None,
            nextagentflow=_map_intent_to_nextagentflow(intent),
            next_suggested_action=chat_response.suggested_actions[0].action if chat_response.suggested_actions else None,
            nextuserflow="",
            updatedNextQuery=""
        )
        logger.info("Legacy analyze response sent",session_id=session_id,success=response.success,nextagentflow=response.nextagentflow)
        logger.debug("Legacy analyze response payload", session_id=session_id, response=response.model_dump())
        return response
        
    except Exception as e:
        logger.error(
            "Legacy analyze error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        error_response = LegacyAnalyzeResponse(success=False,error=str(e),message=f"Error: {str(e)}")
        logger.debug("Legacy analyze error response payload", error_response=error_response.model_dump())
        return error_response

def _map_intent_to_nextagentflow(intent: Optional[str]) -> Optional[str]:
    """Map intent types to legacy nextagentflow values."""
    if not intent:
        return None
    mapping = {
        "generate_test_cases": "confirmedUserStoryToTestScenario",
        "generate_test_script": "confirmedTestCaseToTestScript",
    }
    return mapping.get(intent)

@app.get("/v1/memory/{session_id}", tags=["Memory"])
async def get_session_memory(session_id: str):
    """Get session memory state."""
    logger.info("get_session_memory: Request received", session_id=session_id)
    memory = get_memory()
    context = await memory.get_full_context(session_id)
    response = {
        "session_id": session_id,
        "message_count": len(context.get("history", [])),
        "entities": context.get("entities", {}),
        "last_intent": context.get("last_intent"),
        "context": context.get("context", {})
    }
    logger.info("get_session_memory: Response sent", session_id=session_id, message_count=response["message_count"])
    return response

@app.delete("/v1/memory/{session_id}", tags=["Memory"])
async def clear_session_memory(session_id: str):
    """Clear session memory."""
    logger.info("clear_session_memory: Request received", session_id=session_id)
    memory = get_memory()
    await memory.clear_session(session_id)
    response = {"status": "cleared", "session_id": session_id}
    logger.info("clear_session_memory: Response sent - memory cleared", session_id=session_id)
    return response

@app.get("/v1/memory/{session_id}/history", tags=["Memory"])
async def get_conversation_history(session_id: str, limit: int = 20):
    """Get conversation history."""
    logger.info("get_conversation_history: Request received", session_id=session_id, limit=limit)
    memory = get_memory()
    history = await memory.get_conversation_history(session_id, limit=limit)
    response = {"session_id": session_id, "messages": history, "count": len(history)}
    logger.info("get_conversation_history: Response sent", session_id=session_id, message_count=response["count"])
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=str(request.url),
        method=request.method
    )
    error_response = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        details={"path": str(request.url)}
    )
    logger.debug("HTTP exception response", error_response=error_response.model_dump())
    return JSONResponse(status_code=exc.status_code,content=error_response.model_dump())

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url),
        method=request.method,exc_info=True)
    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An internal error occurred",
        details={"error": str(exc)} if settings.debug else None
    )
    logger.debug("General exception response", error_response=error_response.model_dump())
    return JSONResponse(status_code=500,content=error_response.model_dump())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app",host=settings.host,port=settings.port,reload=settings.debug,log_level=settings.log_level.lower())
