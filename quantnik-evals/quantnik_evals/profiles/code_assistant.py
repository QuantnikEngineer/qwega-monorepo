"""Code Assistant agent profile."""

from __future__ import annotations

import json
from typing import Any

from quantnik_evals.agent_profile import AgentProfile, register_profile
from quantnik_evals.models import DimensionScore


@register_profile
class CodeAssistantProfile(AgentProfile):
    """Evaluation profile for the Code Assistant agent.

    Provides AI-powered code assistance (generation, explanation, refactoring).
    """

    name = "code_assistant"
    description = "Code Assistant — AI-powered code generation, explanation, and refactoring"
    trace_name = "codeassist"
    default_dataset = "code-assistant-eval"

    dimensions = [
        "code_correctness",
        "code_quality",
        "instruction_following",
        "explanation_clarity",
        "depth",
        "reasoning_quality",
        "causal_understanding",
    ]

    output_schema = {
        "required_fields": ["response"],
    }

    judge_prompts = {
        "code_correctness": """\
You are a senior software engineer. Assess the **correctness** of the
AI-generated code.

## User Request
{input_text}

## AI Response
{output_text}

## Criteria
- Does the code correctly implement the requested functionality?
- Would it compile/run without errors?
- Are edge cases handled?
- Is the logic correct?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "issues": ["<any correctness issues>"]
}}
""",
        "code_quality": """\
You are a senior software engineer. Assess the **quality** of the
AI-generated code.

## AI Response
{output_text}

## Criteria
- Is the code clean, readable, and well-structured?
- Does it follow language idioms and best practices?
- Is error handling appropriate?
- Are security best practices followed?
- Is naming clear and consistent?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "instruction_following": """\
You are evaluating how well the AI **followed the user's instructions**.

## User Request
{input_text}

## AI Response
{output_text}

## Criteria
- Does the response address exactly what was asked?
- Are all specified requirements met?
- Are constraints (language, framework, style) respected?
- Is there unnecessary extra content?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "met_requirements": ["<what was addressed>"],
  "unmet_requirements": ["<what was missed>"]
}}
""",
        "explanation_clarity": """\
You are evaluating the **clarity of explanations** provided alongside code.

## AI Response
{output_text}

## Criteria
- Are code explanations clear and accurate?
- Is the right level of detail provided?
- Are complex concepts broken down well?
- Would a developer understand the reasoning?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        for key in ("message", "query", "prompt", "code", "request"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        gen = input_data.get("generation_input", {})
        if isinstance(gen, dict):
            for key in ("message", "query", "prompt", "code"):
                if key in gen:
                    return str(gen[key])
        return json.dumps(input_data, indent=2, default=str)
