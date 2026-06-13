"""User Story Validator agent profile."""

from __future__ import annotations

import json
from typing import Any

from quantnik_evals.agent_profile import AgentProfile, register_profile
from quantnik_evals.models import DimensionScore


@register_profile
class UserStoryValidatorProfile(AgentProfile):
    """Evaluation profile for the User Story Validator agent.

    Validates user stories against the original BRD document.
    Endpoint: POST /v1/api/validate-user-story
    """

    name = "userstory_validator"
    description = "User Story Validator — validates stories against BRD for accuracy and coverage"
    trace_name = "userstory_validator"
    default_dataset = "userstory-validator-eval"

    dimensions = [
        "validation_accuracy",
        "gap_detection",
        "feedback_quality",
        "alignment_assessment",
        "depth",
        "reasoning_quality",
    ]

    output_schema = {
        "required_fields": ["validation_result"],
    }

    judge_prompts = {
        "validation_accuracy": """\
You are an expert agile coach. Assess the **accuracy** of this AI
validation of user stories against a BRD.

## BRD Document & User Stories (Input)
{input_text}

## Validation Result
{output_text}

## Criteria
- Are the identified issues genuinely misaligned with the BRD?
- Are the "pass" judgments correct (stories truly match the BRD)?
- Are there false positives (flagged issues that aren't real)?
- Are there false negatives (missed misalignments)?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "correct_validations": [<indices>],
  "incorrect_validations": [<indices with reasoning>]
}}
""",
        "gap_detection": """\
You are an expert business analyst. Assess how well the validator
detects **gaps** between user stories and BRD requirements.

## BRD & User Stories
{input_text}

## Validation Output
{output_text}

## Criteria
- Are missing requirements from the BRD identified?
- Are over-scoped stories (beyond BRD) flagged?
- Are partial coverage cases correctly identified?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "detected_gaps": ["<correctly found>"],
  "missed_gaps": ["<not detected>"]
}}
""",
        "feedback_quality": """\
You are evaluating the **quality of feedback** provided by the validator.

## Validation Output
{output_text}

## Criteria
- Is the feedback actionable (tells the user what to fix)?
- Is it specific (references exact stories and requirements)?
- Is the language clear and constructive?
- Are suggestions for improvement provided?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "alignment_assessment": """\
You are evaluating the **alignment assessment** between stories and BRD.

## BRD & Stories
{input_text}

## Validation Result
{output_text}

## Criteria
- Is the overall alignment score/status reasonable?
- Does the priority of issues make sense?
- Are critical misalignments prioritized over minor ones?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        for key in ("user_stories", "brd_document", "stories", "input"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        return json.dumps(input_data, indent=2, default=str)
