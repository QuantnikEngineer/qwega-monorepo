"""Evaluation runner — orchestrates dataset, judge, programmatic evals, and Langfuse scoring."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from langfuse import Langfuse

from quantnik_evals.agent_profile import AgentProfile
from quantnik_evals.config import EvalConfig
from quantnik_evals.dataset_manager import DatasetManager
from quantnik_evals.llm_judge import LLMJudge, build_langfuse_httpx_client
from quantnik_evals.models import DimensionScore, EvalResult

logger = logging.getLogger(__name__)


class EvalRunner:
    """Orchestrate a full evaluation run for any agent."""

    def __init__(self, config: EvalConfig, profile: AgentProfile) -> None:
        self._config = config
        self._profile = profile
        self._lf = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            host=config.langfuse_host,
            httpx_client=build_langfuse_httpx_client(),
        )
        self._judge = LLMJudge(config, profile)
        self._dataset_mgr = DatasetManager(config, profile)

    # ------------------------------------------------------------------
    # Run evaluation
    # ------------------------------------------------------------------

    def run(
        self,
        dataset_name: str | None = None,
        dimensions: list[str] | None = None,
        max_items: int | None = None,
    ) -> list[EvalResult]:
        """Run evaluation on all items in a dataset."""
        name = (
            dataset_name
            or self._config.dataset_name
            or self._profile.default_dataset
        )
        run_name = (
            self._config.run_name
            or f"{self._profile.name}-eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )
        dims = dimensions or self._profile.dimensions

        logger.info("Starting '%s' evaluation run '%s' on dataset '%s'",
                     self._profile.name, run_name, name)
        items = self._dataset_mgr.load_dataset(name)
        if max_items:
            items = items[:max_items]

        max_workers = min(self._config.max_workers, len(items)) if items else 1
        logger.info("Using %d parallel workers for %d items", max_workers, len(items))

        results: list[EvalResult] = [None] * len(items)  # type: ignore[list-item]

        def _process_item(idx: int, item: Any) -> tuple[int, EvalResult]:
            logger.info("Evaluating item %d/%d: %s", idx + 1, len(items), item.id)
            try:
                result = self._evaluate_item(item, dims, run_name)
                self._push_scores(result)
                return idx, result
            except Exception as exc:
                logger.error("Failed to evaluate item %s: %s", item.id, exc)
                return idx, EvalResult(
                    trace_id=item.trace_id or item.id,
                    agent=self._profile.name,
                    dataset_item_id=item.id,
                    run_name=run_name,
                    error=str(exc),
                )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_process_item, i, item): i
                for i, item in enumerate(items)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        self._lf.flush()
        self._print_summary(results, run_name)
        return results

    def run_on_trace(
        self,
        trace_id: str,
        dimensions: list[str] | None = None,
    ) -> EvalResult:
        """Run evaluation on a single Langfuse trace."""
        dims = dimensions or self._profile.dimensions
        run_name = f"{self._profile.name}-trace-{trace_id[:8]}"

        trace = self._lf.api.trace.get(trace_id)
        observations = trace.observations or []

        input_data = self._profile.extract_input(trace, observations)
        output_data = self._profile.extract_output(trace, observations)
        token_info = self._profile.extract_token_info(observations)

        if not output_data:
            return EvalResult(
                trace_id=trace_id,
                agent=self._profile.name,
                run_name=run_name,
                error="No agent output found in trace observations",
            )

        result = self._run_evaluations(
            trace_id=trace_id,
            input_data=input_data,
            output_data=output_data,
            token_info=token_info,
            dims=dims,
            run_name=run_name,
        )
        self._push_scores(result)
        self._lf.flush()
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate_item(
        self,
        item: Any,
        dims: list[str],
        run_name: str,
    ) -> EvalResult:
        """Evaluate a single dataset item."""
        input_data = item.input or {}
        output_data = item.expected_output or {}
        trace_id = item.trace_id or item.id
        token_info: dict[str, int] = {}

        # If the item has a trace_id, try to fetch actual output from trace
        if item.trace_id:
            try:
                full_trace = self._lf.api.trace.get(item.trace_id)
                observations = full_trace.observations or []
                fetched_output = self._profile.extract_output(full_trace, observations)
                if fetched_output:
                    output_data = fetched_output
                fetched_input = self._profile.extract_input(full_trace, observations)
                if fetched_input:
                    input_data = fetched_input
                token_info = self._profile.extract_token_info(observations)
            except Exception as exc:
                logger.warning("Failed to fetch trace %s: %s", trace_id, exc)

        result = self._run_evaluations(
            trace_id=trace_id,
            input_data=input_data,
            output_data=output_data,
            token_info=token_info,
            dims=dims,
            run_name=run_name,
        )
        result.dataset_item_id = item.id
        return result

    def _run_evaluations(
        self,
        *,
        trace_id: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        token_info: dict[str, int],
        dims: list[str],
        run_name: str,
    ) -> EvalResult:
        """Run all evaluators and collect results."""
        # LLM-as-judge
        result = self._judge.evaluate(
            trace_id=trace_id,
            input_data=input_data,
            output_data=output_data,
            dimensions=dims,
        )
        result.run_name = run_name

        # Programmatic evaluators from the profile
        try:
            prog_scores = self._profile.run_programmatic_evals(
                input_data, output_data, token_info,
            )
            result.scores.extend(prog_scores)
        except Exception as exc:
            logger.warning("Programmatic evaluators failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # Score push to Langfuse
    # ------------------------------------------------------------------

    def _push_scores(self, result: EvalResult) -> None:
        """Push evaluation scores back to Langfuse as trace scores."""
        if result.error:
            return

        prefix = f"{self._profile.name}_eval"
        for ds in result.scores:
            try:
                self._lf.create_score(
                    trace_id=result.trace_id,
                    name=f"{prefix}_{ds.dimension}",
                    value=ds.score,
                    comment=ds.reasoning[:500] if ds.reasoning else None,
                    data_type="NUMERIC",
                )
            except Exception as exc:
                logger.error("Failed to push score %s for trace %s: %s",
                             ds.dimension, result.trace_id, exc)

        # Aggregate score
        if result.scores:
            try:
                self._lf.create_score(
                    trace_id=result.trace_id,
                    name=f"{prefix}_overall",
                    value=result.overall_score,
                    comment=f"Aggregate of {len(result.scores)} dimension scores",
                    data_type="NUMERIC",
                )
            except Exception as exc:
                logger.error("Failed to push overall score for trace %s: %s",
                             result.trace_id, exc)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _print_summary(self, results: list[EvalResult], run_name: str) -> None:
        """Log a summary table of evaluation results."""
        agent = self._profile.name
        logger.info("\n%s", "="*70)
        logger.info("  Agent: %s", agent)
        logger.info("  Evaluation Run: %s", run_name)
        logger.info("  Items evaluated: %d", len(results))
        logger.info("  Errors: %d", sum(1 for r in results if r.error))
        logger.info("%s\n", "="*70)

        dim_scores: dict[str, list[float]] = {}
        for r in results:
            for s in r.scores:
                dim_scores.setdefault(s.dimension, []).append(s.score)

        logger.info("  %-30s %6s %6s %6s %4s", "Dimension", "Mean", "Min", "Max", "N")
        logger.info("  %s %s %s %s %s", "-"*30, "-"*6, "-"*6, "-"*6, "-"*4)
        for dim, scores in sorted(dim_scores.items()):
            mean = sum(scores) / len(scores)
            mn, mx = min(scores), max(scores)
            status = "PASS" if mean >= self._config.pass_threshold else "FAIL"
            logger.info("  %-30s %5.2f  %5.2f  %5.2f  %3d  %s", dim, mean, mn, mx, len(scores), status)

        if dim_scores:
            all_scores = [s for ss in dim_scores.values() for s in ss]
            overall = sum(all_scores) / len(all_scores)
            logger.info("\n  %-30s %5.2f", "OVERALL", overall)
            logger.info("  Pass threshold: %s", self._config.pass_threshold)
            logger.info("  Result: %s", "PASS" if overall >= self._config.pass_threshold else "NEEDS IMPROVEMENT")
        logger.info("")
