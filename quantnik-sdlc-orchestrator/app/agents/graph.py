"""
LangGraph State Machine - SDLC Orchestrator
============================================
Parent orchestrator that routes requests to Planning or Test orchestrators.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType, OrchestratorType, INTENT_TO_ORCHESTRATOR
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory
from app.tools.orchestrator_client import get_orchestrator_client

logger = get_logger(__name__)
FILE_NAME = "graph.py"


class AgentState(TypedDict):
    """State flowing through the SDLC orchestrator graph."""
    session_id: str
    messages: List[Dict[str, str]]
    current_message: str
    intent: Optional[ClassifiedIntent]
    target_orchestrator: Optional[OrchestratorType]
    entities: Dict[str, Any]
    context: Dict[str, Any]
    pending_actions: List[str]
    current_action: Optional[str]
    action_results: List[Dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
    suggested_actions: List[Dict[str, str]]
    metadata: Dict[str, Any]
    child_response: Optional[Dict[str, Any]]


async def retrieve_memory_node(state: AgentState) -> AgentState:
    """Node: Retrieve memory and context from previous interactions."""
    logger.info(f"[{FILE_NAME}] retrieve_memory_node: ENTRY", session_id=state["session_id"])
    
    memory = get_memory()
    
    stored_entities = await memory.get_entities(state["session_id"])
    state["entities"] = {**stored_entities, **state.get("entities", {})}
    
    history = await memory.get_conversation_history(state["session_id"], limit=10)
    if history and not state.get("messages"):
        state["messages"] = history
    
    # Get last orchestrator for confirmation handling
    full_context = await memory.get_full_context(state["session_id"])
    state["context"]["last_orchestrator"] = full_context.get("last_orchestrator")
    state["context"]["suggested_actions"] = full_context.get("suggested_actions", [])
    state["context"]["last_intent"] = full_context.get("last_intent")
    state["context"]["pending_confirmation"] = full_context.get("pending_confirmation")
    
    logger.debug(f"[{FILE_NAME}] retrieve_memory_node: EXIT", entity_count=len(state["entities"]), 
                 pending_confirmation=state["context"].get("pending_confirmation"))
    return state


async def classify_intent_node(state: AgentState) -> AgentState:
    """Node: Classify intent and determine target orchestrator."""
    logger.info(f"[{FILE_NAME}] classify_intent_node: ENTRY", session_id=state["session_id"])
    
    start_time = datetime.utcnow()
    memory = get_memory()
    
    # Check for pending confirmation from previous request
    pending_confirmation = state["context"].get("pending_confirmation")
    if pending_confirmation:
        message_lower = state["current_message"].lower().strip()
        confirmation_words = [
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed", 
            "continue", "go ahead", "do it", "confirm", "confirmed", "correct",
            "right", "absolutely", "definitely", "please", "yes please"
        ]
        denial_words = ["no", "nope", "cancel", "stop", "don't", "dont", "never mind", "nevermind"]
        
        is_confirmed = message_lower in confirmation_words or any(
            message_lower == word or message_lower.startswith(word + " ")
            for word in confirmation_words
        )
        is_denied = message_lower in denial_words or any(
            message_lower == word or message_lower.startswith(word + " ")
            for word in denial_words
        )
        
        if is_confirmed:
            # User confirmed - proceed with the pending intent
            intent_type_map = {e.value: e for e in IntentType}
            pending_intent_type = intent_type_map.get(pending_confirmation.get("intent"))
            if pending_intent_type:
                state["intent"] = ClassifiedIntent(
                    intent=pending_intent_type,
                    target_orchestrator=OrchestratorType.COMMON_INTEGRATION,
                    confidence=1.0,
                    reasoning="User confirmed pending intent"
                )
                state["target_orchestrator"] = OrchestratorType.COMMON_INTEGRATION
            await memory.clear_pending_confirmation(state["session_id"])
            return state
        elif is_denied:
            # User denied - mark as needing clarification
            await memory.clear_pending_confirmation(state["session_id"])
            state["intent"] = ClassifiedIntent(
                intent=IntentType.UNKNOWN,
                target_orchestrator=OrchestratorType.UNKNOWN,
                confidence=1.0,
                requires_clarification=True,
                reasoning="User denied pending confirmation"
            )
            state["target_orchestrator"] = OrchestratorType.UNKNOWN
            return state
        else:
            # User provided different input - clear pending and re-classify
            await memory.clear_pending_confirmation(state["session_id"])
    
    # Check for explicit intent or target orchestrator override
    explicit_intent = state.get("context", {}).get("explicit_intent")
    target_orch = state.get("context", {}).get("target_orchestrator")
    
    if target_orch:
        orch_type = OrchestratorType(target_orch) if target_orch in ["planning", "test"] else OrchestratorType.UNKNOWN
        state["target_orchestrator"] = orch_type
        state["intent"] = ClassifiedIntent(
            intent=IntentType.UNKNOWN,
            target_orchestrator=orch_type,
            confidence=1.0,
            reasoning="Explicit orchestrator target"
        )
        return state
    
    classifier = get_classifier()
    
    classified = await classifier.classify(
        message=state["current_message"],
        history=state.get("messages", []),
        context=state.get("context", {})
    )
    
    state["intent"] = classified
    state["target_orchestrator"] = classified.target_orchestrator
    state["entities"].update(classified.entities)
    state["metadata"]["intent_classification_ms"] = int(
        (datetime.utcnow() - start_time).total_seconds() * 1000
    )
    
    # Save intent to memory
    await memory.set_last_intent(state["session_id"], classified.intent.value)
    
    logger.info(
        f"[{FILE_NAME}] classify_intent_node: EXIT",
        intent=classified.intent.value,
        orchestrator=classified.target_orchestrator.value,
        confidence=classified.confidence
    )
    
    return state


def _get_selected_option(user_message: str, suggested_actions: List[Dict[str, Any]]) -> int:
    """Determine which suggested action the user selected."""
    msg_lower = user_message.lower().strip()
    
    number_words = {
        "first": 0, "1": 0, "one": 0, "option 1": 0,
        "second": 1, "2": 1, "two": 1, "option 2": 1,
        "third": 2, "3": 2, "three": 2, "option 3": 2,
    }
    
    for pattern, index in number_words.items():
        if pattern in msg_lower or msg_lower == pattern:
            if index < len(suggested_actions):
                return index
    
    # Match by keywords in action
    for idx, action in enumerate(suggested_actions):
        action_text = action.get("action", "").lower()
        if any(word in msg_lower for word in action_text.split() if len(word) > 3):
            return idx
    
    return 0


async def plan_actions_node(state: AgentState) -> AgentState:
    """Node: Plan actions based on intent and target orchestrator."""
    logger.info(f"[{FILE_NAME}] plan_actions_node: ENTRY", 
                intent=state["intent"].intent.value if state["intent"] else "none",
                orchestrator=state["target_orchestrator"].value if state["target_orchestrator"] else "none")
    
    intent = state["intent"]
    if not intent:
        state["error"] = "No intent classified"
        return state
    
    # Check if intent requires confirmation (feedback, query, list_documents)
    intents_requiring_confirmation = [
        IntentType.CONTEXT_ENRICH_FEEDBACK,
        IntentType.CONTEXT_ENRICH_QUERY,
        IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS
    ]
    
    pending_confirmation = state["context"].get("pending_confirmation")
    if intent.intent in intents_requiring_confirmation and not pending_confirmation:
        # Store pending confirmation and request user confirmation
        memory = get_memory()
        await memory.set_pending_confirmation(state["session_id"], {
            "intent": intent.intent.value,
            "target_orchestrator": "common_integration",
            "original_message": state["current_message"],
            "entities": state.get("entities", {})
        })
        
        intent_messages = {
            IntentType.CONTEXT_ENRICH_FEEDBACK: "It seems you want to **provide feedback, rating, review, or suggestion**. Is that correct?",
            IntentType.CONTEXT_ENRICH_QUERY: "It seems you want to **query the knowledge base** for information. Is that correct?",
            IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS: "It seems you want to **list or view documents** in the knowledge base. Is that correct?"
        }
        
        state["response"] = f"{intent_messages.get(intent.intent, 'Is this what you want to do?')}\n\nPlease reply with **Yes** to proceed or **No** to do something else."
        state["suggested_actions"] = [
            {"action": "Yes, proceed", "intent": intent.intent.value, "orchestrator": "common_integration"},
            {"action": "No, do something else", "intent": "unknown", "orchestrator": "unknown"},
        ]
        state["pending_actions"] = []  # Don't execute any actions, just return confirmation request
        state["metadata"]["requires_confirmation"] = True
        return state
    
    # Handle CONFIRMATION - route to appropriate orchestrator
    if intent.intent == IntentType.CONFIRMATION:
        suggested_actions = state["context"].get("suggested_actions", [])
        last_orch = state["context"].get("last_orchestrator")
        
        if suggested_actions:
            selected_idx = _get_selected_option(state["current_message"], suggested_actions)
            if selected_idx < len(suggested_actions):
                selected = suggested_actions[selected_idx]
                target_orch = selected.get("orchestrator", last_orch)
                
                if target_orch:
                    state["target_orchestrator"] = OrchestratorType(target_orch)
                    state["pending_actions"] = ["route_to_child_orchestrator"]
                    state["metadata"]["selected_action"] = selected
                    state["metadata"]["selected_index"] = selected_idx + 1
                    logger.info("Confirmation: routing to orchestrator", 
                               orchestrator=target_orch, 
                               selected_action=selected.get("action"))
                    return state
        
        # If no suggested actions but have last orchestrator, route there
        if last_orch:
            state["target_orchestrator"] = OrchestratorType(last_orch)
            state["pending_actions"] = ["route_to_child_orchestrator"]
            return state
        
        state["pending_actions"] = ["handle_unclear_confirmation"]
        return state
    
    # Handle GENERAL_QUESTION locally
    if intent.intent == IntentType.GENERAL_QUESTION:
        state["pending_actions"] = ["generate_help_response"]
        return state
    
    # Handle UNKNOWN
    if intent.intent == IntentType.UNKNOWN or state["target_orchestrator"] == OrchestratorType.UNKNOWN:
        if intent.requires_clarification:
            state["pending_actions"] = ["request_clarification"]
        else:
            state["pending_actions"] = ["request_clarification"]
        return state
    
    # Route to child orchestrator
    state["pending_actions"] = ["route_to_child_orchestrator"]
    
    logger.info("Actions planned", 
                actions=state["pending_actions"],
                target=state["target_orchestrator"].value if state["target_orchestrator"] else "none")
    return state


async def execute_action_node(state: AgentState) -> AgentState:
    """Node: Execute the planned action."""
    if not state["pending_actions"]:
        return state
    
    action = state["pending_actions"].pop(0)
    state["current_action"] = action
    
    logger.info("Executing action", action=action)
    start_time = datetime.utcnow()
    
    try:
        result = await _execute_action(action, state)
        
        state["action_results"].append({
            "action": action,
            "success": True,
            "result": result,
            "duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        })
        
    except Exception as e:
        logger.error("Action failed", action=action, error=str(e))
        state["action_results"].append({
            "action": action,
            "success": False,
            "error": str(e)
        })
        state["error"] = f"Action '{action}' failed: {str(e)}"
    
    return state


async def _execute_action(action: str, state: AgentState) -> Dict[str, Any]:
    """Execute a single action."""
    
    action_handlers = {
        "route_to_child_orchestrator": lambda: _route_to_child(state),
        "generate_help_response": lambda: _handle_help(state),
        "request_clarification": lambda: _handle_clarification(state),
        "handle_unclear_confirmation": lambda: _handle_unclear_confirmation(state),
    }
    
    handler = action_handlers.get(action)
    if handler:
        return await handler()
    
    raise ValueError(f"Unknown action: {action}")


async def _route_to_child(state: AgentState) -> Dict[str, Any]:
    """Route request to child orchestrator."""
    target = state["target_orchestrator"]
    if not target or target == OrchestratorType.UNKNOWN:
        raise ValueError("No target orchestrator specified")
    
    client = get_orchestrator_client()
    
    # Build context for child orchestrator
    context = {**state.get("context", {})}
    context["entities"] = state.get("entities", {})
    
    # Pass explicit intent to child orchestrator
    # Priority: 1. selected_action intent (from confirmation), 2. classified intent
    selected_action = state.get("metadata", {}).get("selected_action")
    explicit_intent = None
    if selected_action:
        explicit_intent = selected_action.get("intent")
    elif state.get("intent") and hasattr(state["intent"], "intent"):
        # Pass the classified intent to the child orchestrator
        explicit_intent = state["intent"].intent.value
    
    # Call child orchestrator
    response = await client.call_chat(
        orchestrator=target,
        session_id=state["session_id"],
        message=state["current_message"],
        context=context,
        history=state.get("messages", []),
        explicit_intent=explicit_intent
    )
    
    state["child_response"] = response
    state["response"] = response.get("message", "Request processed.")
    state["suggested_actions"] = [
        {**sa, "orchestrator": target.value}
        for sa in response.get("suggested_actions", [])
    ]
    
    # Update memory with which orchestrator handled this
    memory = get_memory()
    await memory.set_last_orchestrator(state["session_id"], target.value)
    
    return {
        "routed_to": target.value,
        "child_response": response
    }


async def _handle_help(state: AgentState) -> Dict[str, Any]:
    """Generate help response explaining all capabilities."""
    client = get_orchestrator_client()
    capabilities = client.get_all_capabilities()
    
    planning_cap = next((c for c in capabilities if c["name"] == "planning"), {})
    test_cap = next((c for c in capabilities if c["name"] == "test"), {})
    
    state["response"] = (
        "I'm QUANTNIK SDLC Orchestrator, your software development lifecycle assistant. "
        "I coordinate between specialized orchestrators:\n\n"
        "**Planning Orchestrator:**\n"
        f"{planning_cap.get('description', 'Handles planning tasks')}\n"
        "- Create BRDs from transcripts\n"
        "- Generate user stories from BRDs\n"
        "- Validate user stories\n"
        "- Get BRD summaries\n\n"
        "**Test Orchestrator:**\n"
        f"{test_cap.get('description', 'Handles test tasks')}\n"
        "- Generate test cases from user stories\n"
        "- Create automated test scripts (Selenium, Playwright)\n\n"
        "Just tell me what you'd like to do!"
    )
    
    state["suggested_actions"] = [
        {"action": "Create a BRD", "intent": "create_brd", "orchestrator": "planning"},
        {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
    ]
    
    return {"help_sent": True}


async def _handle_clarification(state: AgentState) -> Dict[str, Any]:
    """Request clarification from user."""
    intent = state.get("intent")
    
    if intent and intent.clarification_question:
        state["response"] = intent.clarification_question
    else:
        state["response"] = (
            "I'm not sure what you'd like to do. Could you please clarify?\n\n"
            "I can help with:\n"
            "- **BRD creation** from transcripts\n"
            "- **User story generation** from BRDs\n"

            "- **Test cases generation** from user stories\n"
            "- **Test script automation**\n\n"
            "- **List/show documents** in knowledge base\n"
            "- **Query knowledge base** for information\n\n"
            "What would you like to do?"
        )
    
    state["suggested_actions"] = [
        {"action": "Create a BRD from transcript", "intent": "create_brd", "orchestrator": "planning"},
        {"action": "Generate user stories from BRD", "intent": "create_user_story", "orchestrator": "planning"},
        {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
        {"action": "Show my documents", "intent": "context_enrich_list_documents", "orchestrator": "common_integration"},
    ]
    
    return {"clarification_sent": True}


async def _handle_unclear_confirmation(state: AgentState) -> Dict[str, Any]:
    """Handle confirmation when context is unclear."""
    state["response"] = (
        "I understand you want to proceed, but I'm not sure what action to take. "
        "What would you like to do?\n\n"
        "**Planning:**\n"
        "- Create a BRD\n"
        "- Generate user stories\n"
        "- Validate user stories\n\n"
        "**Testing:**\n"
        "- Generate test cases\n"
        "- Create test scripts\n\n"
        "**Knowledge Base:**\n"
        "- Show my documents\n"
        "- Query knowledge base"
    )
    
    state["suggested_actions"] = [
        {"action": "Create a BRD", "intent": "create_brd", "orchestrator": "planning"},
        {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
        {"action": "Show my documents", "intent": "context_enrich_list_documents", "orchestrator": "common_integration"},
    ]
    
    return {"unclear_confirmation_handled": True}


async def synthesize_response_node(state: AgentState) -> AgentState:
    """Node: Synthesize final response."""
    logger.info("Synthesizing response", session_id=state["session_id"])
    
    # Response already set by action handlers
    if state.get("response"):
        return state
    
    if state.get("error"):
        state["response"] = f"I encountered an issue: {state['error']}"
        return state
    
    state["response"] = "I've processed your request. Is there anything else you'd like to do?"
    return state


async def update_memory_node(state: AgentState) -> AgentState:
    """Node: Update conversation memory."""
    logger.info("Updating memory", session_id=state["session_id"])
    
    memory = get_memory()
    
    # Save user message
    await memory.add_user_message(
        state["session_id"],
        state["current_message"],
        metadata={"intent": state["intent"].intent.value if state["intent"] else None}
    )
    
    # Save assistant response
    routed_to = None
    if state.get("child_response"):
        routed_to = state["target_orchestrator"].value if state["target_orchestrator"] else None
    
    if state.get("response"):
        await memory.add_assistant_message(
            state["session_id"],
            state["response"],
            metadata={
                "intent": state["intent"].intent.value if state["intent"] else None,
                "actions": [r.get("action") for r in state.get("action_results", [])],
            },
            routed_to=routed_to
        )
    
    # Update entities
    if state.get("entities"):
        await memory.update_entities(state["session_id"], state["entities"])
    
    # Save suggested actions for confirmation handling
    if state.get("suggested_actions"):
        await memory.set_suggested_actions(state["session_id"], state["suggested_actions"])
    
    return state


def should_continue_actions(state: AgentState) -> Literal["execute", "synthesize"]:
    """Conditional: Check if more actions need execution."""
    if state.get("error"):
        return "synthesize"
    if state.get("pending_actions"):
        return "execute"
    return "synthesize"


def build_orchestrator_graph() -> StateGraph:
    """Build the SDLC orchestrator LangGraph."""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("retrieve_memory", retrieve_memory_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("plan_actions", plan_actions_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("synthesize_response", synthesize_response_node)
    graph.add_node("update_memory", update_memory_node)
    
    # Define edges
    graph.set_entry_point("retrieve_memory")
    graph.add_edge("retrieve_memory", "classify_intent")
    graph.add_edge("classify_intent", "plan_actions")
    graph.add_edge("plan_actions", "execute_action")
    
    graph.add_conditional_edges(
        "execute_action",
        should_continue_actions,
        {"execute": "execute_action", "synthesize": "synthesize_response"}
    )
    
    graph.add_edge("synthesize_response", "update_memory")
    graph.add_edge("update_memory", END)
    
    # Compile with memory
    memory_saver = MemorySaver()
    compiled = graph.compile(checkpointer=memory_saver)
    
    logger.info("SDLC Orchestrator graph built successfully")
    return compiled


_graph_instance = None


def get_orchestrator_graph():
    """Get or create the orchestrator graph."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_orchestrator_graph()
    return _graph_instance
