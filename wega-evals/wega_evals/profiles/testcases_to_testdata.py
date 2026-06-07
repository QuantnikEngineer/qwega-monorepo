"""Test Cases to Test Data agent profile."""

from __future__ import annotations

import json
from typing import Any

from wega_evals.agent_profile import AgentProfile, register_profile
from wega_evals.models import DimensionScore


@register_profile
class TestCasesToTestDataProfile(AgentProfile):
    """Evaluation profile for the Test Cases to Test Data agent.

    Generates test data from test cases.
    Endpoint: POST /generate-test-data
    Input: GenerateTestDataRequest {test_cases, output_format}
    """

    name = "testcases_to_testdata"
    description = "TC→Test Data — generates test data sets from test cases"
    trace_name = "testcase_to_testdata_conversion"
    default_dataset = "tc-to-testdata-eval"

    dimensions = [
        "data_completeness",
        "data_validity",
        "boundary_values",
        "data_variety",
    ]

    output_schema = {
        "required_fields": ["test_data"],
    }

    judge_prompts = {
        "data_completeness": """\
You are an expert QA data engineer. Assess the **completeness** of
generated test data against the test cases.

## Test Cases
{input_text}

## Generated Test Data
{output_text}

## Criteria
- Is test data generated for every test case?
- Does each test case have sufficient data variants?
- Are all required input fields populated?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "covered_cases": <int>,
  "total_cases": <int>
}}
""",
        "data_validity": """\
You are an expert QA data engineer. Assess the **validity** of the
generated test data.

## Test Cases
{input_text}

## Generated Test Data
{output_text}

## Criteria
- Is the data realistic and domain-appropriate?
- Are data types correct (strings, numbers, dates, etc.)?
- Are values within valid ranges?
- Would this data actually work in the system under test?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "invalid_data": ["<examples of invalid data>"]
}}
""",
        "boundary_values": """\
You are a QA engineer. Assess the **boundary value coverage** in the
generated test data.

## Test Cases
{input_text}

## Generated Test Data
{output_text}

## Criteria
- Are min/max boundary values included?
- Are empty/null values included where appropriate?
- Are special characters and unicode tested?
- Are overflow/underflow values present?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "boundary_types_covered": ["<types>"],
  "missing_boundaries": ["<types>"]
}}
""",
        "data_variety": """\
You are a QA data engineer. Assess the **variety** of generated test data.

## Generated Test Data
{output_text}

## Criteria
- Is there sufficient variety (not just copy-paste with minor changes)?
- Are positive and negative test data included?
- Are different data distributions represented?
- Are locale/format variations considered (dates, currencies)?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        tc = input_data.get("test_cases", "")
        if tc:
            return tc if isinstance(tc, str) else json.dumps(tc, indent=2, default=str)
        return json.dumps(input_data, indent=2, default=str)
