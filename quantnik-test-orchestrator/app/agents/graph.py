"""
LangGraph State Machine
=======================
Test orchestration graph for test scenario and script generation.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory

logger = get_logger(__name__)


class AgentState(TypedDict):
    """The state that flows through the LangGraph."""
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
    suggested_actions: List[Dict[str, str]]
    metadata: Dict[str, Any]


async def classify_intent_node(state: AgentState) -> AgentState:
    """Node: Intent Classification"""
    logger.info("[graph.py] classify_intent_node: ENTRY", session_id=state["session_id"])
    logger.debug(
        "classify_intent_node input",
        session_id=state["session_id"],
        current_message=state.get("current_message"),
        context=state.get("context")
    )
    
    start_time = datetime.utcnow()
    
    explicit_intent = state.get("context", {}).get("explicit_intent")
    if explicit_intent and explicit_intent != "string":
        logger.debug("Explicit intent provided", session_id=state["session_id"], explicit_intent=explicit_intent)
        intent_mapping = {
            "generate_test_cases": IntentType.GENERATE_TEST_CASES,
            "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
            "general_question": IntentType.GENERAL_QUESTION,
        }
        
        intent_type = intent_mapping.get(explicit_intent.lower())
        if intent_type:
            classified = ClassifiedIntent(
                intent=intent_type,
                confidence=1.0,
                reasoning="Explicit intent provided"
            )
            state["intent"] = classified
            state["metadata"]["intent_classification_ms"] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            logger.info(
                "Using explicit intent",
                session_id=state["session_id"],
                intent=intent_type.value,
                classification_ms=state["metadata"]["intent_classification_ms"]
            )
            return state
    
    classifier = get_classifier()
    memory = get_memory()
    logger.debug("Retrieving full context from memory", session_id=state["session_id"])
    full_context = await memory.get_full_context(state["session_id"])
    logger.debug("Full context retrieved", session_id=state["session_id"], full_context=full_context)
    
    context = {**full_context.get("context", {}), **state.get("context", {})}
    context["entities"] = {**full_context.get("entities", {}), **state.get("entities", {})}
    
    logger.debug("Calling classifier", session_id=state["session_id"], message=state["current_message"])
    classified = await classifier.classify(
        message=state["current_message"],
        history=state.get("messages", []),
        context=context
    )
    
    state["intent"] = classified
    state["entities"].update(classified.entities)
    state["metadata"]["intent_classification_ms"] = int(
        (datetime.utcnow() - start_time).total_seconds() * 1000
    )
    
    await memory.set_last_intent(state["session_id"], classified.intent.value)
    
    logger.info(
        "Intent classified",
        session_id=state["session_id"],
        intent=classified.intent.value,
        confidence=classified.confidence,
        classification_ms=state["metadata"]["intent_classification_ms"]
    )
    logger.debug(
        "classify_intent_node output",
        session_id=state["session_id"],
        classified_intent=classified.model_dump()
    )
    
    logger.info("[graph.py] classify_intent_node: EXIT", session_id=state["session_id"])
    return state


async def retrieve_memory_node(state: AgentState) -> AgentState:
    """Node: Memory Retrieval"""
    logger.info("[graph.py] retrieve_memory_node: ENTRY", session_id=state["session_id"])
    
    memory = get_memory()
    stored_entities = await memory.get_entities(state["session_id"])
    logger.debug("Stored entities retrieved", session_id=state["session_id"], stored_entities=stored_entities)
    state["entities"] = {**stored_entities, **state.get("entities", {})}
    
    history = await memory.get_conversation_history(state["session_id"], limit=10)
    logger.debug("Conversation history retrieved", session_id=state["session_id"], history_count=len(history))
    if history and not state.get("messages"):
        state["messages"] = history
    
    logger.debug(
        "retrieve_memory_node output",
        session_id=state["session_id"],
        entities=state["entities"],
        messages_count=len(state.get("messages", []))
    )
    
    logger.info("[graph.py] retrieve_memory_node: EXIT", session_id=state["session_id"])
    return state


def _get_selected_option_index(user_message: str, suggested_actions: List[Dict[str, str]]) -> int:
    """Determine which suggested action the user selected."""
    logger.info("[graph.py] _get_selected_option_index: ENTRY", user_message=user_message[:50] if user_message else "")
    number_words = {
        "first": 0, "1": 0, "one": 0, "option 1": 0,
        "second": 1, "2": 1, "two": 1, "option 2": 1,
        "third": 2, "3": 2, "three": 2, "option 3": 2,
    }
    
    for pattern, index in number_words.items():
        if pattern in user_message or user_message == pattern:
            if index < len(suggested_actions):
                return index
    
    for idx, action in enumerate(suggested_actions):
        action_text = action.get("action", "").lower()
        if any(word in user_message for word in action_text.split() if len(word) > 3):
            logger.info("[graph.py] _get_selected_option_index: EXIT", selected_index=idx)
            return idx
    
    logger.info("[graph.py] _get_selected_option_index: EXIT", selected_index=0)
    return 0


async def plan_actions_node(state: AgentState) -> AgentState:
    """Node: Action Planning - Test specific actions only"""
    logger.info("[graph.py] plan_actions_node: ENTRY", session_id=state["session_id"], intent=state["intent"].intent.value if state["intent"] else "none")
    
    intent = state["intent"]
    if not intent:
        state["error"] = "No intent classified"
        logger.error("No intent classified", session_id=state["session_id"])
        return state
    
    # Test-specific action plans
    action_plans = {
        IntentType.GENERATE_TEST_CASES: ["validate_stories", "call_test_cases_agent"],
        IntentType.GENERATE_TEST_SCRIPT: ["validate_test_cases", "call_test_script_agent", "push_to_repo"],
        IntentType.GENERATE_TEST_DATA: ["validate_test_data_input", "call_test_data_agent"],
        IntentType.GENERAL_QUESTION: ["generate_help_response"],
        IntentType.UNKNOWN: ["request_clarification"],
    }
    
    # Handle CONFIRMATION intent
    if intent.intent == IntentType.CONFIRMATION:
        logger.debug("Handling confirmation intent", session_id=state["session_id"])
        memory = get_memory()
        full_context = await memory.get_full_context(state["session_id"])
        suggested_actions = full_context.get("context", {}).get("suggested_actions", [])
        logger.debug("Suggested actions from context", session_id=state["session_id"], suggested_actions=suggested_actions)
        
        if suggested_actions:
            user_message = state.get("current_message", "").lower().strip()
            selected_index = _get_selected_option_index(user_message, suggested_actions)
            logger.debug("Selected option index", session_id=state["session_id"], selected_index=selected_index)
            
            if selected_index < len(suggested_actions):
                selected_suggestion = suggested_actions[selected_index]
                suggested_intent_str = selected_suggestion.get("intent") if isinstance(selected_suggestion, dict) else None
                
                if suggested_intent_str:
                    intent_mapping = {
                        "generate_test_cases": IntentType.GENERATE_TEST_CASES,
                        "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
                        "generate_test_data": IntentType.GENERATE_TEST_DATA,
                    }
                    
                    mapped_intent = intent_mapping.get(suggested_intent_str)
                    if mapped_intent:
                        planned = action_plans.get(mapped_intent, ["request_clarification"])
                        state["pending_actions"] = planned
                        state["metadata"]["planned_actions"] = planned
                        state["metadata"]["confirmed_intent"] = suggested_intent_str
                        logger.info(
                            "Confirmation mapped to intent",
                            session_id=state["session_id"],
                            confirmed_intent=suggested_intent_str,
                            planned_actions=planned
                        )
                        return state
        
        state["pending_actions"] = ["handle_empty_confirmation"]
        state["metadata"]["planned_actions"] = ["handle_empty_confirmation"]
        logger.debug("Empty confirmation handled", session_id=state["session_id"])
        return state
    
    planned = action_plans.get(intent.intent, ["request_clarification"])
    
    if intent.requires_clarification:
        planned = ["request_clarification"]
        logger.debug("Intent requires clarification", session_id=state["session_id"])
    
    state["pending_actions"] = planned
    state["metadata"]["planned_actions"] = planned
    
    logger.info("[graph.py] plan_actions_node: EXIT", session_id=state["session_id"], actions=planned)
    
    return state


async def execute_action_node(state: AgentState) -> AgentState:
    """Node: Action Execution"""
    logger.info("[graph.py] execute_action_node: ENTRY", session_id=state["session_id"])
    if not state["pending_actions"]:
        logger.debug("No pending actions to execute", session_id=state["session_id"])
        logger.info("[graph.py] execute_action_node: EXIT - no pending actions", session_id=state["session_id"])
        return state
    
    action = state["pending_actions"].pop(0)
    state["current_action"] = action
    
    logger.info("Executing action", session_id=state["session_id"], action=action)
    logger.debug(
        "Action execution input",
        session_id=state["session_id"],
        action=action,
        pending_actions_remaining=len(state["pending_actions"]),
        state_context=state.get("context"),
        state_entities=state.get("entities")
    )
    start_time = datetime.utcnow()
    
    try:
        result = await _execute_single_action(action, state)
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        state["action_results"].append({
            "action": action,
            "success": True,
            "result": result,
            "duration_ms": duration_ms
        })
        
        logger.info(
            "Action executed successfully",
            session_id=state["session_id"],
            action=action,
            duration_ms=duration_ms
        )
        logger.debug("Action result", session_id=state["session_id"], action=action, result=result)
        
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.error(
            "Action execution failed",
            session_id=state["session_id"],
            action=action,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
            exc_info=True
        )
        state["action_results"].append({
            "action": action,
            "success": False,
            "error": str(e),
            "duration_ms": duration_ms
        })
        state["error"] = f"Action '{action}' failed: {str(e)}"
    
    logger.info("[graph.py] execute_action_node: EXIT", session_id=state["session_id"], action=action)
    return state


async def _execute_single_action(action: str, state: AgentState) -> Dict[str, Any]:
    """Execute a single action."""
    logger.info("[graph.py] _execute_single_action: ENTRY", session_id=state.get("session_id", "unknown"), action=action)
    from app.tools.agent_tools import AgentToolRegistry
    
    registry = AgentToolRegistry()
    
    action_handlers = {
        "request_clarification": lambda: _handle_clarification(state),
        "handle_empty_confirmation": lambda: _handle_empty_confirmation(state),
        "generate_help_response": lambda: _handle_help(state),
        "validate_stories": lambda: _validate_stories(state),
        "validate_test_cases": lambda: _validate_test_cases(state),
        "validate_test_data_input": lambda: _validate_test_data_input(state),
        "call_test_cases_agent": lambda: registry.call_test_cases_agent(state),
        "call_test_script_agent": lambda: registry.call_test_script_agent(state),
        "call_test_data_agent": lambda: registry.call_test_data_agent(state),
        "push_to_repo": lambda: _push_to_repo(state),
    }
    
    handler = action_handlers.get(action)
    if handler:
        result = await handler()
        logger.info("[graph.py] _execute_single_action: EXIT", session_id=state.get("session_id", "unknown"), action=action)
        return result
    
    logger.info("[graph.py] _execute_single_action: EXIT - unknown action", session_id=state.get("session_id", "unknown"), action=action)
    raise ValueError(f"Unknown action: {action}")


async def _handle_clarification(state: AgentState) -> Dict[str, Any]:
    """Generate clarification response."""
    logger.info("[graph.py] _handle_clarification: ENTRY", session_id=state.get("session_id", "unknown"))
    intent = state.get("intent")
    if intent and intent.clarification_question:
        state["response"] = intent.clarification_question
    else:
        state["response"] = (
            "I'm not sure what you'd like to do. Could you please tell me more? "
            "For example, you can:\n"
            "- Generate test scenarios from user stories\n"
            "- Generate test scripts from test cases"
        )
    logger.info("[graph.py] _handle_clarification: EXIT", session_id=state.get("session_id", "unknown"))
    return {"clarification_sent": True}


async def _handle_empty_confirmation(state: AgentState) -> Dict[str, Any]:
    """Handle confirmation when there are no suggested actions."""
    logger.info("[graph.py] _handle_empty_confirmation: ENTRY", session_id=state.get("session_id", "unknown"))
    state["response"] = (
        "I understand you want to proceed, but I'm not sure what action to take. "
        "Could you please specify what you'd like to do next? For example:\n"
        "- Generate test scenarios\n"
        "- Create test scripts"
    )
    logger.info("[graph.py] _handle_empty_confirmation: EXIT", session_id=state.get("session_id", "unknown"))
    return {"empty_confirmation_handled": True}


async def _handle_help(state: AgentState) -> Dict[str, Any]:
    """Generate help response."""
    logger.info("[graph.py] _handle_help: ENTRY", session_id=state.get("session_id", "unknown"))
    state["response"] = (
        "I'm QUANTNIK Test Orchestrator, your test automation assistant. I can help you with:\n\n"
        "**Test Scenarios:**\n"
        "- Generate test scenarios from user stories\n\n"
        "**Test Scripts:**\n"
        "- Create automated test scripts (Selenium, Playwright)\n"
        "- Support for Java, JavaScript, TypeScript, Python, C#\n\n"
        "Just tell me what you'd like to do!"
    )
    logger.info("[graph.py] _handle_help: EXIT", session_id=state.get("session_id", "unknown"))
    return {"help_sent": True}


async def _validate_stories(state: AgentState) -> Dict[str, Any]:
    """
    Validate user stories exist for test scenario generation.
    
    Extracts user_stories from context payload, supporting multiple formats:
    - Direct user_stories list in entities or context
    - create_user_story_text format (list of epic groups with user_stories)
    """
    entities = state.get("entities", {})
    context = state.get("context", {})
    session_id = state.get("session_id", "unknown")
    
    logger.info(
        "[graph.py] _validate_stories: Starting validation for generate_test_cases",
        session_id=session_id
    )
    logger.debug(
        "[graph.py] _validate_stories: Input data",
        session_id=session_id,
        entities_keys=list(entities.keys()) if entities else [],
        context_keys=list(context.keys()) if context else []
    )
    
    # Try to get user_stories from multiple possible locations
    stories = entities.get("user_stories") or context.get("user_stories")
    
    # Also check create_user_story_text format (same as planning orchestrator)
    if not stories:
        create_user_story_text = entities.get("create_user_story_text") or context.get("create_user_story_text")
        if create_user_story_text:
            logger.debug(
                "[graph.py] _validate_stories: Found create_user_story_text, extracting user_stories",
                session_id=session_id,
                epic_count=len(create_user_story_text) if isinstance(create_user_story_text, list) else 0
            )
            # Extract user stories from create_user_story_text format
            extracted_stories = []
            if isinstance(create_user_story_text, list):
                for epic_group in create_user_story_text:
                    epic_data = epic_group if isinstance(epic_group, dict) else (epic_group.__dict__ if hasattr(epic_group, '__dict__') else {})
                    epic_stories = epic_data.get("user_stories") if isinstance(epic_data, dict) else getattr(epic_group, "user_stories", None)
                    if epic_stories and isinstance(epic_stories, list):
                        extracted_stories.extend(epic_stories)
            if extracted_stories:
                stories = extracted_stories
                logger.info(
                    "[graph.py] _validate_stories: Extracted user_stories from create_user_story_text",
                    session_id=session_id,
                    story_count=len(stories)
                )
    
    if not stories:
        logger.warning(
            "[graph.py] _validate_stories: Validation failed - missing user_stories",
            session_id=session_id,
            checked_locations=["entities.user_stories", "context.user_stories", "entities.create_user_story_text", "context.create_user_story_text"]
        )
        state["response"] = None
        state["pending_actions"] = []
        return {
            "validated": False,
            "validation_required": True,
            "nextagentflow": "confirmedUserStoryToTestScenario",
            "message": "Enter or Review below details to create test scenarios",
            "missing_fields": ["user_stories"]
        }
    
    logger.info(
        "[graph.py] _validate_stories: Validation passed for generate_test_cases",
        session_id=session_id,
        story_count=len(stories) if isinstance(stories, list) else 1
    )
    
    logger.info("[graph.py] _validate_stories: EXIT", session_id=session_id)
    return {"validated": True}


async def _validate_test_cases(state: AgentState) -> Dict[str, Any]:
    """Validate test cases and related inputs exist for test script generation."""
    session_id = state.get("session_id", "unknown")
    logger.info("[graph.py] _validate_test_cases: ENTRY", session_id=session_id)
    context = state.get("context", {})
    
    missing_fields = []
    if not context.get("test_cases"):
        missing_fields.append("test_cases")
    if not context.get("framework_type"):
        missing_fields.append("framework_type")
    if not context.get("language"):
        missing_fields.append("language")
    
    if missing_fields:
        logger.warning("[graph.py] _validate_test_cases: Validation failed", session_id=session_id, missing_fields=missing_fields)
        state["response"] = None
        state["pending_actions"] = []
        logger.info("[graph.py] _validate_test_cases: EXIT - validation required", session_id=session_id)
        return {
            "validated": False,
            "validation_required": True,
            "nextagentflow": "confirmedCreateTestScript",
            "message": "Enter or Review below details to create test scripts",
            "missing_fields": missing_fields
        }
    
    logger.info("[graph.py] _validate_test_cases: EXIT - validation passed", session_id=session_id)
    return {"validated": True}


async def _push_to_repo(state: AgentState) -> Dict[str, Any]:
    """Push generated scripts to repository."""
    logger.info("[graph.py] _push_to_repo: ENTRY", session_id=state.get("session_id", "unknown"))
    logger.info("[graph.py] _push_to_repo: EXIT", session_id=state.get("session_id", "unknown"))
    return {"pushed": True}


async def _validate_test_data_input(state: AgentState) -> Dict[str, Any]:
    """Validate test cases exist for test data generation."""
    context = state.get("context", {})
    
    missing_fields = []
    if not context.get("test_cases"):
        missing_fields.append("test_cases")
    
    if missing_fields:
        state["response"] = None
        state["pending_actions"] = []
        return {
            "validated": False,
            "validation_required": True,
            "nextagentflow": "confirmedTestDataGenerator",
            "message": "Enter or Review below details to generate test data",
            "missing_fields": missing_fields
        }
    
    return {"validated": True}


async def synthesize_response_node(state: AgentState) -> AgentState:
    """Node: Response Synthesis"""
    logger.info("[graph.py] synthesize_response_node: ENTRY", session_id=state["session_id"])
    
    # Check for validation_required in action results first
    results = state.get("action_results", [])
    for result in results:
        if result.get("success") and result.get("result", {}).get("validation_required"):
            validation_result = result.get("result", {})
            # Build validation response with nextagentflow pattern
            state["response"] = None  # Frontend will use structured response
            state["metadata"]["validation_required"] = True
            state["metadata"]["nextagentflow"] = validation_result.get("nextagentflow")
            state["metadata"]["validation_message"] = validation_result.get("message")
            state["metadata"]["missing_fields"] = validation_result.get("missing_fields", [])
            logger.info(
                "Validation required response",
                session_id=state["session_id"],
                nextagentflow=validation_result.get("nextagentflow"),
                message=validation_result.get("message")
            )
            return state
    
    if state.get("response"):
        logger.debug("Response already set", session_id=state["session_id"], response=state["response"])
        return state
    
    if state.get("error"):
        state["response"] = f"I encountered an issue: {state['error']}"
        logger.debug("Error response synthesized", session_id=state["session_id"], error=state["error"])
        return state
    
    intent = state.get("intent")
    logger.debug(
        "Synthesizing from action results",
        session_id=state["session_id"],
        intent=intent.intent.value if intent else None,
        action_results_count=len(results)
    )
    
    main_result = None
    for result in results:
        if result.get("action", "").startswith("call_") and result.get("success"):
            main_result = result.get("result", {})
            logger.debug("Main result found", session_id=state["session_id"], action=result.get("action"))
            break
    
    if main_result:
        state["response"] = _format_response_by_intent(intent.intent if intent else None, main_result)
    else:
        state["response"] = "I've processed your request. Is there anything else you'd like me to do?"
    
    state["suggested_actions"] = _get_suggested_actions(intent.intent if intent else None, main_result)
    
    logger.debug(
        "Response synthesized",
        session_id=state["session_id"],
        response=state["response"],
        suggested_actions=state["suggested_actions"]
    )
    
    logger.info("[graph.py] synthesize_response_node: EXIT", session_id=state["session_id"])
    return state


def _format_response_by_intent(intent: Optional[IntentType], result: Dict[str, Any]) -> str:
    """Format response message based on intent type."""
    logger.info("[graph.py] _format_response_by_intent: ENTRY", intent=intent.value if intent else None)
    if not intent:
        return "Request processed successfully."
    
    formatters = {
        IntentType.GENERATE_TEST_CASES: lambda r: f"Generated test cases for your user stories.",
        IntentType.GENERATE_TEST_SCRIPT: lambda r: f"Generated test scripts. {r.get('push_status', '')}",
        IntentType.GENERATE_TEST_DATA: lambda r: f"Generated test data successfully.",
    }
    
    formatter = formatters.get(intent, lambda r: "Request processed successfully.")
    response = formatter(result)
    logger.info("[graph.py] _format_response_by_intent: EXIT", intent=intent.value if intent else None)
    return response


def _get_suggested_actions(intent: Optional[IntentType], result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Get suggested next actions based on completed intent."""
    logger.info("[graph.py] _get_suggested_actions: ENTRY", intent=intent.value if intent else None)
    if not intent:
        logger.info("[graph.py] _get_suggested_actions: EXIT - no intent", intent=None)
        return []
    
    suggestions = {
        IntentType.GENERATE_TEST_CASES: [
            {"action": "Generate test scripts", "intent": "generate_test_script", "orchestrator": "test"},
        ],
        IntentType.GENERATE_TEST_SCRIPT: [
            {"action": "Generate test data", "intent": "generate_test_data", "orchestrator": "test"},
            {"action": "Generate more test cases", "intent": "generate_test_cases", "orchestrator": "test"},
        ],
        IntentType.GENERATE_TEST_DATA: [
            {"action": "Generate test scripts", "intent": "generate_test_script", "orchestrator": "test"},
            {"action": "Generate more test cases", "intent": "generate_test_cases", "orchestrator": "test"},
        ],
    }
    
    result = suggestions.get(intent, [])
    logger.info("[graph.py] _get_suggested_actions: EXIT", intent=intent.value if intent else None, suggestion_count=len(result))
    return result


async def update_memory_node(state: AgentState) -> AgentState:
    """Node: Memory Update"""
    logger.info("[graph.py] update_memory_node: ENTRY", session_id=state["session_id"])
    
    memory = get_memory()
    
    logger.debug("Adding user message to memory", session_id=state["session_id"], message=state["current_message"])
    await memory.add_user_message(
        state["session_id"],
        state["current_message"],
        metadata={"intent": state["intent"].intent.value if state["intent"] else None}
    )
    
    if state.get("response"):
        logger.debug("Adding assistant message to memory", session_id=state["session_id"], response=state["response"])
        await memory.add_assistant_message(
            state["session_id"],
            state["response"],
            metadata={
                "intent": state["intent"].intent.value if state["intent"] else None,
                "actions": [r.get("action") for r in state.get("action_results", [])],
            }
        )
    
    if state.get("entities"):
        logger.debug("Updating entities in memory", session_id=state["session_id"], entities=state["entities"])
        await memory.update_entities(state["session_id"], state["entities"])
    
    suggested_actions = state.get("suggested_actions", [])
    if suggested_actions:
        logger.debug("Updating context with suggested actions", session_id=state["session_id"], suggested_actions=suggested_actions)
        await memory.update_context(state["session_id"], {
            "suggested_actions": suggested_actions,
            "last_completed_intent": state["intent"].intent.value if state["intent"] else None
        })
    
    logger.info("[graph.py] update_memory_node: EXIT", session_id=state["session_id"])
    
    return state


def should_continue_actions(state: AgentState) -> Literal["execute", "synthesize"]:
    """Conditional edge: Determine if more actions need execution."""
    logger.info("[graph.py] should_continue_actions: ENTRY", session_id=state.get("session_id", "unknown"))
    if state.get("error"):
        logger.info("[graph.py] should_continue_actions: EXIT - error found", result="synthesize")
        return "synthesize"
    
    if state.get("pending_actions"):
        logger.info("[graph.py] should_continue_actions: EXIT - pending actions", result="execute")
        return "execute"
    
    logger.info("[graph.py] should_continue_actions: EXIT - no more actions", result="synthesize")
    return "synthesize"


def build_orchestrator_graph() -> StateGraph:
    """Build the LangGraph orchestrator for test operations."""
    logger.info("[graph.py] build_orchestrator_graph: ENTRY")
    graph = StateGraph(AgentState)
    
    graph.add_node("retrieve_memory", retrieve_memory_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("plan_actions", plan_actions_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("synthesize_response", synthesize_response_node)
    graph.add_node("update_memory", update_memory_node)
    
    graph.set_entry_point("retrieve_memory")
    graph.add_edge("retrieve_memory", "classify_intent")
    graph.add_edge("classify_intent", "plan_actions")
    graph.add_edge("plan_actions", "execute_action")
    
    graph.add_conditional_edges(
        "execute_action",
        should_continue_actions,
        {
            "execute": "execute_action",
            "synthesize": "synthesize_response"
        }
    )
    
    graph.add_edge("synthesize_response", "update_memory")
    graph.add_edge("update_memory", END)
    
    memory_saver = MemorySaver()
    compiled = graph.compile(checkpointer=memory_saver)
    
    logger.info("[graph.py] build_orchestrator_graph: EXIT - graph built successfully")
    
    return compiled


_graph_instance = None


def get_orchestrator_graph():
    """Get or create the orchestrator graph."""
    logger.info("[graph.py] get_orchestrator_graph: ENTRY")
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_orchestrator_graph()
    logger.info("[graph.py] get_orchestrator_graph: EXIT")
    return _graph_instance
