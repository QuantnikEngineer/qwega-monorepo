"""
# Ensure .env is loaded before any environment variable usage
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
Langfuse observability wrapper for the Test Cases to Scripts Agent.
Rewritten for Langfuse Python SDK v4 (released March 2026).

Instruments the agent via monkey-patching — no existing code is modified.
Run via main.py instead of api_server.py to enable tracing.

Tracked metrics:
  1. Prompt monitoring (input/output for every Gemini call)
  2. Token usage (input / output / total per generation)
  3. Cost analysis (Langfuse auto-calculates from token counts + model config)
  4. Response latency (per LLM call, per step, end-to-end)
  5. Model performance (success / failure with error details)
  6. Quality scores (code extraction success, push success, files generated)
  7. Tool usage (Harness push success/failure, file counts)
  8. User interaction patterns (framework, language, generation type as metadata/tags)
  9. Error and retry patterns (exception tracking at every layer)
 10. End-to-end agent execution time (trace-level latency)

Required env vars:
  LANGFUSE_SECRET_KEY
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_HOST  (defaults to https://cloud.langfuse.com)
"""

import contextvars
import functools
import os
import time
import uuid

import os
from pathlib import Path

from langfuse import Langfuse

_langfuse: Langfuse = None
_instrumented: bool = False
_middleware_added: bool = False

# Path to the combined CA bundle (built by build_cert_bundle.py)
_combined_ca_env = os.getenv("OTEL_CA_CERT_PATH")
if _combined_ca_env:
    _combined_ca = Path(_combined_ca_env)
else:
    _combined_ca = Path(__file__).resolve().parent / "combined_ca.pem"


# ---------------------------------------------------------------------------
# Context-propagating executor: copies contextvars into thread-pool workers
# so that Langfuse's internal OpenTelemetry context propagates correctly.
# ---------------------------------------------------------------------------
class _ContextPropagatingExecutor:
    """Wraps a ThreadPoolExecutor so that contextvars are copied to workers."""

    def __init__(self, executor):
        self._executor = executor

    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return self._executor.submit(ctx.run, fn, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._executor, name)


# ---------------------------------------------------------------------------
# Helper: infer generation name from prompt text
# ---------------------------------------------------------------------------
def _infer_generation_name(prompt_text: str) -> str:
    lower = prompt_text.lower()
    if "feature file" in lower or "feature:" in lower:
        return "generate-feature-file"
    if "step definition" in lower:
        return "generate-step-definition"
    if "page object" in lower:
        return "generate-page-object"
    return "generate-script"


# ---------------------------------------------------------------------------
# Monkey-patch: ThreadPoolExecutor → context-propagating wrapper
# ---------------------------------------------------------------------------
def _patch_executor(agent_module):
    agent_module.executor = _ContextPropagatingExecutor(agent_module.executor)


# ---------------------------------------------------------------------------
# Monkey-patch: model.generate_content → log every LLM call as a generation
# ---------------------------------------------------------------------------
def _patch_generate_content(agent_module):
    original = agent_module.model.generate_content

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        prompt_text = str(args[0])[:5000] if args else ""
        model_name = agent_module.MODEL_NAME
        gen_config = kwargs.get("generation_config") or agent_module.GENERATION_CONFIG
        gen_name = _infer_generation_name(prompt_text)

        gen = _langfuse.start_observation(
            name=gen_name,
            as_type="generation",
            model=model_name,
            input=prompt_text,
            model_parameters=gen_config if isinstance(gen_config, dict) else {},
        )

        start = time.time()
        try:
            result = original(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000

            # Token usage from Gemini response
            usage = {}
            if hasattr(result, "usage_metadata"):
                um = result.usage_metadata
                usage = {
                    "input": getattr(um, "prompt_token_count", 0),
                    "output": getattr(um, "candidates_token_count", 0),
                    "total": getattr(um, "total_token_count", 0),
                }

            output_text = ""
            try:
                output_text = result.text[:5000] if result.text else ""
            except Exception:
                output_text = "[unable to extract]"

            gen.update(
                output=output_text,
                usage_details=usage if usage else None,
                metadata={"latency_ms": round(latency_ms, 2)},
                status_message="success",
                level="DEFAULT",
            )
            gen.end()
            return result

        except Exception as exc:
            latency_ms = (time.time() - start) * 1000
            gen.update(
                output=str(exc),
                status_message=f"error: {type(exc).__name__}: {exc}",
                level="ERROR",
                metadata={"latency_ms": round(latency_ms, 2)},
            )
            gen.end()
            raise

    agent_module.model.generate_content = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: convert_test_cases_to_scripts → span per conversion
# ---------------------------------------------------------------------------
def _patch_convert_test_cases(agent_module):
    original = agent_module.convert_test_cases_to_scripts

    @functools.wraps(original)
    def wrapped(test_cases, framework_type, language, script_generation_type):
        with _langfuse.start_as_current_observation(
            name="convert_test_cases",
            as_type="span",
            input={
                "framework_type": framework_type,
                "language": language,
                "generation_type": script_generation_type,
            },
        ) as span:
            start = time.time()
            try:
                result = original(test_cases, framework_type, language, script_generation_type)
                latency_ms = (time.time() - start) * 1000

                is_bdd = result.get("is_bdd", False)
                span.update(
                    output={
                        "is_bdd": is_bdd,
                        "has_feature": bool(result.get("feature")),
                        "has_step_definition": bool(result.get("step_definition")),
                        "has_page_object": bool(result.get("page_object")),
                        "has_script": bool(result.get("script")),
                    },
                    metadata={"latency_ms": round(latency_ms, 2)},
                    status_message="success",
                    level="DEFAULT",
                )
                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata={"latency_ms": round(latency_ms, 2)},
                )
                raise

    agent_module.convert_test_cases_to_scripts = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: push_to_harness_devops → span per push (tool-usage tracking)
# ---------------------------------------------------------------------------
def _patch_push_to_harness(agent_module):
    original = agent_module.push_to_harness_devops

    @functools.wraps(original)
    def wrapped(code_blocks, folder_name):
        with _langfuse.start_as_current_observation(
            name="push_to_harness",
            as_type="span",
            input={
                "folder_name": folder_name,
                "file_count": len(code_blocks),
                "file_names": list(code_blocks.keys()),
            },
        ) as span:
            start = time.time()
            try:
                result = original(code_blocks, folder_name)
                latency_ms = (time.time() - start) * 1000

                success = bool(result)
                span.update(
                    output={"file_urls": result, "success": success},
                    metadata={
                        "latency_ms": round(latency_ms, 2),
                        "files_pushed": len(result),
                    },
                    level="DEFAULT" if success else "WARNING",
                    status_message="success" if success else "push_returned_empty",
                )
                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata={"latency_ms": round(latency_ms, 2)},
                )
                raise

    agent_module.push_to_harness_devops = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: process_single_test_case → span per test case + quality scores
# ---------------------------------------------------------------------------
def _patch_process_single_test_case(agent_module):
    original = agent_module.process_single_test_case

    @functools.wraps(original)
    async def wrapped(tc, framework_type, language, script_generation_type):
        tc_id = tc.get("Test Case ID", tc.get("id", "unknown"))
        tc_name = tc.get("Test Case Name", tc.get("name", "unknown"))

        with _langfuse.start_as_current_observation(
            name=f"process_test_case_{tc_id}",
            as_type="span",
            input={
                "test_case_id": tc_id,
                "test_case_name": tc_name,
                "framework_type": framework_type,
                "language": language,
                "generation_type": script_generation_type,
            },
        ) as span:
            start = time.time()
            try:
                result = await original(tc, framework_type, language, script_generation_type)
                latency_ms = (time.time() - start) * 1000

                code_blocks, file_urls, folder_name = result
                extraction_success = len(code_blocks) > 0
                push_success = len(file_urls) > 0

                span.update(
                    output={
                        "folder_name": folder_name,
                        "files_generated": list(code_blocks.keys()),
                        "files_pushed": len(file_urls),
                    },
                    metadata={
                        "latency_ms": round(latency_ms, 2),
                        "extraction_success": extraction_success,
                        "push_success": push_success,
                    },
                    status_message="success",
                    level="DEFAULT",
                )

                # Quality scores attached to the trace
                span.score_trace(name="code_extraction_success", value=1.0 if extraction_success else 0.0)
                span.score_trace(name="push_success", value=1.0 if push_success else 0.0)
                span.score_trace(name="files_generated", value=float(len(code_blocks)))

                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata={"latency_ms": round(latency_ms, 2)},
                )
                span.score_trace(name="code_extraction_success", value=0.0)
                span.score_trace(name="push_success", value=0.0)
                raise

    agent_module.process_single_test_case = wrapped


# ---------------------------------------------------------------------------
# ASGI middleware: one Langfuse trace per /convert request
# Uses start_as_current_observation to create the root span. All child
# observations created downstream auto-nest under this span via context.
# ---------------------------------------------------------------------------
class LangfuseASGIMiddleware:
    """Lightweight ASGI middleware — creates a Langfuse root span for /convert."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path != "/convert":
            await self.app(scope, receive, send)
            return

        status_code = 500
        request_id = uuid.uuid4().hex

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        with _langfuse.start_as_current_observation(
            name="testcase_to_script_conversion",
            as_type="span",
            input={"endpoint": path, "method": scope.get("method", "")},
            metadata={"request_id": request_id},
        ) as root_span:
            # Link trace to a Langfuse session via OTEL span attribute
            try:
                root_span._otel_span.set_attribute("session.id", request_id)
            except Exception:
                pass

            start = time.time()
            try:
                await self.app(scope, receive, send_wrapper)
                latency_ms = (time.time() - start) * 1000

                root_span.update(
                    output={"status_code": status_code},
                    metadata={
                        "total_latency_ms": round(latency_ms, 2),
                        "status_code": status_code,
                        "request_id": request_id,
                    },
                )
                success = 200 <= status_code < 300
                root_span.score_trace(name="request_success", value=1.0 if success else 0.0)

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                root_span.update(
                    output={"error": str(exc)},
                    metadata={"total_latency_ms": round(latency_ms, 2)},
                    level="ERROR",
                    status_message=str(exc),
                )
                root_span.score_trace(name="request_success", value=0.0)
                raise

        # flush() MUST be OUTSIDE the with-block so the OTEL span is fully
        # ended before being exported (per Langfuse v4 documentation).
        _langfuse.flush()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_span_exporter():
    """
    Build a custom OTLPSpanExporter with the combined CA certificate bundle.
    This allows OTEL trace export over HTTPS to the Langfuse ALB with a
    self-signed cert, while also trusting corporate proxy CAs for Google APIs.
    Returns None if no combined CA bundle exists (falls back to defaults).
    """
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    cert_file = str(_combined_ca) if _combined_ca.exists() else None

    if not cert_file:
        print("  ⚠ No combined_ca.pem found — using default SSL for OTEL export")
        return None

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        import base64

        auth_value = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{host}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth_value}"},
            certificate_file=cert_file,
            timeout=int(os.getenv("LANGFUSE_TIMEOUT_SEC", "20")),
        )
        print(f"  ✅ Custom OTEL exporter built with CA bundle: {cert_file}")
        return exporter
    except ImportError:
        print("  ⚠ opentelemetry-exporter-otlp-proto-http not installed, using defaults")
        return None
    except Exception as e:
        print(f"  ⚠ Could not build custom OTEL exporter: {e}")
        return None


def instrument():
    """
    Monkey-patch agent functions with Langfuse instrumentation.

    Must be called AFTER importing testcase_to_scripts_agent
    but BEFORE importing api_server (so api_server picks up patched refs).

    Creates the Langfuse client eagerly (singleton race fix) with an optional
    custom OTEL span exporter for self-signed ALB certificates.
    """
    global _langfuse, _instrumented

    if _instrumented:
        return

    span_exporter = _build_span_exporter()

    init_kwargs = {
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY"),
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY"),
        "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }
    if span_exporter is not None:
        init_kwargs["span_exporter"] = span_exporter

    _langfuse = Langfuse(**init_kwargs)

    import testcase_to_scripts_agent as agent_module

    _patch_executor(agent_module)
    _patch_generate_content(agent_module)
    _patch_convert_test_cases(agent_module)
    _patch_push_to_harness(agent_module)
    _patch_process_single_test_case(agent_module)

    _instrumented = True
    print("✅ Langfuse instrumentation applied (functions patched)")


def add_middleware(app):
    """Add the ASGI tracing middleware to a FastAPI/Starlette app."""
    global _middleware_added

    if _middleware_added:
        return

    app.add_middleware(LangfuseASGIMiddleware)
    _middleware_added = True
    print("✅ Langfuse ASGI middleware added")


def shutdown():
    """Flush pending events and shut down the Langfuse client."""
    global _langfuse
    if _langfuse:
        _langfuse.flush()
        _langfuse.shutdown()
        print("✅ Langfuse shutdown complete")
