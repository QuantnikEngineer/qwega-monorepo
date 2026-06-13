"""
Streaming LangGraph - Test Orchestrator
=======================================
Graph with milestone streaming for real-time progress updates.
"""

from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import asyncio

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType
from app.models.streaming import (
    MilestoneEvent, TestMilestones, StreamingResponse, StreamingError, MilestoneStage, ChildAgentEvent
)
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory
from app.tools.agent_tools import AgentToolRegistry

logger = get_logger(__name__)


async def execute_with_streaming(
    session_id: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    explicit_intent: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Execute test orchestration with streaming milestones.
    """
    start_time = datetime.utcnow()
    context = context or {}
    history = history or []
    
    logger.info(
        "[streaming_graph.py] execute_with_streaming: ENTRY",
        session_id=session_id,
        message_preview=message[:50] if message else ""
    )
    logger.debug(
        "Streaming execution input",
        session_id=session_id,
        message=message,
        context=context,
        history_count=len(history),
        explicit_intent=explicit_intent
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
    
    logger.debug("Initial streaming state prepared", session_id=session_id, state=state)
    
    registry = AgentToolRegistry()
    
    try:
        # === MILESTONE: Request Received ===
        logger.debug("SSE milestone: request_received", session_id=session_id)
        yield TestMilestones.received(session_id).to_sse()
        await asyncio.sleep(0.3)
        
        # === MILESTONE: Thinking ===
        logger.debug("SSE milestone: thinking", session_id=session_id, message_preview=message[:50])
        yield TestMilestones.thinking(message[:50]).to_sse()
        
        # Retrieve memory
        logger.debug("Retrieving memory for streaming", session_id=session_id)
        memory = get_memory()
        stored_entities = await memory.get_entities(session_id)
        state["entities"] = {**stored_entities, **state["entities"]}
        logger.debug("Memory entities retrieved", session_id=session_id, entities=state["entities"])
        
        full_context = await memory.get_full_context(session_id)
        state["context"]["suggested_actions"] = full_context.get("suggested_actions", [])
        state["context"]["last_intent"] = full_context.get("last_intent")
        logger.debug("Full context retrieved", session_id=session_id, full_context=full_context)
        
        await asyncio.sleep(0.5)
        
        # === MILESTONE: Analyzing Intent ===
        logger.debug("SSE milestone: analyzing_intent", session_id=session_id)
        yield TestMilestones.analyzing_intent().to_sse()
        
        # Check for explicit intent
        if explicit_intent and explicit_intent != "string":
            logger.debug("Using explicit intent", session_id=session_id, explicit_intent=explicit_intent)
            intent_mapping = {
                "generate_test_cases": IntentType.GENERATE_TEST_CASES,
                "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
                "generate_test_data": IntentType.GENERATE_TEST_DATA,
            }
            intent_type = intent_mapping.get(explicit_intent.lower())
            if intent_type:
                classified = ClassifiedIntent(
                    intent=intent_type,
                    confidence=1.0,
                    reasoning="Explicit intent provided"
                )
                state["intent"] = classified
                logger.info("Explicit intent classified", session_id=session_id, intent=intent_type.value)
        
        if not state["intent"]:
            logger.debug("Classifying intent via classifier", session_id=session_id)
            classifier = get_classifier()
            classified = await classifier.classify(
                message=message,
                history=history,
                context=state["context"]
            )
            state["intent"] = classified
            state["entities"].update(classified.entities)
            logger.info(
                "Intent classified",
                session_id=session_id,
                intent=classified.intent.value,
                confidence=classified.confidence,
                entities=classified.entities
            )
        
        logger.debug(
            "SSE milestone: analyzing_intent complete",
            session_id=session_id,
            intent=state["intent"].intent.value,
            confidence=state["intent"].confidence
        )
        yield TestMilestones.analyzing_intent(
            intent=state["intent"].intent.value,
            confidence=state["intent"].confidence
        ).to_sse()
        
        await memory.set_last_intent(session_id, state["intent"].intent.value)
        await asyncio.sleep(0.3)
        
        intent = state["intent"]
        
        # === Handle CONFIRMATION ===
        if intent.intent == IntentType.CONFIRMATION:
            suggested_actions = state["context"].get("suggested_actions", [])
            if suggested_actions:
                selected = _get_selected_action(message, suggested_actions)
                if selected:
                    new_intent = selected.get("intent")
                    if new_intent:
                        intent_mapping = {
                            "generate_test_cases": IntentType.GENERATE_TEST_CASES,
                            "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
                            "generate_test_data": IntentType.GENERATE_TEST_DATA,
                        }
                        mapped = intent_mapping.get(new_intent)
                        if mapped:
                            state["intent"] = ClassifiedIntent(
                                intent=mapped,
                                confidence=1.0,
                                reasoning="User confirmed action"
                            )
                            intent = state["intent"]
        
        # === MILESTONE: Planning ===
        logger.debug("SSE milestone: planning", session_id=session_id, intent=intent.intent.value)
        action_plans = {
            IntentType.GENERATE_TEST_CASES: ["validate_stories", "call_test_cases_agent"],
            IntentType.GENERATE_TEST_SCRIPT: ["validate_test_cases", "call_test_script_agent", "push_to_repo"],
            IntentType.GENERATE_TEST_DATA: ["validate_test_data_input", "call_test_data_agent"],
            IntentType.GENERAL_QUESTION: ["generate_help_response"],
            IntentType.UNKNOWN: ["request_clarification"],
        }
        
        planned = action_plans.get(intent.intent, ["request_clarification"])
        if intent.requires_clarification:
            planned = ["request_clarification"]
        
        state["pending_actions"] = planned.copy()
        logger.info("Actions planned", session_id=session_id, planned_actions=planned)
        
        yield TestMilestones.planning(planned).to_sse()
        await asyncio.sleep(0.3)
        
        # === Execute Actions with Milestones ===
        total_actions = len(planned)
        action_index = 0
        
        while state["pending_actions"]:
            action = state["pending_actions"].pop(0)
            action_index += 1
            
            logger.info(
                "Executing action",
                session_id=session_id,
                action=action,
                action_index=action_index,
                total_actions=total_actions
            )
            
            # Handle streaming agent calls separately
            if action == "call_test_cases_agent":
                logger.debug("SSE milestone: calling_scenario_agent", session_id=session_id)
                yield TestMilestones.calling_scenario_agent().to_sse()
                
                try:
                    if settings.enable_child_agent_streaming:
                        # Stream events from child agent
                        logger.info("Using streaming mode for test scenario agent", session_id=session_id)
                        child_event_count = 0
                        final_result = None
                        async for event in registry.call_test_cases_agent_streaming(state):
                            child_event_count += 1
                            logger.debug(
                                "Forwarding child agent SSE event",
                                session_id=session_id,
                                agent="test_scenario_agent",
                                event_number=child_event_count
                            )
                            yield event
                            
                            # Try to extract final result from response event
                            try:
                                import json
                                event_data = json.loads(event.replace("data: ", "").strip())
                                if event_data.get("type") == "response":
                                    final_result = event_data.get("data", {})
                            except:
                                pass
                        
                        result = final_result or {"success": True, "streamed": True, "event_count": child_event_count}
                        logger.info(
                            "Streaming action completed",
                            session_id=session_id,
                            action=action,
                            child_events=child_event_count
                        )
                    else:
                        # Non-streaming fallback
                        logger.info("Using non-streaming mode for test scenario agent", session_id=session_id)
                        result = await registry.call_test_cases_agent(state)
                        logger.info("Non-streaming action completed", session_id=session_id, action=action)
                    
                    state["action_results"].append({
                        "action": action,
                        "success": True,
                        "result": result
                    })
                except Exception as e:
                    state["error"] = str(e)
                    state["action_results"].append({
                        "action": action,
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(
                        "Test scenario agent action failed",
                        session_id=session_id,
                        action=action,
                        error=str(e),
                        error_type=type(e).__name__,
                        streaming=settings.enable_child_agent_streaming,
                        exc_info=True
                    )
                    yield StreamingError(message=f"Test Scenario agent error: {str(e)}", source_agent="test_scenario_agent").to_sse()
                    break
                    
            elif action == "call_test_script_agent":
                framework = state["context"].get("framework_type", "Selenium")
                logger.debug("SSE milestone: calling_script_agent", session_id=session_id, framework=framework)
                yield TestMilestones.calling_script_agent(framework).to_sse()
                
                try:
                    if settings.enable_child_agent_streaming:
                        # Stream events from child agent
                        logger.info("Using streaming mode for test script agent", session_id=session_id)
                        child_event_count = 0
                        final_result = None
                        async for event in registry.call_test_script_agent_streaming(state):
                            child_event_count += 1
                            logger.debug(
                                "Forwarding child agent SSE event",
                                session_id=session_id,
                                agent="test_script_agent",
                                event_number=child_event_count
                            )
                            yield event
                            
                            # Try to extract final result from response event
                            try:
                                import json
                                event_data = json.loads(event.replace("data: ", "").strip())
                                if event_data.get("type") == "response":
                                    final_result = event_data.get("data", {})
                                    # Extract push_results from the response
                                    if "push_results" in event_data:
                                        if final_result is None:
                                            final_result = {}
                                        final_result["push_results"] = event_data.get("push_results")
                            except:
                                pass
                        
                        result = final_result or {"success": True, "streamed": True, "event_count": child_event_count}
                        logger.info(
                            "Streaming action completed",
                            session_id=session_id,
                            action=action,
                            child_events=child_event_count,
                            has_push_results=bool(result.get("push_results"))
                        )
                    else:
                        # Non-streaming fallback
                        logger.info("Using non-streaming mode for test script agent", session_id=session_id)
                        result = await registry.call_test_script_agent(state)
                        logger.info("Non-streaming action completed", session_id=session_id, action=action)
                    
                    state["action_results"].append({
                        "action": action,
                        "success": True,
                        "result": result
                    })
                except Exception as e:
                    state["error"] = str(e)
                    state["action_results"].append({
                        "action": action,
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(
                        "Test script agent action failed",
                        session_id=session_id,
                        action=action,
                        error=str(e),
                        error_type=type(e).__name__,
                        streaming=settings.enable_child_agent_streaming,
                        exc_info=True
                    )
                    yield StreamingError(message=f"Test Script agent error: {str(e)}", source_agent="test_script_agent").to_sse()
                    break

            elif action == "call_test_data_agent":
                logger.debug("SSE milestone: calling_test_data_agent", session_id=session_id)
                yield TestMilestones.calling_test_data_agent().to_sse()
                
                try:
                    if settings.enable_child_agent_streaming:
                        logger.info("Using streaming mode for test data agent", session_id=session_id)
                        child_event_count = 0
                        final_result = None
                        async for event in registry.call_test_data_agent_streaming(state):
                            child_event_count += 1
                            logger.debug(
                                "Forwarding child agent SSE event",
                                session_id=session_id,
                                agent="test_data_agent",
                                event_number=child_event_count
                            )
                            yield event
                            
                            try:
                                import json
                                event_data = json.loads(event.replace("data: ", "").strip())
                                if event_data.get("type") == "response":
                                    final_result = event_data.get("data", {})
                            except:
                                pass
                        
                        result = final_result or {"success": True, "streamed": True, "event_count": child_event_count}
                        logger.info(
                            "Streaming action completed",
                            session_id=session_id,
                            action=action,
                            child_events=child_event_count
                        )
                    else:
                        logger.info("Using non-streaming mode for test data agent", session_id=session_id)
                        result = await registry.call_test_data_agent(state)
                        logger.info("Non-streaming action completed", session_id=session_id, action=action)
                    
                    state["action_results"].append({
                        "action": action,
                        "success": True,
                        "result": result
                    })
                except Exception as e:
                    state["error"] = str(e)
                    state["action_results"].append({
                        "action": action,
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(
                        "Test data agent action failed",
                        session_id=session_id,
                        action=action,
                        error=str(e),
                        error_type=type(e).__name__,
                        streaming=settings.enable_child_agent_streaming,
                        exc_info=True
                    )
                    yield StreamingError(message=f"Test Data agent error: {str(e)}", source_agent="test_data_agent").to_sse()
                    break
                    
            elif action == "push_to_repo":
                logger.debug("SSE milestone: pushing_to_repo", session_id=session_id)
                yield TestMilestones.pushing_to_repo().to_sse()
                try:
                    result = await _execute_action(action, state, registry)
                    state["action_results"].append({
                        "action": action,
                        "success": True,
                        "result": result
                    })
                    logger.info("Action executed successfully", session_id=session_id, action=action, result=result)
                except Exception as e:
                    state["error"] = str(e)
                    state["action_results"].append({"action": action, "success": False, "error": str(e)})
                    logger.error("Action execution failed", session_id=session_id, action=action, error=str(e), exc_info=True)
                    break
            else:
                logger.debug("SSE milestone: executing", session_id=session_id, action=action)
                yield TestMilestones.executing(action, action_index, total_actions).to_sse()
                
                try:
                    result = await _execute_action(action, state, registry)
                    state["action_results"].append({
                        "action": action,
                        "success": True,
                        "result": result
                    })
                    logger.info(
                        "Action executed successfully",
                        session_id=session_id,
                        action=action,
                        result=result
                    )
                except ValueError as e:
                    error_msg = str(e)
                    # Handle validation errors with nextagentflow
                    if error_msg == "Missing user_stories":
                        logger.info("Validation required: missing user_stories", session_id=session_id)
                        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        validation_response = StreamingResponse(
                            session_id=session_id,
                            message="Please select user story(ies) or review and proceed to generate test cases.",
                            status="success",
                            nextagentflow="confirmedUserStoryToTestScenario",
                            data={
                                "intent": state["intent"].intent.value if state["intent"] else None,
                                "entities": state["entities"],
                                "validation_required": True,
                                "missing_fields": ["user_stories"]
                            },
                            suggested_actions=[],
                            total_duration_ms=duration_ms
                        )
                        yield validation_response.to_sse()
                        return
                    elif error_msg == "Missing test_cases":
                        logger.info("Validation required: missing test_cases", session_id=session_id)
                        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        validation_response = StreamingResponse(
                            session_id=session_id,
                            message="Please provide test cases to generate test scripts.",
                            status="success",
                            nextagentflow="confirmedTestCaseToTestScript",
                            data={
                                "intent": state["intent"].intent.value if state["intent"] else None,
                                "entities": state["entities"],
                                "validation_required": True,
                                "missing_fields": ["test_cases"]
                            },
                            suggested_actions=[],
                            total_duration_ms=duration_ms
                        )
                        yield validation_response.to_sse()
                        return
                    elif error_msg == "Missing test_data_cases":
                        logger.info("Validation required: missing test_cases for test data", session_id=session_id)
                        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        validation_response = StreamingResponse(
                            session_id=session_id,
                            message="Please provide test cases to generate test data.",
                            status="success",
                            nextagentflow="confirmedTestDataGenerator",
                            data={
                                "intent": state["intent"].intent.value if state["intent"] else None,
                                "entities": state["entities"],
                                "validation_required": True,
                                "missing_fields": ["test_cases"]
                            },
                            suggested_actions=[],
                            total_duration_ms=duration_ms
                        )
                        yield validation_response.to_sse()
                        return
                    else:
                        # Re-raise other ValueError exceptions
                        raise
                except Exception as e:
                    state["error"] = str(e)
                    state["action_results"].append({
                        "action": action,
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(
                        "Action execution failed",
                        session_id=session_id,
                        action=action,
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True
                    )
                    break
        
        # === MILESTONE: Processing Response ===
        logger.debug("SSE milestone: processing_response", session_id=session_id)
        yield TestMilestones.processing_response().to_sse()
        await asyncio.sleep(0.3)
        
        # === MILESTONE: Synthesizing ===
        logger.debug("SSE milestone: synthesizing", session_id=session_id)
        yield TestMilestones.synthesizing().to_sse()
        
        # Build response if not set
        if not state.get("response"):
            if state.get("error"):
                state["response"] = f"I encountered an issue: {state['error']}"
                logger.debug("Response built from error", session_id=session_id, error=state["error"])
            else:
                state["response"] = _format_response(intent.intent, state["action_results"])
                logger.debug("Response formatted", session_id=session_id, response=state["response"])
        
        # Set suggested actions
        if not state["suggested_actions"]:
            state["suggested_actions"] = _get_suggested_actions(intent.intent)
            logger.debug("Suggested actions set", session_id=session_id, suggested_actions=state["suggested_actions"])
        
        # Update memory
        logger.debug("Updating memory with conversation", session_id=session_id)
        await memory.add_user_message(session_id, message)
        await memory.add_assistant_message(session_id, state["response"])
        
        if state["entities"]:
            await memory.update_entities(session_id, state["entities"])
        
        if state["suggested_actions"]:
            await memory.update_context(session_id, {"suggested_actions": state["suggested_actions"]})
        
        await asyncio.sleep(0.3)
        
        # === MILESTONE: Complete ===
        logger.debug("SSE milestone: complete", session_id=session_id)
        yield TestMilestones.complete("Test generation completed successfully").to_sse()
        
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # === Final Response ===
        # Extract job_id, poll_url, total, message, test_scripts, push_results from action_results
        job_id = None
        poll_url = None
        total = None
        message = None
        test_scripts = None
        push_results = None
        test_data = None
        for action_result in state["action_results"]:
            if action_result.get("success") and action_result.get("result"):
                result_data = action_result["result"]
                job_id = result_data.get("job_id") or job_id
                poll_url = result_data.get("poll_url") or poll_url
                total = result_data.get("total") or total
                message = result_data.get("message") or message
                test_scripts = result_data.get("test_scripts") or test_scripts
                push_results = result_data.get("push_results") or push_results
                test_data = result_data.get("test_data") or test_data
        
        final_response = StreamingResponse(
            session_id=session_id,
            message=state["response"],
            status="success" if not state.get("error") else "error",
            data={
                "intent": state["intent"].intent.value if state["intent"] else None,
                "entities": state["entities"],
                "action_results": state["action_results"],
                "job_id": job_id,
                "poll_url": poll_url,
                "total": total,
                "message": message,
                "test_scripts": test_scripts,
                "push_results": push_results,
                "test_data": test_data,
            },
            suggested_actions=state["suggested_actions"],
            total_duration_ms=duration_ms
        )
        
        logger.info(
            "Streaming execution completed",
            session_id=session_id,
            status=final_response.status,
            duration_ms=duration_ms
        )
        logger.debug("SSE final response", session_id=session_id, final_response=final_response.__dict__)
        
        yield final_response.to_sse()
        
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.error(
            "Streaming execution error",
            error=str(e),
            error_type=type(e).__name__,
            session_id=session_id,
            duration_ms=duration_ms,
            exc_info=True
        )
        
        logger.debug("SSE error event", session_id=session_id, error=str(e))
        yield StreamingError(message=str(e)).to_sse()
        
        final_response = StreamingResponse(
            session_id=session_id,
            message=f"I encountered an error: {str(e)}",
            status="error",
            total_duration_ms=duration_ms
        )
        logger.debug("SSE error final response", session_id=session_id, final_response=final_response.__dict__)
        yield final_response.to_sse()
    
    finally:
        logger.debug("Closing registry", session_id=session_id)
        await registry.close()
        logger.info("[streaming_graph.py] execute_with_streaming: EXIT", session_id=session_id)


async def _execute_action(action: str, state: Dict[str, Any], registry: AgentToolRegistry) -> Dict[str, Any]:
    """
    Execute a single non-streaming action.
    
    Note: Streaming agent calls (call_test_cases_agent, call_test_script_agent)
    are handled directly in execute_with_streaming() to allow SSE forwarding.
    """
    session_id = state.get("session_id", "unknown")
    logger.info("[streaming_graph.py] _execute_action: ENTRY", session_id=session_id, action=action)
    
    if action == "request_clarification":
        state["response"] = _get_clarification_response(state.get("intent"))
        logger.debug("Clarification response set", session_id=session_id, response=state["response"])
        logger.info("[streaming_graph.py] _execute_action: EXIT - clarification", session_id=session_id, action=action)
        return {"clarification_sent": True}
    
    if action == "generate_help_response":
        state["response"] = _get_help_response()
        logger.debug("Help response set", session_id=session_id, response=state["response"])
        logger.info("[streaming_graph.py] _execute_action: EXIT - help response", session_id=session_id, action=action)
        return {"help_sent": True}
    
    if action == "validate_stories":
        entities = state.get("entities", {})
        context = state.get("context", {})
        
        logger.info(
            "[streaming_graph.py] _execute_action validate_stories: Starting validation for generate_test_cases",
            session_id=session_id
        )
        logger.debug(
            "[streaming_graph.py] _execute_action validate_stories: Input data",
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
                    "[streaming_graph.py] _execute_action validate_stories: Found create_user_story_text, extracting user_stories",
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
                        "[streaming_graph.py] _execute_action validate_stories: Extracted user_stories from create_user_story_text",
                        session_id=session_id,
                        story_count=len(stories)
                    )
        
        if not stories:
            state["error"] = "Please provide user stories to proceed"
            logger.warning(
                "[streaming_graph.py] _execute_action validate_stories: Validation failed - missing user_stories",
                session_id=session_id,
                checked_locations=["entities.user_stories", "context.user_stories", "entities.create_user_story_text", "context.create_user_story_text"]
            )
            raise ValueError("Missing user_stories")
        
        logger.info(
            "[streaming_graph.py] _execute_action validate_stories: Validation passed for generate_test_cases",
            session_id=session_id,
            story_count=len(stories) if isinstance(stories, list) else 1
        )
        logger.info("[streaming_graph.py] _execute_action: EXIT - validate_stories passed", session_id=session_id, action=action)
        return {"validated": True}
    
    if action == "validate_test_cases":
        logger.info("[streaming_graph.py] _execute_action validate_test_cases: ENTRY", session_id=session_id)
        context = state.get("context", {})
        if not context.get("test_cases"):
            state["error"] = "Please provide test cases"
            logger.warning("[streaming_graph.py] _execute_action validate_test_cases: Validation failed - missing test_cases", session_id=session_id)
            raise ValueError("Missing test_cases")
        logger.info("[streaming_graph.py] _execute_action: EXIT - validate_test_cases passed", session_id=session_id, action=action)
        return {"validated": True}
    
    if action == "validate_test_data_input":
        context = state.get("context", {})
        if not context.get("test_cases"):
            state["error"] = "Please provide test cases for data generation"
            logger.warning("Validation failed: missing test_cases for test data", session_id=session_id)
            raise ValueError("Missing test_data_cases")
        logger.debug("Test data input validated", session_id=session_id)
        return {"validated": True}
    
    if action == "push_to_repo":
        logger.info("[streaming_graph.py] _execute_action: EXIT - push_to_repo", session_id=session_id, action=action)
        return {"pushed": True}
    
    logger.warning("[streaming_graph.py] _execute_action: EXIT - unknown action", session_id=session_id, action=action)
    return {}


def _get_selected_action(message: str, suggested_actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get selected action from message."""
    logger.info("[streaming_graph.py] _get_selected_action: ENTRY", message=message[:50] if message else "")
    msg_lower = message.lower().strip()
    
    number_words = {"first": 0, "1": 0, "second": 1, "2": 1, "third": 2, "3": 2}
    
    for pattern, index in number_words.items():
        if pattern in msg_lower:
            if index < len(suggested_actions):
                logger.info("[streaming_graph.py] _get_selected_action: EXIT", selected_index=index)
                return suggested_actions[index]
    
    logger.info("[streaming_graph.py] _get_selected_action: EXIT - default first action")
    return suggested_actions[0] if suggested_actions else None


def _format_response(intent: IntentType, results: List[Dict[str, Any]]) -> str:
    """Format response based on intent."""
    logger.info("[streaming_graph.py] _format_response: ENTRY", intent=intent.value if intent else None)
    main_result = None
    for r in results:
        if r.get("action", "").startswith("call_") and r.get("success"):
            main_result = r.get("result", {})
            break
    
    if not main_result:
        logger.info("[streaming_graph.py] _format_response: EXIT - no main result")
        return "I've processed your test request."
    
    formatters = {
        IntentType.GENERATE_TEST_CASES: lambda r: "Generated test scenarios for your user stories.",
        IntentType.GENERATE_TEST_SCRIPT: lambda r: f"Generated test scripts. {r.get('push_status', '')}",
        IntentType.GENERATE_TEST_DATA: lambda r: "Generated test data successfully.",
    }
    
    formatter = formatters.get(intent, lambda r: "Test request processed successfully.")
    response = formatter(main_result)
    logger.info("[streaming_graph.py] _format_response: EXIT", intent=intent.value if intent else None)
    return response


def _get_suggested_actions(intent: IntentType) -> List[Dict[str, str]]:
    """Get suggested actions for intent."""
    logger.info("[streaming_graph.py] _get_suggested_actions: ENTRY", intent=intent.value if intent else None)
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
    logger.info("[streaming_graph.py] _get_suggested_actions: EXIT", intent=intent.value if intent else None, suggestion_count=len(result))
    return result


def _get_clarification_response(intent: Optional[ClassifiedIntent]) -> str:
    """Get clarification response."""
    logger.info("[streaming_graph.py] _get_clarification_response: ENTRY")
    if intent and intent.clarification_question:
        logger.info("[streaming_graph.py] _get_clarification_response: EXIT - using intent clarification")
        return intent.clarification_question
    logger.info("[streaming_graph.py] _get_clarification_response: EXIT - using default clarification")
    return (
        "I'm not sure what you'd like to do. Could you please tell me more? "
        "For example, you can:\n"
        "- Generate test scenarios from user stories\n"
        "- Generate test scripts from test cases"
    )


def _get_help_response() -> str:
    """Get help response."""
    logger.info("[streaming_graph.py] _get_help_response: ENTRY")
    logger.info("[streaming_graph.py] _get_help_response: EXIT")
    return (
        "I'm QUANTNIK Test Orchestrator, your test automation assistant. I can help you with:\n\n"
        "**Test Scenarios:**\n"
        "- Generate test scenarios from user stories\n\n"
        "**Test Scripts:**\n"
        "- Create automated test scripts (Selenium, Playwright)\n"
        "- Support for Java, JavaScript, TypeScript, Python, C#\n\n"
        "Just tell me what you'd like to do!"
    )
