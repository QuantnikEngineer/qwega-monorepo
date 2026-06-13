"""CARA code review agent profile."""

from __future__ import annotations

import json
import re
from typing import Any

from quantnik_evals.agent_profile import AgentProfile, register_profile
from quantnik_evals.models import DimensionScore, ItemEval


@register_profile
class CARAProfile(AgentProfile):
    """Evaluation profile for the CARA code review agent."""

    name = "cara"
    description = "CARA — AI code review agent (PR diffs → structured findings)"
    trace_name = "cara_prompt_stream"
    default_dataset = "cara-eval"

    dimensions = [
        "review_relevance",
        "review_completeness",
        "finding_accuracy",
        "severity_calibration",
        "false_positive_rate",
        "remediation_quality",
        "reasoning_quality",
        "causal_understanding",
    ]

    output_schema = {
        "required_fields": ["overall_status", "summary"],
        "status_field": "overall_status",
        "status_values": ["pass", "needs_attention", "failed"],
        "items_field": "vulnerabilities_and_bugs",
        "item_required_fields": [
            "file_path", "line_number", "issue_type",
            "severity_score", "comment",
        ],
        "severity_field": "severity_score",
        "severity_range": [1, 10],
    }

    judge_prompts = {
        # ----- review_relevance -----
        "review_relevance": """\
You are an expert code review evaluator. Assess whether this AI-generated
code review is **relevant** to the actual code changes.

## Code Diff
{diff}

## AI Review Output
{output_text}

## Criteria
- Are findings actually present in the diff (not hallucinated)?
- Do findings reference correct files and line numbers?
- Is the summary accurately reflecting the changes?
- Are identified issue types appropriate?

Score from 0.0 to 1.0:
- 1.0 = All findings directly relevant to the diff
- 0.5 = Mix of relevant and irrelevant findings
- 0.0 = Findings mostly hallucinated or unrelated

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "hallucinated_findings": [<indices>],
  "relevant_findings": [<indices>]
}}
""",
        # ----- review_completeness -----
        "review_completeness": """\
You are an expert code review evaluator. Assess whether this AI code review
is **complete** — did it catch the important issues?

## Code Diff
{diff}

## AI Review Output
{output_text}

## Criteria
- Did the review identify security vulnerabilities in the diff?
- Did it catch bugs or logic errors?
- Did it flag important best-practice violations?
- Are there significant issues in the diff that were missed?

Score 0.0 to 1.0:
- 1.0 = All significant issues caught
- 0.5 = Some important issues caught, some missed
- 0.0 = Most significant issues missed

Respond in JSON:
{{
  "score": <float 0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "missed_issues": ["<description>"],
  "caught_issues": ["<description>"]
}}
""",
        # ----- finding_accuracy -----
        "finding_accuracy": """\
You are an expert code review evaluator. Assess the **accuracy** of each
individual finding.

## Code Diff
{diff}

## Findings
{findings_json}

For EACH finding, determine:
1. Is it a true positive (real issue) or false positive?
2. Is the severity_score (1-10) appropriate?
3. Is the suggested_remediation_code correct?

Respond in JSON:
{{
  "overall_accuracy_score": <float 0.0-1.0>,
  "reasoning": "<overall assessment>",
  "finding_evaluations": [
    {{
      "index": <int>,
      "file_path": "<str>",
      "line_number": <int>,
      "is_true_positive": <bool>,
      "severity_appropriate": <bool>,
      "expected_severity": <int or null>,
      "remediation_correct": <bool>,
      "reasoning": "<why>"
    }}
  ]
}}
""",
        # ----- severity_calibration -----
        "severity_calibration": """\
You are an expert code review evaluator. Assess whether **severity scores**
(1-10) are well-calibrated.

## Severity Scale
- 9-10: Critical — security exploit, data loss, system crash
- 7-8: High — significant bug, major vulnerability
- 4-6: Medium — maintainability issue, moderate risk
- 2-3: Low — style issue, minor improvement
- 1: Info — cosmetic

## Findings
{findings_json}

## Code Diff (context)
{diff}

Respond in JSON:
{{
  "calibration_score": <float 0.0-1.0>,
  "reasoning": "<assessment>",
  "mean_deviation": <float>,
  "findings": [
    {{
      "index": <int>,
      "actual_severity": <int>,
      "expected_severity": <int>,
      "assessment": "over-rated" | "under-rated" | "appropriate"
    }}
  ]
}}
""",
        # ----- false_positive_rate -----
        "false_positive_rate": """\
You are an expert code review evaluator. Determine the **false positive rate**
of the findings.

## Code Diff
{diff}

## Findings
{findings_json}

A finding is a FALSE POSITIVE if:
- The described issue does not exist in the code
- The code is actually correct despite the finding
- The finding references wrong file/line
- The issue is so trivial it wastes developer time

Respond in JSON:
{{
  "false_positive_rate": <float 0.0-1.0>,
  "true_positive_count": <int>,
  "false_positive_count": <int>,
  "total_findings": <int>,
  "reasoning": "<assessment>",
  "evaluations": [
    {{
      "index": <int>,
      "verdict": "true_positive" | "false_positive",
      "reasoning": "<why>"
    }}
  ]
}}
""",
        # ----- remediation_quality -----
        "remediation_quality": """\
You are an expert code review evaluator. Assess the **quality of suggested
remediation code**.

## Code Diff
{diff}

## Findings with Remediation
{findings_json}

For each finding with suggested_remediation_code, assess:
1. Does the fix address the issue?
2. Is the code syntactically correct?
3. Would it introduce new issues?
4. Is it idiomatic?

Respond in JSON:
{{
  "overall_score": <float 0.0-1.0>,
  "reasoning": "<assessment>",
  "evaluations": [
    {{
      "index": <int>,
      "fix_addresses_issue": <bool>,
      "syntactically_correct": <bool>,
      "introduces_new_issues": <bool>,
      "score": <float 0.0-1.0>
    }}
  ]
}}
""",
    }

    # ------------------------------------------------------------------
    # CARA-specific extractors
    # ------------------------------------------------------------------

    def extract_input(self, trace: Any, observations: list[Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if trace and trace.input:
            result.update(
                trace.input if isinstance(trace.input, dict)
                else {"raw_input": trace.input}
            )
        if trace and trace.metadata and isinstance(trace.metadata, dict):
            for key in ("endpoint", "method", "owner", "repo", "pr_number"):
                if key in trace.metadata:
                    result[key] = trace.metadata[key]

        for obs in observations:
            if obs.type == "GENERATION" and obs.input:
                obs_input = obs.input if isinstance(obs.input, dict) else {}
                if "diff" in str(obs_input).lower() or "review" in (obs.name or "").lower():
                    result["generation_input"] = obs_input
                    result["model"] = obs.model or ""
                    break
        return result

    def extract_output(self, trace: Any, observations: list[Any]) -> dict[str, Any] | None:
        import json
        for obs in observations:
            if obs.type != "GENERATION" or not obs.output:
                continue
            output = obs.output
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(output, dict) and "overall_status" in output:
                return output
        return None

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        """For CARA, the primary input is the code diff."""
        gen = input_data.get("generation_input", {})
        if isinstance(gen, dict):
            for key in ("diff", "contents", "code"):
                if key in gen and isinstance(gen[key], str):
                    return gen[key]
        return json.dumps(input_data, indent=2, default=str)

    def format_judge_context(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, str]:
        """Provide CARA-specific template variables."""
        diff = self.extract_primary_input_text(input_data)
        findings = output_data.get("vulnerabilities_and_bugs", [])
        return {
            "diff": diff,
            "findings_json": json.dumps(findings, indent=2),
        }

    # ------------------------------------------------------------------
    # CARA-specific programmatic evaluators
    # ------------------------------------------------------------------

    def run_programmatic_evals(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        token_info: dict[str, int],
    ) -> list[DimensionScore]:
        scores = super().run_programmatic_evals(input_data, output_data, token_info)

        # Severity distribution check
        scores.append(self._check_severity_distribution(output_data))

        # Line reference accuracy
        diff = self.extract_primary_input_text(input_data)
        if diff:
            scores.append(self._check_line_references(output_data, diff))

        return scores

    def _check_severity_distribution(self, output: dict[str, Any]) -> DimensionScore:
        findings = output.get("vulnerabilities_and_bugs", [])
        if not findings:
            return DimensionScore(
                dimension="severity_distribution",
                score=1.0,
                reasoning="No findings",
                evaluator="programmatic",
            )

        sevs = [f.get("severity_score", 5) for f in findings]
        unique = len(set(sevs))
        critical = sum(1 for s in sevs if s >= 9)
        mean = sum(sevs) / len(sevs)
        penalties = 0.0
        reasons = []

        if len(sevs) > 2 and unique == 1:
            penalties += 0.3
            reasons.append(f"All {len(sevs)} findings same severity ({sevs[0]})")
        if len(sevs) > 1 and critical / len(sevs) > 0.5:
            penalties += 0.2
            reasons.append(f"{critical}/{len(sevs)} critical")
        if mean > 8.0:
            penalties += 0.1
            reasons.append(f"Mean {mean:.1f} very high")

        return DimensionScore(
            dimension="severity_distribution",
            score=max(0.0, 1.0 - penalties),
            reasoning="; ".join(reasons) or "Distribution looks reasonable",
            details={"severities": sevs, "mean": mean},
            evaluator="programmatic",
        )

    def _check_line_references(self, output: dict[str, Any], diff: str) -> DimensionScore:
        findings = output.get("vulnerabilities_and_bugs", [])
        if not findings:
            return DimensionScore(
                dimension="line_reference_accuracy",
                score=1.0,
                reasoning="No findings",
                evaluator="programmatic",
            )

        diff_files = set(re.findall(r"^diff --git a/(.+?) b/", diff, re.MULTILINE))
        diff_files.update(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))

        valid = 0
        for f in findings:
            fp = f.get("file_path", "")
            ln = f.get("line_number", 0)
            in_diff = any(fp.endswith(df) or df.endswith(fp) for df in diff_files) if fp else False
            if in_diff and ln > 0:
                valid += 1

        total = len(findings)
        return DimensionScore(
            dimension="line_reference_accuracy",
            score=valid / total if total else 1.0,
            reasoning=f"{valid}/{total} findings reference files in the diff",
            evaluator="programmatic",
        )
