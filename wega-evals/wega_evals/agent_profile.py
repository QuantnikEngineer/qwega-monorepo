"""Agent profile base class and registry.

Each agent (CARA, BRD Summary, User Story Generator, etc.) provides a profile
that tells the evaluation framework:
  - What dimensions to evaluate
  - What LLM judge prompts to use for each dimension
  - How the agent's output is structured
  - How to extract input/output from Langfuse traces
  - What programmatic checks to run
"""

from __future__ import annotations

import json
import logging
from typing import Any

from wega_evals.common_prompts import COMMON_JUDGE_PROMPTS, UNIVERSAL_DIMENSIONS
from wega_evals.models import DimensionScore, ItemEval

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[AgentProfile]] = {}


def register_profile(cls: type[AgentProfile]) -> type[AgentProfile]:
    """Class decorator to register an agent profile."""
    _REGISTRY[cls.name] = cls
    return cls


def get_profile(name: str) -> AgentProfile:
    """Instantiate a registered profile by name."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(f"Unknown agent profile '{name}'. Available: {available}")
    return _REGISTRY[name]()


def list_profiles() -> dict[str, str]:
    """Return {name: description} of all registered profiles."""
    return {name: cls.description for name, cls in sorted(_REGISTRY.items())}


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class AgentProfile:
    """Base class for agent evaluation profiles.

    Subclass this and set the class attributes + override methods
    for your specific agent.
    """

    # --- Identity (override in subclass) ---
    name: str = ""
    description: str = ""

    # --- Langfuse trace filter ---
    trace_name: str = ""               # e.g. "cara_prompt", "brd_summary"

    # --- Default dataset name ---
    default_dataset: str = "eval"

    # --- Dimensions to evaluate ---
    dimensions: list[str] = []

    # --- LLM judge prompt templates ---
    # Map dimension name -> prompt template string.
    # Templates can use {input_text}, {output_text}, and any keys
    # returned by format_judge_context().
    judge_prompts: dict[str, str] = {}

    # --- Output schema definition (for programmatic validation) ---
    output_schema: dict[str, Any] = {
        # "required_fields": ["summary"],
        # "status_field": "status",
        # "status_values": ["pass", "fail"],
        # "items_field": "findings",        # list field to iterate
        # "item_required_fields": ["id", "description"],
        # "severity_field": "severity",     # field within items
        # "severity_range": [1, 10],
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-merge universal dimensions and common judge prompts."""
        super().__init_subclass__(**kwargs)
        # Merge universal dimensions (avoid duplicates, append at end)
        if cls.dimensions:
            existing = set(cls.dimensions)
            for dim in UNIVERSAL_DIMENSIONS:
                if dim not in existing:
                    cls.dimensions = [*cls.dimensions, dim]
        # Merge common judge prompts (profile-specific prompts take priority)
        if cls.judge_prompts is not None:
            merged = {**COMMON_JUDGE_PROMPTS, **cls.judge_prompts}
            cls.judge_prompts = merged

    # ------------------------------------------------------------------
    # Trace extraction — override for custom trace structures
    # ------------------------------------------------------------------

    def extract_input(self, trace: Any, observations: list[Any]) -> dict[str, Any]:
        """Extract agent input from a Langfuse trace + observations.

        Default: pulls trace.input and the first GENERATION's input.
        """
        result: dict[str, Any] = {}
        if trace.input:
            result.update(
                trace.input if isinstance(trace.input, dict)
                else {"raw_input": trace.input}
            )
        if trace.metadata and isinstance(trace.metadata, dict):
            result["trace_metadata"] = trace.metadata

        for obs in observations:
            if obs.type == "GENERATION" and obs.input:
                result["generation_input"] = (
                    obs.input if isinstance(obs.input, dict) else {"raw": obs.input}
                )
                result["model"] = obs.model or ""
                break
        return result

    def extract_output(self, trace: Any, observations: list[Any]) -> dict[str, Any] | None:
        """Extract agent output from observations.

        Default: finds the last GENERATION output that is a dict.
        """
        for obs in reversed(observations):
            if obs.type != "GENERATION" or not obs.output:
                continue
            output = obs.output
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(output, dict):
                return output
        return None

    def extract_primary_input_text(self, input_data: dict[str, Any]) -> str:
        """Extract the primary input text for the LLM judge prompt.

        Override to customize which input field is the main content.
        Default: JSON-dumps the entire input.
        """
        return json.dumps(input_data, indent=2, default=str)

    def extract_primary_output_text(self, output_data: dict[str, Any]) -> str:
        """Extract the primary output text for the LLM judge prompt.

        Default: JSON-dumps the entire output.
        """
        return json.dumps(output_data, indent=2, default=str)

    # ------------------------------------------------------------------
    # Judge prompt formatting
    # ------------------------------------------------------------------

    def format_judge_context(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, str]:
        """Return extra template variables for judge prompts.

        The framework always provides {input_text} and {output_text}.
        Override this to add agent-specific variables like {diff},
        {findings_json}, {user_prompt}, etc.
        """
        return {}

    # ------------------------------------------------------------------
    # Programmatic evaluators
    # ------------------------------------------------------------------

    def run_programmatic_evals(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        token_info: dict[str, int],
    ) -> list[DimensionScore]:
        """Run programmatic (non-LLM) evaluators.

        Default implementation runs structural validation based on
        output_schema. Override to add agent-specific checks.
        """
        scores = []
        scores.append(self._validate_structure(output_data))
        if token_info:
            scores.append(self._evaluate_token_efficiency(output_data, token_info))
        scores.append(self._evaluate_latency(token_info))
        scores.append(self._evaluate_cost_efficiency(token_info))
        return scores

    # ------------------------------------------------------------------
    # Built-in programmatic evaluators
    # ------------------------------------------------------------------

    def _validate_structure(self, output: dict[str, Any]) -> DimensionScore:
        """Validate output against the declared output_schema."""
        schema = self.output_schema
        if not schema:
            return DimensionScore(
                dimension="structural_validity",
                score=1.0,
                reasoning="No output schema defined — skipping",
                evaluator="programmatic",
            )

        checks: dict[str, bool] = {}

        # Required top-level fields
        for field in schema.get("required_fields", []):
            checks[f"has_{field}"] = field in output and bool(output[field])

        # Status field valid values
        status_field = schema.get("status_field")
        status_values = schema.get("status_values")
        if status_field and status_values:
            checks[f"{status_field}_valid"] = output.get(status_field) in status_values

        # Items list exists
        items_field = schema.get("items_field")
        if items_field:
            checks[f"has_{items_field}"] = isinstance(output.get(items_field), list)

            # Item required fields
            items = output.get(items_field, [])
            item_fields = set(schema.get("item_required_fields", []))
            if items and item_fields:
                valid_items = sum(
                    1 for it in items if item_fields.issubset(set(it.keys()))
                )
                checks["items_have_required_fields"] = valid_items == len(items)

        if not checks:
            return DimensionScore(
                dimension="structural_validity",
                score=1.0,
                reasoning="No structural checks configured",
                evaluator="programmatic",
            )

        passed = sum(checks.values())
        total = len(checks)
        failed = [k for k, v in checks.items() if not v]

        return DimensionScore(
            dimension="structural_validity",
            score=passed / total,
            reasoning=(
                f"Structural checks: {passed}/{total} passed"
                + (f". Failed: {', '.join(failed)}" if failed else "")
            ),
            details={"checks": checks},
            evaluator="programmatic",
        )

    def _evaluate_token_efficiency(
        self,
        output: dict[str, Any],
        token_info: dict[str, int],
    ) -> DimensionScore:
        """Evaluate token efficiency — generic version."""
        input_tokens = token_info.get("input", 0)
        output_tokens = token_info.get("output", 0)
        total = input_tokens + output_tokens

        # Simple heuristic: flag if output is disproportionately large
        if input_tokens > 0:
            ratio = output_tokens / input_tokens
            if ratio > 2.0:
                score = 0.5
                reasoning = f"Output/input token ratio {ratio:.1f} is high"
            elif ratio < 0.01:
                score = 0.6
                reasoning = f"Output/input token ratio {ratio:.3f} is very low"
            else:
                score = 1.0
                reasoning = f"Token ratio {ratio:.2f} is reasonable"
        else:
            score = 1.0
            reasoning = "No input token data available"

        return DimensionScore(
            dimension="token_efficiency",
            score=score,
            reasoning=reasoning,
            details={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total,
            },
            evaluator="programmatic",
        )

    # ------------------------------------------------------------------
    # Token info extraction
    # ------------------------------------------------------------------

    def extract_token_info(self, observations: list[Any]) -> dict[str, int]:
        """Extract token usage, latency, and cost from trace observations."""
        info: dict[str, int] = {}
        total_duration_ms = 0
        total_cost: float = 0.0
        for obs in observations:
            if obs.type != "GENERATION":
                continue
            usage = obs.usage_details or {}
            if usage:
                info["input"] = info.get("input", 0) + int(usage.get("input", 0))
                info["output"] = info.get("output", 0) + int(usage.get("output", 0))
            # Capture latency from observation start/end times
            if obs.start_time and obs.end_time:
                delta = (obs.end_time - obs.start_time).total_seconds() * 1000
                total_duration_ms += int(delta)
            # Capture cost if available
            if hasattr(obs, "calculated_total_cost") and obs.calculated_total_cost:
                total_cost += float(obs.calculated_total_cost)
        if total_duration_ms:
            info["latency_ms"] = total_duration_ms
        if total_cost > 0:
            info["cost_usd"] = int(total_cost * 1_000_000)  # microdollars
        return info

    # ------------------------------------------------------------------
    # Latency evaluator
    # ------------------------------------------------------------------

    def _evaluate_latency(self, token_info: dict[str, int]) -> DimensionScore:
        """Evaluate response latency."""
        latency_ms = token_info.get("latency_ms", 0)
        if not latency_ms:
            return DimensionScore(
                dimension="latency",
                score=1.0,
                reasoning="No latency data available in trace",
                evaluator="programmatic",
            )

        latency_s = latency_ms / 1000.0
        # Scoring: <10s = 1.0, 10-30s = 0.8, 30-60s = 0.6, 60-120s = 0.4, >120s = 0.2
        if latency_s <= 10:
            score = 1.0
        elif latency_s <= 30:
            score = 0.8
        elif latency_s <= 60:
            score = 0.6
        elif latency_s <= 120:
            score = 0.4
        else:
            score = 0.2

        return DimensionScore(
            dimension="latency",
            score=score,
            reasoning=f"Total generation latency: {latency_s:.1f}s",
            details={"latency_ms": latency_ms, "latency_s": round(latency_s, 1)},
            evaluator="programmatic",
        )

    # ------------------------------------------------------------------
    # Cost efficiency evaluator
    # ------------------------------------------------------------------

    def _evaluate_cost_efficiency(self, token_info: dict[str, int]) -> DimensionScore:
        """Evaluate cost efficiency based on token usage."""
        input_tokens = token_info.get("input", 0)
        output_tokens = token_info.get("output", 0)
        total_tokens = input_tokens + output_tokens

        if not total_tokens:
            return DimensionScore(
                dimension="cost_efficiency",
                score=1.0,
                reasoning="No token data available",
                evaluator="programmatic",
            )

        # Cost scoring based on total tokens:
        # <5K = 1.0, 5K-20K = 0.8, 20K-50K = 0.6, 50K-100K = 0.4, >100K = 0.3
        if total_tokens <= 5_000:
            score = 1.0
        elif total_tokens <= 20_000:
            score = 0.8
        elif total_tokens <= 50_000:
            score = 0.6
        elif total_tokens <= 100_000:
            score = 0.4
        else:
            score = 0.3

        cost_usd = token_info.get("cost_usd", 0) / 1_000_000 if token_info.get("cost_usd") else None

        details: dict[str, Any] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
        if cost_usd is not None:
            details["estimated_cost_usd"] = round(cost_usd, 6)

        reasoning = f"Total tokens: {total_tokens:,} (in: {input_tokens:,}, out: {output_tokens:,})"
        if cost_usd is not None:
            reasoning += f", cost: ${cost_usd:.6f}"

        return DimensionScore(
            dimension="cost_efficiency",
            score=score,
            reasoning=reasoning,
            details=details,
            evaluator="programmatic",
        )
