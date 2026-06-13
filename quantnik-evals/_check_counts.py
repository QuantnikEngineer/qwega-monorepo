"""Quick check: trace count + dataset item count for each agent."""

from __future__ import annotations

import os, sys
os.environ.setdefault("SSL_CERT_FILE", "")  # let _ensure_ca_bundle handle it

from dotenv import load_dotenv
load_dotenv()

from quantnik_evals.llm_judge import _ensure_ca_bundle, build_langfuse_httpx_client
_ensure_ca_bundle()

from langfuse import Langfuse
from quantnik_evals.agent_profile import list_profiles, get_profile

lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
    httpx_client=build_langfuse_httpx_client(),
)

print(f"{'Agent':<25} {'Trace Name':<35} {'Traces':>7} {'Dataset':>25} {'Items':>7}")
print("-" * 105)

for name in sorted(list_profiles().keys()):
    profile = get_profile(name)
    trace_name = profile.trace_name
    dataset_name = profile.default_dataset

    # Count traces
    try:
        traces = lf.api.trace.list(name=trace_name, limit=1)
        trace_count = traces.meta.total_items if hasattr(traces.meta, 'total_items') else len(traces.data)
    except Exception as e:
        trace_count = f"ERR: {e}"

    # Count dataset items
    try:
        ds = lf.api.datasets.get(dataset_name=dataset_name)
        item_count = len(ds.items) if hasattr(ds, 'items') and ds.items else "0"
    except Exception:
        # Try listing items
        try:
            items = lf.api.dataset_items.list(dataset_name=dataset_name)
            item_count = items.meta.total_items if hasattr(items.meta, 'total_items') else len(items.data)
        except Exception:
            item_count = "N/A"

    print(f"{name:<25} {trace_name:<35} {str(trace_count):>7} {dataset_name or 'N/A':>25} {str(item_count):>7}")
