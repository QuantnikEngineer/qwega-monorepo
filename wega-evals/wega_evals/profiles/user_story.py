"""User Story Generator agent profile."""

from __future__ import annotations

import json
from typing import Any

from wega_evals.agent_profile import AgentProfile, register_profile
from wega_evals.models import DimensionScore


@register_profile
class UserStoryProfile(AgentProfile):
    """Evaluation profile for the User Story Generator agent."""

    name = "user_story"
    description = "User Story Generator — converts requirements/BRDs into user stories"
    trace_name = "user_story_gen"
    default_dataset = "user-story-eval"

    dimensions = [
        "story_quality",
        "acceptance_criteria_quality",
        "coverage",
        "invest_compliance",
        "story_sizing",
    ]

    output_schema = {
        "required_fields": ["stories"],
        "items_field": "stories",
        "item_required_fields": [
            "title", "description", "acceptance_criteria", "priority",
        ],
    }

    judge_prompts = {
        # ----- story_quality -----
        "story_quality": """\
You are an expert agile coach evaluator. Assess the **quality** of
AI-generated user stories.

## Source Requirements
{input_text}

## Generated User Stories
{output_text}

## Criteria
- Do stories follow "As a [role], I want [goal], so that [benefit]" format?
- Are stories clear and understandable to developers?
- Are roles, goals, and benefits well-defined?
- Are stories actionable (not vague)?

Score 0.0 to 1.0:
- 1.0 = All stories are clear, well-structured, actionable
- 0.5 = Mix of good and poor stories
- 0.0 = Stories are vague, poorly structured

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "good_stories": [<indices>],
  "weak_stories": [{{
    "index": <int>,
    "issue": "<what's wrong>"
  }}]
}}
""",
        # ----- acceptance_criteria_quality -----
        "acceptance_criteria_quality": """\
You are an expert QA engineer evaluator. Assess the **acceptance criteria**
quality for these user stories.

## Source Requirements
{input_text}

## Generated Stories with Acceptance Criteria
{output_text}

## Criteria
- Are acceptance criteria testable (Given/When/Then or clear conditions)?
- Do they cover the main happy path?
- Do they cover edge cases and error scenarios?
- Are they specific enough to verify?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "strong_criteria": [<indices of stories with good AC>],
  "weak_criteria": [{{
    "story_index": <int>,
    "issue": "<what's missing or vague>"
  }}]
}}
""",
        # ----- coverage -----
        "coverage": """\
You are an expert product manager. Assess whether the generated stories
**cover** all requirements from the source.

## Source Requirements
{input_text}

## Generated User Stories
{output_text}

## Criteria
- Is every requirement from the source represented by at least one story?
- Are there obvious gaps in coverage?
- Are cross-cutting concerns (security, performance, etc.) addressed?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "covered_requirements": ["<req covered>"],
  "uncovered_requirements": ["<req missed>"]
}}
""",
        # ----- invest_compliance -----
        "invest_compliance": """\
You are an expert agile coach. Assess whether stories follow the
**INVEST** criteria (Independent, Negotiable, Valuable, Estimable,
Small, Testable).

## Generated User Stories
{output_text}

For each story, check:
- **I**ndependent: Can be delivered without depending on other stories
- **N**egotiable: Not overly prescriptive implementation details
- **V**aluable: Delivers value to the user/stakeholder
- **E**stimable: Enough detail to estimate effort
- **S**mall: Right-sized for a sprint
- **T**estable: Clear way to verify completion

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "story_assessments": [
    {{
      "index": <int>,
      "independent": <bool>,
      "negotiable": <bool>,
      "valuable": <bool>,
      "estimable": <bool>,
      "small": <bool>,
      "testable": <bool>
    }}
  ]
}}
""",
        # ----- story_sizing -----
        "story_sizing": """\
You are an expert scrum master. Assess whether the stories are
**properly sized** — not too large (epics) or too small (tasks).

## Generated User Stories
{output_text}

## Criteria
- Are stories small enough to complete in one sprint?
- Are they large enough to deliver meaningful value?
- Are epics properly broken down?
- Are there any that should be split or merged?

Score 0.0 to 1.0. Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<explanation>",
  "properly_sized": [<indices>],
  "too_large": [<indices that need splitting>],
  "too_small": [<indices that should be merged>]
}}
""",
    }

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        """Source requirements are the primary input."""
        for key in ("requirements", "brd_document", "document", "content", "text", "epic"):
            if key in input_data and isinstance(input_data[key], str):
                return input_data[key]
        gen = input_data.get("generation_input", {})
        if isinstance(gen, dict):
            for key in ("requirements", "document", "content", "text"):
                if key in gen:
                    return str(gen[key])
        return json.dumps(input_data, indent=2, default=str)

    def run_programmatic_evals(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        token_info: dict[str, int],
    ) -> list[DimensionScore]:
        scores = super().run_programmatic_evals(input_data, output_data, token_info)

        # Check story format compliance
        stories = output_data.get("stories", [])
        if stories:
            format_ok = 0
            for s in stories:
                desc = s.get("description", "")
                if "as a" in desc.lower() and ("i want" in desc.lower() or "want to" in desc.lower()):
                    format_ok += 1
            scores.append(DimensionScore(
                dimension="story_format_compliance",
                score=format_ok / len(stories) if stories else 1.0,
                reasoning=f"{format_ok}/{len(stories)} stories follow 'As a...' format",
                evaluator="programmatic",
            ))

            # Check acceptance criteria presence
            with_ac = sum(1 for s in stories if s.get("acceptance_criteria"))
            scores.append(DimensionScore(
                dimension="acceptance_criteria_presence",
                score=with_ac / len(stories) if stories else 1.0,
                reasoning=f"{with_ac}/{len(stories)} stories have acceptance criteria",
                evaluator="programmatic",
            ))

        return scores
