"""BRD Summary agent profile."""

from __future__ import annotations

import json
from typing import Any

from quantnik_evals.agent_profile import AgentProfile, register_profile
from quantnik_evals.models import DimensionScore


@register_profile
class BRDSummaryProfile(AgentProfile):
    """Evaluation profile for the BRD Summary agent."""

    name = "brd_summary"
    description = "BRD Summary — generates structured summaries from Business Requirements Documents"
    trace_name = "brd_summary_request"
    default_dataset = "brd-summary-eval"

    dimensions = [
        "summary_accuracy",
        "completeness",
        "key_points_extraction",
        "stakeholder_identification",
        "requirement_categorization",
    ]

    output_schema = {
        "required_fields": ["summary", "key_requirements"],
        "status_field": "status",
        "status_values": ["complete", "partial", "failed"],
        "items_field": "key_requirements",
        "item_required_fields": ["id", "description", "category", "priority"],
    }

    judge_prompts = {
        # ----- summary_accuracy -----
        "summary_accuracy": """\
You are an expert business analyst evaluator. Assess whether this AI-generated
BRD summary **accurately** represents the source document.

## Source BRD Document
{input_text}

## AI-Generated Summary
{output_text}

## Criteria
- Does the summary capture the core business objective?
- Are key requirements accurately represented?
- Is any important information misrepresented or distorted?
- Does the summary introduce information not in the source?

Score 0.0 to 1.0:
- 1.0 = Perfectly accurate, no distortions or hallucinations
- 0.5 = Mostly accurate but some inaccuracies
- 0.0 = Major misrepresentations

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "inaccuracies": ["<any found inaccuracies>"],
  "hallucinations": ["<info not in source>"]
}}
""",
        # ----- completeness -----
        "completeness": """\
You are an expert business analyst evaluator. Assess the **completeness**
of this BRD summary.

## Source BRD Document
{input_text}

## AI-Generated Summary
{output_text}

## Criteria
- Are all functional requirements covered?
- Are non-functional requirements mentioned?
- Are stakeholders identified?
- Are constraints and assumptions documented?
- Are success criteria or acceptance criteria included?

Score 0.0 to 1.0:
- 1.0 = All important aspects covered
- 0.5 = Core requirements covered but gaps exist
- 0.0 = Most important elements missing

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "covered_aspects": ["<what was covered>"],
  "missing_aspects": ["<what was missed>"]
}}
""",
        # ----- key_points_extraction -----
        "key_points_extraction": """\
You are an expert business analyst evaluator. Assess how well the agent
extracted **key points** from the BRD.

## Source BRD Document
{input_text}

## Extracted Key Requirements
{output_text}

## Criteria
- Are the most critical requirements identified?
- Are priorities correctly assigned?
- Are categories meaningful and consistent?
- Is the extraction specific (not vague)?

Score 0.0 to 1.0:
- 1.0 = All key points correctly extracted with proper priority
- 0.5 = Most key points found but priority/categorization off
- 0.0 = Key points missed or poorly extracted

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "well_extracted": ["<good extractions>"],
  "missed_or_weak": ["<missed key points>"]
}}
""",
        # ----- stakeholder_identification -----
        "stakeholder_identification": """\
You are an expert business analyst. Assess the agent's **stakeholder
identification** from the BRD.

## Source BRD Document
{input_text}

## AI Output
{output_text}

## Criteria
- Are primary stakeholders identified?
- Are roles and responsibilities captured?
- Are external stakeholders included where relevant?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "identified_stakeholders": ["<found>"],
  "missed_stakeholders": ["<missed>"]
}}
""",
        # ----- requirement_categorization -----
        "requirement_categorization": """\
You are an expert business analyst. Assess how well requirements are
**categorized** in the summary.

## Source BRD Document
{input_text}

## AI Output
{output_text}

## Criteria
- Are functional vs non-functional requirements distinguished?
- Are categories consistent and meaningful?
- Is priority assignment reasonable?
- Are dependencies between requirements identified?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "well_categorized": ["<examples>"],
  "miscategorized": ["<examples>"]
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        """BRD document is the primary input."""
        for key in ("brd_document", "document", "brd_text", "content", "text"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        gen = input_data.get("generation_input", {})
        if isinstance(gen, dict):
            for key in ("document", "content", "text", "brd"):
                if key in gen:
                    return str(gen[key])
        return json.dumps(input_data, indent=2, default=str)
