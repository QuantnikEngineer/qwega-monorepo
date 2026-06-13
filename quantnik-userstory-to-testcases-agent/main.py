"""
Instrumented entry point for the UserStory-to-TestCases Agent.

Run this instead of api_server.py to enable Langfuse + OTEL tracing.
The original api_server.py / userstory2TestCasesAgent.py are NOT modified;
instrumentation is applied via monkey-patching before api_server imports
the agent module.

Bootstrap order (critical):
  Step 0  Build CA bundle from certifi + repo cert + LANGFUSE_CA_CERT env
          and point standard SSL env vars at it BEFORE any networking
          library is imported (httpx, requests, opentelemetry exporters,
          langfuse SDK). Otherwise OTLP exports hit self-signed Langfuse
          ALB and fail with SSLCertVerificationError.
  Step 1  load_dotenv() so subsequent imports see the same env as the app.
  Step 2  Apply Langfuse monkey-patches BEFORE api_server is imported.
  Step 3  Import the FastAPI app from api_server (picks up patched refs).
  Step 4  Wrap ASGI app with Langfuse + envelope tracing middleware.
  Step 5  Register flush + shutdown on process exit.

Usage:
    python main.py
    # or
    uvicorn main:app --host 0.0.0.0 --port 8080
"""

import atexit
import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step 0: Build CA bundle and point standard SSL env vars at it.
# Must run BEFORE httpx / requests / opentelemetry / langfuse are imported.
# ---------------------------------------------------------------------------
try:
    import build_cert_bundle

    _ca_bundle = build_cert_bundle.build()
    if _ca_bundle.exists():
        os.environ.setdefault("SSL_CERT_FILE", str(_ca_bundle))
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_ca_bundle))
        os.environ.setdefault("OTEL_CA_CERT_PATH", str(_ca_bundle))
        # OTEL standard env vars (read by the OTLP HTTP exporter that the
        # langfuse SDK uses under the hood). setdefault preserves any
        # explicit override the operator may have set.
        os.environ.setdefault("OTEL_EXPORTER_OTLP_CERTIFICATE", str(_ca_bundle))
        os.environ.setdefault(
            "OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE", str(_ca_bundle)
        )
        logger.info("CA bundle ready at %s", _ca_bundle)
    else:
        logger.warning(
            "build_cert_bundle returned a path that does not exist: %s",
            _ca_bundle,
        )
except Exception as exc:
    logger.warning("Could not build CA bundle: %s", exc)

# ---------------------------------------------------------------------------
# Step 1: Load .env (no-op in cloud environments where env is injected).
# ---------------------------------------------------------------------------
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

# ---------------------------------------------------------------------------
# Step 2: Apply Langfuse monkey-patches BEFORE api_server is imported.
# ---------------------------------------------------------------------------
import langfuse_instrumentation  # noqa: E402

langfuse_instrumentation.instrument()

# ---------------------------------------------------------------------------
# Step 3: Import the FastAPI app (picks up the already-patched functions).
# ---------------------------------------------------------------------------
from api_server import app  # noqa: E402

# ---------------------------------------------------------------------------
# Step 4: Wrap the ASGI app with the Langfuse + envelope tracing middleware.
# ---------------------------------------------------------------------------
langfuse_instrumentation.add_middleware(app)

# ---------------------------------------------------------------------------
# Step 5: Ensure clean shutdown on process exit.
# ---------------------------------------------------------------------------
atexit.register(langfuse_instrumentation.shutdown)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
