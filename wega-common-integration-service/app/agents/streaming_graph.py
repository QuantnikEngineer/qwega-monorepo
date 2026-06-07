"""
Streaming Graph
===============
Graph with milestone streaming for real-time progress updates.
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import asyncio

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType, IngestSource, FeedbackType
from app.models.streaming import (
    MilestoneEvent, CommonIntegrationMilestones, StreamingResponse, StreamingError, MilestoneStage, HeartbeatEvent
)
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory
from app.tools.rag_client import get_rag_client

logger = get_logger(__name__)

FILE_NAME = "streaming_graph.py"

# Heartbeat interval in seconds (send keep-alive during long operations)
# Uses config value or defaults to 15 seconds
HEARTBEAT_INTERVAL = settings.sse_heartbeat_interval


# Hostnames recognised as code-repository platforms. When source="website" is
# received but a URL points at one of these hosts, we fall back to source="repo"
# so the RAG backend uses RepositoryConnector (GitHub/Harness API) instead of
# raw HTML scraping. Defense-in-depth alongside the frontend's own detection.
_REPO_HOST_SUFFIXES = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "dev.azure.com",
    "visualstudio.com",
    "harness.io",
)


def _is_repo_url(raw: str) -> bool:
    try:
        from urllib.parse import urlparse
        u = urlparse(raw)
        host = (u.hostname or "").lower()
        if not host:
            return False
        if not any(host == s or host.endswith("." + s) for s in _REPO_HOST_SUFFIXES):
            return False
        parts = [p for p in (u.path or "").strip("/").split("/") if p]
        if host.endswith("harness.io"):
            return "repos" in parts or len(parts) >= 4
        return len(parts) >= 2
    except Exception:
        return False


def create_heartbeat(session_id: str) -> str:
    """Create a heartbeat SSE event to keep the connection alive."""
    logger.debug(f"[{FILE_NAME}] Emitting heartbeat", session_id=session_id)
    return HeartbeatEvent(session_id=session_id).to_sse()


async def execute_with_heartbeat(
    coro,
    session_id: str,
    heartbeat_interval: float = None
):
    """
    Execute a coroutine while yielding heartbeats to keep the SSE connection alive.
    
    Args:
        coro: The coroutine to execute
        session_id: Session ID for heartbeat events
        heartbeat_interval: Seconds between heartbeats (defaults to HEARTBEAT_INTERVAL)
        
    Yields:
        Heartbeat SSE events while waiting, then the final result
    """
    interval = heartbeat_interval or HEARTBEAT_INTERVAL
    task = asyncio.create_task(coro)
    heartbeat_count = 0
    
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=interval)
        except asyncio.TimeoutError:
            # Task still running, emit heartbeat to keep connection alive
            heartbeat_count += 1
            logger.info(
                f"[{FILE_NAME}] execute_with_heartbeat: Emitting heartbeat #{heartbeat_count}",
                session_id=session_id,
                interval=interval
            )
            yield create_heartbeat(session_id)
        except asyncio.CancelledError:
            # Request was cancelled, cancel the task and re-raise
            task.cancel()
            logger.warning(f"[{FILE_NAME}] execute_with_heartbeat: Cancelled", session_id=session_id)
            raise
    
    # Task completed, get the result
    try:
        result = task.result()
        logger.info(
            f"[{FILE_NAME}] execute_with_heartbeat: Task completed",
            session_id=session_id,
            total_heartbeats=heartbeat_count
        )
        yield result
    except Exception as e:
        logger.error(
            f"[{FILE_NAME}] execute_with_heartbeat: Task failed",
            session_id=session_id,
            error=str(e)
        )
        raise



async def execute_with_streaming(
    session_id: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    explicit_intent: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Execute orchestration with streaming milestones.
    
    Args:
        session_id: Session identifier
        message: User message
        context: Additional context (including selected_model)
        history: Conversation history
        explicit_intent: Explicit intent override
        
    Yields:
        SSE formatted milestone events
    """
    start_time = datetime.utcnow()
    context = context or {}
    history = history or []
    selected_model = context.get("selected_model")
    
    logger.info(
        f"[{FILE_NAME}] execute_with_streaming: ENTRY",
        session_id=session_id,
        message_preview=message[:50] if message else "",
        selected_model=selected_model
    )
    
    state = {
        "session_id": session_id,
        "messages": history,
        "current_message": message,
        "intent": None,
        "entities": context.get("entities", {}),
        "context": context,
        "pending_actions": [],
        "action_results": [],
        "response": None,
        "error": None,
        "suggested_actions": [],
        "metadata": {},
    }
    
    rag_client = get_rag_client()
    
    try:
        # === MILESTONE: Request Received ===
        logger.debug(f"[{FILE_NAME}] SSE milestone: request_received", session_id=session_id)
        yield CommonIntegrationMilestones.received(session_id).to_sse()
        await asyncio.sleep(0.3)
        
        # === MILESTONE: Thinking ===
        logger.debug(f"[{FILE_NAME}] SSE milestone: thinking", session_id=session_id)
        yield CommonIntegrationMilestones.thinking(message[:50]).to_sse()
        
        # Retrieve memory
        memory = get_memory()
        stored_entities = await memory.get_entities(session_id)
        state["entities"] = {**stored_entities, **state["entities"]}
        
        full_context = await memory.get_full_context(session_id)
        state["context"]["suggested_actions"] = full_context.get("suggested_actions", [])
        state["context"]["last_intent"] = full_context.get("last_intent")
        
        await asyncio.sleep(0.3)
        
        # === MILESTONE: Analyzing Intent ===
        logger.debug(f"[{FILE_NAME}] SSE milestone: analyzing_intent", session_id=session_id)
        yield CommonIntegrationMilestones.analyzing_intent().to_sse()
        
        # Check for explicit intent
        if explicit_intent and explicit_intent != "string":
            intent_mapping = {
                "context_enrich_upload": IntentType.CONTEXT_ENRICH_UPLOAD,
                "context_enrich_ingest": IntentType.CONTEXT_ENRICH_INGEST,
                "context_enrich_feedback": IntentType.CONTEXT_ENRICH_FEEDBACK,
                "context_enrich_query": IntentType.CONTEXT_ENRICH_QUERY,
                "context_enrich_list_documents": IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS,
            }
            intent_type = intent_mapping.get(explicit_intent.lower())
            if intent_type:
                state["intent"] = ClassifiedIntent(
                    intent=intent_type,
                    confidence=1.0,
                    reasoning="Explicit intent provided"
                )
                logger.info(
                    f"[{FILE_NAME}] Explicit intent classified",
                    session_id=session_id,
                    intent=intent_type.value
                )
        
        if not state["intent"]:
            classifier = get_classifier()
            classified = await classifier.classify(
                message=message,
                history=history,
                context=state["context"]
            )
            state["intent"] = classified
            state["entities"].update(classified.entities)
        
        yield CommonIntegrationMilestones.analyzing_intent(
            intent=state["intent"].intent.value,
            confidence=state["intent"].confidence
        ).to_sse()
        
        await memory.set_last_intent(session_id, state["intent"].intent.value)
        await asyncio.sleep(0.3)
        
        intent = state["intent"]
        
        # === Execute based on intent with heartbeat support ===
        result = None
        
        if intent.intent == IntentType.CONTEXT_ENRICH_UPLOAD:
            yield CommonIntegrationMilestones.uploading_files(
                len(context.get("files", []))
            ).to_sse()
            
            # Execute with heartbeat to keep connection alive during long uploads
            async for item in execute_with_heartbeat(
                _execute_upload_streaming(state, rag_client, selected_model),
                session_id
            ):
                if isinstance(item, str):
                    yield item  # heartbeat
                else:
                    result = item  # final result
            
        elif intent.intent == IntentType.CONTEXT_ENRICH_INGEST:
            source = context.get("source", "unknown")
            yield CommonIntegrationMilestones.ingesting(source).to_sse()
            
            # Execute with heartbeat to keep connection alive during long ingestion
            async for item in execute_with_heartbeat(
                _execute_ingest_streaming(state, rag_client, selected_model),
                session_id
            ):
                if isinstance(item, str):
                    yield item  # heartbeat
                else:
                    result = item  # final result
            
        elif intent.intent == IntentType.CONTEXT_ENRICH_FEEDBACK:
            yield CommonIntegrationMilestones.submitting_feedback().to_sse()
            
            # Execute with heartbeat to keep connection alive during feedback submission
            async for item in execute_with_heartbeat(
                _execute_feedback_streaming(state, rag_client, selected_model),
                session_id
            ):
                if isinstance(item, str):
                    yield item  # heartbeat
                else:
                    result = item  # final result
            
        elif intent.intent == IntentType.CONTEXT_ENRICH_QUERY:
            yield CommonIntegrationMilestones.querying().to_sse()
            
            # Execute with heartbeat to keep connection alive during RAG query
            async for item in execute_with_heartbeat(
                _execute_query_streaming(state, rag_client, selected_model),
                session_id
            ):
                if isinstance(item, str):
                    yield item  # heartbeat
                else:
                    result = item  # final result
            
        elif intent.intent == IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS:
            yield CommonIntegrationMilestones.executing("Fetching documents", 0.5).to_sse()
            
            # Execute with heartbeat to keep connection alive during document listing
            async for item in execute_with_heartbeat(
                _execute_list_documents_streaming(state, rag_client),
                session_id
            ):
                if isinstance(item, str):
                    yield item  # heartbeat
                else:
                    result = item  # final result
            
        elif intent.intent == IntentType.GENERAL_QUESTION:
            yield CommonIntegrationMilestones.executing("Generating help response", 0.5).to_sse()
            result = _generate_help_response_streaming(state)
            
        elif intent.intent == IntentType.CONFIRMATION:
            yield CommonIntegrationMilestones.executing("Processing confirmation", 0.5).to_sse()
            result = _handle_confirmation_streaming(state)
            
        else:
            yield CommonIntegrationMilestones.executing("Requesting clarification", 0.5).to_sse()
            result = _request_clarification_streaming(state)
        
        state["action_results"].append(result)
        
        if not result.get("success"):
            state["error"] = result.get("error", "Action failed")
        
        # Store to memory
        await memory.add_message(session_id, "user", message)
        
        if state["response"]:
            await memory.add_message(
                session_id,
                "assistant",
                state["response"],
                metadata={"intent": state["intent"].intent.value if state["intent"] else None}
            )
        
        await memory.set_entities(session_id, state["entities"])
        
        if state["suggested_actions"]:
            await memory.set_suggested_actions(session_id, state["suggested_actions"])
        
        # === MILESTONE: Complete ===
        logger.debug(f"[{FILE_NAME}] SSE milestone: complete", session_id=session_id)
        
        # Map intent to nextagentflow for frontend state management
        intent_to_nextagentflow = {
            "context_enrich_upload": "confirmedContextEnrichUpload",
            "context_enrich_ingest": "confirmedContextEnrichIngest",
            "context_enrich_feedback": "confirmedContextEnrichFeedback",
            "context_enrich_query": "confirmedContextEnrichQuery",
            "context_enrich_list_documents": "confirmedContextEnrichListDocuments",
        }
        current_intent = state["intent"].intent.value if state["intent"] else None
        nextagentflow = intent_to_nextagentflow.get(current_intent)
        
        final_response = StreamingResponse(
            session_id=session_id,
            message=state["response"] or "Request processed.",
            status="success" if not state["error"] else "error",
            nextagentflow=nextagentflow,
            data={
                "intent": state["intent"].intent.value if state["intent"] else None,
                "entities": state["entities"],
                "action_results": state["action_results"]
            },
            suggested_actions=state["suggested_actions"],
            metadata={
                "start_time": start_time.isoformat(),
                "end_time": datetime.utcnow().isoformat(),
                "selected_model": selected_model
            }
        )
        yield final_response.to_sse()
        
        logger.info(
            f"[{FILE_NAME}] execute_with_streaming: EXIT",
            session_id=session_id,
            status="success" if not state["error"] else "error"
        )
        
    except Exception as e:
        logger.error(
            f"[{FILE_NAME}] execute_with_streaming: ERROR",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__
        )
        yield CommonIntegrationMilestones.error(str(e)).to_sse()


async def _execute_upload_streaming(state: Dict, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute file upload with streaming updates."""
    logger.info(f"[{FILE_NAME}] _execute_upload_streaming: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    files = context.get("files", [])
    if not files:
        state["response"] = "No files provided for upload. Please include files in the request."
        state["suggested_actions"] = [
            {"action": "Upload documents", "intent": "context_enrich_upload"}
        ]
        logger.warning(f"[{FILE_NAME}] _execute_upload_streaming: EXIT - No files")
        return {"success": False, "error": "No files provided"}
    
    try:
        response = await rag_client.upload_files(files, selected_model, project_name=context.get("project_name"))
        
        state["response"] = response.message
        state["suggested_actions"] = [
            {"action": "Query the knowledge base", "intent": "context_enrich_query"},
            {"action": "Upload more documents", "intent": "context_enrich_upload"}
        ]
        
        logger.info(f"[{FILE_NAME}] _execute_upload_streaming: EXIT - Success")
        return {
            "success": True,
            "result": {
                "documents": [doc.model_dump() for doc in response.documents],
                "skipped": response.skipped,
                "message": response.message
            }
        }
    except Exception as e:
        state["response"] = f"Upload failed: {str(e)}"
        logger.error(f"[{FILE_NAME}] _execute_upload_streaming: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_ingest_streaming(state: Dict, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute content ingestion with streaming updates."""
    logger.info(f"[{FILE_NAME}] _execute_ingest_streaming: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    
    # DEBUG: Log the full context to understand what we received
    logger.info(
        f"[{FILE_NAME}] _execute_ingest_streaming: Context received",
        session_id=state["session_id"],
        context_keys=list(context.keys()),
        context=context
    )
    print(f"\n[INGEST_DEBUG] Full context: {context}\n", flush=True)
    
    source_str = context.get("source")
    logger.info(f"[{FILE_NAME}] _execute_ingest_streaming: Source extracted", source=source_str)
    print(f"[INGEST_DEBUG] Source: {source_str}", flush=True)
    
    if not source_str:
        state["response"] = "No ingest source specified. Please provide: website, sharepoint, repo, or agent_output."
        state["suggested_actions"] = [
            {"action": "Ingest from website", "intent": "context_enrich_ingest"},
            {"action": "Ingest from repository", "intent": "context_enrich_ingest"}
        ]
        logger.warning(f"[{FILE_NAME}] _execute_ingest_streaming: EXIT - No source")
        return {"success": False, "error": "No source provided"}
    
    try:
        source = IngestSource(source_str)
    except ValueError:
        state["response"] = f"Invalid source type: {source_str}"
        return {"success": False, "error": f"Invalid source type: {source_str}"}
    
    payload = {}
    session_id = state["session_id"]  # Get session_id from state
    
    if source == IngestSource.WEBSITE:
        urls = context.get("urls", [])
        logger.info(f"[{FILE_NAME}] _execute_ingest_streaming: Website URLs", urls=urls)
        print(f"[INGEST_DEBUG] URLs from context: {urls}", flush=True)
        if not urls:
            state["response"] = "No URLs provided for website ingestion."
            logger.warning(f"[{FILE_NAME}] _execute_ingest_streaming: No URLs in context")
            return {"success": False, "error": "No URLs provided"}

        # Server-side fallback: split off URLs that look like a code repository
        # (github.com, harness.io, gitlab.com, ...) and route them as REPO.
        repo_urls = [u for u in urls if _is_repo_url(u)]
        site_urls = [u for u in urls if not _is_repo_url(u)]

        repo_results: list = []
        repo_skipped: list = []
        repo_messages: list[str] = []

        for r_url in repo_urls:
            repo_payload = {
                "repo_url": r_url,
                "session_id": session_id,
            }
            for key in ("branch", "path_filter", "token"):
                if context.get(key):
                    repo_payload[key] = context[key]
            try:
                logger.info(
                    f"[{FILE_NAME}] _execute_ingest_streaming: Auto-routing URL to repo",
                    repo_url=r_url,
                )
                r_resp = await rag_client.ingest(
                    IngestSource.REPO,
                    repo_payload,
                    selected_model,
                    project_name=context.get("project_name"),
                )
                repo_results.extend([doc.model_dump() for doc in r_resp.documents])
                repo_skipped.extend(r_resp.skipped or [])
                repo_messages.append(r_resp.message)
            except Exception as e:
                logger.error(
                    f"[{FILE_NAME}] _execute_ingest_streaming: repo auto-route failed",
                    repo_url=r_url, error=str(e),
                )
                repo_messages.append(f"Repo {r_url} failed: {e}")

        # If there are no remaining website URLs, return the aggregated repo result.
        if not site_urls:
            agg_message = " | ".join(repo_messages) if repo_messages else "Repo ingest completed."
            state["response"] = agg_message
            state["suggested_actions"] = [
                {"action": "Query the knowledge base", "intent": "context_enrich_query"},
                {"action": "Ingest more content", "intent": "context_enrich_ingest"},
            ]
            logger.info(
                f"[{FILE_NAME}] _execute_ingest_streaming: EXIT - repo-only auto-route",
                repo_count=len(repo_urls),
            )
            return {
                "success": True,
                "result": {
                    "source": "repo",
                    "documents": repo_results,
                    "skipped": repo_skipped,
                    "message": agg_message,
                },
            }

        # Otherwise continue with the remaining true-website URLs as before.
        payload["urls"] = site_urls
        payload["session_id"] = session_id
        # Stash the repo aggregate so we can merge into the final response.
        state.setdefault("_aux", {})["repo_aggregate"] = {
            "documents": repo_results,
            "skipped": repo_skipped,
            "messages": repo_messages,
        }
        logger.info(f"[{FILE_NAME}] _execute_ingest_streaming: Payload built", payload=payload)
        print(f"[INGEST_DEBUG] Final payload for RAG: {payload}", flush=True)
    elif source == IngestSource.SHAREPOINT:
        link = context.get("link")
        if not link:
            state["response"] = "No SharePoint link provided."
            return {"success": False, "error": "No SharePoint link provided"}
        payload["link"] = link
        payload["session_id"] = session_id  # Add session_id to payload
        if context.get("token"):
            payload["token"] = context["token"]
    elif source == IngestSource.REPO:
        repo_url = context.get("repo_url")
        if not repo_url:
            state["response"] = "No repository URL provided."
            return {"success": False, "error": "No repository URL provided"}
        payload["repo_url"] = repo_url
        payload["session_id"] = session_id  # Add session_id to payload
        for key in ["branch", "path_filter", "token"]:
            if context.get(key):
                payload[key] = context[key]
    elif source == IngestSource.AGENT_OUTPUT:
        if not context.get("agent_name") or not context.get("source_url"):
            state["response"] = "agent_name and source_url required for agent_output ingestion."
            return {"success": False, "error": "Missing agent_name or source_url"}
        payload["agent_name"] = context["agent_name"]
        payload["source_url"] = context["source_url"]
        for key in ["content", "title", "artifact_type", "sdlc_phase", "session_id", "parent_doc_id", "payload"]:
            if context.get(key):
                payload[key] = context[key]
    
    try:
        response = await rag_client.ingest(source, payload, selected_model, project_name=context.get("project_name"))

        # Merge in any auto-routed repo results (only set when source==website
        # and at least one URL was a repo host).
        repo_aux = (state.get("_aux") or {}).get("repo_aggregate") or {}
        merged_docs = [doc.model_dump() for doc in response.documents] + list(repo_aux.get("documents", []))
        merged_skipped = list(response.skipped or []) + list(repo_aux.get("skipped", []))
        merged_message = response.message
        if repo_aux.get("messages"):
            merged_message = " | ".join([response.message, *repo_aux["messages"]])

        state["response"] = merged_message
        state["suggested_actions"] = [
            {"action": "Query the knowledge base", "intent": "context_enrich_query"},
            {"action": "Ingest more content", "intent": "context_enrich_ingest"}
        ]

        logger.info(f"[{FILE_NAME}] _execute_ingest_streaming: EXIT - Success")
        return {
            "success": True,
            "result": {
                "source": response.source,
                "documents": merged_docs,
                "skipped": merged_skipped,
                "message": merged_message,
            }
        }
    except Exception as e:
        state["response"] = f"Ingestion failed: {str(e)}"
        logger.error(f"[{FILE_NAME}] _execute_ingest_streaming: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_feedback_streaming(state: Dict, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute feedback submission with streaming updates."""
    logger.info(f"[{FILE_NAME}] _execute_feedback_streaming: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    feedback_type_str = context.get("feedback_type")
    
    if not feedback_type_str:
        state["response"] = "No feedback_type specified. Please provide: rating, correction, or domain_preference."
        state["suggested_actions"] = [
            {"action": "Submit rating", "intent": "context_enrich_feedback"},
            {"action": "Submit correction", "intent": "context_enrich_feedback"}
        ]
        logger.warning(f"[{FILE_NAME}] _execute_feedback_streaming: EXIT - No feedback_type")
        return {"success": False, "error": "No feedback_type provided"}
    
    try:
        feedback_type = FeedbackType(feedback_type_str)
    except ValueError:
        state["response"] = f"Invalid feedback_type: {feedback_type_str}"
        return {"success": False, "error": f"Invalid feedback_type: {feedback_type_str}"}
    
    try:
        response = await rag_client.submit_feedback(
            feedback_type=feedback_type,
            rating=context.get("rating"),
            content=context.get("content"),
            artifact_type=context.get("artifact_type"),
            sdlc_phase=context.get("sdlc_phase"),
            agent_name=context.get("agent_name"),
            session_id=state["session_id"],
            ref_doc_id=context.get("ref_doc_id"),
            selected_model=selected_model,
            project_name=context.get("project_name")
        )
        
        state["response"] = response.message
        state["suggested_actions"] = [
            {"action": "Submit more feedback", "intent": "context_enrich_feedback"},
            {"action": "Query the knowledge base", "intent": "context_enrich_query"}
        ]
        
        logger.info(f"[{FILE_NAME}] _execute_feedback_streaming: EXIT - Success")
        return {
            "success": True,
            "result": {
                "id": response.id,
                "feedback_type": response.feedback_type,
                "indexed": response.indexed,
                "message": response.message
            }
        }
    except Exception as e:
        state["response"] = f"Feedback submission failed: {str(e)}"
        logger.error(f"[{FILE_NAME}] _execute_feedback_streaming: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_list_documents_streaming(state: Dict, rag_client) -> Dict[str, Any]:
    """Execute list documents with streaming updates."""
    logger.info(f"[{FILE_NAME}] _execute_list_documents_streaming: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    filename = context.get("filename")
    skip = context.get("skip", 0)
    limit = context.get("limit", 20)
    
    # Extract filename from message if not in context
    if not filename:
        message_lower = state["current_message"].lower()
        import re
        filename_match = re.search(r'[\w\-_]+\.(pdf|doc|docx|txt|md|xlsx|xls|csv|json|xml)', message_lower, re.IGNORECASE)
        if filename_match:
            filename = filename_match.group(0)
    
    try:
        response = await rag_client.list_documents(
            skip=skip,
            limit=limit,
            filename=filename,
            project_name=context.get("project_name")
        )
        
        if response.documents:
            doc_list = []
            for doc in response.documents:
                doc_list.append(f"- **{doc.original_name}** (Status: {doc.status}, Phase: {doc.sdlc_phase or 'N/A'})")
            
            docs_text = "\n".join(doc_list)
            state["response"] = f"Found {response.total} document(s):\n\n{docs_text}"
        else:
            if filename:
                state["response"] = f"No documents found matching '{filename}'."
            else:
                state["response"] = "No documents found in the knowledge base."
        
        state["suggested_actions"] = [
            {"action": "Query the knowledge base", "intent": "context_enrich_query"},
            {"action": "Upload more documents", "intent": "context_enrich_upload"},
            {"action": "List more documents", "intent": "context_enrich_list_documents"}
        ]
        
        logger.info(f"[{FILE_NAME}] _execute_list_documents_streaming: EXIT - Success")
        return {
            "success": True,
            "result": {
                "total": response.total,
                "documents": [doc.model_dump() for doc in response.documents],
                "message": state["response"]
            }
        }
    except Exception as e:
        state["response"] = f"Failed to list documents: {str(e)}"
        logger.error(f"[{FILE_NAME}] _execute_list_documents_streaming: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_query_streaming(state: Dict, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute knowledge base query with streaming updates."""
    logger.info(f"[{FILE_NAME}] _execute_query_streaming: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    query = context.get("query") or state["current_message"]
    
    if not query or len(query) < 3:
        state["response"] = "Query must be at least 3 characters long."
        state["suggested_actions"] = [
            {"action": "Try a different query", "intent": "context_enrich_query"}
        ]
        logger.warning(f"[{FILE_NAME}] _execute_query_streaming: EXIT - Query too short")
        return {"success": False, "error": "Query too short"}
    
    from app.models.requests import SDLCPhase
    sdlc_phase = None
    if context.get("sdlc_phase"):
        try:
            sdlc_phase = SDLCPhase(context["sdlc_phase"])
        except ValueError:
            pass
    
    try:
        response = await rag_client.query(
            query=query,
            sdlc_phase=sdlc_phase,
            top_k=context.get("top_k", 5),
            include_sources=context.get("include_sources", True),
            criticality=context.get("criticality"),
            include_non_critical=bool(context.get("include_non_critical", False)),
            selected_model=selected_model,
            project_name=context.get("project_name")
        )
        
        state["response"] = response.answer
        state["suggested_actions"] = [
            {"action": "Ask another question", "intent": "context_enrich_query"},
            {"action": "Upload more documents", "intent": "context_enrich_upload"}
        ]
        
        logger.info(f"[{FILE_NAME}] _execute_query_streaming: EXIT - Success")
        return {
            "success": True,
            "result": {
                "query": response.query,
                "answer": response.answer,
                "sources": [src.model_dump() for src in response.sources],
                "guardrail_passed": response.guardrail_passed,
                "retrieval_count": response.retrieval_count,
                "sdlc_phase": response.sdlc_phase
            }
        }
    except Exception as e:
        state["response"] = f"Query failed: {str(e)}"
        logger.error(f"[{FILE_NAME}] _execute_query_streaming: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


def _generate_help_response_streaming(state: Dict) -> Dict[str, Any]:
    """Generate help response."""
    logger.info(f"[{FILE_NAME}] _generate_help_response_streaming: ENTRY")
    
    state["response"] = """I can help you with the following knowledge base operations:

**Upload Documents:** Upload files to the knowledge base for indexing.

**Ingest Content:** Ingest from websites, SharePoint, repositories, or agent outputs.

**Submit Feedback:** Provide ratings, corrections, or domain preferences.

**Query Knowledge Base:** Search for information in the knowledge base.

What would you like to do?"""
    
    state["suggested_actions"] = [
        {"action": "Upload documents", "intent": "context_enrich_upload"},
        {"action": "Ingest content", "intent": "context_enrich_ingest"},
        {"action": "Submit feedback", "intent": "context_enrich_feedback"},
        {"action": "Query knowledge base", "intent": "context_enrich_query"}
    ]
    
    logger.info(f"[{FILE_NAME}] _generate_help_response_streaming: EXIT")
    return {"success": True, "result": {"message": state["response"]}}


def _handle_confirmation_streaming(state: Dict) -> Dict[str, Any]:
    """Handle user confirmation."""
    logger.info(f"[{FILE_NAME}] _handle_confirmation_streaming: ENTRY")
    
    suggested_actions = state["context"].get("suggested_actions", [])
    if suggested_actions:
        state["response"] = "What would you like me to help you with next?"
        state["suggested_actions"] = suggested_actions
    else:
        state["response"] = "I understood your confirmation. How can I help you?"
        state["suggested_actions"] = [
            {"action": "Upload documents", "intent": "context_enrich_upload"},
            {"action": "Query knowledge base", "intent": "context_enrich_query"}
        ]
    
    logger.info(f"[{FILE_NAME}] _handle_confirmation_streaming: EXIT")
    return {"success": True, "result": {"message": state["response"]}}


def _request_clarification_streaming(state: Dict) -> Dict[str, Any]:
    """Request clarification from user."""
    logger.info(f"[{FILE_NAME}] _request_clarification_streaming: ENTRY")
    
    if state["intent"] and state["intent"].clarification_question:
        state["response"] = state["intent"].clarification_question
    else:
        state["response"] = """I'm not sure what you'd like to do. I can help with:

- Upload documents to knowledge base
- Ingest content from websites, SharePoint, or repos
- Submit feedback (ratings, corrections)
- Query the knowledge base

What would you like to do?"""
    
    state["suggested_actions"] = [
        {"action": "Upload documents", "intent": "context_enrich_upload"},
        {"action": "Ingest content", "intent": "context_enrich_ingest"},
        {"action": "Submit feedback", "intent": "context_enrich_feedback"},
        {"action": "Query knowledge base", "intent": "context_enrich_query"}
    ]
    
    logger.info(f"[{FILE_NAME}] _request_clarification_streaming: EXIT")
    return {"success": True, "result": {"message": state["response"]}}
