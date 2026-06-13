"""User Story to Test Cases agent profile."""

from __future__ import annotations

import json
from typing import Any

from quantnik_evals.agent_profile import AgentProfile, register_profile
from quantnik_evals.models import DimensionScore


@register_profile
class UserStoryToTestCasesProfile(AgentProfile):
    """Evaluation profile for the User Story to Test Cases agent.

    Generates test cases from user stories in bulk.
    Endpoint: POST /v1/generate-test-cases/bulk
    Input: BulkRequest {userStories: [StoryItem], ScenarioTypes: [...]}
    """

    name = "userstory_to_testcases"
    description = "US→Test Cases — generates test cases from user stories"
    trace_name = "userstory_to_testcases"
    default_dataset = "us-to-testcases-eval"

    dimensions = [
        "test_case_coverage",
        "test_case_quality",
        "scenario_type_compliance",
        "traceability",
        "edge_case_coverage",
        "depth",
    ]

    output_schema = {
        "required_fields": ["test_cases"],
        "items_field": "test_cases",
        "item_required_fields": ["test_case_id", "title", "steps", "expected_result"],
    }

    judge_prompts = {
        "test_case_coverage": """\
You are an expert QA engineer. Assess the **coverage** of generated
test cases against the source user stories.

## User Stories
{input_text}

## Generated Test Cases
{output_text}

## Criteria
- Is every user story covered by at least one test case?
- Are acceptance criteria translated into verifiable test steps?
- Are there stories with no corresponding test cases?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "covered_stories": [<story IDs covered>],
  "uncovered_stories": [<story IDs missed>]
}}
""",
        "test_case_quality": """\
You are an expert QA engineer. Assess the **quality** of individual
test cases.

## Generated Test Cases
{output_text}

## Criteria
- Are test steps clear, specific, and reproducible?
- Are expected results well-defined?
- Are preconditions stated?
- Are test cases independent (no hidden dependencies)?
- Do test cases avoid ambiguity?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "strong_cases": [<indices>],
  "weak_cases": [{{
    "index": <int>,
    "issue": "<problem>"
  }}]
}}
""",
        "scenario_type_compliance": """\
You are a QA lead. Assess whether test cases cover the requested
**scenario types** (positive, negative, boundary, etc.).

## Requested Scenario Types
{scenario_types}

## Generated Test Cases
{output_text}

## Criteria
- Are all requested scenario types represented?
- Is the distribution of scenario types reasonable?
- Are negative/boundary cases meaningful (not trivial)?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "type_distribution": {{"<type>": <count>}}
}}
""",
        "traceability": """\
You are a QA engineer. Assess the **traceability** between test cases
and user stories.

## User Stories
{input_text}

## Generated Test Cases
{output_text}

## Criteria
- Can each test case be traced back to a specific user story?
- Are story IDs / references included in test cases?
- Is the mapping clear and correct?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "edge_case_coverage": """\
You are an expert QA engineer. Assess the **edge case coverage** in
the generated test cases.

## User Stories
{input_text}

## Generated Test Cases
{output_text}

## Criteria
- Are boundary conditions tested?
- Are error/failure scenarios covered?
- Are concurrent/race condition scenarios considered?
- Are data validation edge cases included?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "good_edge_cases": ["<description>"],
  "missing_edge_cases": ["<description>"]
}}
""",
    }

    def format_judge_context(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, str]:
        scenario_types = input_data.get("ScenarioTypes", input_data.get("scenario_types", []))
        return {"scenario_types": json.dumps(scenario_types, indent=2)}

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        stories = input_data.get("userStories", input_data.get("user_stories", []))
        if stories:
            return json.dumps(stories, indent=2, default=str)
        return json.dumps(input_data, indent=2, default=str)
