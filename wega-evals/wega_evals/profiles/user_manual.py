"""User Manual Generator agent profile."""

from __future__ import annotations

import json
from typing import Any

from wega_evals.agent_profile import AgentProfile, register_profile
from wega_evals.models import DimensionScore


@register_profile
class UserManualProfile(AgentProfile):
    """Evaluation profile for the User Manual Generator agent.

    Generates user manuals from repository URLs.
    Endpoint: POST /generate-manual
    Input: GenerateManualRequest {url, project_name}
    Output: GenerateManualResponse {status, session_id, confluence_url}
    """

    name = "user_manual"
    description = "User Manual — generates user manuals from repository code"
    trace_name = "usermanual_generation"
    default_dataset = "user-manual-eval"

    dimensions = [
        "content_accuracy",
        "completeness",
        "readability",
        "structure_quality",
        "audience_appropriateness",
        "depth",
    ]

    output_schema = {
        "required_fields": ["status"],
        "status_field": "status",
        "status_values": ["success", "completed", "failed"],
    }

    judge_prompts = {
        "content_accuracy": """\
You are a technical writer evaluator. Assess the **accuracy** of the
generated user manual against the source repository.

## Repository / Project Info
{input_text}

## Generated Manual Content
{output_text}

## Criteria
- Are features and functionality described accurately?
- Are API endpoints / commands documented correctly?
- Are configuration options accurate?
- Is there any outdated or incorrect information?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "inaccuracies": ["<any found>"]
}}
""",
        "completeness": """\
You are a technical writer. Assess the **completeness** of the manual.

## Repository / Project Info
{input_text}

## Generated Manual
{output_text}

## Criteria
- Are all major features documented?
- Is there an installation/setup section?
- Are usage examples provided?
- Is troubleshooting/FAQ included?
- Are API references complete?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "covered_sections": ["<sections present>"],
  "missing_sections": ["<sections missing>"]
}}
""",
        "readability": """\
You are a technical communication expert. Assess the **readability**
of the generated manual.

## Generated Manual
{output_text}

## Criteria
- Is the language clear and concise?
- Are technical terms explained?
- Is formatting consistent (headings, lists, code blocks)?
- Is the reading level appropriate for the target audience?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "structure_quality": """\
You are evaluating the **structure** of the generated manual.

## Generated Manual
{output_text}

## Criteria
- Is the document well-organized with logical sections?
- Is there a table of contents?
- Are sections properly nested and ordered?
- Is information easy to find?
- Is navigation intuitive?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "audience_appropriateness": """\
You are evaluating whether the manual is appropriate for its **target
audience** (end users, developers, or administrators).

## Repository / Project Info
{input_text}

## Generated Manual
{output_text}

## Criteria
- Is the content targeted at the right audience?
- Is the level of technical detail appropriate?
- Are prerequisites clearly stated?
- Would the intended reader find this useful?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        for key in ("url", "project_name", "repository_url"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        return json.dumps(input_data, indent=2, default=str)
