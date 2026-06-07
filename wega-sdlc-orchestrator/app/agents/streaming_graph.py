"""
Streaming LangGraph State Machine - SDLC Orchestrator
=====================================================
Graph with milestone streaming support for real-time progress updates.
"""

from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import asyncio

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType, OrchestratorType, INTENT_TO_ORCHESTRATOR
from app.models.streaming import (
    MilestoneEvent, MilestoneTemplates, SDLCMilestones,
    StreamingResponse, StreamingError, MilestoneStage, AnimationType
)
import json
from app.agents.intent_classifier import get_classifier, ClassifiedIntent
from app.memory.conversation_memory import get_memory
from app.tools.orchestrator_client import get_orchestrator_client

logger = get_logger(__name__)


class StreamingAgentState(TypedDict):
    """State for streaming execution."""
    session_id: str
    messages: List[Dict[str, str]]
    current_message: str
    intent: Optional[ClassifiedIntent]
    target_orchestrator: Optional[OrchestratorType]
    entities: Dict[str, Any]
    context: Dict[str, Any]
    pending_actions: List[str]
    action_results: List[Dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
    suggested_actions: List[Dict[str, str]]
    metadata: Dict[str, Any]
    child_response: Optional[Dict[str, Any]]


async def execute_with_streaming(
    session_id: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    explicit_intent: Optional[str] = None,
    target_orchestrator: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Execute the SDLC orchestration with streaming milestones.
    
    Yields SSE-formatted milestone events during execution.
    """
    start_time = datetime.utcnow()
    context = context or {}
    history = history or []
    
    logger.info(
        "[execute_with_streaming] Starting streaming execution",
        session_id=session_id,
        message_length=len(message),
        message_preview=message[:100],
        has_context=bool(context),
        history_count=len(history),
        explicit_intent=explicit_intent,
        target_orchestrator=target_orchestrator
    )
    
    state: StreamingAgentState = {
        "session_id": session_id,
        "messages": history,
        "current_message": message,
        "intent": None,
        "target_orchestrator": None,
        "entities": context.get("entities", {}),
        "context": context,
        "pending_actions": [],
        "action_results": [],
        "response": None,
        "error": None,
        "suggested_actions": [],
        "metadata": {"start_time": start_time.isoformat()},
        "child_response": None,
    }
    
    try:
        # === MILESTONE: Request Received ===
        logger.debug("[execute_with_streaming] Emitting SSE milestone: received", session_id=session_id)
        yield MilestoneTemplates.received(session_id).to_sse()
        await asyncio.sleep(0.3)  # Brief pause for visual effect
        
        # === MILESTONE: Thinking ===
        logger.debug("[execute_with_streaming] Emitting SSE milestone: thinking", session_id=session_id)
        yield MilestoneTemplates.thinking(message[:50]).to_sse()
        
        # Retrieve memory
        logger.debug("[execute_with_streaming] Retrieving memory context", session_id=session_id)
        memory = get_memory()
        stored_entities = await memory.get_entities(session_id)
        state["entities"] = {**stored_entities, **state["entities"]}
        
        full_context = await memory.get_full_context(session_id)
        state["context"]["last_orchestrator"] = full_context.get("last_orchestrator")
        state["context"]["suggested_actions"] = full_context.get("suggested_actions", [])
        state["context"]["last_intent"] = full_context.get("last_intent")
        state["context"]["pending_confirmation"] = full_context.get("pending_confirmation")
        
        logger.debug(
            "[execute_with_streaming] Memory context retrieved",
            session_id=session_id,
            last_orchestrator=state["context"].get("last_orchestrator"),
            last_intent=state["context"].get("last_intent"),
            suggested_actions_count=len(state["context"].get("suggested_actions", [])),
            pending_confirmation=state["context"].get("pending_confirmation")
        )
        
        await asyncio.sleep(0.5)
        
        # === MILESTONE: Analyzing Intent ===
        logger.debug("[execute_with_streaming] Emitting SSE milestone: analyzing_intent", session_id=session_id)
        yield MilestoneTemplates.analyzing_intent().to_sse()
        
        # Check for explicit overrides
        if target_orchestrator:
            logger.info(
                "[execute_with_streaming] Using explicit target orchestrator override",
                session_id=session_id,
                target_orchestrator=target_orchestrator
            )
            orch_type = OrchestratorType(target_orchestrator) if target_orchestrator in ["planning", "test"] else OrchestratorType.UNKNOWN
            state["target_orchestrator"] = orch_type
            state["intent"] = ClassifiedIntent(
                intent=IntentType.UNKNOWN,
                target_orchestrator=orch_type,
                confidence=1.0,
                reasoning="Explicit orchestrator target"
            )
        elif explicit_intent and explicit_intent != "string":
            # Use explicit intent to skip LLM classification and route directly
            intent_type_map = {e.value: e for e in IntentType}
            intent_type = intent_type_map.get(explicit_intent.lower())
            if intent_type:
                target_orch = INTENT_TO_ORCHESTRATOR.get(intent_type, OrchestratorType.UNKNOWN)
                state["target_orchestrator"] = target_orch
                state["intent"] = ClassifiedIntent(
                    intent=intent_type,
                    target_orchestrator=target_orch,
                    confidence=1.0,
                    reasoning="Explicit intent provided"
                )
                state["metadata"]["explicit_intent"] = explicit_intent
                logger.info(
                    "[execute_with_streaming] Using explicit intent override",
                    session_id=session_id,
                    explicit_intent=explicit_intent,
                    target_orchestrator=target_orch.value
                )
            else:
                # Fallback to LLM classification if intent not recognized
                logger.debug("[execute_with_streaming] Explicit intent not recognized, falling back to classifier", session_id=session_id, explicit_intent=explicit_intent)
                classifier = get_classifier()
                classified = await classifier.classify(
                    message=message,
                    history=history,
                    context=state["context"]
                )
                state["intent"] = classified
                state["target_orchestrator"] = classified.target_orchestrator
                state["entities"].update(classified.entities)
        else:
            # Classify intent
            logger.debug("[execute_with_streaming] Classifying intent via classifier", session_id=session_id)
            classifier = get_classifier()
            classified = await classifier.classify(
                message=message,
                history=history,
                context=state["context"]
            )
            state["intent"] = classified
            state["target_orchestrator"] = classified.target_orchestrator
            state["entities"].update(classified.entities)
            logger.info(
                "[execute_with_streaming] Intent classified",
                session_id=session_id,
                intent=classified.intent.value,
                target_orchestrator=classified.target_orchestrator.value,
                confidence=classified.confidence,
                requires_clarification=classified.requires_clarification
            )
        
        # Emit intent result
        logger.debug(
            "[execute_with_streaming] Emitting SSE milestone: intent result",
            session_id=session_id,
            intent=state["intent"].intent.value,
            confidence=state["intent"].confidence
        )
        yield MilestoneTemplates.analyzing_intent(
            intent=state["intent"].intent.value,
            confidence=state["intent"].confidence
        ).to_sse()
        
        await memory.set_last_intent(session_id, state["intent"].intent.value)
        await asyncio.sleep(0.3)
        
        # === Handle based on intent ===
        intent = state["intent"]
        logger.debug(
            "[execute_with_streaming] Processing intent",
            session_id=session_id,
            intent=intent.intent.value,
            target_orchestrator=state["target_orchestrator"].value if state["target_orchestrator"] else None
        )
        
        # === Check for pending confirmation from previous request ===
        pending_confirmation = state["context"].get("pending_confirmation")
        if pending_confirmation:
            logger.info(
                "[execute_with_streaming] Found pending confirmation",
                session_id=session_id,
                pending_intent=pending_confirmation.get("intent"),
                user_message=message
            )
            
            # Check if user confirmed (yes, proceed, ok, etc.) or denied (no, cancel, etc.)
            message_lower = message.lower().strip()
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
                logger.info(
                    "[execute_with_streaming] User confirmed pending intent",
                    session_id=session_id,
                    pending_intent=pending_confirmation.get("intent")
                )
                # Set intent and orchestrator from pending confirmation
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
                    intent = state["intent"]
                
                # Clear pending confirmation
                await memory.clear_pending_confirmation(session_id)
                
            elif is_denied:
                # User denied - clear pending confirmation and ask what they want
                logger.info(
                    "[execute_with_streaming] User denied pending intent",
                    session_id=session_id
                )
                await memory.clear_pending_confirmation(session_id)
                
                state["response"] = (
                    "No problem! What would you like to do instead?\n\n"
                    "I can help with:\n"
                    "- **BRD creation** from transcripts\n"
                    "- **User story generation** from BRDs\n"
                    "- **Test case generation**\n"
                    "- **Query knowledge base** for information\n"
                    "- **List documents** in knowledge base\n"
                    "- **Provide feedback** or suggestions\n\n"
                    "Just let me know!"
                )
                state["suggested_actions"] = [
                    {"action": "Create a BRD", "intent": "create_brd", "orchestrator": "planning"},
                    {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
                    {"action": "Query knowledge base", "intent": "context_enrich_query", "orchestrator": "common_integration"},
                ]
                
                # Skip to final response
                await memory.add_user_message(session_id, message)
                await memory.add_assistant_message(session_id, state["response"])
                if state["suggested_actions"]:
                    await memory.set_suggested_actions(session_id, state["suggested_actions"])
                
                yield MilestoneTemplates.complete("Request completed").to_sse()
                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                final_response = StreamingResponse(
                    session_id=session_id,
                    message=state["response"],
                    status="success",
                    suggested_actions=state["suggested_actions"],
                    total_duration_ms=duration_ms
                )
                yield final_response.to_sse()
                return
            else:
                # User provided a different input - re-classify and clear pending confirmation
                logger.info(
                    "[execute_with_streaming] User provided different input, re-classifying",
                    session_id=session_id,
                    new_message=message[:100]
                )
                await memory.clear_pending_confirmation(session_id)
                # Continue with the newly classified intent (already done above)
        
        # === Check if intent requires confirmation (feedback, query, list_documents) ===
        intents_requiring_confirmation = [
            IntentType.CONTEXT_ENRICH_FEEDBACK,
            IntentType.CONTEXT_ENRICH_QUERY,
            IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS
        ]
        
        if intent.intent in intents_requiring_confirmation and not pending_confirmation:
            # Generate confirmation message based on intent
            intent_messages = {
                IntentType.CONTEXT_ENRICH_FEEDBACK: {
                    "message": "It seems you want to **provide feedback, rating, review, or suggestion**. Is that correct?",
                    "action": "Provide feedback"
                },
                IntentType.CONTEXT_ENRICH_QUERY: {
                    "message": "It seems you want to **query the knowledge base** for information. Is that correct?",
                    "action": "Query knowledge base"
                },
                IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS: {
                    "message": "It seems you want to **list or view documents** in the knowledge base. Is that correct?",
                    "action": "List documents"
                }
            }
            
            intent_info = intent_messages.get(intent.intent, {})
            confirmation_message = intent_info.get("message", "Is this what you want to do?")
            
            logger.info(
                "[execute_with_streaming] Intent requires confirmation",
                session_id=session_id,
                intent=intent.intent.value,
                confirmation_message=confirmation_message
            )
            
            # Store pending confirmation
            await memory.set_pending_confirmation(session_id, {
                "intent": intent.intent.value,
                "target_orchestrator": "common_integration",
                "original_message": message,
                "entities": state["entities"]
            })
            
            state["response"] = f"{confirmation_message}\n\nPlease reply with **Yes** to proceed or **No** to do something else."
            state["suggested_actions"] = [
                {"action": "Yes, proceed", "intent": intent.intent.value, "orchestrator": "common_integration"},
                {"action": "No, do something else", "intent": "unknown", "orchestrator": "unknown"},
            ]
            
            # Update memory and return confirmation request
            await memory.add_user_message(session_id, message)
            await memory.add_assistant_message(session_id, state["response"])
            await memory.set_suggested_actions(session_id, state["suggested_actions"])
            
            yield MilestoneTemplates.complete("Awaiting confirmation").to_sse()
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            final_response = StreamingResponse(
                session_id=session_id,
                message=state["response"],
                status="success",  # Use "success" status so frontend doesn't treat as error
                data={"intent": intent.intent.value, "requires_confirmation": True},
                suggested_actions=state["suggested_actions"],
                total_duration_ms=duration_ms
            )
            yield final_response.to_sse()
            return
        
        # Handle CONFIRMATION
        if intent.intent == IntentType.CONFIRMATION:
            logger.info("[execute_with_streaming] Handling CONFIRMATION intent", session_id=session_id)
            suggested_actions = state["context"].get("suggested_actions", [])
            last_orch = state["context"].get("last_orchestrator")
            
            if suggested_actions:
                selected = _get_selected_action(message, suggested_actions)
                if selected:
                    target_orch = selected.get("orchestrator", last_orch)
                    if target_orch:
                        state["target_orchestrator"] = OrchestratorType(target_orch)
                        state["metadata"]["selected_action"] = selected
                        logger.info(
                            "[execute_with_streaming] Confirmation: selected action from suggestions",
                            session_id=session_id,
                            selected_action=selected,
                            target_orchestrator=target_orch
                        )
            elif last_orch:
                state["target_orchestrator"] = OrchestratorType(last_orch)
                logger.info(
                    "[execute_with_streaming] Confirmation: using last orchestrator",
                    session_id=session_id,
                    last_orchestrator=last_orch
                )
        
        # Handle GENERAL_QUESTION
        if intent.intent == IntentType.GENERAL_QUESTION:
            logger.info("[execute_with_streaming] Handling GENERAL_QUESTION intent", session_id=session_id)
            logger.debug("[execute_with_streaming] Emitting SSE milestone: planning (generate_help)", session_id=session_id)
            yield MilestoneTemplates.planning(["generate_help"]).to_sse()
            await asyncio.sleep(0.3)
            
            logger.debug("[execute_with_streaming] Emitting SSE milestone: synthesizing", session_id=session_id)
            yield MilestoneTemplates.synthesizing().to_sse()
            
            state["response"] = _generate_help_response()
            state["suggested_actions"] = [
                {"action": "Create a BRD", "intent": "create_brd", "orchestrator": "planning"},
                {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
                {"action": "Show my documents", "intent": "context_enrich_list_documents", "orchestrator": "common_integration"},
            ]
            logger.debug("[execute_with_streaming] Help response generated", session_id=session_id)
        
        # Handle UNKNOWN
        elif intent.intent == IntentType.UNKNOWN or state["target_orchestrator"] == OrchestratorType.UNKNOWN:
            logger.info("[execute_with_streaming] Handling UNKNOWN intent - requesting clarification", session_id=session_id)
            logger.debug("[execute_with_streaming] Emitting SSE milestone: planning (request_clarification)", session_id=session_id)
            yield MilestoneTemplates.planning(["request_clarification"]).to_sse()
            
            if intent.requires_clarification and intent.clarification_question:
                state["response"] = intent.clarification_question
            else:
                state["response"] = _generate_clarification_response()
            
            state["suggested_actions"] = [
                {"action": "Create a BRD from transcript", "intent": "create_brd", "orchestrator": "planning"},
                {"action": "Generate user stories from BRD", "intent": "create_user_story", "orchestrator": "planning"},
                {"action": "Generate test cases", "intent": "generate_test_cases", "orchestrator": "test"},
                {"action": "Show my documents", "intent": "context_enrich_list_documents", "orchestrator": "common_integration"},
            ]
            logger.debug("[execute_with_streaming] Clarification response generated", session_id=session_id)
        
        # Route to child orchestrator
        elif state["target_orchestrator"] in [OrchestratorType.PLANNING, OrchestratorType.TEST, OrchestratorType.COMMON_INTEGRATION]:
            target = state["target_orchestrator"]
            logger.info(
                "[execute_with_streaming] Routing to child orchestrator",
                session_id=session_id,
                target_orchestrator=target.value
            )
            
            # === MILESTONE: Routing ===
            if target == OrchestratorType.PLANNING:
                logger.debug("[execute_with_streaming] Emitting SSE milestone: routing_to_planning", session_id=session_id)
                yield SDLCMilestones.routing_to_planning().to_sse()
            elif target == OrchestratorType.COMMON_INTEGRATION:
                logger.debug("[execute_with_streaming] Emitting SSE milestone: routing_to_common_integration", session_id=session_id)
                yield MilestoneTemplates.calling_agent("Rag Integration Service").to_sse()
            else:
                logger.debug("[execute_with_streaming] Emitting SSE milestone: routing_to_test", session_id=session_id)
                yield SDLCMilestones.routing_to_test().to_sse()
            
            await asyncio.sleep(0.5)
            
            # === MILESTONE: Calling Child Orchestrator ===
            agent_display_name = "Rag Integration Service" if target == OrchestratorType.COMMON_INTEGRATION else f"{target.value.title()} Orchestrator"
            logger.debug(
                "[execute_with_streaming] Emitting SSE milestone: calling_agent",
                session_id=session_id,
                agent=agent_display_name
            )
            yield MilestoneTemplates.calling_agent(agent_display_name).to_sse()
            
            client = get_orchestrator_client()
            
            # Build context
            child_context = {**state["context"]}
            child_context["entities"] = state["entities"]
            
            # Determine explicit intent for child orchestrator
            # Priority: 1. selected_action intent (from confirmation), 2. parent's explicit_intent, 3. classified intent
            explicit_child_intent = None
            selected_action = state.get("metadata", {}).get("selected_action")
            if selected_action:
                explicit_child_intent = selected_action.get("intent")
            # Forward explicit_intent from parent request if set
            if not explicit_child_intent and state.get("metadata", {}).get("explicit_intent"):
                explicit_child_intent = state["metadata"]["explicit_intent"]
            # Use the classified intent if nothing else is set
            if not explicit_child_intent and state.get("intent") and hasattr(state["intent"], "intent"):
                explicit_child_intent = state["intent"].intent.value
            
            logger.info(
                "[execute_with_streaming] Calling child orchestrator with streaming",
                session_id=session_id,
                target_orchestrator=target.value,
                explicit_child_intent=explicit_child_intent,
                child_context=child_context
            )
            
            # === Stream from child orchestrator and forward milestones ===
            child_final_response = None
            forwarded_event_count = 0
            
            try:
                async for event_data in client.call_chat_stream(
                    orchestrator=target,
                    session_id=session_id,
                    message=message,
                    context=child_context,
                    history=history,
                    explicit_intent=explicit_child_intent
                ):
                    event_type = event_data.get("type", "")
                    
                    if event_type == "milestone":
                        # Forward milestone from child orchestrator
                        # Add source info so frontend knows it's from child
                        event_data["_forwarded_from"] = target.value
                        forwarded_event_count += 1
                        logger.debug(
                            "[execute_with_streaming] Forwarding SSE milestone from child",
                            session_id=session_id,
                            source_orchestrator=target.value,
                            event_stage=event_data.get("stage"),
                            event_title=event_data.get("title"),
                            forwarded_count=forwarded_event_count,
                            event_data=event_data
                        )
                        yield f"data: {json.dumps(event_data)}\n\n"
                    
                    elif event_type in ["response", "complete"]:
                        # This is the final response from child orchestrator
                        # Note: Planning/Test use "response", Common Integration uses "complete"
                        child_final_response = event_data
                        logger.info(
                            "[execute_with_streaming] Received final response from child orchestrator",
                            session_id=session_id,
                            source_orchestrator=target.value,
                            status=event_data.get("status"),
                            response_data=event_data
                        )
                    
                    elif event_type == "error":
                        # Forward error from child orchestrator
                        event_data["_forwarded_from"] = target.value
                        logger.error(
                            "[execute_with_streaming] Forwarding error from child orchestrator",
                            session_id=session_id,
                            source_orchestrator=target.value,
                            error_message=event_data.get("message"),
                            error_data=event_data
                        )
                        yield f"data: {json.dumps(event_data)}\n\n"
                
                logger.info(
                    "[execute_with_streaming] Child orchestrator streaming completed",
                    session_id=session_id,
                    target_orchestrator=target.value,
                    total_forwarded_events=forwarded_event_count
                )
                
            except Exception as stream_error:
                logger.warning(
                    "[execute_with_streaming] Child orchestrator streaming failed, falling back to non-streaming",
                    session_id=session_id,
                    orchestrator=target.value,
                    error=str(stream_error),
                    error_type=type(stream_error).__name__
                )
                # Fallback to non-streaming call
                logger.debug("[execute_with_streaming] Emitting SSE milestone: awaiting_child_response (fallback)", session_id=session_id)
                yield SDLCMilestones.awaiting_child_response(target.value).to_sse()
                
                response = await client.call_chat(
                    orchestrator=target,
                    session_id=session_id,
                    message=message,
                    context=child_context,
                    history=history,
                    explicit_intent=explicit_child_intent
                )
                child_final_response = {
                    "session_id": session_id,
                    "message": response.get("message", "Request processed."),
                    "status": response.get("status", "success"),
                    "nextagentflow": response.get("nextagentflow"),
                    "data": response.get("data"),
                    "suggested_actions": response.get("suggested_actions", [])
                }
                logger.info(
                    "[execute_with_streaming] Fallback non-streaming response received",
                    session_id=session_id,
                    target_orchestrator=target.value,
                    response=child_final_response
                )
            
            # Process child response
            if child_final_response:
                state["child_response"] = child_final_response
                state["response"] = child_final_response.get("message", "Request processed.")
                state["suggested_actions"] = [
                    {**sa, "orchestrator": target.value}
                    for sa in child_final_response.get("suggested_actions", [])
                ]
                logger.debug(
                    "[execute_with_streaming] Child response processed",
                    session_id=session_id,
                    response_length=len(state["response"]),
                    suggested_actions_count=len(state["suggested_actions"])
                )
            else:
                state["response"] = "Request processed by child orchestrator."
                logger.warning(
                    "[execute_with_streaming] No final response from child, using default",
                    session_id=session_id,
                    target_orchestrator=target.value
                )
            
            await memory.set_last_orchestrator(session_id, target.value)
            
            # === MILESTONE: Processing Response ===
            logger.debug("[execute_with_streaming] Emitting SSE milestone: processing_response", session_id=session_id)
            yield MilestoneTemplates.processing_response().to_sse()
            await asyncio.sleep(0.3)
        
        # === MILESTONE: Synthesizing ===
        if not state.get("response"):
            logger.debug("[execute_with_streaming] Emitting SSE milestone: synthesizing (default response)", session_id=session_id)
            yield MilestoneTemplates.synthesizing().to_sse()
            state["response"] = "I've processed your request. Is there anything else you'd like to do?"
        
        # Update memory
        logger.debug("[execute_with_streaming] Updating memory with conversation", session_id=session_id)
        await memory.add_user_message(session_id, message)
        
        routed_to = state["target_orchestrator"].value if state["target_orchestrator"] and state["target_orchestrator"] != OrchestratorType.UNKNOWN else None
        
        await memory.add_assistant_message(
            session_id,
            state["response"],
            routed_to=routed_to
        )
        
        if state["entities"]:
            await memory.update_entities(session_id, state["entities"])
        
        if state["suggested_actions"]:
            await memory.set_suggested_actions(session_id, state["suggested_actions"])
        
        # === MILESTONE: Complete ===
        logger.debug("[execute_with_streaming] Emitting SSE milestone: complete", session_id=session_id)
        yield MilestoneTemplates.complete("Request completed successfully").to_sse()
        
        # Calculate duration
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Extract nextagentflow, job_id, push_results and data from child_response
        nextagentflow = None
        job_id = None
        push_results = None
        child_data = {}
        child_response = state.get("child_response")
        if child_response:
            nextagentflow = child_response.get("nextagentflow")
            # Include child response data at root level
            child_data = child_response.get("data", {}) or {}
            # Extract job_id from child data
            job_id = child_data.get("job_id")
            # Extract push_results from child data
            # push_results = child_data.get("push_results")
            # If message is nested in data, use it
            nested_message = child_data.get("message")
            if nested_message and isinstance(nested_message, str):
                state["response"] = nested_message
        
        # Merge child data with intent/entities data
        response_data = {
            "intent": state["intent"].intent.value if state["intent"] else None,
            "entities": state["entities"],
            **child_data,  # Include all data from child orchestrator response
        }
        
        # === Final Response ===
        final_response = StreamingResponse(
            session_id=session_id,
            message=state["response"],
            status="success" if not state.get("error") else "error",
            job_id=job_id,
            nextagentflow=nextagentflow,
            data=response_data,
            suggested_actions=state["suggested_actions"],
            routed_to=routed_to,
            total_duration_ms=duration_ms
        )
        
        logger.info(
            "[execute_with_streaming] Emitting final SSE response",
            session_id=session_id,
            status=final_response.status,
            routed_to=routed_to,
            duration_ms=duration_ms,
            response_message_length=len(state["response"]),
            final_response=final_response.model_dump()
        )
        yield final_response.to_sse()
        
        logger.info(
            "[execute_with_streaming] Streaming execution completed successfully",
            session_id=session_id,
            total_duration_ms=duration_ms
        )
        
    except Exception as e:
        logger.error(
            "[execute_with_streaming] Streaming execution error",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__,
            message=message[:100]
        )
        logger.debug("[execute_with_streaming] Emitting SSE error event", session_id=session_id, error=str(e))
        yield StreamingError(message=str(e)).to_sse()
        
        # Still send a final response
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        final_response = StreamingResponse(
            session_id=session_id,
            message=f"I encountered an error: {str(e)}",
            status="error",
            total_duration_ms=duration_ms
        )
        logger.info(
            "[execute_with_streaming] Emitting final SSE error response",
            session_id=session_id,
            duration_ms=duration_ms,
            error=str(e)
        )
        yield final_response.to_sse()


def _get_selected_action(message: str, suggested_actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get the selected action from user message."""
    logger.debug(
        "[_get_selected_action] Matching user message to suggested actions",
        message=message,
        suggested_actions_count=len(suggested_actions)
    )
    msg_lower = message.lower().strip()
    
    number_words = {
        "first": 0, "1": 0, "one": 0, "option 1": 0,
        "second": 1, "2": 1, "two": 1, "option 2": 1,
        "third": 2, "3": 2, "three": 2, "option 3": 2,
    }
    
    for pattern, index in number_words.items():
        if pattern in msg_lower or msg_lower == pattern:
            if index < len(suggested_actions):
                selected = suggested_actions[index]
                logger.debug(
                    "[_get_selected_action] Matched by number pattern",
                    pattern=pattern,
                    index=index,
                    selected_action=selected
                )
                return selected
    
    for action in suggested_actions:
        action_text = action.get("action", "").lower()
        if any(word in msg_lower for word in action_text.split() if len(word) > 3):
            logger.debug(
                "[_get_selected_action] Matched by keyword",
                action=action
            )
            return action
    
    default_action = suggested_actions[0] if suggested_actions else None
    logger.debug(
        "[_get_selected_action] No match found, returning default",
        default_action=default_action
    )
    return default_action


def _generate_help_response() -> str:
    """Generate help response."""
    logger.debug("[_generate_help_response] Generating help response")
    return (
        "I'm WEGA SDLC Orchestrator, your software development lifecycle assistant. "
        "I coordinate between specialized orchestrators:\n\n"
        "**Planning Orchestrator:**\n"
        "- Create BRDs from transcripts\n"
        "- Generate user stories from BRDs\n"
        "- Validate user stories\n"
        "- Get BRD summaries\n\n"
        "**Test Orchestrator:**\n"
        "- Generate test cases from user stories\n"
        "- Create automated test scripts (Selenium, Playwright)\n\n"
        "**Knowledge Base:**\n"
        "- Show/list my documents\n"
        "- Query the knowledge base\n"
        "- Upload documents\n\n"
        "Just tell me what you'd like to do!"
    )


def _generate_clarification_response() -> str:
    """Generate clarification response."""
    logger.debug("[_generate_clarification_response] Generating clarification response")
    return (
        "I'm not sure what you'd like to do. Could you please clarify?\n\n"
        "I can help with:\n"
        "- **BRD creation** from transcripts\n"
        "- **User story generation** from BRDs\n"
        "- **Test cases generation** from user stories\n"
        "- **Test script automation**\n\n"
        "- **List/show my documents** in knowledge base\n"
        "- **Query the knowledge base** for information\n\n"
        "What would you like to do?"
    )
