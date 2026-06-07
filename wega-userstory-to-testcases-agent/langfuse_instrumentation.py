"""
Langfuse + OpenTelemetry observability wrapper for the
UserStory-to-TestCases Agent.

Written for Langfuse Python SDK v4 (OTEL-based). Instruments the agent
via monkey-patching - no existing code is modified. Run via main.py
instead of api_server.py to enable tracing.

Workflow envelope support
-------------------------
This module is envelope-aware. When invoked by an upstream orchestrator
(SDLC / Planning / BRD agent) the inbound request carries an envelope via
the standard ``X-Workflow-*`` and ``X-Parent-*`` headers. The ASGI
middleware:

  1. Reads those headers, builds a canonical workflow envelope, and
     installs it on a contextvar so every downstream monkey-patch sees
     the same context.
  2. If the request supplies ``X-Parent-Trace-Id`` (and optionally
     ``X-Parent-Observation-Id``), the root Langfuse span is nested
     under that existing trace via ``trace_context``, so this agent's
     observation appears inside the parent's Langfuse trace rather than
     as an orphan trace.
  3. Stamps envelope fields onto the root span (and onto every span via
     a global OTEL SpanProcessor) so dashboards can filter / pivot on
     ``workflow_run_id``, ``parent_workflow_run_id``, ``tenant`` etc.

Dual observability:
  - Langfuse: LLM-specific tracing, prompts, costs, token usage, latency.
  - OTEL Collector -> Prometheus -> Grafana: real-time metrics, alerts.

Tracked metrics (Langfuse):
  1. Test scenario generation (Vertex AI/Gemini calls per user story)
  2. Test case generation (LLM prompting with test scenario context)
  3. Token usage (input / output / total per LLM call)
  4. Cost analysis (Langfuse auto-calculates from token counts + model)
  5. Response latency (per LLM call, per bulk job, end-to-end)
  6. Jira Test issue creation
  7. Xray GraphQL operations
  8. qTest case/step creation
  9. Error and retry patterns

OTEL metrics (Grafana):
  llm_requests_total, llm_tokens_total, llm_request_duration_seconds,
  testcase_generation_total, jira_push_total, xray_operations_total,
  qtest_push_total, http_request_duration_seconds.

Required env vars (Langfuse):
  LANGFUSE_SECRET_KEY
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_HOST                 (defaults to https://cloud.langfuse.com)

Optional cert env vars (resolved at runtime by build_cert_bundle.py and
exported on import via main.py):
  OTEL_CA_CERT_PATH             explicit path to a PEM file (preferred)
  LANGFUSE_CA_CERT              raw or base64 PEM, merged into the bundle

Optional env vars for OTEL Collector:
  OTEL_EXPORTER_OTLP_ENDPOINT   (e.g. http://otel-collector:4317)
  OTEL_EXPORTER_OTLP_PROTOCOL   (grpc or http/protobuf, default: grpc)
  OTEL_SERVICE_NAME             (default: wega-userstory-to-testcases-agent)
  OTEL_RESOURCE_ATTRIBUTES      (e.g. service.namespace=wega,deployment.environment=prod)
"""

from __future__ import annotations

import base64
import functools
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from langfuse import Langfuse

# Envelope helpers - shared with any future explicit-context callers.
from utils.envelope import (
    ENVELOPE_KEYS,
    build_envelope,
    envelope_to_metadata,
    envelope_to_tags,
    get_current_envelope,
    reset_current_envelope,
    set_current_envelope,
    stamp_envelope_on_span,
)

logger = logging.getLogger(__name__)

_langfuse: Optional[Langfuse] = None
_instrumented: bool = False
_middleware_added: bool = False
_otel_initialized: bool = False

# Path to the combined CA bundle (built by build_cert_bundle.py)
_combined_ca = Path(__file__).resolve().parent / "combined_ca.pem"

# ---------------------------------------------------------------------------
# OTEL metrics handles (initialized by _init_otel_metrics)
# ---------------------------------------------------------------------------
_otel_tracer = None
_llm_request_counter = None
_llm_token_counter = None
_llm_latency_histogram = None
_testcase_generation_counter = None
_jira_push_counter = None
_xray_operations_counter = None
_qtest_push_counter = None
_http_request_duration_histogram = None
_otel_meter_provider = None
_otel_tracer_provider = None


# ---------------------------------------------------------------------------
# Resolve CA certificate bundle for OTEL export.
# ---------------------------------------------------------------------------
_ca_cert_path: Optional[str] = None


def _resolve_ca_cert() -> Optional[str]:
    """Return a path to a combined CA cert PEM file, or None if unavailable."""
    global _ca_cert_path
    if _ca_cert_path:
        return _ca_cert_path

    explicit_path = os.getenv("OTEL_CA_CERT_PATH")
    if explicit_path and Path(explicit_path).exists():
        _ca_cert_path = explicit_path
        return _ca_cert_path

    if _combined_ca.exists():
        _ca_cert_path = str(_combined_ca)
        return _ca_cert_path

    cert_b64 = os.getenv("LANGFUSE_CA_CERT")
    if cert_b64:
        try:
            import certifi
            import tempfile

            if "BEGIN CERTIFICATE" in cert_b64:
                custom_cert = cert_b64.encode("utf-8")
            else:
                custom_cert = base64.b64decode(cert_b64)
            system_ca = Path(certifi.where()).read_bytes()

            tmp = tempfile.NamedTemporaryFile(
                prefix="langfuse_ca_", suffix=".pem", delete=False
            )
            tmp.write(system_ca)
            tmp.write(b"\n")
            tmp.write(custom_cert)
            tmp.close()
            _ca_cert_path = tmp.name
            logger.info(
                "Combined CA bundle built (system CAs + custom cert) -> %s",
                _ca_cert_path,
            )
            return _ca_cert_path
        except Exception as exc:
            logger.warning("Failed to decode LANGFUSE_CA_CERT: %s", exc)

    return None


# ---------------------------------------------------------------------------
# OTEL metrics initialization
# ---------------------------------------------------------------------------
def _init_otel_metrics():
    """Initialize OpenTelemetry TracerProvider + MeterProvider for Grafana."""
    global _otel_initialized, _otel_tracer
    global _testcase_generation_counter, _jira_push_counter, _xray_operations_counter, _qtest_push_counter
    global _llm_request_counter, _llm_token_counter, _llm_latency_histogram
    global _http_request_duration_histogram
    global _otel_meter_provider, _otel_tracer_provider

    if _otel_initialized:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set - OTEL metrics disabled")
        _otel_initialized = True
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")

        service_name = os.getenv("OTEL_SERVICE_NAME", "wega-userstory-to-testcases-agent")
        resource_attrs = {"service.name": service_name}
        extra_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        if extra_attrs:
            for pair in extra_attrs.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    resource_attrs[k.strip()] = v.strip()
        resource = Resource.create(resource_attrs)

        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcSpanExporter
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GrpcMetricExporter
            span_exporter = GrpcSpanExporter(endpoint=endpoint, insecure=True)
            metric_exporter = GrpcMetricExporter(endpoint=endpoint, insecure=True)
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpSpanExporter
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HttpMetricExporter
            span_exporter = HttpSpanExporter(endpoint=f"{endpoint}/v1/traces")
            metric_exporter = HttpMetricExporter(endpoint=f"{endpoint}/v1/metrics")

        _otel_tracer_provider = TracerProvider(resource=resource)
        _otel_tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(_otel_tracer_provider)
        _otel_tracer = trace.get_tracer("wega-userstory-to-testcases-agent")

        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
        _otel_meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(_otel_meter_provider)
        meter = metrics.get_meter("wega-userstory-to-testcases-agent")

        _llm_request_counter = meter.create_counter(
            name="llm_requests_total",
            description="Total LLM requests",
            unit="1",
        )
        _llm_token_counter = meter.create_counter(
            name="llm_tokens_total",
            description="Total tokens used by LLM",
            unit="1",
        )
        _llm_latency_histogram = meter.create_histogram(
            name="llm_request_duration_seconds",
            description="LLM request latency in seconds",
            unit="s",
        )
        _testcase_generation_counter = meter.create_counter(
            name="testcase_generation_total",
            description="Total test case generation requests",
            unit="1",
        )
        _jira_push_counter = meter.create_counter(
            name="jira_push_total",
            description="Total Jira Test issue creation operations",
            unit="1",
        )
        _xray_operations_counter = meter.create_counter(
            name="xray_operations_total",
            description="Total Xray GraphQL operations",
            unit="1",
        )
        _qtest_push_counter = meter.create_counter(
            name="qtest_push_total",
            description="Total qTest case/step creation operations",
            unit="1",
        )
        _http_request_duration_histogram = meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s",
        )

        _otel_initialized = True
        logger.info(
            "OTEL metrics initialized (endpoint=%s, protocol=%s, service=%s)",
            endpoint, protocol, service_name,
        )

    except ImportError as exc:
        logger.warning("OTEL SDK packages not installed, metrics disabled: %s", exc)
        _otel_initialized = True
    except Exception as exc:
        logger.warning("Failed to initialize OTEL metrics: %s", exc)
        _otel_initialized = True


# ---------------------------------------------------------------------------
# Envelope helpers (instrumentation-side)
# ---------------------------------------------------------------------------
def _current_envelope_or_build(
    *,
    trace_name: str,
    session_id: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Return the ambient envelope, or build a synthetic one as a fallback."""
    env = get_current_envelope()
    if env:
        env = dict(env)
    else:
        env = build_envelope(trace_name=trace_name, session_id=session_id)
    if extra:
        env = {**env, **{k: v for k, v in extra.items() if v is not None}}
    return env


def _apply_envelope_to_trace(span, envelope: Mapping[str, Any]) -> None:
    """Tag the *trace* (not just a span) with envelope fields."""
    try:
        from langfuse._client.attributes import LangfuseOtelSpanAttributes as A

        otel_span = getattr(span, "_otel_span", None)
        if otel_span is None:
            return
        tags = envelope_to_tags(envelope)
        if tags:
            otel_span.set_attribute(A.TRACE_TAGS, tags)
        otel_span.set_attribute(
            A.TRACE_METADATA,
            json.dumps(envelope_to_metadata(envelope), default=str),
        )
        if envelope.get("session_id"):
            otel_span.set_attribute(A.TRACE_SESSION_ID, str(envelope["session_id"]))
        if envelope.get("user_id"):
            otel_span.set_attribute(A.TRACE_USER_ID, str(envelope["user_id"]))
        if envelope.get("trace_name"):
            otel_span.set_attribute(A.TRACE_NAME, str(envelope["trace_name"]))
    except Exception:
        # Observability must never crash the request flow.
        pass


def _build_span_metadata(
    envelope: Mapping[str, Any],
    extra: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Merge envelope keys + extra span-local metadata."""
    return envelope_to_metadata(envelope, extra=extra or {})


# ---------------------------------------------------------------------------
# Global SpanProcessor: stamp envelope OTEL attributes on EVERY span.
# ---------------------------------------------------------------------------
def _make_envelope_span_processor():
    """Construct an OTEL SpanProcessor that stamps envelope on each span."""
    try:
        from opentelemetry.sdk.trace import SpanProcessor

        class _EnvelopeStamper(SpanProcessor):
            def on_start(self, span, parent_context=None):
                try:
                    envelope = get_current_envelope()
                    if not envelope:
                        return
                    for key in (
                        "workflow_run_id",
                        "parent_workflow_run_id",
                        "phase",
                        "tenant",
                        "env",
                        "artifact_id",
                        "agent_name",
                        "agent_version",
                        "prompt_version",
                        "input_fingerprint",
                        "session_id",
                        "request_id",
                        "trace_name",
                        "user_id",
                    ):
                        value = envelope.get(key)
                        if value is None or value == "":
                            continue
                        span.set_attribute(f"workflow.{key}", str(value))
                    policy_flags = envelope.get("policy_flags")
                    if policy_flags:
                        span.set_attribute(
                            "workflow.policy_flags",
                            "|".join(str(v) for v in policy_flags),
                        )

                    try:
                        from langfuse._client.attributes import (
                            LangfuseOtelSpanAttributes as A,
                        )

                        tags = envelope_to_tags(envelope)
                        if tags:
                            span.set_attribute(A.TRACE_TAGS, tags)
                        if envelope.get("session_id"):
                            span.set_attribute(
                                A.TRACE_SESSION_ID, str(envelope["session_id"])
                            )
                        if envelope.get("user_id"):
                            span.set_attribute(
                                A.TRACE_USER_ID, str(envelope["user_id"])
                            )
                        span.set_attribute(
                            A.OBSERVATION_METADATA,
                            json.dumps(
                                envelope_to_metadata(envelope), default=str
                            ),
                        )
                    except Exception:
                        pass
                except Exception:
                    pass

            def on_end(self, span):
                return None

            def shutdown(self):
                return None

            def force_flush(self, timeout_millis: int = 30000):
                return True

        return _EnvelopeStamper()
    except Exception as exc:
        logger.debug("envelope SpanProcessor unavailable: %s", exc)
        return None


def _register_envelope_processor() -> None:
    """Register the global envelope SpanProcessor with the active TracerProvider."""
    try:
        from opentelemetry import trace as otel_trace

        provider = otel_trace.get_tracer_provider()
        add_span_processor = getattr(provider, "add_span_processor", None)
        if not callable(add_span_processor):
            logger.debug(
                "TracerProvider %r does not support add_span_processor, skipping envelope stamping",
                type(provider).__name__,
            )
            return
        processor = _make_envelope_span_processor()
        if processor is None:
            return
        add_span_processor(processor)
        logger.info("Envelope SpanProcessor registered on TracerProvider")
    except Exception as exc:
        logger.debug("Failed to register envelope SpanProcessor: %s", exc)


# ---------------------------------------------------------------------------
# Monkey-patch: model.generate_content -> Langfuse generation per LLM call
# ---------------------------------------------------------------------------
def _patch_generate_content(agent_module):
    # When LLM_PROVIDER=azure (or any non-google), Vertex SDK is not
    # initialised and agent_module.model is None. Skip patching.
    if getattr(agent_module, "model", None) is None:
        return
    original = agent_module.model.generate_content

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        prompt_text = str(args[0])[:5000] if args else ""
        model_name = agent_module.MODEL_NAME
        gen_config = kwargs.get("generation_config") or agent_module.GENERATION_CONFIG

        envelope = _current_envelope_or_build(
            trace_name="userstory_testcases_llm",
            extra={"llm_provider": "google"},
        )

        gen = _langfuse.start_observation(
            name="generate-test-data-llm",
            as_type="generation",
            model=model_name,
            input=prompt_text,
            model_parameters=gen_config if isinstance(gen_config, dict) else {},
            metadata=_build_span_metadata(envelope, {"llm_provider": "google"}),
        )
        stamp_envelope_on_span(gen, envelope)

        start = time.time()
        try:
            result = original(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000
            duration_sec = (time.time() - start)

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
                metadata=_build_span_metadata(
                    envelope, {"latency_ms": round(latency_ms, 2)}
                ),
                status_message="success",
                level="DEFAULT",
            )
            gen.end()

            if _llm_request_counter:
                _llm_request_counter.add(1, {"model": model_name, "status": "success"})
            if _llm_latency_histogram:
                _llm_latency_histogram.record(duration_sec, {"model": model_name})
            if _llm_token_counter and usage:
                _llm_token_counter.add(usage.get("input", 0), {"model": model_name, "type": "input"})
                _llm_token_counter.add(usage.get("output", 0), {"model": model_name, "type": "output"})

            return result

        except Exception as exc:
            latency_ms = (time.time() - start) * 1000
            duration_sec = (time.time() - start)
            gen.update(
                output=str(exc),
                status_message=f"error: {type(exc).__name__}: {exc}",
                level="ERROR",
                metadata=_build_span_metadata(
                    envelope, {"latency_ms": round(latency_ms, 2)}
                ),
            )
            gen.end()

            if _llm_request_counter:
                _llm_request_counter.add(1, {"model": model_name, "status": "error"})
            if _llm_latency_histogram:
                _llm_latency_histogram.record(duration_sec, {"model": model_name})

            raise

    agent_module.model.generate_content = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: _llm_generate (used by Azure / multi-provider path)
# ---------------------------------------------------------------------------
def _patch_llm_generate(agent_module):
    if not hasattr(agent_module, "_llm_generate"):
        return
    original = agent_module._llm_generate

    @functools.wraps(original)
    def wrapped(prompt: str, temperature_override=None):
        provider = getattr(agent_module, "LLM_PROVIDER", None) or os.getenv(
            "LLM_PROVIDER", "google"
        )
        model_name = (
            getattr(agent_module, "AZURE_DEPLOYMENT", None)
            if provider == "azure"
            else getattr(agent_module, "MODEL_NAME", "unknown")
        )

        envelope = _current_envelope_or_build(
            trace_name="userstory_testcases_llm",
            extra={"llm_provider": provider},
        )

        gen = _langfuse.start_observation(
            name="generate-test-data-llm",
            as_type="generation",
            model=model_name,
            input=str(prompt)[:5000] if prompt else "",
            model_parameters={
                "temperature": temperature_override,
            },
            metadata=_build_span_metadata(envelope, {"llm_provider": provider}),
        )
        stamp_envelope_on_span(gen, envelope)

        start = time.time()
        try:
            result = original(prompt, temperature_override)
            latency_ms = (time.time() - start) * 1000
            duration_sec = (time.time() - start)
            gen.update(
                output=str(result)[:5000] if result else "",
                metadata=_build_span_metadata(
                    envelope, {"latency_ms": round(latency_ms, 2)}
                ),
                status_message="success",
                level="DEFAULT",
            )
            gen.end()

            if _llm_request_counter:
                _llm_request_counter.add(1, {"model": model_name, "status": "success"})
            if _llm_latency_histogram:
                _llm_latency_histogram.record(duration_sec, {"model": model_name})

            return result

        except Exception as exc:
            latency_ms = (time.time() - start) * 1000
            gen.update(
                output=str(exc),
                status_message=f"error: {type(exc).__name__}: {exc}",
                level="ERROR",
                metadata=_build_span_metadata(
                    envelope, {"latency_ms": round(latency_ms, 2)}
                ),
            )
            gen.end()

            if _llm_request_counter:
                _llm_request_counter.add(1, {"model": model_name, "status": "error"})

            raise

    agent_module._llm_generate = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: process_single_story_jira -> span for Jira test creation
# ---------------------------------------------------------------------------
def _patch_process_single_story_jira(agent_module):
    if not hasattr(agent_module, "process_single_story_jira"):
        return
    original = agent_module.process_single_story_jira

    @functools.wraps(original)
    def wrapped(jira_story_id: str, userstory: str, scenario_type: str):
        envelope = _current_envelope_or_build(
            trace_name="process_single_story_jira",
            extra={"jira_story_id": jira_story_id, "scenario_type": scenario_type},
        )
        with _langfuse.start_as_current_observation(
            name="process_single_story_jira",
            as_type="span",
            input={
                "jira_story_id": jira_story_id,
                "scenario_type": scenario_type,
                "story_length": len(userstory) if userstory else 0,
            },
            metadata=_build_span_metadata(envelope, {"target": "jira"}),
        ) as span:
            stamp_envelope_on_span(span, envelope)
            start = time.time()
            try:
                result = original(jira_story_id, userstory, scenario_type)
                latency_ms = (time.time() - start) * 1000

                test_count = len(result.get("test_cases", [])) if result else 0
                span.update(
                    output={
                        "success": True,
                        "test_count": test_count,
                        "jira_issues_created": result.get("jira_issue_keys", []) if result else [],
                    },
                    metadata=_build_span_metadata(
                        envelope, {"latency_ms": round(latency_ms, 2), "target": "jira"}
                    ),
                    status_message="success",
                    level="DEFAULT",
                )

                if _jira_push_counter:
                    _jira_push_counter.add(1, {"status": "success", "scenario": scenario_type})
                if _testcase_generation_counter:
                    _testcase_generation_counter.add(
                        test_count, {"operation": "jira_creation", "status": "success"}
                    )

                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata=_build_span_metadata(
                        envelope, {"latency_ms": round(latency_ms, 2)}
                    ),
                )
                if _jira_push_counter:
                    _jira_push_counter.add(1, {"status": "failed", "scenario": scenario_type})
                raise

    agent_module.process_single_story_jira = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: process_single_story_qtest
# ---------------------------------------------------------------------------
def _patch_process_single_story_qtest(agent_module):
    if not hasattr(agent_module, "process_single_story_qtest"):
        return
    original = agent_module.process_single_story_qtest

    @functools.wraps(original)
    def wrapped(userstory: str, scenario_type: str):
        envelope = _current_envelope_or_build(
            trace_name="process_single_story_qtest",
            extra={"scenario_type": scenario_type},
        )
        with _langfuse.start_as_current_observation(
            name="process_single_story_qtest",
            as_type="span",
            input={
                "scenario_type": scenario_type,
                "story_length": len(userstory) if userstory else 0,
            },
            metadata=_build_span_metadata(envelope, {"target": "qtest"}),
        ) as span:
            stamp_envelope_on_span(span, envelope)
            start = time.time()
            try:
                result = original(userstory, scenario_type)
                latency_ms = (time.time() - start) * 1000

                test_count = len(result.get("test_cases", [])) if result else 0
                span.update(
                    output={
                        "success": True,
                        "test_count": test_count,
                        "qtest_case_ids": result.get("qtest_case_ids", []) if result else [],
                    },
                    metadata=_build_span_metadata(
                        envelope, {"latency_ms": round(latency_ms, 2), "target": "qtest"}
                    ),
                    status_message="success",
                    level="DEFAULT",
                )

                if _qtest_push_counter:
                    _qtest_push_counter.add(1, {"status": "success", "scenario": scenario_type})
                if _testcase_generation_counter:
                    _testcase_generation_counter.add(
                        test_count, {"operation": "qtest_creation", "status": "success"}
                    )

                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata=_build_span_metadata(
                        envelope, {"latency_ms": round(latency_ms, 2)}
                    ),
                )
                if _qtest_push_counter:
                    _qtest_push_counter.add(1, {"status": "failed", "scenario": scenario_type})
                raise

    agent_module.process_single_story_qtest = wrapped


# ---------------------------------------------------------------------------
# Monkey-patch: process_brownfield_story_jira
# ---------------------------------------------------------------------------
def _patch_process_brownfield_story_jira(agent_module):
    if not hasattr(agent_module, "process_brownfield_story_jira"):
        return
    original = agent_module.process_brownfield_story_jira

    @functools.wraps(original)
    def wrapped(jira_story_id: str, userstory: str, scenario_type: str):
        envelope = _current_envelope_or_build(
            trace_name="process_brownfield_story_jira",
            extra={"jira_story_id": jira_story_id, "scenario_type": scenario_type},
        )
        with _langfuse.start_as_current_observation(
            name="process_brownfield_story_jira",
            as_type="span",
            input={
                "jira_story_id": jira_story_id,
                "scenario_type": scenario_type,
                "story_length": len(userstory) if userstory else 0,
            },
            metadata=_build_span_metadata(envelope, {"target": "jira_brownfield"}),
        ) as span:
            stamp_envelope_on_span(span, envelope)
            start = time.time()
            try:
                result = original(jira_story_id, userstory, scenario_type)
                latency_ms = (time.time() - start) * 1000

                span.update(
                    output={"success": True},
                    metadata=_build_span_metadata(
                        envelope,
                        {"latency_ms": round(latency_ms, 2), "target": "jira_brownfield"},
                    ),
                    status_message="success",
                    level="DEFAULT",
                )

                if _jira_push_counter:
                    _jira_push_counter.add(1, {"status": "success", "scenario": scenario_type, "mode": "brownfield"})

                return result

            except Exception as exc:
                latency_ms = (time.time() - start) * 1000
                span.update(
                    output=str(exc),
                    level="ERROR",
                    status_message=f"error: {type(exc).__name__}: {exc}",
                    metadata=_build_span_metadata(
                        envelope, {"latency_ms": round(latency_ms, 2)}
                    ),
                )
                if _jira_push_counter:
                    _jira_push_counter.add(1, {"status": "failed", "scenario": scenario_type, "mode": "brownfield"})
                raise

    agent_module.process_brownfield_story_jira = wrapped


# ---------------------------------------------------------------------------
# ASGI middleware: one Langfuse trace per tracked endpoint, nested under
# the upstream parent trace if envelope headers are set.
# ---------------------------------------------------------------------------
class LangfuseASGIMiddleware:
    """Lightweight ASGI middleware - creates a Langfuse root span per request.

    Envelope behavior
    -----------------
    On every request to a tracked path the middleware:

      * Builds a workflow envelope from inbound ``X-Workflow-*`` /
        ``X-Parent-*`` headers (or fresh defaults if none are present).
      * Sets that envelope on the ambient contextvar so every downstream
        monkey-patched span sees it.
      * If ``X-Parent-Trace-Id`` is present, opens the root observation
        with ``trace_context={"trace_id": ..., "parent_span_id": ...}``
        so this agent's span appears INSIDE the parent's existing
        Langfuse trace instead of starting a new orphan trace.
      * Stamps envelope tags / metadata on both the trace and the
        observation, then resets the contextvar in a ``finally`` block.
    """

    _TRACKED_PATHS = {
        "/v1/generate-test-cases/bulk",
        "/v1/generate-test-cases/bulk/brownfield",
        "/v1/generate-test-cases/bulk/qtest",
        "/v1/generate-test-cases/bulk/ado",
    }

    def __init__(self, app):
        self.app = app

    @staticmethod
    def _scope_headers(scope: Mapping[str, Any]) -> dict[str, str]:
        """Extract HTTP headers from an ASGI scope, lowercased."""
        out: dict[str, str] = {}
        raw = scope.get("headers") or []
        for k, v in raw:
            try:
                key = k.decode("latin-1").lower() if isinstance(k, (bytes, bytearray)) else str(k).lower()
                val = v.decode("latin-1") if isinstance(v, (bytes, bytearray)) else str(v)
                out[key] = val
            except Exception:
                continue
        return out

    @staticmethod
    def _split_csv(value: Optional[str]) -> list[str]:
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    def _envelope_from_request(
        self,
        scope: Mapping[str, Any],
        trace_name: str,
        request_id: str,
        session_id: Optional[str],
    ) -> dict:
        """Build a workflow envelope from inbound headers.

        Honors the following optional inbound headers:

            X-Workflow-Run-Id, X-Parent-Workflow-Run-Id, X-Workflow-Phase,
            X-Tenant, X-Agent-Name, X-Agent-Version, X-Prompt-Version,
            X-Policy-Flags (csv), X-Artifact-Id, X-User-Id,
            X-Parent-Span-Id, X-Parent-Trace-Id, X-Parent-Observation-Id
        """
        headers = self._scope_headers(scope)
        overrides: dict[str, Any] = {}
        if headers.get("x-workflow-run-id"):
            overrides["workflow_run_id"] = headers["x-workflow-run-id"]
        if headers.get("x-parent-workflow-run-id"):
            overrides["parent_workflow_run_id"] = headers["x-parent-workflow-run-id"]
        if headers.get("x-workflow-phase"):
            overrides["phase"] = headers["x-workflow-phase"]
        if headers.get("x-tenant"):
            overrides["tenant"] = headers["x-tenant"]
        if headers.get("x-agent-name"):
            overrides["agent_name"] = headers["x-agent-name"]
        if headers.get("x-agent-version"):
            overrides["agent_version"] = headers["x-agent-version"]
        if headers.get("x-prompt-version"):
            overrides["prompt_version"] = headers["x-prompt-version"]
        if headers.get("x-policy-flags"):
            overrides["policy_flags"] = self._split_csv(headers["x-policy-flags"])
        if headers.get("x-artifact-id"):
            overrides["artifact_id"] = headers["x-artifact-id"]
        if headers.get("x-user-id"):
            overrides["user_id"] = headers["x-user-id"]
        if headers.get("x-parent-span-id"):
            overrides["parent_span_id"] = headers["x-parent-span-id"]
        if headers.get("x-parent-trace-id"):
            overrides["parent_trace_id"] = headers["x-parent-trace-id"]
        if headers.get("x-parent-observation-id"):
            overrides["parent_observation_id"] = headers["x-parent-observation-id"]
            overrides.setdefault(
                "parent_span_id", headers["x-parent-observation-id"]
            )

        return build_envelope(
            trace_name=trace_name,
            session_id=session_id,
            request_id=request_id,
            user_id=overrides.get("user_id"),
            phase=overrides.get("phase", "runtime"),
            parent_span_id=overrides.get("parent_span_id"),
            input_payload={
                "path": scope.get("path"),
                "method": scope.get("method"),
            },
            overrides=overrides,
        )

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path not in self._TRACKED_PATHS:
            await self.app(scope, receive, send)
            return

        status_code = 500
        request_id = uuid.uuid4().hex
        method = scope.get("method", "")
        trace_name = "userstory_testcases_request"

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        envelope = self._envelope_from_request(
            scope, trace_name, request_id, session_id=None
        )
        env_token = set_current_envelope(envelope)

        root_span_kwargs: dict[str, Any] = dict(
            name=trace_name,
            as_type="span",
            input={"endpoint": path, "method": method},
            metadata=_build_span_metadata(
                envelope,
                {
                    "request_id": request_id,
                    "http.method": method,
                    "http.path": path,
                },
            ),
        )
        if envelope.get("parent_trace_id") or envelope.get("parent_span_id"):
            trace_context: dict[str, str] = {}
            if envelope.get("parent_trace_id"):
                trace_context["trace_id"] = envelope["parent_trace_id"]
            if envelope.get("parent_span_id"):
                trace_context["parent_span_id"] = envelope["parent_span_id"]
            if trace_context:
                root_span_kwargs["trace_context"] = trace_context

        try:
            with _langfuse.start_as_current_observation(
                **root_span_kwargs
            ) as root_span:
                try:
                    otel_span = getattr(root_span, "_otel_span", None)
                    if otel_span is not None:
                        otel_span.set_attribute(
                            "session.id", envelope.get("session_id") or request_id
                        )
                except Exception:
                    pass
                stamp_envelope_on_span(root_span, envelope)
                _apply_envelope_to_trace(root_span, envelope)

                start = time.time()
                try:
                    await self.app(scope, receive, send_wrapper)
                    latency_ms = (time.time() - start) * 1000
                    duration_sec = (time.time() - start)
                    success = 200 <= status_code < 300

                    root_span.update(
                        output={"status_code": status_code},
                        metadata=_build_span_metadata(
                            envelope,
                            {
                                "total_latency_ms": round(latency_ms, 2),
                                "status_code": status_code,
                                "request_id": request_id,
                            },
                        ),
                        status_message="success" if success else "error",
                        level="DEFAULT" if success else "ERROR",
                    )
                    root_span.score_trace(
                        name="request_success",
                        value=1.0 if success else 0.0,
                    )

                    if _http_request_duration_histogram:
                        _http_request_duration_histogram.record(
                            duration_sec,
                            {"endpoint": path, "method": method, "status_code": str(status_code)},
                        )

                except Exception as exc:
                    latency_ms = (time.time() - start) * 1000
                    duration_sec = (time.time() - start)
                    root_span.update(
                        output={"error": str(exc)},
                        metadata=_build_span_metadata(
                            envelope,
                            {"total_latency_ms": round(latency_ms, 2)},
                        ),
                        level="ERROR",
                        status_message=str(exc),
                    )
                    root_span.score_trace(name="request_success", value=0.0)

                    if _http_request_duration_histogram:
                        _http_request_duration_histogram.record(
                            duration_sec,
                            {"endpoint": path, "method": method, "status_code": "500"},
                        )

                    raise
        finally:
            try:
                reset_current_envelope(env_token)
            except Exception:
                pass
            # flush() MUST be OUTSIDE the with-block so the OTEL span is
            # fully ended before being exported. Run in a background
            # thread so it never blocks the HTTP response.
            if _langfuse is not None:
                threading.Thread(target=_langfuse.flush, daemon=True).start()


# ---------------------------------------------------------------------------
# Exporter builders
# ---------------------------------------------------------------------------
def _build_langfuse_exporter():
    """Build an OTLPSpanExporter targeting the Langfuse OTEL endpoint."""
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    cert_file = _resolve_ca_cert()
    if not cert_file:
        logger.warning("No combined CA bundle found - using default SSL for Langfuse OTEL export")

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        auth_value = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        kwargs: dict[str, Any] = {
            "endpoint": f"{host}/api/public/otel/v1/traces",
            "headers": {"Authorization": f"Basic {auth_value}"},
            "timeout": int(os.getenv("LANGFUSE_TIMEOUT_SEC", "20")),
        }
        if cert_file:
            kwargs["certificate_file"] = cert_file
        exporter = OTLPSpanExporter(**kwargs)
        logger.info("Langfuse OTEL exporter built (cert=%s)", cert_file or "system-default")
        return exporter
    except ImportError:
        logger.warning("opentelemetry-exporter-otlp-proto-http not installed, skipping Langfuse exporter")
        return None
    except Exception as exc:
        logger.warning("Could not build Langfuse OTEL exporter: %s", exc)
        return None


def _build_otel_collector_exporter():
    """Build an OTLPSpanExporter targeting a standalone OTEL collector."""
    endpoint = os.getenv("OTEL_COLLECTOR_ENDPOINT", "")
    if not endpoint:
        return None

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        headers: dict[str, str] = {}
        auth_token = os.getenv("OTEL_COLLECTOR_AUTH_TOKEN", "")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        custom_headers = os.getenv("OTEL_COLLECTOR_HEADERS", "")
        if custom_headers:
            for pair in custom_headers.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    headers[k.strip()] = v.strip()

        cert_file = _resolve_ca_cert()

        kwargs: dict[str, Any] = {
            "endpoint": endpoint,
            "timeout": int(os.getenv("OTEL_COLLECTOR_TIMEOUT_SEC", "10")),
        }
        if headers:
            kwargs["headers"] = headers
        if cert_file:
            kwargs["certificate_file"] = cert_file

        exporter = OTLPSpanExporter(**kwargs)
        logger.info("Standalone OTEL collector exporter built: %s", endpoint)
        return exporter
    except ImportError:
        logger.warning("opentelemetry-exporter-otlp-proto-http not installed, skipping OTEL collector")
        return None
    except Exception as exc:
        logger.warning("Could not build OTEL collector exporter: %s", exc)
        return None


class _MultiSpanExporter:
    """Fans out span exports to multiple OTEL exporters."""

    def __init__(self, exporters):
        self._exporters = [e for e in exporters if e is not None]

    def export(self, spans):
        for exporter in self._exporters:
            try:
                exporter.export(spans)
            except Exception as exc:
                logger.warning("Exporter %s failed: %s", type(exporter).__name__, exc)

    def shutdown(self):
        for exporter in self._exporters:
            try:
                exporter.shutdown()
            except Exception:
                pass

    def force_flush(self, timeout_millis=None):
        for exporter in self._exporters:
            try:
                if hasattr(exporter, "force_flush"):
                    exporter.force_flush(timeout_millis)
            except Exception:
                pass


def _build_span_exporter():
    """Return Langfuse exporter, OTEL collector exporter, or both."""
    langfuse_exporter = _build_langfuse_exporter()
    otel_exporter = _build_otel_collector_exporter()
    exporters = [e for e in [langfuse_exporter, otel_exporter] if e is not None]
    if len(exporters) == 0:
        return None
    if len(exporters) == 1:
        return exporters[0]
    logger.info("Multi-exporter configured (Langfuse + OTEL Collector)")
    return _MultiSpanExporter(exporters)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Workflow-envelope propagation across threads and FastAPI BackgroundTasks.
#
# The LangfuseASGIMiddleware sets the workflow envelope (which carries the
# upstream BRD agent's ``workflow_run_id`` and any parent trace ids) on a
# ContextVar for the duration of the request. Two boundaries normally drop
# that context, causing nested LLM spans to fabricate a fresh
# ``workflow_run_id`` and detach from the BRD's trace:
#
#   1. FastAPI ``BackgroundTasks`` -- they run AFTER the response is sent, by
#      which point the middleware has already reset the envelope ContextVar.
#   2. ``concurrent.futures.ThreadPoolExecutor`` workers -- worker threads do
#      not inherit ContextVars from the submitting thread.
#
# We patch both boundaries here (with zero changes to api_server.py or
# userstory2TestCasesAgent.py) so the envelope flows cleanly all the way
# down to every Gemini / OpenAI span.
# ---------------------------------------------------------------------------
def _patch_background_task_envelope():
    """Capture the workflow envelope at BackgroundTask construction time and
    re-apply it when the task actually runs."""
    try:
        from starlette.background import BackgroundTask
    except Exception:
        logger.debug("starlette.background.BackgroundTask not available; skipping patch")
        return

    if getattr(BackgroundTask, "_envelope_patched", False):
        return

    import asyncio as _asyncio

    orig_init = BackgroundTask.__init__

    def patched_init(self, func, *args, **kwargs):
        envelope = get_current_envelope()
        if envelope:
            captured = dict(envelope)
            if _asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def _wrapped_async(*a, **kw):
                    token = set_current_envelope(captured)
                    try:
                        return await func(*a, **kw)
                    finally:
                        reset_current_envelope(token)
                wrapped = _wrapped_async
            else:
                @functools.wraps(func)
                def _wrapped_sync(*a, **kw):
                    token = set_current_envelope(captured)
                    try:
                        return func(*a, **kw)
                    finally:
                        reset_current_envelope(token)
                wrapped = _wrapped_sync
            return orig_init(self, wrapped, *args, **kwargs)
        return orig_init(self, func, *args, **kwargs)

    BackgroundTask.__init__ = patched_init
    BackgroundTask._envelope_patched = True
    logger.info("Starlette BackgroundTask envelope propagation patched")


def _patch_executor_envelope():
    """Patch ``ThreadPoolExecutor.submit`` to forward the ambient envelope
    to worker threads. Snapshot at submit time, re-apply inside the worker."""
    from concurrent.futures import ThreadPoolExecutor

    if getattr(ThreadPoolExecutor, "_envelope_patched", False):
        return

    orig_submit = ThreadPoolExecutor.submit

    def patched_submit(self, fn, *args, **kwargs):
        envelope = get_current_envelope()
        if envelope:
            captured = dict(envelope)
            @functools.wraps(fn)
            def _wrapped(*a, **kw):
                token = set_current_envelope(captured)
                try:
                    return fn(*a, **kw)
                finally:
                    reset_current_envelope(token)
            return orig_submit(self, _wrapped, *args, **kwargs)
        return orig_submit(self, fn, *args, **kwargs)

    ThreadPoolExecutor.submit = patched_submit
    ThreadPoolExecutor._envelope_patched = True
    logger.info("ThreadPoolExecutor.submit envelope propagation patched")


def instrument():
    """Monkey-patch agent functions with Langfuse instrumentation + OTEL metrics.

    Must be called AFTER importing userstory2TestCasesAgent (handled by
    main.py) but BEFORE importing api_server so api_server picks up the
    patched references.
    """
    global _langfuse, _instrumented

    if _instrumented:
        return

    # Ensure SSL env vars point at our combined CA bundle so Langfuse
    # SDK + OTEL exporter can verify self-signed ALB certs.
    ca_path = _resolve_ca_cert()
    if ca_path:
        os.environ.setdefault("SSL_CERT_FILE", ca_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_path)
        os.environ.setdefault("CURL_CA_BUNDLE", ca_path)

    _init_otel_metrics()

    span_exporter = None
    if os.getenv("LANGFUSE_SKIP_CUSTOM_EXPORTER", "").lower() not in ("1", "true", "yes"):
        span_exporter = _build_span_exporter()

    init_kwargs: dict[str, Any] = {
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY"),
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY"),
        "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }
    if span_exporter is not None:
        init_kwargs["span_exporter"] = span_exporter

    _langfuse = Langfuse(**init_kwargs)

    # Register the global envelope SpanProcessor AFTER the Langfuse client
    # has wired up its TracerProvider, so envelope attributes land on
    # every span emitted by every library.
    _register_envelope_processor()

    import userstory2TestCasesAgent as agent_module

    _patch_generate_content(agent_module)
    _patch_llm_generate(agent_module)
    _patch_process_single_story_jira(agent_module)
    _patch_process_single_story_qtest(agent_module)
    _patch_process_brownfield_story_jira(agent_module)

    # Cross-thread / background-task envelope propagation. Must run AFTER the
    # agent module is imported (so the ThreadPoolExecutor used in bulk runners
    # picks up the patched submit), but can be called before middleware is
    # attached - both patches are idempotent.
    _patch_background_task_envelope()
    _patch_executor_envelope()

    _instrumented = True
    logger.info(
        "Langfuse instrumentation applied (UserStory-to-TestCases functions patched, envelope-aware)"
    )


def add_middleware(app):
    """Attach the ASGI tracing middleware to a FastAPI/Starlette app."""
    global _middleware_added
    if _middleware_added:
        return
    app.add_middleware(LangfuseASGIMiddleware)
    _middleware_added = True
    logger.info("Langfuse ASGI middleware added")


def shutdown():
    """Flush pending events and shut down Langfuse + OTEL providers."""
    global _langfuse, _otel_tracer_provider, _otel_meter_provider
    if _langfuse:
        try:
            _langfuse.flush()
            _langfuse.shutdown()
            logger.info("Langfuse shutdown complete")
        except Exception as exc:
            logger.debug("Langfuse shutdown error: %s", exc)
    if _otel_tracer_provider:
        try:
            _otel_tracer_provider.shutdown()
        except Exception:
            pass
    if _otel_meter_provider:
        try:
            _otel_meter_provider.shutdown()
        except Exception:
            pass
        logger.info("OTEL providers shutdown complete")
