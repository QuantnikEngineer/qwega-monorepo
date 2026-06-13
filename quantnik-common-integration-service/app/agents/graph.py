"""
Orchestrator Graph
==================
LangGraph-based orchestrator for context enrichment operations.
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType, IngestSource, FeedbackType
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory
from app.tools.rag_client import get_rag_client

logger = get_logger(__name__)

FILE_NAME = "graph.py"


# Hostnames recognised as code-repository platforms. Used as a server-side
# fallback when source="website" arrives but a URL points at one of these
# hosts — we route it as source="repo" instead so the RAG backend uses
# RepositoryConnector (GitHub/Harness API).
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


class AgentState(TypedDict):
    """State managed by the orchestrator graph."""
    session_id: str
    messages: List[Dict[str, str]]
    current_message: str
    intent: Optional[ClassifiedIntent]
    entities: Dict[str, Any]
    context: Dict[str, Any]
    pending_actions: List[str]
    current_action: Optional[str]
    action_results: List[Dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
    suggested_actions: List[Dict[str, Any]]
    metadata: Dict[str, Any]


async def retrieve_memory(state: AgentState) -> AgentState:
    """Retrieve conversation memory."""
    logger.info(f"[{FILE_NAME}] retrieve_memory: ENTRY", session_id=state["session_id"])
    
    memory = get_memory()
    
    stored_entities = await memory.get_entities(state["session_id"])
    state["entities"] = {**stored_entities, **state["entities"]}
    
    full_context = await memory.get_full_context(state["session_id"])
    state["context"]["suggested_actions"] = full_context.get("suggested_actions", [])
    state["context"]["last_intent"] = full_context.get("last_intent")
    
    logger.info(f"[{FILE_NAME}] retrieve_memory: EXIT", session_id=state["session_id"])
    return state


async def classify_intent(state: AgentState) -> AgentState:
    """Classify user intent."""
    logger.info(f"[{FILE_NAME}] classify_intent: ENTRY", session_id=state["session_id"])
    
    explicit_intent = state["context"].get("explicit_intent")
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
                f"[{FILE_NAME}] classify_intent: EXIT - Explicit intent",
                session_id=state["session_id"],
                intent=intent_type.value
            )
            return state
    
    classifier = get_classifier()
    classified = await classifier.classify(
        message=state["current_message"],
        history=state["messages"],
        context=state["context"]
    )
    
    state["intent"] = classified
    state["entities"].update(classified.entities)
    
    memory = get_memory()
    await memory.set_last_intent(state["session_id"], classified.intent.value)
    
    logger.info(
        f"[{FILE_NAME}] classify_intent: EXIT",
        session_id=state["session_id"],
        intent=classified.intent.value,
        confidence=classified.confidence
    )
    return state


async def plan_actions(state: AgentState) -> AgentState:
    """Plan actions based on intent."""
    logger.info(
        f"[{FILE_NAME}] plan_actions: ENTRY",
        session_id=state["session_id"],
        intent=state["intent"].intent.value if state["intent"] else None
    )
    
    intent = state["intent"]
    
    action_plans = {
        IntentType.CONTEXT_ENRICH_UPLOAD: ["execute_upload"],
        IntentType.CONTEXT_ENRICH_INGEST: ["execute_ingest"],
        IntentType.CONTEXT_ENRICH_FEEDBACK: ["execute_feedback"],
        IntentType.CONTEXT_ENRICH_QUERY: ["execute_query"],
        IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS: ["execute_list_documents"],
        IntentType.GENERAL_QUESTION: ["generate_help_response"],
        IntentType.CONFIRMATION: ["handle_confirmation"],
        IntentType.UNKNOWN: ["request_clarification"],
    }
    
    planned = action_plans.get(intent.intent, ["request_clarification"])
    
    if intent.requires_clarification:
        planned = ["request_clarification"]
    
    state["pending_actions"] = planned.copy()
    
    logger.info(
        f"[{FILE_NAME}] plan_actions: EXIT",
        session_id=state["session_id"],
        planned_actions=planned
    )
    return state


async def execute_actions(state: AgentState) -> AgentState:
    """Execute planned actions."""
    logger.info(
        f"[{FILE_NAME}] execute_actions: ENTRY",
        session_id=state["session_id"],
        pending_actions=state["pending_actions"]
    )
    
    rag_client = get_rag_client()
    selected_model = state["context"].get("selected_model")
    
    while state["pending_actions"]:
        action = state["pending_actions"].pop(0)
        state["current_action"] = action
        
        logger.debug(f"[{FILE_NAME}] execute_actions: Executing action", action=action)
        
        try:
            if action == "execute_upload":
                result = await _execute_upload(state, rag_client, selected_model)
            elif action == "execute_ingest":
                result = await _execute_ingest(state, rag_client, selected_model)
            elif action == "execute_feedback":
                result = await _execute_feedback(state, rag_client, selected_model)
            elif action == "execute_query":
                result = await _execute_query(state, rag_client, selected_model)
            elif action == "execute_list_documents":
                result = await _execute_list_documents(state, rag_client)
            elif action == "generate_help_response":
                result = _generate_help_response(state)
            elif action == "handle_confirmation":
                result = _handle_confirmation(state)
            elif action == "request_clarification":
                result = _request_clarification(state)
            else:
                result = {"success": False, "error": f"Unknown action: {action}"}
            
            state["action_results"].append({
                "action": action,
                "success": result.get("success", False),
                "result": result.get("result"),
                "error": result.get("error")
            })
            
            if not result.get("success"):
                state["error"] = result.get("error", "Action failed")
                break
                
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] execute_actions: Action error",
                action=action,
                error=str(e),
                error_type=type(e).__name__
            )
            state["action_results"].append({
                "action": action,
                "success": False,
                "error": str(e)
            })
            state["error"] = str(e)
            break
    
    state["current_action"] = None
    
    logger.info(
        f"[{FILE_NAME}] execute_actions: EXIT",
        session_id=state["session_id"],
        action_count=len(state["action_results"]),
        has_error=state["error"] is not None
    )
    return state


async def _execute_upload(state: AgentState, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute file upload action."""
    logger.info(f"[{FILE_NAME}] _execute_upload: ENTRY", session_id=state["session_id"])
    
    files = state["context"].get("files", [])
    if not files:
        logger.warning(f"[{FILE_NAME}] _execute_upload: No files provided")
        return {
            "success": False,
            "error": "No files provided for upload. Please include files in the context."
        }
    
    project_name = state["context"].get("project_name")
    
    try:
        response = await rag_client.upload_files(files, selected_model, project_name=project_name)
        
        state["response"] = response.message
        state["suggested_actions"] = [
            {"action": "Query the knowledge base", "intent": "context_enrich_query"},
            {"action": "Upload more documents", "intent": "context_enrich_upload"}
        ]
        
        logger.info(
            f"[{FILE_NAME}] _execute_upload: EXIT - Success",
            document_count=len(response.documents)
        )
        return {
            "success": True,
            "result": {
                "documents": [doc.model_dump() for doc in response.documents],
                "skipped": response.skipped,
                "message": response.message
            }
        }
    except Exception as e:
        logger.error(f"[{FILE_NAME}] _execute_upload: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_ingest(state: AgentState, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute content ingestion action."""
    logger.info(f"[{FILE_NAME}] _execute_ingest: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    source_str = context.get("source")
    
    if not source_str:
        logger.warning(f"[{FILE_NAME}] _execute_ingest: No source provided")
        return {
            "success": False,
            "error": "No ingest source specified. Please provide source type (website, sharepoint, repo, agent_output)."
        }
    
    try:
        source = IngestSource(source_str)
    except ValueError:
        return {"success": False, "error": f"Invalid source type: {source_str}"}
    
    payload = {}
    repo_aux: Dict[str, Any] = {"documents": [], "skipped": [], "messages": []}
    if source == IngestSource.WEBSITE:
        urls = context.get("urls", [])
        if not urls:
            return {"success": False, "error": "No URLs provided for website ingestion."}

        # Server-side fallback: split off URLs that look like a code repository
        # and route them as REPO via RepositoryConnector.
        repo_urls = [u for u in urls if _is_repo_url(u)]
        site_urls = [u for u in urls if not _is_repo_url(u)]

        project_name_for_repo = context.get("project_name")
        for r_url in repo_urls:
            repo_payload = {"repo_url": r_url}
            for key in ("branch", "path_filter", "token"):
                if context.get(key):
                    repo_payload[key] = context[key]
            try:
                logger.info(
                    f"[{FILE_NAME}] _execute_ingest: Auto-routing URL to repo",
                    repo_url=r_url,
                )
                r_resp = await rag_client.ingest(
                    IngestSource.REPO,
                    repo_payload,
                    selected_model,
                    project_name=project_name_for_repo,
                )
                repo_aux["documents"].extend([doc.model_dump() for doc in r_resp.documents])
                repo_aux["skipped"].extend(r_resp.skipped or [])
                repo_aux["messages"].append(r_resp.message)
            except Exception as e:
                logger.error(
                    f"[{FILE_NAME}] _execute_ingest: repo auto-route failed",
                    repo_url=r_url, error=str(e),
                )
                repo_aux["messages"].append(f"Repo {r_url} failed: {e}")

        if not site_urls:
            agg_message = " | ".join(repo_aux["messages"]) if repo_aux["messages"] else "Repo ingest completed."
            state["response"] = agg_message
            state["suggested_actions"] = [
                {"action": "Query the knowledge base", "intent": "context_enrich_query"},
                {"action": "Ingest more content", "intent": "context_enrich_ingest"},
            ]
            logger.info(
                f"[{FILE_NAME}] _execute_ingest: EXIT - repo-only auto-route",
                repo_count=len(repo_urls),
            )
            return {
                "success": True,
                "result": {
                    "source": "repo",
                    "documents": repo_aux["documents"],
                    "skipped": repo_aux["skipped"],
                    "message": agg_message,
                },
            }

        payload["urls"] = site_urls
    elif source == IngestSource.SHAREPOINT:
        link = context.get("link")
        if not link:
            return {"success": False, "error": "No SharePoint link provided."}
        payload["link"] = link
        if context.get("token"):
            payload["token"] = context["token"]
    elif source == IngestSource.REPO:
        repo_url = context.get("repo_url")
        if not repo_url:
            return {"success": False, "error": "No repository URL provided."}
        payload["repo_url"] = repo_url
        if context.get("branch"):
            payload["branch"] = context["branch"]
        if context.get("path_filter"):
            payload["path_filter"] = context["path_filter"]
        if context.get("token"):
            payload["token"] = context["token"]
    elif source == IngestSource.AGENT_OUTPUT:
        agent_name = context.get("agent_name")
        source_url = context.get("source_url")
        if not agent_name or not source_url:
            return {"success": False, "error": "agent_name and source_url required for agent_output ingestion."}
        payload["agent_name"] = agent_name
        payload["source_url"] = source_url
        for key in ["content", "title", "artifact_type", "sdlc_phase", "session_id", "parent_doc_id", "payload"]:
            if context.get(key):
                payload[key] = context[key]
    
    project_name = context.get("project_name")
    
    try:
        response = await rag_client.ingest(source, payload, selected_model, project_name=project_name)

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

        logger.info(
            f"[{FILE_NAME}] _execute_ingest: EXIT - Success",
            source=source.value,
            document_count=len(merged_docs)
        )
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
        logger.error(f"[{FILE_NAME}] _execute_ingest: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_feedback(state: AgentState, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute feedback submission action."""
    logger.info(f"[{FILE_NAME}] _execute_feedback: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    feedback_type_str = context.get("feedback_type")
    
    if not feedback_type_str:
        logger.warning(f"[{FILE_NAME}] _execute_feedback: No feedback_type provided")
        return {
            "success": False,
            "error": "No feedback_type specified. Please provide: rating, correction, or domain_preference."
        }
    
    try:
        feedback_type = FeedbackType(feedback_type_str)
    except ValueError:
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
            project_name=context.get("project_name"),
            query_log_id=context.get("query_log_id"),
            conversation_id=context.get("conversation_id"),
        )
        
        state["response"] = response.message
        state["suggested_actions"] = [
            {"action": "Submit more feedback", "intent": "context_enrich_feedback"},
            {"action": "Query the knowledge base", "intent": "context_enrich_query"}
        ]
        
        logger.info(
            f"[{FILE_NAME}] _execute_feedback: EXIT - Success",
            feedback_id=response.id,
            indexed=response.indexed
        )
        return {
            "success": True,
            "result": {
                "id": response.id,
                "feedback_type": response.feedback_type,
                "indexed": response.indexed,
                "message": response.message,
                "status": response.status,
                "query_log_id": response.query_log_id,
            }
        }
    except Exception as e:
        logger.error(f"[{FILE_NAME}] _execute_feedback: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


async def _execute_list_documents(state: AgentState, rag_client) -> Dict[str, Any]:
    """Execute list documents action."""
    logger.info(f"[{FILE_NAME}] _execute_list_documents: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    filename = context.get("filename")
    skip = context.get("skip", 0)
    limit = context.get("limit", 20)
    
    # Extract filename from message if not in context
    if not filename:
        message_lower = state["current_message"].lower()
        # Try to extract filename patterns like "BRD_Payment_Module.pdf"
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
        
        logger.info(
            f"[{FILE_NAME}] _execute_list_documents: EXIT - Success",
            total=response.total,
            returned_count=len(response.documents)
        )
        return {
            "success": True,
            "result": {
                "total": response.total,
                "documents": [doc.model_dump() for doc in response.documents],
                "message": state["response"]
            }
        }
    except Exception as e:
        logger.error(f"[{FILE_NAME}] _execute_list_documents: EXIT - Error", error=str(e))
        state["response"] = f"Failed to list documents: {str(e)}"
        return {"success": False, "error": str(e)}


async def _execute_query(state: AgentState, rag_client, selected_model: Optional[str]) -> Dict[str, Any]:
    """Execute knowledge base query action."""
    logger.info(f"[{FILE_NAME}] _execute_query: ENTRY", session_id=state["session_id"])
    
    context = state["context"]
    query = context.get("query") or state["current_message"]
    
    if not query or len(query) < 3:
        logger.warning(f"[{FILE_NAME}] _execute_query: Query too short")
        return {
            "success": False,
            "error": "Query must be at least 3 characters long."
        }
    
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
        
        logger.info(
            f"[{FILE_NAME}] _execute_query: EXIT - Success",
            retrieval_count=response.retrieval_count,
            guardrail_passed=response.guardrail_passed
        )
        return {
            "success": True,
            "result": {
                "query": response.query,
                "answer": response.answer,
                "sources": [src.model_dump() for src in response.sources],
                "guardrail_passed": response.guardrail_passed,
                "retrieval_count": response.retrieval_count,
                "sdlc_phase": response.sdlc_phase,
                "query_log_id": response.query_log_id,
                "conversation_id": response.conversation_id,
            }
        }
    except Exception as e:
        logger.error(f"[{FILE_NAME}] _execute_query: EXIT - Error", error=str(e))
        return {"success": False, "error": str(e)}


def _generate_help_response(state: AgentState) -> Dict[str, Any]:
    """Generate help response."""
    logger.info(f"[{FILE_NAME}] _generate_help_response: ENTRY", session_id=state["session_id"])
    
    state["response"] = """I can help you with the following knowledge base operations:

**Upload Documents:**
Upload files to the knowledge base for indexing and retrieval.

**Ingest Content:**
Ingest content from various sources:
- Websites (crawl and index web pages)
- SharePoint (index SharePoint documents)
- Repositories (index code repositories)
- Agent outputs (index generated content)

**Submit Feedback:**
- Rating: Provide positive/negative feedback
- Correction: Submit factual corrections
- Domain Preference: Add company/domain-specific rules

**Query Knowledge Base:**
Search and query the knowledge base for information.

What would you like to do?"""
    
    state["suggested_actions"] = [
        {"action": "Upload documents", "intent": "context_enrich_upload"},
        {"action": "Ingest content", "intent": "context_enrich_ingest"},
        {"action": "Submit feedback", "intent": "context_enrich_feedback"},
        {"action": "Query knowledge base", "intent": "context_enrich_query"}
    ]
    
    logger.info(f"[{FILE_NAME}] _generate_help_response: EXIT")
    return {"success": True, "result": {"message": state["response"]}}


def _handle_confirmation(state: AgentState) -> Dict[str, Any]:
    """Handle user confirmation."""
    logger.info(f"[{FILE_NAME}] _handle_confirmation: ENTRY", session_id=state["session_id"])
    
    suggested_actions = state["context"].get("suggested_actions", [])
    if suggested_actions:
        state["response"] = "What would you like me to help you with next?"
        state["suggested_actions"] = suggested_actions
    else:
        state["response"] = "I understood your confirmation. How can I help you with the knowledge base?"
        state["suggested_actions"] = [
            {"action": "Upload documents", "intent": "context_enrich_upload"},
            {"action": "Query knowledge base", "intent": "context_enrich_query"}
        ]
    
    logger.info(f"[{FILE_NAME}] _handle_confirmation: EXIT")
    return {"success": True, "result": {"message": state["response"]}}


def _request_clarification(state: AgentState) -> Dict[str, Any]:
    """Request clarification from user."""
    logger.info(f"[{FILE_NAME}] _request_clarification: ENTRY", session_id=state["session_id"])
    
    if state["intent"] and state["intent"].clarification_question:
        state["response"] = state["intent"].clarification_question
    else:
        state["response"] = """I'm not sure what you'd like to do. I can help with:

**Context Enrichment:**
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
    
    logger.info(f"[{FILE_NAME}] _request_clarification: EXIT")
    return {"success": True, "result": {"message": state["response"]}}


async def generate_response(state: AgentState) -> AgentState:
    """Generate final response."""
    logger.info(f"[{FILE_NAME}] generate_response: ENTRY", session_id=state["session_id"])
    
    memory = get_memory()
    
    await memory.add_message(state["session_id"], "user", state["current_message"])
    
    if state["response"]:
        await memory.add_message(
            state["session_id"],
            "assistant",
            state["response"],
            metadata={"intent": state["intent"].intent.value if state["intent"] else None}
        )
    
    await memory.set_entities(state["session_id"], state["entities"])
    
    if state["suggested_actions"]:
        await memory.set_suggested_actions(state["session_id"], state["suggested_actions"])
    
    state["metadata"]["end_time"] = datetime.utcnow().isoformat()
    
    logger.info(
        f"[{FILE_NAME}] generate_response: EXIT",
        session_id=state["session_id"],
        has_response=state["response"] is not None,
        has_error=state["error"] is not None
    )
    return state


def create_graph() -> StateGraph:
    """Create the orchestrator graph."""
    logger.info(f"[{FILE_NAME}] create_graph: ENTRY")
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("plan_actions", plan_actions)
    workflow.add_node("execute_actions", execute_actions)
    workflow.add_node("generate_response", generate_response)
    
    workflow.set_entry_point("retrieve_memory")
    workflow.add_edge("retrieve_memory", "classify_intent")
    workflow.add_edge("classify_intent", "plan_actions")
    workflow.add_edge("plan_actions", "execute_actions")
    workflow.add_edge("execute_actions", "generate_response")
    workflow.add_edge("generate_response", END)
    
    logger.info(f"[{FILE_NAME}] create_graph: EXIT")
    return workflow.compile()


_graph_instance = None


def get_orchestrator_graph():
    """Get the global orchestrator graph instance."""
    global _graph_instance
    if _graph_instance is None:
        logger.info(f"[{FILE_NAME}] get_orchestrator_graph: Creating new graph instance")
        _graph_instance = create_graph()
    return _graph_instance
