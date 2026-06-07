"""SDLC Orchestrator agent profile."""

from __future__ import annotations

import json
from typing import Any

from wega_evals.agent_profile import AgentProfile, register_profile
from wega_evals.models import DimensionScore


@register_profile
class SDLCOrchestratorProfile(AgentProfile):
    """Evaluation profile for the SDLC Orchestrator.

    Routes user intents across agents (BRD, User Story, Test Cases, etc.).
    Endpoints: POST /v1/chat, POST /api/v1/prompt/analyze
    Output: ChatResponse {session_id, message, status, routed_to, ...}
    """

    name = "sdlc_orchestrator"
    description = "SDLC Orchestrator — routes intents across SDLC agents"
    trace_name = "sdlc_orchestrator_request"
    default_dataset = "sdlc-orchestrator-eval"

    dimensions = [
        "intent_routing_accuracy",
        "response_quality",
        "context_retention",
        "flow_orchestration",
        "reasoning_quality",
    ]

    output_schema = {
        "required_fields": ["message", "status"],
        "status_field": "status",
        "status_values": ["success", "error", "pending", "completed"],
    }

    judge_prompts = {
        "intent_routing_accuracy": """\
You are an expert at evaluating AI orchestration agents. Assess whether
the orchestrator **correctly routed** the user's intent to the right agent.

## User Message
{input_text}

## Orchestrator Response
{output_text}

## Available Agents
BRD Generator, User Story Generator, User Story Validator,
Test Case Generator, Test Data Generator, Test Script Generator,
Code Review (CARA), Code Assistant, User Manual Generator, BRD Summary

## Criteria
- Was the intent correctly identified?
- Was it routed to the appropriate downstream agent?
- If ambiguous, did the orchestrator ask for clarification?
- Was the routed_to field correct?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "detected_intent": "<what the orchestrator detected>",
  "correct_agent": "<which agent should have been used>",
  "routed_to": "<which agent was actually used>"
}}
""",
        "response_quality": """\
You are evaluating the **response quality** of an SDLC orchestrator.

## User Input
{input_text}

## Orchestrator Response
{output_text}

## Criteria
- Is the response helpful and informative?
- Does it clearly communicate what action was taken?
- Are next steps or suggested actions provided?
- Is the response well-formatted?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "context_retention": """\
You are evaluating the orchestrator's **context retention** across
conversation turns.

## Conversation History
{input_text}

## Latest Response
{output_text}

## Criteria
- Does the orchestrator remember previous context?
- Are session-level decisions consistent?
- Does it avoid asking for information already provided?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "flow_orchestration": """\
You are evaluating the **flow orchestration** — how well the
orchestrator manages multi-step SDLC workflows.

## Conversation / Workflow
{input_text}

## Response
{output_text}

## Criteria
- Does it correctly chain agent calls (e.g., BRD → Stories → Tests)?
- Are intermediate results properly passed between agents?
- Is the workflow status communicated clearly?
- Are errors from downstream agents handled gracefully?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        for key in ("message", "query_text", "chat_history"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        gen = input_data.get("generation_input", {})
        if isinstance(gen, dict):
            for key in ("message", "query_text", "content"):
                if key in gen:
                    return str(gen[key])
        return json.dumps(input_data, indent=2, default=str)
