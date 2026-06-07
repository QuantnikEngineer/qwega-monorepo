"""Test Case to Test Scripts agent profile."""

from __future__ import annotations

import json
from typing import Any

from wega_evals.agent_profile import AgentProfile, register_profile
from wega_evals.models import DimensionScore


@register_profile
class TestCaseToScriptsProfile(AgentProfile):
    """Evaluation profile for the Test Case to Test Scripts agent.

    Converts test cases into executable test scripts.
    Endpoint: POST /convert
    Input: ConversionRequest {test_cases, framework_type, language, script_generation_type}
    Output: ConversionResponse {status, push_results, zip_filename, zip_base64}
    """

    name = "testcase_to_scripts"
    description = "TC→Scripts — converts test cases into executable test scripts"
    trace_name = "testcase_to_script_conversion"
    default_dataset = "tc-to-scripts-eval"

    dimensions = [
        "script_correctness",
        "framework_compliance",
        "test_coverage_mapping",
        "code_quality",
        "executability",
    ]

    output_schema = {
        "required_fields": ["status"],
    }

    judge_prompts = {
        "script_correctness": """\
You are an expert test automation engineer. Assess the **correctness**
of generated test scripts.

## Source Test Cases
{input_text}

## Generated Test Scripts
{output_text}

## Target Framework: {framework_type}
## Target Language: {language}

## Criteria
- Do the scripts correctly implement the test case steps?
- Are assertions matching the expected results?
- Is the test logic correct (setup, action, verification, teardown)?
- Are there logical errors in the scripts?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "correct_scripts": [<indices>],
  "incorrect_scripts": [{{
    "index": <int>,
    "issue": "<problem>"
  }}]
}}
""",
        "framework_compliance": """\
You are an expert test automation engineer. Assess whether the scripts
follow **framework best practices**.

## Generated Scripts
{output_text}

## Target Framework: {framework_type}
## Target Language: {language}

## Criteria
- Do scripts follow the framework's conventions and patterns?
- Are proper annotations/decorators used?
- Are framework utilities used correctly?
- Is the project structure idiomatic?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "test_coverage_mapping": """\
You are a QA lead. Assess the **mapping** between test cases and
generated scripts.

## Test Cases
{input_text}

## Generated Scripts
{output_text}

## Criteria
- Is every test case represented by a test script?
- Are test case IDs referenced in the scripts?
- Is the mapping 1:1 or are some combined/split appropriately?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "mapped": <int>,
  "unmapped": <int>
}}
""",
        "code_quality": """\
You are a senior software engineer. Assess the **code quality** of
the generated test scripts.

## Generated Scripts
{output_text}

## Criteria
- Is the code clean, readable, and well-structured?
- Are meaningful variable and method names used?
- Is there proper error handling?
- Are hardcoded values avoided (using constants/config)?
- Is code duplication minimized?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>"
}}
""",
        "executability": """\
You are a test automation engineer. Assess whether the generated
scripts are likely **executable** without modifications.

## Generated Scripts
{output_text}

## Target Framework: {framework_type}
## Target Language: {language}

## Criteria
- Would the scripts compile/parse without errors?
- Are all imports present and correct?
- Are dependencies properly referenced?
- Would test runners pick up these tests?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "likely_issues": ["<potential execution problems>"]
}}
""",
    }

    # ------------------------------------------------------------------
    # Custom extraction — traces store scripts in generate-script
    # GENERATION observations (string output) and config in
    # convert_test_cases span input.
    # ------------------------------------------------------------------

    def extract_input(self, trace: Any, observations: list[Any]) -> dict[str, Any]:
        result = super().extract_input(trace, observations)
        # Pull framework_type / language from convert_test_cases span
        for obs in observations:
            if obs.name == "convert_test_cases" and obs.input:
                inp = obs.input if isinstance(obs.input, dict) else {}
                result["framework_type"] = inp.get("framework_type", "unknown")
                result["language"] = inp.get("language", "unknown")
                result["generation_type"] = inp.get("generation_type", "")
                break
        return result

    def extract_output(self, trace: Any, observations: list[Any]) -> dict[str, Any] | None:
        # Collect all generated scripts from generation observations
        # Handles: generate-script (Playwright), generate-feature-file + generate-step-definition (BDD)
        script_obs_names = {"generate-script", "generate-feature-file", "generate-step-definition"}
        scripts: list[str] = []
        for obs in observations:
            if obs.name in script_obs_names and obs.type == "GENERATION" and obs.output:
                scripts.append(str(obs.output))
        if not scripts:
            return None
        return {
            "status": "success",
            "scripts": scripts,
            "script_count": len(scripts),
        }

    def format_judge_context(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "framework_type": str(input_data.get("framework_type", "unknown")),
            "language": str(input_data.get("language", "unknown")),
        }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        tc = input_data.get("test_cases", "")
        if tc:
            return tc if isinstance(tc, str) else json.dumps(tc, indent=2, default=str)
        return json.dumps(input_data, indent=2, default=str)

    def extract_primary_output_text(self, output_data: dict[str, Any]) -> str:
        if not output_data:
            return ""
        scripts = output_data.get("scripts", [])
        if scripts:
            return "\n\n---\n\n".join(scripts)
        return json.dumps(output_data, indent=2, default=str)
