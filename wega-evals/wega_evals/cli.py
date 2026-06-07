"""CLI entry point for the wega-evals framework.

Usage:
    # List available agent profiles
    wega-eval list-agents

    # Seed a dataset from Langfuse traces
    wega-eval --agent cara seed --limit 20

    # Run evaluation on a dataset
    wega-eval --agent cara run --dataset cara-eval

    # Evaluate a single trace
    wega-eval --agent cara trace <trace-id>

    # Use a different agent
    wega-eval --agent brd_summary run --dataset brd-eval
    wega-eval --agent user_story run --dataset user-story-eval
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Import profiles to trigger registration
import wega_evals.profiles.cara  # noqa: F401
import wega_evals.profiles.brd_summary  # noqa: F401
import wega_evals.profiles.brd  # noqa: F401
import wega_evals.profiles.user_story  # noqa: F401
import wega_evals.profiles.userstory_validator  # noqa: F401
import wega_evals.profiles.userstory_to_testcases  # noqa: F401
import wega_evals.profiles.testcases_to_testdata  # noqa: F401
import wega_evals.profiles.testcase_to_scripts  # noqa: F401
import wega_evals.profiles.sdlc_orchestrator  # noqa: F401
import wega_evals.profiles.code_assistant  # noqa: F401
import wega_evals.profiles.user_manual  # noqa: F401

from wega_evals.agent_profile import get_profile, list_profiles
from wega_evals.config import EvalConfig
from wega_evals.dataset_manager import DatasetManager
from wega_evals.llm_judge import _ensure_ca_bundle
from wega_evals.runner import EvalRunner

logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()
    _ensure_ca_bundle()          # must run before any httpx/Langfuse client
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="wega-evals: Reusable LLM Agent Evaluation Framework",
    )
    parser.add_argument(
        "--agent", "-a",
        default="",
        help="Agent profile name (e.g., cara, brd_summary, user_story)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- list-agents ---
    sub.add_parser("list-agents", help="List available agent profiles")

    # --- seed ---
    p_seed = sub.add_parser("seed", help="Seed a dataset from Langfuse traces")
    p_seed.add_argument("--dataset", default="", help="Dataset name (default: agent's default)")
    p_seed.add_argument("--limit", type=int, default=20, help="Max traces to fetch")
    p_seed.add_argument("--trace-name", default="", help="Override trace name filter")
    p_seed.add_argument("--min-obs", type=int, default=2, help="Min observations per trace")

    # --- run ---
    p_run = sub.add_parser("run", help="Run evaluation on a dataset")
    p_run.add_argument("--dataset", default="", help="Dataset name")
    p_run.add_argument("--run-name", default="", help="Evaluation run name")
    p_run.add_argument("--max-items", type=int, default=None, help="Max items to evaluate")
    p_run.add_argument("--dimensions", default="", help="Comma-separated dimensions")
    p_run.add_argument("--judge-model", default="", help="Override judge model")
    p_run.add_argument("--concurrency", type=int, default=None, help="Parallel items (default: 4)")
    p_run.add_argument("--output", "-o", default="", help="Save results to JSON file")

    # --- trace ---
    p_trace = sub.add_parser("trace", help="Evaluate a single trace")
    p_trace.add_argument("trace_id", help="Langfuse trace ID")
    p_trace.add_argument("--dimensions", default="", help="Comma-separated dimensions")
    p_trace.add_argument("--judge-model", default="", help="Override judge model")

    # --- add-item ---
    p_add = sub.add_parser("add-item", help="Add a manual dataset item")
    p_add.add_argument("--dataset", default="", help="Dataset name")
    p_add.add_argument("--input-file", required=True, help="Path to input JSON file")
    p_add.add_argument("--expected-file", default="", help="Path to expected output JSON")
    p_add.add_argument("--item-id", default="", help="Custom item ID")

    args = parser.parse_args()

    if args.command == "list-agents":
        _cmd_list_agents()
        return

    # All other commands require --agent
    if not args.agent:
        parser.error("--agent is required for this command")

    profile = get_profile(args.agent)
    config = EvalConfig()

    if args.command == "seed":
        _cmd_seed(args, config, profile)
    elif args.command == "run":
        _cmd_run(args, config, profile)
    elif args.command == "trace":
        _cmd_trace(args, config, profile)
    elif args.command == "add-item":
        _cmd_add_item(args, config, profile)


def _cmd_list_agents() -> None:
    profiles = list_profiles()
    if not profiles:
        logger.warning("No agent profiles registered.")
        return
    logger.info("\nAvailable agent profiles:\n")
    for name, desc in profiles.items():
        logger.info("  %s %s", f"{name:<20}", desc)
    logger.info("")


def _cmd_seed(args, config, profile) -> None:
    if args.dataset:
        config.dataset_name = args.dataset
    mgr = DatasetManager(config, profile)
    items = mgr.seed_from_traces(
        trace_name=args.trace_name or None,
        limit=args.limit,
        min_observations=args.min_obs,
    )
    if not items:
        logger.warning("No qualifying traces found. Try --min-obs 1 or --limit 50.")
        return
    ds_name = args.dataset or profile.default_dataset
    mgr.push_dataset(items, dataset_name=ds_name)
    logger.info("Seeded %d items into dataset '%s'", len(items), ds_name)


def _cmd_run(args, config, profile) -> None:
    if args.dataset:
        config.dataset_name = args.dataset
    if args.judge_model:
        config.judge_model = args.judge_model
    if args.run_name:
        config.run_name = args.run_name
    if args.concurrency:
        config.max_workers = args.concurrency

    dims = _parse_dimensions(args.dimensions) if args.dimensions else None

    runner = EvalRunner(config, profile)
    results = runner.run(
        dataset_name=args.dataset or None,
        dimensions=dims,
        max_items=args.max_items,
    )

    if args.output:
        output_data = [r.model_dump() for r in results]
        Path(args.output).write_text(
            json.dumps(output_data, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Results saved to %s", args.output)


def _cmd_trace(args, config, profile) -> None:
    if args.judge_model:
        config.judge_model = args.judge_model

    dims = _parse_dimensions(args.dimensions) if args.dimensions else None

    runner = EvalRunner(config, profile)
    result = runner.run_on_trace(args.trace_id, dimensions=dims)

    if result.error:
        logger.error("Error: %s", result.error)
        sys.exit(1)

    logger.info("\nAgent: %s", profile.name)
    logger.info("Trace: %s", result.trace_id)
    logger.info("Overall: %.2f\n", result.overall_score)
    logger.info("%-30s %6s  %s", "Dimension", "Score", "Status")
    logger.info("%s %s  %s", "-"*30, "-"*6, "-"*6)
    for s in result.scores:
        status = "PASS" if s.score >= config.pass_threshold else "FAIL"
        logger.info("  %-28s %5.2f  %s", s.dimension, s.score, status)
        if s.reasoning:
            logger.info("    %s", s.reasoning[:120])
    logger.info("")


def _cmd_add_item(args, config, profile) -> None:
    input_data = json.loads(
        Path(args.input_file).read_text(encoding="utf-8")
    )
    expected = None
    if args.expected_file:
        expected = json.loads(
            Path(args.expected_file).read_text(encoding="utf-8")
        )

    if args.dataset:
        config.dataset_name = args.dataset

    mgr = DatasetManager(config, profile)
    item = mgr.add_item(
        input_data=input_data,
        expected_output=expected,
        item_id=args.item_id or None,
        dataset_name=args.dataset or None,
    )
    logger.info("Added item '%s' to dataset '%s'", item.id, args.dataset or profile.default_dataset)


def _parse_dimensions(dim_str: str) -> list[str] | None:
    dims = [d.strip() for d in dim_str.split(",") if d.strip()]
    return dims or None


if __name__ == "__main__":
    main()
