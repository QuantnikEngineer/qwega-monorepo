"""
Extract metrics from Langfuse REST API for the Test Cases to Scripts Agent.

Queries all GENERATION observations, computes per-trace token usage and cost,
and outputs metrics_report.json and cost_summary.txt.

Usage:
    python scripts/extract_metrics.py

Required env vars:
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

_combined_ca_env = os.getenv("OTEL_CA_CERT_PATH")
if _combined_ca_env:
    _combined_ca = Path(_combined_ca_env)
else:
    _combined_ca = Path(__file__).resolve().parent.parent / "combined_ca.pem"
SSL_VERIFY = str(_combined_ca) if _combined_ca.exists() else True

OUTPUT_DIR = Path(__file__).resolve().parent
COST_PER_1K_INPUT = 0.000125   # Gemini Flash pricing (adjust as needed)
COST_PER_1K_OUTPUT = 0.000375


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=HOST,
        auth=(PUBLIC_KEY, SECRET_KEY),
        verify=SSL_VERIFY,
        timeout=30,
    )


def fetch_generations(limit: int = 100) -> list:
    """Fetch recent GENERATION observations from Langfuse."""
    with _client() as c:
        resp = c.get("/api/public/observations", params={
            "type": "GENERATION",
            "limit": limit,
        })
        resp.raise_for_status()
        return resp.json().get("data", [])


def fetch_traces(limit: int = 100) -> list:
    """Fetch recent traces from Langfuse."""
    with _client() as c:
        resp = c.get("/api/public/traces", params={"limit": limit})
        resp.raise_for_status()
        return resp.json().get("data", [])


def compute_metrics(generations: list) -> dict:
    """Compute aggregate metrics from generation observations."""
    trace_map = {}
    for gen in generations:
        trace_id = gen.get("traceId", "unknown")
        usage = gen.get("usageDetails") or {}
        input_tokens = usage.get("input", 0)
        output_tokens = usage.get("output", 0)
        total_tokens = usage.get("total", 0)

        if trace_id not in trace_map:
            trace_map[trace_id] = {
                "trace_id": trace_id,
                "generations": [],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            }

        entry = trace_map[trace_id]
        entry["generations"].append({
            "name": gen.get("name", ""),
            "model": gen.get("model", ""),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "latency_ms": gen.get("latency"),
            "status": gen.get("statusMessage", ""),
            "created_at": gen.get("startTime", ""),
        })
        entry["total_input_tokens"] += input_tokens
        entry["total_output_tokens"] += output_tokens
        entry["total_tokens"] += total_tokens
        entry["cost"] += (
            (input_tokens / 1000) * COST_PER_1K_INPUT
            + (output_tokens / 1000) * COST_PER_1K_OUTPUT
        )

    return trace_map


def main():
    print("Fetching generations from Langfuse...")
    generations = fetch_generations()
    print(f"  Found {len(generations)} generation(s)")

    if not generations:
        print("No generations found. Exiting.")
        sys.exit(0)

    trace_map = compute_metrics(generations)

    # Summary
    total_input = sum(t["total_input_tokens"] for t in trace_map.values())
    total_output = sum(t["total_output_tokens"] for t in trace_map.values())
    total_all = sum(t["total_tokens"] for t in trace_map.values())
    total_cost = sum(t["cost"] for t in trace_map.values())

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_traces": len(trace_map),
        "total_generations": len(generations),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_all,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_1k_input": COST_PER_1K_INPUT,
        "cost_per_1k_output": COST_PER_1K_OUTPUT,
        "traces": {k: v for k, v in trace_map.items()},
    }

    # Write JSON report
    json_path = OUTPUT_DIR / "metrics_report.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n✅ Metrics report: {json_path}")

    # Write cost summary TXT
    txt_path = OUTPUT_DIR / "cost_summary.txt"
    lines = [
        f"Langfuse Metrics Summary — {summary['generated_at']}",
        f"{'='*60}",
        f"Total Traces:         {len(trace_map)}",
        f"Total Generations:    {len(generations)}",
        f"Total Input Tokens:   {total_input:,}",
        f"Total Output Tokens:  {total_output:,}",
        f"Total Tokens:         {total_all:,}",
        f"Total Cost (USD):     ${total_cost:.6f}",
        f"",
        f"Cost Projections:",
        f"  100 requests/day:   ${total_cost / max(len(trace_map),1) * 100 * 30:.2f}/month",
        f"  500 requests/day:   ${total_cost / max(len(trace_map),1) * 500 * 30:.2f}/month",
        f"  1000 requests/day:  ${total_cost / max(len(trace_map),1) * 1000 * 30:.2f}/month",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Cost summary: {txt_path}")


if __name__ == "__main__":
    main()
