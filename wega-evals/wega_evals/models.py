"""Generic data models for the evaluation framework.

All models are agent-agnostic. Agent-specific structure lives in profiles.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """A single evaluation dimension score."""

    dimension: str                     # Free-form name, defined by agent profile
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    evaluator: str = ""                # "llm_judge" or "programmatic"


class ItemEval(BaseModel):
    """Per-item evaluation detail (e.g., per-finding for code review)."""

    item_key: str = ""                 # Identifier within the output (e.g., file:line)
    is_correct: bool = True
    score: float = 1.0
    reasoning: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """Complete evaluation result for a single trace/dataset-item."""

    trace_id: str
    agent: str = ""                    # Agent profile name
    dataset_item_id: str | None = None
    run_name: str = ""
    scores: list[DimensionScore] = Field(default_factory=list)
    item_evals: list[ItemEval] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @property
    def overall_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)


class DatasetItem(BaseModel):
    """A single evaluation dataset item."""

    id: str
    input: dict[str, Any]
    expected_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
