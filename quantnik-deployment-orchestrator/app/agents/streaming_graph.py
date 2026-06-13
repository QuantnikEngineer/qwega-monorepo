from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, TypedDict

from app.agents.intent_classifier import ClassifiedIntent, get_classifier
from app.core.logging import get_logger
from app.memory.conversation_memory import get_memory
from app.models.requests import ChildAgentType, IntentType
from app.models.streaming import DeploymentMilestones, MilestoneTemplates, StreamingError, StreamingResponse
from app.tools.agent_client import get_agent_client

logger = get_logger(__name__)

CI_BUILDER_HANDOFF_FLOW = "confirmedGenerateCiPipeline"
CI_BUILDER_HANDOFF_MESSAGE = "Complete the CI pipeline form below to continue."


class StreamingAgentState(TypedDict):
    session_id: str
    messages: list[dict[str, str]]
    current_message: str
    intent: Optional[ClassifiedIntent]
    target_agent: Optional[ChildAgentType]
    entities: dict[str, Any]
    context: dict[str, Any]
    action_results: list[dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
    suggested_actions: list[dict[str, Any]]
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


async def execute_with_streaming(
    session_id: str,
    message: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    explicit_intent: str | None = None,
    target_agent: str | None = None,
) -> AsyncGenerator[str, None]:
    start_time = datetime.utcnow()
    context = context or {}
    history = history or []
    state: StreamingAgentState = {
        "session_id": session_id,
        "messages": history,
        "current_message": message,
        "intent": None,
        "target_agent": None,
        "entities": context.get("entities", {}),
        "context": context,
        "action_results": [],
        "response": None,
        "error": None,
        "suggested_actions": [],
        "child_response": None,
    }

    try:
        yield MilestoneTemplates.received(session_id).to_sse()
        await asyncio.sleep(0.1)
        yield MilestoneTemplates.thinking(message[:80]).to_sse()

        memory = get_memory()
        stored_history = await memory.get_conversation_history(session_id, limit=10)
        if stored_history and not state["messages"]:
            state["messages"] = stored_history
        state["context"]["last_agent"] = await memory.get_last_agent(session_id)
        state["context"]["suggested_actions"] = await memory.get_suggested_actions(session_id)

        yield MilestoneTemplates.analyzing_intent().to_sse()
        classified = _classify_request(message, state["context"], explicit_intent, target_agent)
        if classified is None:
            classifier = get_classifier()
            classified = await classifier.classify(message, state["context"])

        state["intent"] = classified
        state["target_agent"] = classified.target_agent
        state["entities"].update(classified.entities)
        yield MilestoneTemplates.analyzing_intent(classified.intent.value, classified.confidence).to_sse()

        if classified.intent == IntentType.CONFIRMATION:
            selected_action = _get_selected_action(message, state["context"].get("suggested_actions", []))
            if selected_action and selected_action.get("agent") in {"ci", "cd"}:
                state["target_agent"] = ChildAgentType(selected_action["agent"])
            else:
                state["response"] = "Please confirm that you want to generate a CI pipeline."
                state["suggested_actions"] = [{"action": "Generate a CI pipeline", "intent": "generate_ci_pipeline", "agent": "ci"}]

        if classified.intent == IntentType.GENERAL_QUESTION and not state["response"]:
            yield MilestoneTemplates.planning(["generate_help_response"]).to_sse()
            state["response"] = (
                "I can route CI pipeline requests to the CI agent and stream status back through the deployment flow. "
                "CD remains queued for a later phase."
            )
            state["suggested_actions"] = [{"action": "Generate a CI pipeline", "intent": "generate_ci_pipeline", "agent": "ci"}]

        elif (classified.intent == IntentType.UNKNOWN or state["target_agent"] == ChildAgentType.UNKNOWN) and not state["response"]:
            yield MilestoneTemplates.planning(["request_clarification"]).to_sse()
            state["response"] = classified.clarification_question or "Do you want to generate a CI pipeline?"
            state["suggested_actions"] = [{"action": "Generate a CI pipeline", "intent": "generate_ci_pipeline", "agent": "ci"}]

        elif state["target_agent"] is not None and state["target_agent"] != ChildAgentType.UNKNOWN:
            client = get_agent_client()
            if state["target_agent"] == ChildAgentType.CI:
                yield DeploymentMilestones.routing_to_ci().to_sse()
                if not _has_structured_ci_request(state["context"]):
                    child_response = _build_ci_builder_handoff_response()
                else:
                    yield MilestoneTemplates.executing(
                        "Preparing the normalized CI payload.",
                        progress=0.56,
                        details={
                            "pipeline_name": (state["context"].get("ci_pipeline_request") or {}).get("pipelineName"),
                            "platform": ((state["context"].get("ci_pipeline_request") or {}).get("target") or {}).get("platform"),
                        },
                    ).to_sse()
                    yield MilestoneTemplates.calling_agent("CI Agent").to_sse()
                    child_response = await client.call_ci_agent(message=message, context=state["context"])
            else:
                yield DeploymentMilestones.routing_to_cd().to_sse()
                yield MilestoneTemplates.calling_agent("CD Agent").to_sse()
                child_response = await client.call_cd_agent(message=message, context=state["context"])

            state["child_response"] = child_response
            state["response"] = child_response.get("message", "Deployment request processed.")
            state["suggested_actions"] = child_response.get("suggested_actions", [])
            child_error = (child_response.get("data") or {}).get("error")
            child_failed = child_response.get("status") == "error"
            if child_failed:
                state["error"] = state["response"]
                yield StreamingError(
                    title="CI Agent Rejected Request" if state["target_agent"] == ChildAgentType.CI else "Child Agent Error",
                    message=state["response"] or "Child agent request failed.",
                    details=child_error,
                ).to_sse()
            state["action_results"].append(
                {
                    "action": f"call_{state['target_agent'].value}_agent",
                    "success": not child_failed,
                    "result": {"status": child_response.get("status"), "error": child_error},
                }
            )

            await memory.set_last_agent(session_id, state["target_agent"].value)
            yield MilestoneTemplates.processing_response().to_sse()

        await memory.add_user_message(session_id, message)
        if state["response"]:
            await memory.add_assistant_message(session_id, state["response"])
        if state["suggested_actions"]:
            await memory.set_suggested_actions(session_id, state["suggested_actions"])

        summary = state["response"] or "Deployment request processed successfully."
        yield MilestoneTemplates.complete(summary).to_sse()

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        child_data = (state.get("child_response") or {}).get("data", {}) or {}
        final_response = StreamingResponse(
            session_id=session_id,
            message=summary,
            status="error" if state.get("error") or ((state.get("child_response") or {}).get("status") == "error") else "success",
            nextagentflow=(state.get("child_response") or {}).get("nextagentflow"),
            data={
                "intent": state["intent"].intent.value if state.get("intent") else None,
                "entities": state.get("entities", {}),
                "action_results": state.get("action_results", []),
                **({"error": {"type": "orchestrator_error", "detail": [state["error"]]}} if state.get("error") and not ((state.get("child_response") or {}).get("data") or {}).get("error") else {}),
                **child_data,
            },
            suggested_actions=state.get("suggested_actions", []),
            routed_to=state["target_agent"].value if state.get("target_agent") and state["target_agent"] != ChildAgentType.UNKNOWN else None,
            total_duration_ms=duration_ms,
        )
        yield final_response.to_sse()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Deployment streaming execution failed")
        yield StreamingError(message=str(exc)).to_sse()
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        yield StreamingResponse(
            session_id=session_id,
            message=f"I encountered an error: {exc}",
            status="error",
            data={"error": {"type": "orchestrator_exception", "detail": [str(exc)]}},
            total_duration_ms=duration_ms,
        ).to_sse()


def _classify_request(
    message: str,
    context: dict[str, Any],
    explicit_intent: str | None,
    target_agent: str | None,
) -> ClassifiedIntent | None:
    if target_agent in {"ci", "cd"}:
        agent = ChildAgentType(target_agent)
        intent = IntentType.GENERATE_CI_PIPELINE if agent == ChildAgentType.CI else IntentType.GENERATE_CD_PIPELINE
        return ClassifiedIntent(
            intent=intent,
            target_agent=agent,
            confidence=1.0,
            reasoning="Explicit target agent provided.",
        )

    if explicit_intent:
        mapping = {
            "generate_ci_pipeline": IntentType.GENERATE_CI_PIPELINE,
            "confirmedgeneratecipipeline": IntentType.GENERATE_CI_PIPELINE,
            "generate_cd_pipeline": IntentType.GENERATE_CD_PIPELINE,
        }
        intent = mapping.get(explicit_intent.lower())
        if intent is not None:
            agent = ChildAgentType.CI if intent == IntentType.GENERATE_CI_PIPELINE else ChildAgentType.CD
            return ClassifiedIntent(
                intent=intent,
                target_agent=agent,
                confidence=1.0,
                reasoning="Explicit intent provided.",
            )

    if context.get("ci_pipeline_request"):
        target = (context.get("ci_pipeline_request") or {}).get("target", {})
        return ClassifiedIntent(
            intent=IntentType.GENERATE_CI_PIPELINE,
            target_agent=ChildAgentType.CI,
            confidence=0.99,
            entities={"platform": target.get("platform")},
            reasoning="Structured CI payload provided.",
        )

    if message.lower().strip() in {"yes", "ok", "okay", "proceed", "continue", "1", "one"}:
        return ClassifiedIntent(
            intent=IntentType.CONFIRMATION,
            target_agent=ChildAgentType.UNKNOWN,
            confidence=0.92,
            reasoning="Confirmation response detected.",
        )

    return None


def _get_selected_action(message: str, suggested_actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not suggested_actions:
        return None

    normalized = message.lower().strip()
    index_lookup = {
        "1": 0,
        "one": 0,
        "first": 0,
        "option 1": 0,
        "2": 1,
        "two": 1,
        "second": 1,
        "option 2": 1,
    }
    for token, index in index_lookup.items():
        if normalized == token or token in normalized:
            if index < len(suggested_actions):
                return suggested_actions[index]

    return suggested_actions[0]