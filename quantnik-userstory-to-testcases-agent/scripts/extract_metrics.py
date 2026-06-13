"""
Langfuse Metrics Extraction Script for Test Cases to Test Data Agent.

Queries the Langfuse REST API to fetch all GENERATION observations
and compute per-trace token usage and cost metrics.

Output:
  scripts/metrics_report.json
  scripts/cost_summary.txt

Usage:
    python scripts/extract_metrics.py
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# Gemini Flash pricing (per 1K tokens) — adjust as needed
COST_PER_1K_INPUT = 0.000125
COST_PER_1K_OUTPUT = 0.000375

SCRIPTS_DIR = Path(__file__).resolve().parent
CA_BUNDLE = Path(__file__).resolve().parent.parent / "combined_ca.pem"


def fetch_generations():
    """Fetch all GENERATION observations from Langfuse."""
    import httpx

    url = f"{LANGFUSE_HOST}/api/public/observations?type=GENERATION"
    verify = str(CA_BUNDLE) if CA_BUNDLE.exists() else True

    all_generations = []
    page = 1

    while True:
        resp = httpx.get(
            f"{url}&page={page}&limit=100",
            auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
            verify=verify,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        observations = data.get("data", [])
        if not observations:
            break
        all_generations.extend(observations)
        page += 1

    return all_generations


def compute_metrics(generations):
    """Group generations by trace and compute token/cost metrics."""
    traces = {}

    for gen in generations:
        trace_id = gen.get("traceId", "unknown")
        if trace_id not in traces:
            traces[trace_id] = {
                "trace_id": trace_id,
                "generations": [],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            }

        usage = gen.get("usageDetails") or gen.get("usage") or {}
        input_tokens = usage.get("input", 0) or 0
        output_tokens = usage.get("output", 0) or 0
        total_tokens = usage.get("total", input_tokens + output_tokens) or 0

        cost = (input_tokens / 1000 * COST_PER_1K_INPUT) + (
            output_tokens / 1000 * COST_PER_1K_OUTPUT
        )

        traces[trace_id]["generations"].append(
            {
                "id": gen.get("id"),
                "name": gen.get("name"),
                "model": gen.get("model"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost, 8),
                "latency_ms": gen.get("latency"),
            }
        )
        traces[trace_id]["total_input_tokens"] += input_tokens
        traces[trace_id]["total_output_tokens"] += output_tokens
        traces[trace_id]["total_tokens"] += total_tokens
        traces[trace_id]["estimated_cost_usd"] += cost

    # Round costs
    for t in traces.values():
        t["estimated_cost_usd"] = round(t["estimated_cost_usd"], 8)

    return list(traces.values())


def main():
    logger.info("Fetching GENERATION observations from Langfuse...")
    generations = fetch_generations()
    logger.info(f"  Found {len(generations)} generation(s)")

    if not generations:
        logger.info("No generations found. Exiting.")
        return

    metrics = compute_metrics(generations)
    logger.info(f"  Grouped into {len(metrics)} trace(s)")

    # Write JSON report
    report_path = SCRIPTS_DIR / "metrics_report.json"
    report_path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    logger.info(f"  ✅ Metrics report: {report_path}")

    # Write cost summary
    total_cost = sum(t["estimated_cost_usd"] for t in metrics)
    total_tokens = sum(t["total_tokens"] for t in metrics)
    summary_lines = [
        "=== Langfuse Cost Summary ===",
        f"Total traces: {len(metrics)}",
        f"Total generations: {len(generations)}",
        f"Total tokens: {total_tokens:,}",
        f"  Input tokens: {sum(t['total_input_tokens'] for t in metrics):,}",
        f"  Output tokens: {sum(t['total_output_tokens'] for t in metrics):,}",
        f"Estimated cost: ${total_cost:.6f}",
        f"Avg cost/trace: ${total_cost / len(metrics):.6f}" if metrics else "",
    ]
    summary_path = SCRIPTS_DIR / "cost_summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    logger.info(f"  ✅ Cost summary: {summary_path}")


if __name__ == "__main__":
    main()
