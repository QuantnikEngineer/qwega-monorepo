"""Langfuse REST API helpers used by the dashboard.

Wraps the public endpoints we consume and normalises responses into pandas
DataFrames so the dashboard can stay declarative.

All functions are defensive: missing fields default to ``None``/``0`` so the
dashboard never breaks if the Langfuse API evolves.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd

from wega_evals.llm_judge import _ensure_ca_bundle


_ensure_ca_bundle()


# ── HTTP client ──────────────────────────────────────────────────────


def build_client() -> httpx.Client:
    """Build a Langfuse httpx client trusting the combined CA bundle.

    Honors ``LANGFUSE_VERIFY_SSL=false`` to disable verification (useful
    when Langfuse is fronted by a self-signed certificate or a TLS-
    intercepting corporate proxy where the CA bundle cannot be assembled).
    """
    verify_env = os.environ.get("LANGFUSE_VERIFY_SSL", "").strip().lower()
    if verify_env in ("0", "false", "no", "off"):
        verify: Any = False
        # Silence the InsecureRequestWarning since this is an explicit opt-in.
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
    else:
        bundle = os.environ.get("SSL_CERT_FILE", "")
        verify = bundle if bundle and os.path.exists(bundle) else True
    return httpx.Client(
        base_url=os.getenv("LANGFUSE_HOST", "").rstrip("/"),
        auth=(
            os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            os.getenv("LANGFUSE_SECRET_KEY", ""),
        ),
        verify=verify,
        timeout=60.0,
    )


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _paginate(
    client: httpx.Client,
    path: str,
    params: dict[str, Any] | None = None,
    limit_per_page: int = 100,
    max_pages: int = 200,
) -> list[dict[str, Any]]:
    """Generic paginator that drains a Langfuse list endpoint."""
    out: list[dict[str, Any]] = []
    page = 1
    p = dict(params or {})
    while page <= max_pages:
        p.update({"page": page, "limit": limit_per_page})
        resp = client.get(path, params={k: v for k, v in p.items() if v is not None})
        resp.raise_for_status()
        body = resp.json()
        items = body.get("data") or body.get("items") or []
        if not items:
            break
        out.extend(items)
        meta = body.get("meta", {}) or {}
        total_pages = meta.get("totalPages") or meta.get("totalPages", 1)
        if not total_pages or page >= total_pages:
            break
        page += 1
    return out


# ── Scores ───────────────────────────────────────────────────────────


def fetch_scores(
    client: httpx.Client | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> pd.DataFrame:
    """Return numeric scores produced by wega-evals."""
    client = client or build_client()
    params = {"dataType": "NUMERIC", "fromTimestamp": _iso(from_ts), "toTimestamp": _iso(to_ts)}
    rows: list[dict[str, Any]] = []
    for s in _paginate(client, "/api/public/v2/scores", params):
        name = s.get("name", "")
        if "_eval_" not in name:
            continue
        parts = name.split("_eval_", 1)
        rows.append(
            {
                "id": s.get("id", ""),
                "trace_id": s.get("traceId", ""),
                "agent": parts[0],
                "dimension": parts[1] if len(parts) > 1 else name,
                "score": s.get("value", 0.0),
                "comment": s.get("comment", ""),
                "created_at": s.get("createdAt", ""),
            }
        )
    cols = ["id", "trace_id", "agent", "dimension", "score", "comment", "created_at"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    return df


# ── Traces ───────────────────────────────────────────────────────────


def fetch_traces(
    client: httpx.Client | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    name: str | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
    limit_pages: int = 50,
) -> pd.DataFrame:
    """Return trace-level metrics: latency, cost, tokens, tags, user/session."""
    client = client or build_client()
    params: dict[str, Any] = {
        "fromTimestamp": _iso(from_ts),
        "toTimestamp": _iso(to_ts),
        "name": name,
        "userId": user_id,
    }
    if tags:
        params["tags"] = ",".join(tags)
    items = _paginate(client, "/api/public/traces", params, max_pages=limit_pages)
    rows: list[dict[str, Any]] = []
    for t in items:
        usage = t.get("usage") or {}
        # Langfuse may expose tokens under several aliases
        in_tok = (
            usage.get("input")
            or usage.get("promptTokens")
            or t.get("inputTokens")
            or t.get("promptTokens")
            or 0
        )
        out_tok = (
            usage.get("output")
            or usage.get("completionTokens")
            or t.get("outputTokens")
            or t.get("completionTokens")
            or 0
        )
        tot_tok = (
            usage.get("total")
            or usage.get("totalTokens")
            or t.get("totalTokens")
            or (int(in_tok) + int(out_tok))
            or 0
        )
        rows.append(
            {
                "trace_id": t.get("id", ""),
                "name": t.get("name", ""),
                "timestamp": t.get("timestamp", ""),
                "user_id": t.get("userId") or "",
                "session_id": t.get("sessionId") or "",
                "release": t.get("release") or "",
                "version": t.get("version") or "",
                "tags": ",".join(t.get("tags") or []),
                "latency": t.get("latency") or 0.0,
                "total_cost": float(t.get("totalCost") or t.get("calculatedTotalCost") or 0.0),
                "input_tokens": int(in_tok or 0),
                "output_tokens": int(out_tok or 0),
                "total_tokens": int(tot_tok or 0),
                "observation_count": len(t.get("observations") or []),
                "score_count": len(t.get("scores") or []),
                "html_path": t.get("htmlPath") or "",
            }
        )
    cols = [
        "trace_id", "name", "timestamp", "user_id", "session_id", "release",
        "version", "tags", "latency", "total_cost", "input_tokens",
        "output_tokens", "total_tokens", "observation_count", "score_count",
        "html_path",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


# ── Observations (generations / spans) ───────────────────────────────


def fetch_observations(
    client: httpx.Client | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    type_filter: str | None = "GENERATION",
    limit_pages: int = 50,
) -> pd.DataFrame:
    """Return generations / spans with model, tokens, cost, latency."""
    client = client or build_client()
    params: dict[str, Any] = {
        "fromStartTime": _iso(from_ts),
        "toStartTime": _iso(to_ts),
        "type": type_filter,
    }
    items = _paginate(client, "/api/public/observations", params, max_pages=limit_pages)
    rows: list[dict[str, Any]] = []
    for o in items:
        usage = o.get("usage") or {}
        rows.append(
            {
                "id": o.get("id", ""),
                "trace_id": o.get("traceId", ""),
                "name": o.get("name", ""),
                "type": o.get("type", ""),
                "start_time": o.get("startTime") or "",
                "end_time": o.get("endTime") or "",
                "completion_start_time": o.get("completionStartTime") or "",
                "model": o.get("model") or "",
                "level": o.get("level") or "",
                "status_message": o.get("statusMessage") or "",
                "prompt_id": o.get("promptId") or "",
                "latency": o.get("latency") or 0.0,
                "time_to_first_token": o.get("timeToFirstToken") or 0.0,
                "input_tokens": usage.get("input") or o.get("promptTokens") or 0,
                "output_tokens": usage.get("output") or o.get("completionTokens") or 0,
                "total_tokens": usage.get("total") or o.get("totalTokens") or 0,
                "input_cost": float(o.get("calculatedInputCost") or o.get("inputCost") or 0.0),
                "output_cost": float(o.get("calculatedOutputCost") or o.get("outputCost") or 0.0),
                "total_cost": float(o.get("calculatedTotalCost") or o.get("totalCost") or 0.0),
            }
        )
    cols = [
        "id", "trace_id", "name", "type", "start_time", "end_time",
        "completion_start_time", "model", "level", "status_message",
        "prompt_id", "latency", "time_to_first_token", "input_tokens",
        "output_tokens", "total_tokens", "input_cost", "output_cost",
        "total_cost",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    return df


# ── Daily aggregated metrics ────────────────────────────────────────


def fetch_daily_metrics(
    client: httpx.Client | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    trace_name: str | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
) -> pd.DataFrame:
    """Daily aggregated metrics: countTraces, countObservations, totalCost, per-model usage."""
    client = client or build_client()
    params: dict[str, Any] = {
        "fromTimestamp": _iso(from_ts),
        "toTimestamp": _iso(to_ts),
        "traceName": trace_name,
        "userId": user_id,
    }
    if tags:
        params["tags"] = ",".join(tags)
    items = _paginate(client, "/api/public/metrics/daily", params, max_pages=20)

    day_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    for d in items:
        date = d.get("date", "")
        day_rows.append(
            {
                "date": date,
                "count_traces": d.get("countTraces") or 0,
                "count_observations": d.get("countObservations") or 0,
                "total_cost": float(d.get("totalCost") or 0.0),
            }
        )
        for m in d.get("usage") or []:
            model_rows.append(
                {
                    "date": date,
                    "model": m.get("model") or "",
                    "input_usage": m.get("inputUsage") or 0,
                    "output_usage": m.get("outputUsage") or 0,
                    "total_usage": m.get("totalUsage") or 0,
                    "count_traces": m.get("countTraces") or 0,
                    "count_observations": m.get("countObservations") or 0,
                    "total_cost": float(m.get("totalCost") or 0.0),
                }
            )

    days_df = (
        pd.DataFrame(day_rows)
        if day_rows
        else pd.DataFrame(columns=["date", "count_traces", "count_observations", "total_cost"])
    )
    if not days_df.empty:
        days_df["date"] = pd.to_datetime(days_df["date"], utc=True, errors="coerce")
    models_df = (
        pd.DataFrame(model_rows)
        if model_rows
        else pd.DataFrame(
            columns=[
                "date", "model", "input_usage", "output_usage", "total_usage",
                "count_traces", "count_observations", "total_cost",
            ]
        )
    )
    if not models_df.empty:
        models_df["date"] = pd.to_datetime(models_df["date"], utc=True, errors="coerce")
    days_df.attrs["per_model"] = models_df
    return days_df


def daily_model_breakdown(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Pull the per-model dataframe attached to a daily-metrics result."""
    return daily_df.attrs.get("per_model", pd.DataFrame())


# ── Sessions ─────────────────────────────────────────────────────────


def fetch_sessions(
    client: httpx.Client | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit_pages: int = 20,
) -> pd.DataFrame:
    client = client or build_client()
    params = {"fromTimestamp": _iso(from_ts), "toTimestamp": _iso(to_ts)}
    items = _paginate(client, "/api/public/sessions", params, max_pages=limit_pages)
    rows: list[dict[str, Any]] = []
    for s in items:
        rows.append(
            {
                "id": s.get("id", ""),
                "created_at": s.get("createdAt") or "",
                "project_id": s.get("projectId") or "",
                "user_id": s.get("userId") or "",
            }
        )
    cols = ["id", "created_at", "project_id", "user_id"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    return df


# ── Datasets & runs ─────────────────────────────────────────────────


def fetch_datasets(client: httpx.Client | None = None) -> pd.DataFrame:
    client = client or build_client()
    items = _paginate(client, "/api/public/v2/datasets", {}, max_pages=10)
    rows = [
        {
            "name": d.get("name", ""),
            "description": d.get("description") or "",
            "created_at": d.get("createdAt") or "",
            "updated_at": d.get("updatedAt") or "",
        }
        for d in items
    ]
    cols = ["name", "description", "created_at", "updated_at"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    return df


def fetch_dataset_runs(
    dataset_name: str,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    client = client or build_client()
    try:
        items = _paginate(
            client, f"/api/public/datasets/{dataset_name}/runs", {}, max_pages=20
        )
    except httpx.HTTPStatusError:
        return pd.DataFrame(columns=["name", "created_at", "dataset_name", "description"])
    rows = [
        {
            "name": r.get("name", ""),
            "dataset_name": dataset_name,
            "created_at": r.get("createdAt") or "",
            "updated_at": r.get("updatedAt") or "",
            "description": r.get("description") or "",
            "metadata": r.get("metadata") or "",
        }
        for r in items
    ]
    cols = ["name", "dataset_name", "created_at", "updated_at", "description", "metadata"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    return df


# ── Models ──────────────────────────────────────────────────────────


def fetch_models(client: httpx.Client | None = None) -> pd.DataFrame:
    client = client or build_client()
    try:
        items = _paginate(client, "/api/public/models", {}, max_pages=10)
    except httpx.HTTPStatusError:
        return pd.DataFrame(
            columns=["id", "model_name", "match_pattern", "unit", "input_price", "output_price"]
        )
    rows = []
    for m in items:
        rows.append(
            {
                "id": m.get("id", ""),
                "model_name": m.get("modelName") or "",
                "match_pattern": m.get("matchPattern") or "",
                "unit": m.get("unit") or "",
                "input_price": m.get("inputPrice") or 0.0,
                "output_price": m.get("outputPrice") or 0.0,
                "total_price": m.get("totalPrice") or 0.0,
                "start_date": m.get("startDate") or "",
                "is_langfuse_managed": m.get("isLangfuseManaged") or False,
            }
        )
    cols = [
        "id", "model_name", "match_pattern", "unit", "input_price",
        "output_price", "total_price", "start_date", "is_langfuse_managed",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)
