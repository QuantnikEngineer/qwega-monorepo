"""
Workflow Envelope: canonical context object propagated through every
agent and tool call in the UserStory-to-TestCases agent call graph.

Mirrors the contract used by the BRD Summary agent (quantnik-brd-summary-agent/
utils/envelope.py) so cross-agent traces share the same key set and
Langfuse dashboards see a uniform schema regardless of which orchestrator
originated the call.

Goals:
  * One source of truth for cross-cutting context (workflow_run_id, phase,
    tenant, env, artifact_id, agent_name, agent_version, prompt_version,
    input_fingerprint, policy_flags, constraints, expected_outputs,
    session_id, request_id, parent_span_id, parent_trace_id,
    parent_observation_id).
  * Mirrored to a contextvar so deeply-nested code paths (LLM SDK
    monkey-patches, Jira/Xray/qTest helpers) can pick up the same context
    without an explicit argument.
  * Helpers to flatten the envelope into Langfuse trace ``tags`` and
    observation ``metadata``.

NOTE: ``api_server.py`` / ``userstory2TestCasesAgent.py`` are NEVER touched
by this module. Envelope flow is entirely driven by the
langfuse_instrumentation.py ASGI middleware which sets the contextvar at
the request boundary and reads it inside every monkey-patched wrapper.
"""

from __future__ import annotations

import contextvars
import hashlib
import os
import uuid
from typing import Any, Iterable, Mapping, Optional


# ---------------------------------------------------------------------------
# Canonical envelope keys. Keep stable - they are consumed by dashboards.
# ---------------------------------------------------------------------------
ENVELOPE_KEYS: tuple[str, ...] = (
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
    "policy_flags",
    "constraints",
    "expected_outputs",
    "session_id",
    "request_id",
    "parent_span_id",
    "parent_trace_id",
    "parent_observation_id",
    "user_id",
    "trace_name",
)


# ---------------------------------------------------------------------------
# Contextvar - ambient envelope for the current thread / async task.
# ---------------------------------------------------------------------------
_current_envelope: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "userstory_to_testcases_workflow_envelope", default=None
)


def get_current_envelope() -> Optional[dict]:
    """Return the envelope currently set in the ambient context (or None)."""
    return _current_envelope.get()


def set_current_envelope(envelope: Mapping[str, Any]) -> contextvars.Token:
    """Set ``envelope`` as the ambient context envelope.

    Returns a token that can be passed to ``reset_current_envelope`` to
    restore the prior value.
    """
    return _current_envelope.set(dict(envelope))


def reset_current_envelope(token: contextvars.Token) -> None:
    """Restore the envelope to the value held before ``set_current_envelope``."""
    _current_envelope.reset(token)


class envelope_scope:
    """Context manager that sets/resets the ambient envelope."""

    __slots__ = ("_envelope", "_token")

    def __init__(self, envelope: Mapping[str, Any]):
        self._envelope = dict(envelope)
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> dict:
        self._token = set_current_envelope(self._envelope)
        return self._envelope

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            reset_current_envelope(self._token)
            self._token = None


# ---------------------------------------------------------------------------
# Builders / mergers
# ---------------------------------------------------------------------------
def _input_fingerprint(payload: Any) -> str:
    """Deterministic short hash of an input payload, for log correlation."""
    try:
        raw = repr(payload).encode("utf-8", errors="replace")
    except Exception:
        raw = b""
    return hashlib.sha256(raw).hexdigest()[:16]


def build_envelope(
    *,
    trace_name: str,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    phase: str = "runtime",
    artifact_id: Optional[str] = None,
    input_payload: Any = None,
    policy_flags: Optional[Iterable[str]] = None,
    constraints: Optional[Mapping[str, Any]] = None,
    expected_outputs: Optional[Iterable[str]] = None,
    parent_span_id: Optional[str] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Build a fully-populated workflow envelope.

    All cross-cutting environment defaults (agent_name, env, agent_version,
    prompt_version) are sourced from environment variables, so the envelope
    is the same shape on every endpoint.
    """
    envelope: dict[str, Any] = {
        "workflow_run_id": str(uuid.uuid4()),
        "parent_workflow_run_id": None,
        "phase": phase,
        "tenant": os.getenv("TENANT", "default"),
        "env": os.getenv("APP_ENV", "development"),
        "artifact_id": artifact_id or "userstory_testcases",
        "agent_name": os.getenv("AGENT_NAME", "quantnik-userstory-to-testcases-agent"),
        "agent_version": os.getenv("AGENT_VERSION", "dev"),
        "prompt_version": os.getenv("PROMPT_VERSION", "dev"),
        "input_fingerprint": _input_fingerprint(input_payload) if input_payload is not None else None,
        "policy_flags": list(policy_flags) if policy_flags else [],
        "constraints": dict(constraints) if constraints else {"max_tokens": 8192},
        "expected_outputs": list(expected_outputs) if expected_outputs else ["test_cases"],
        "session_id": session_id,
        "request_id": request_id or uuid.uuid4().hex,
        "parent_span_id": parent_span_id,
        "parent_trace_id": None,
        "parent_observation_id": None,
        "user_id": user_id,
        "trace_name": trace_name,
    }
    if overrides:
        envelope.update(overrides)
    return envelope


def merge_envelope(
    base: Optional[Mapping[str, Any]],
    *,
    child_overrides: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Return a new envelope inheriting from ``base`` with optional overrides."""
    merged: dict = dict(base) if base else {}
    if child_overrides:
        merged.update(child_overrides)
    return merged


def ensure_envelope(
    envelope: Optional[Mapping[str, Any]],
    *,
    trace_name: str = "userstory_testcases_unknown",
    session_id: Optional[str] = None,
) -> dict:
    """Return ``envelope`` if non-empty, else the ambient one, else a fresh one."""
    if envelope:
        return dict(envelope)
    ambient = get_current_envelope()
    if ambient:
        return dict(ambient)
    return build_envelope(trace_name=trace_name, session_id=session_id)


# ---------------------------------------------------------------------------
# Conversion helpers - flatten envelope into Langfuse-friendly shapes.
# ---------------------------------------------------------------------------
def envelope_to_tags(envelope: Mapping[str, Any]) -> list[str]:
    """Render an envelope as a list of Langfuse trace tags.

    Tags are flat strings encoded as ``key=value`` so they can be filtered
    server-side. Lists are joined with ``|`` to keep tag count bounded.
    """
    tags: list[str] = []
    for key in ENVELOPE_KEYS:
        if key not in envelope:
            continue
        value = envelope[key]
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            joined = "|".join(str(v) for v in value)
            if joined:
                tags.append(f"{key}={joined}")
        elif isinstance(value, Mapping):
            try:
                tags.append(f"{key}={','.join(f'{k}:{v}' for k, v in value.items())}")
            except Exception:
                pass
        else:
            tags.append(f"{key}={value}")
    return tags


def envelope_to_metadata(envelope: Mapping[str, Any], extra: Optional[Mapping[str, Any]] = None) -> dict:
    """Render an envelope as a metadata dict for a Langfuse observation."""
    md: dict = {k: envelope.get(k) for k in ENVELOPE_KEYS if k in envelope}
    if extra:
        md.update(extra)
    return md


def stamp_envelope_on_span(span, envelope: Mapping[str, Any]) -> None:
    """Best-effort: write envelope fields as OTEL attributes on a Langfuse span.

    Safe to call with any span object - failures are swallowed because
    instrumentation must never break the request flow.
    """
    try:
        otel_span = getattr(span, "_otel_span", None)
        if otel_span is None:
            return
        for key in ENVELOPE_KEYS:
            val = envelope.get(key)
            if val is None:
                continue
            if isinstance(val, (list, tuple, set)):
                otel_span.set_attribute(f"workflow.{key}", "|".join(str(v) for v in val))
            elif isinstance(val, Mapping):
                otel_span.set_attribute(f"workflow.{key}", str(val))
            else:
                otel_span.set_attribute(f"workflow.{key}", str(val))
    except Exception:
        pass
