"""Check trace structures for all remaining agents."""
import os
import httpx
from dotenv import load_dotenv
load_dotenv()
from wega_evals.llm_judge import _ensure_ca_bundle
_ensure_ca_bundle()

ca_bundle = os.environ.get("SSL_CERT_FILE", os.environ.get("REQUESTS_CA_BUNDLE"))
host = os.environ["LANGFUSE_HOST"]
pk = os.environ["LANGFUSE_PUBLIC_KEY"]
sk = os.environ["LANGFUSE_SECRET_KEY"]

verify = ca_bundle if ca_bundle and os.path.exists(ca_bundle) else True
print(f"CA bundle: {ca_bundle} (exists: {os.path.exists(ca_bundle) if ca_bundle else False})")
client = httpx.Client(verify=verify, auth=(pk, sk), timeout=30, base_url=host.rstrip("/"))

agents = {
    "sdlc_orchestrator_request": "sdlc_orchestrator",
    "codeassist": "code_assistant",
    "brd_summary_request": "brd_summary",
    "brd_chat": "brd",
    "usermanual_generation": "user_manual",
    "cara_prompt_stream": "cara",
}

for trace_name, agent in agents.items():
    print(f"=== {agent} ({trace_name}) ===")
    r = client.get("/api/public/traces", params={"name": trace_name, "limit": 1})
    data = r.json()
    traces = data.get("data", [])
    if not traces:
        print("  No traces")
        continue
    t = traces[0]
    tid = t["id"]
    r2 = client.get(f"/api/public/traces/{tid}")
    full = r2.json()
    obs = full.get("observations", [])
    print(f"  Obs count: {len(obs)}")
    gens = [o for o in obs if o.get("type") == "GENERATION"]
    print(f"  GENERATION count: {len(gens)}")
    if gens:
        g = gens[-1]
        out = g.get("output")
        out_type = type(out).__name__
        out_preview = str(out)[:200] if out else "None"
        print(f"  Last gen name: {g.get('name')}")
        print(f"  Output type: {out_type}")
        print(f"  Output preview: {out_preview}")
        if isinstance(out, dict):
            print(f"  Output keys: {list(out.keys())}")
    # Also check trace-level output
    trace_out = full.get("output")
    if trace_out:
        print(f"  Trace output type: {type(trace_out).__name__}")
        print(f"  Trace output preview: {str(trace_out)[:200]}")
    print()
