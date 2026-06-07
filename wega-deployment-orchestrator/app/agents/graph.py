from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.intent_classifier import ClassifiedIntent, get_classifier
from app.core.logging import get_logger
from app.memory.conversation_memory import get_memory
from app.models.requests import ChildAgentType, INTENT_TO_AGENT, IntentType
from app.tools.agent_client import get_agent_client

logger = get_logger(__name__)

CI_BUILDER_HANDOFF_FLOW = "confirmedGenerateCiPipeline"
CI_BUILDER_HANDOFF_MESSAGE = "Complete the CI pipeline form below to continue."


class AgentState(TypedDict):
    session_id: str
    messages: list[dict[str, str]]
    current_message: str
    intent: Optional[ClassifiedIntent]
    target_agent: Optional[ChildAgentType]
    entities: dict[str, Any]
    context: dict[str, Any]
    pending_actions: list[str]
    current_action: Optional[str]
    action_results: list[dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
    suggested_actions: list[dict[str, str]]
    metadata: dict[str, Any]
    child_response: Optional[dict[str, Any]]


def _has_structured_ci_request(context: dict[str, Any]) -> bool:
    ci_pipeline_request = context.get("ci_pipeline_request")
    return isinstance(ci_pipeline_request, dict) and bool(ci_pipeline_request)


def _build_ci_builder_handoff_response() -> dict[str, Any]:
    return {
        "status": "success",
        "message": CI_BUILDER_HANDOFF_MESSAGE,
        "nextagentflow": CI_BUILDER_HANDOFF_FLOW,
        "data": {
            "intent": IntentType.GENERATE_CI_PIPELINE.value,
            "message": CI_BUILDER_HANDOFF_MESSAGE,
        },
        "suggested_actions": [],
    }


async def retrieve_memory_node(state: AgentState) -> AgentState:
    memory = get_memory()
    history = await memory.get_conversation_history(state["session_id"], limit=10)
    if history and not state.get("messages"):
        state["messages"] = history
    state["context"]["last_agent"] = await memory.get_last_agent(state["session_id"])
    state["context"]["suggested_actions"] = await memory.get_suggested_actions(state["session_id"])
    return state


async def classify_intent_node(state: AgentState) -> AgentState:
    explicit_intent = state.get("context", {}).get("explicit_intent")
    target_agent = state.get("context", {}).get("target_agent")

    if target_agent in {"ci", "cd"}:
        agent = ChildAgentType(target_agent)
        intent_type = IntentType.GENERATE_CI_PIPELINE if agent == ChildAgentType.CI else IntentType.GENERATE_CD_PIPELINE
        state["intent"] = ClassifiedIntent(
            intent=intent_type,
            target_agent=agent,
            confidence=1.0,
            reasoning="Explicit target agent provided.",
        )
        state["target_agent"] = agent
        return state

    if explicit_intent:
        mapping = {
            "generate_ci_pipeline": IntentType.GENERATE_CI_PIPELINE,
            "generate_cd_pipeline": IntentType.GENERATE_CD_PIPELINE,
        }
        intent_type = mapping.get(str(explicit_intent).lower())
        if intent_type:
            state["intent"] = ClassifiedIntent(
                intent=intent_type,
                target_agent=INTENT_TO_AGENT[intent_type],
                confidence=1.0,
                reasoning="Explicit intent provided.",
            )
            state["target_agent"] = INTENT_TO_AGENT[intent_type]
            return state

    classifier = get_classifier()
    classified = await classifier.classify(state["current_message"], state.get("context", {}))
    state["intent"] = classified
    state["target_agent"] = classified.target_agent
    state["entities"].update(classified.entities)
    return state


async def plan_actions_node(state: AgentState) -> AgentState:
    intent = state.get("intent")
    if not intent:
        state["error"] = "No intent classified"
        return state

    if intent.intent == IntentType.CONFIRMATION:
        suggested_actions = state["context"].get("suggested_actions", [])
        if suggested_actions:
            selected = suggested_actions[0]
            agent = selected.get("agent")
            if agent in {"ci", "cd"}:
                state["target_agent"] = ChildAgentType(agent)
                state["context"]["explicit_intent"] = selected.get("intent")
                state["pending_actions"] = ["route_to_child_agent"]
                return state

    if intent.intent == IntentType.GENERAL_QUESTION:
        state["pending_actions"] = ["generate_help_response"]
        return state

    if intent.intent == IntentType.UNKNOWN or state["target_agent"] == ChildAgentType.UNKNOWN:
        state["pending_actions"] = ["request_clarification"]
        return state

    state["pending_actions"] = ["route_to_child_agent"]
    return state


async def execute_action_node(state: AgentState) -> AgentState:
    if not state["pending_actions"]:
        return state

    action = state["pending_actions"].pop(0)
    state["current_action"] = action

    try:
        result = await _execute_action(action, state)
        success = result.get("status") != "error" if isinstance(result, dict) else True
        state["action_results"].append({"action": action, "success": success, "result": result})
        if not success and not state.get("error"):
            state["error"] = result.get("message", "Child agent request failed.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Action failed")
        state["action_results"].append({"action": action, "success": False, "error": str(exc)})
        state["error"] = str(exc)

    return state


async def _execute_action(action: str, state: AgentState) -> dict[str, Any]:
    if action == "route_to_child_agent":
        return await _route_to_child(state)
    if action == "generate_help_response":
        return await _handle_help(state)
    if action == "request_clarification":
        return await _handle_clarification(state)
    raise ValueError(f"Unknown action: {action}")


async def _route_to_child(state: AgentState) -> dict[str, Any]:
    target = state["target_agent"]
    if not target or target == ChildAgentType.UNKNOWN:
        raise ValueError("No target deployment agent specified.")

    client = get_agent_client()
    if target == ChildAgentType.CI:
        if not _has_structured_ci_request(state.get("context", {})):
            response = _build_ci_builder_handoff_response()
        else:
            response = await client.call_ci_agent(
                message=state["current_message"],
                context=state.get("context", {}),
            )
    else:
        response = await client.call_cd_agent(
            message=state["current_message"],
            context=state.get("context", {}),
        )

    state["child_response"] = response
    state["response"] = response.get("message", "Deployment request processed.")
    state["suggested_actions"] = response.get("suggested_actions", [])
    if response.get("status") == "error":
        state["error"] = response.get("message", "Child agent request failed.")

    memory = get_memory()
    await memory.set_last_agent(state["session_id"], target.value)
    return response


async def _handle_help(state: AgentState) -> dict[str, Any]:
    state["response"] = (
        "I can help with deployment workflows through specialized agents. "
        "Right now the CI flow is wired end-to-end, and CD remains queued for a later phase. "
        "Ask me to generate a CI pipeline and I will route it to the CI agent."
    )
    state["suggested_actions"] = [
        {"action": "Generate a CI pipeline", "intent": "generate_ci_pipeline", "agent": "ci"},
    ]
    return {"help": True}


async def _handle_clarification(state: AgentState) -> dict[str, Any]:
    intent = state.get("intent")
    state["response"] = intent.clarification_question if intent else "Do you want to generate a CI pipeline? The CD flow is not wired yet."
    state["suggested_actions"] = [
        {"action": "Generate a CI pipeline", "intent": "generate_ci_pipeline", "agent": "ci"},
    ]
    return {"clarification": True}


async def synthesize_response_node(state: AgentState) -> AgentState:
    if state.get("child_response"):
        state["response"] = state["child_response"].get("message", state.get("response"))
    elif not state.get("response"):
        state["response"] = "Deployment request processed."
    return state


async def update_memory_node(state: AgentState) -> AgentState:
    memory = get_memory()
    await memory.add_user_message(state["session_id"], state["current_message"])
    if state.get("response"):
        await memory.add_assistant_message(state["session_id"], state["response"])
    if state.get("suggested_actions"):
        await memory.set_suggested_actions(state["session_id"], state["suggested_actions"])
    return state


def should_continue_actions(state: AgentState) -> Literal["execute", "synthesize"]:
    if state.get("error"):
        return "synthesize"
    if state.get("pending_actions"):
        return "execute"
    return "synthesize"


def build_orchestrator_graph() -> StateGraph:
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
        {"execute": "execute_action", "synthesize": "synthesize_response"},
    )
    graph.add_edge("synthesize_response", "update_memory")
    graph.add_edge("update_memory", END)

    return graph.compile(checkpointer=MemorySaver())


_graph_instance = None


def get_orchestrator_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_orchestrator_graph()
    return _graph_instance