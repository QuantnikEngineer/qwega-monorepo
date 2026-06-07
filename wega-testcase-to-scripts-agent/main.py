"""
Instrumented entry point for the Test Cases to Scripts Agent.

Run this instead of api_server.py to enable Langfuse observability.
All existing code remains untouched — instrumentation is applied via
monkey-patching before api_server imports the agent module.

Usage:
    python main.py
    # or
    uvicorn main:app --host 0.0.0.0 --port 8080

Required env vars (add to .env or export):
    LANGFUSE_SECRET_KEY=sk-lf-...
    LANGFUSE_PUBLIC_KEY=pk-lf-...
    LANGFUSE_HOST=https://cloud.langfuse.com   (or your self-hosted URL)
"""

# 0. Set combined CA bundle env vars BEFORE any network imports.
#    This ensures both the requests library and Python's ssl module use
#    the combined bundle for all outgoing HTTPS (Google APIs + Langfuse ALB).
import os as _os
from pathlib import Path as _P

_combined_ca_env = _os.getenv("OTEL_CA_CERT_PATH")
if _combined_ca_env:
    _combined_ca = _P(_combined_ca_env)
else:
    _combined_ca = _P(__file__).resolve().parent / "combined_ca.pem"
if _combined_ca.exists():
    _os.environ.setdefault("SSL_CERT_FILE", str(_combined_ca))
    _os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_combined_ca))
    if _combined_ca_env:
        print(f"✅ SSL CA bundle set from OTEL_CA_CERT_PATH: {_combined_ca}")
    else:
        print(f"✅ SSL CA bundle set (default path): {_combined_ca}")

import atexit

# 1. Load the agent module (triggers Vertex AI init, model creation, etc.)
import testcase_to_scripts_agent  # noqa: F401

# 2. Apply Langfuse monkey-patches to the agent module's functions.
#    This MUST happen before api_server is imported, because api_server
#    does `from testcase_to_scripts_agent import process_single_test_case`
# 0. Load .env as early as possible
try:
     from dotenv import load_dotenv
     load_dotenv()
except ImportError:
     pass

# 1. Set combined CA bundle env vars BEFORE any network imports.
from langfuse_instrumentation import instrument, add_middleware, shutdown

instrument()

# 3. Now import the FastAPI app — it gets the already-patched functions.
from api_server import app  # noqa: E402

# 4. Add the ASGI middleware that creates a Langfuse trace per /convert request.
add_middleware(app)

# 5. Ensure Langfuse flushes on process exit.
atexit.register(shutdown)

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Instrumented Test Cases to Test Scripts Agent API...")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
