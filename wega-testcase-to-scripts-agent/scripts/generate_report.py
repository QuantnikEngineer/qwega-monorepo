"""
Generate a detailed metrics report from Langfuse data.

Reads metrics_report.json (from extract_metrics.py) and produces:
  - scripts/test_script_metrics_report.txt  (human-readable)
  - scripts/test_script_metrics_report.json (machine-readable with per-trace breakdowns)

Usage:
    python scripts/generate_report.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
METRICS_JSON = SCRIPTS_DIR / "metrics_report.json"


def load_metrics() -> dict:
    if not METRICS_JSON.exists():
        print(f"ERROR: {METRICS_JSON} not found. Run extract_metrics.py first.")
        sys.exit(1)
    return json.loads(METRICS_JSON.read_text(encoding="utf-8"))


def generate_report(metrics: dict):
    traces = metrics.get("traces", {})
    total_traces = metrics["total_traces"]
    total_gens = metrics["total_generations"]
    total_input = metrics["total_input_tokens"]
    total_output = metrics["total_output_tokens"]
    total_tokens = metrics["total_tokens"]
    total_cost = metrics["total_cost_usd"]
    avg_cost = total_cost / max(total_traces, 1)

    report_lines = [
        "=" * 70,
        "  TEST CASES TO SCRIPTS AGENT — LANGFUSE METRICS REPORT",
        "=" * 70,
        f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "─" * 70,
        "  SUMMARY",
        "─" * 70,
        f"  Total Traces (requests):    {total_traces}",
        f"  Total Generations (LLM):    {total_gens}",
        f"  Avg Generations per Trace:  {total_gens / max(total_traces, 1):.1f}",
        "",
        f"  Total Input Tokens:         {total_input:,}",
        f"  Total Output Tokens:        {total_output:,}",
        f"  Total Tokens:               {total_tokens:,}",
        "",
        f"  Total Cost (USD):           ${total_cost:.6f}",
        f"  Avg Cost per Request:       ${avg_cost:.6f}",
        "",
        "─" * 70,
        "  PER-TRACE BREAKDOWN",
        "─" * 70,
    ]

    for trace_id, data in traces.items():
        report_lines.append(f"\n  Trace: {trace_id}")
        report_lines.append(f"    Input Tokens:   {data['total_input_tokens']:,}")
        report_lines.append(f"    Output Tokens:  {data['total_output_tokens']:,}")
        report_lines.append(f"    Total Tokens:   {data['total_tokens']:,}")
        report_lines.append(f"    Cost:           ${data['cost']:.6f}")
        report_lines.append(f"    Generations:    {len(data['generations'])}")
        for gen in data["generations"]:
            latency = gen.get("latency_ms")
            lat_str = f"{latency}ms" if latency is not None else "N/A"
            report_lines.append(
                f"      - {gen['name']:<30} "
                f"in={gen['input_tokens']:>6}  out={gen['output_tokens']:>6}  "
                f"latency={lat_str}"
            )

    report_lines.extend([
        "",
        "─" * 70,
        "  COST PROJECTIONS (USD/month)",
        "─" * 70,
        f"    50 requests/day:    ${avg_cost * 50 * 30:.2f}",
        f"   100 requests/day:    ${avg_cost * 100 * 30:.2f}",
        f"   500 requests/day:    ${avg_cost * 500 * 30:.2f}",
        f"  1000 requests/day:    ${avg_cost * 1000 * 30:.2f}",
        "",
        "=" * 70,
    ])

    # Write TXT
    txt_path = SCRIPTS_DIR / "test_script_metrics_report.txt"
    txt_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"✅ Report: {txt_path}")

    # Write filtered JSON
    filtered = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_traces": total_traces,
            "total_generations": total_gens,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "avg_cost_per_request": round(avg_cost, 6),
        },
        "cost_projections_monthly": {
            "50_per_day": round(avg_cost * 50 * 30, 2),
            "100_per_day": round(avg_cost * 100 * 30, 2),
            "500_per_day": round(avg_cost * 500 * 30, 2),
            "1000_per_day": round(avg_cost * 1000 * 30, 2),
        },
        "traces": traces,
    }
    json_path = SCRIPTS_DIR / "test_script_metrics_report.json"
    json_path.write_text(json.dumps(filtered, indent=2, default=str), encoding="utf-8")
    print(f"✅ JSON report: {json_path}")


def main():
    metrics = load_metrics()
    generate_report(metrics)


if __name__ == "__main__":
    main()
