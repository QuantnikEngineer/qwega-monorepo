"""
Langfuse Report Generator for Test Cases to Test Data Agent.

Reads metrics_report.json and produces formatted reports
with per-trace breakdowns and cost projections.

Output:
  scripts/testdata_metrics_report.txt
  scripts/testdata_metrics_report.json

Usage:
    python scripts/generate_report.py
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCRIPTS_DIR = Path(__file__).resolve().parent
METRICS_FILE = SCRIPTS_DIR / "metrics_report.json"


def main():
    if not METRICS_FILE.exists():
        logger.error(f"ERROR: {METRICS_FILE} not found. Run extract_metrics.py first.")
        return

    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    if not metrics:
        logger.info("No metrics data found.")
        return

    total_traces = len(metrics)
    total_gens = sum(len(t["generations"]) for t in metrics)
    total_input = sum(t["total_input_tokens"] for t in metrics)
    total_output = sum(t["total_output_tokens"] for t in metrics)
    total_tokens = sum(t["total_tokens"] for t in metrics)
    total_cost = sum(t["estimated_cost_usd"] for t in metrics)
    avg_cost = total_cost / total_traces if total_traces else 0

    # Cost projections
    projections = {}
    for daily in [50, 100, 500, 1000]:
        monthly = daily * 30
        projections[f"{daily}_per_day"] = {
            "daily_requests": daily,
            "monthly_requests": monthly,
            "estimated_monthly_cost_usd": round(avg_cost * monthly, 4),
        }

    # Build TXT report
    lines = [
        "=" * 60,
        "  Test Cases to Test Data Agent — Metrics Report",
        f"  Generated: {datetime.now().isoformat()}",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 40,
        f"  Total traces:       {total_traces}",
        f"  Total generations:  {total_gens}",
        f"  Total tokens:       {total_tokens:,}",
        f"    Input tokens:     {total_input:,}",
        f"    Output tokens:    {total_output:,}",
        f"  Total cost:         ${total_cost:.6f}",
        f"  Avg cost/trace:     ${avg_cost:.6f}",
        "",
        "COST PROJECTIONS (30-day month)",
        "-" * 40,
    ]
    for label, proj in projections.items():
        lines.append(
            f"  {proj['daily_requests']:>5} req/day → "
            f"{proj['monthly_requests']:>6} req/month → "
            f"${proj['estimated_monthly_cost_usd']:.4f}/month"
        )

    lines += ["", "PER-TRACE BREAKDOWN", "-" * 40]
    for t in metrics:
        lines.append(f"\n  Trace: {t['trace_id']}")
        lines.append(f"    Generations: {len(t['generations'])}")
        lines.append(f"    Tokens: {t['total_tokens']:,} (in:{t['total_input_tokens']:,} / out:{t['total_output_tokens']:,})")
        lines.append(f"    Cost: ${t['estimated_cost_usd']:.8f}")
        for g in t["generations"]:
            lines.append(f"      - {g['name']} [{g['model']}]: {g['total_tokens']} tokens, ${g['cost_usd']:.8f}")

    lines.append("")

    txt_path = SCRIPTS_DIR / "testdata_metrics_report.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"✅ TXT report: {txt_path}")

    # Build JSON report
    json_report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_traces": total_traces,
            "total_generations": total_gens,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 8),
            "avg_cost_per_trace_usd": round(avg_cost, 8),
        },
        "projections": projections,
        "traces": metrics,
    }

    json_path = SCRIPTS_DIR / "testdata_metrics_report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    logger.info(f"✅ JSON report: {json_path}")


if __name__ == "__main__":
    main()
