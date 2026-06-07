"""Wega Evals - Observability dashboard.

Surfaces operational metrics from Langfuse: cost, tokens, latency, errors,
sessions, models, traces, and observations.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from wega_evals.dashboard_common import (
    COLOR_CYAN,
    COLOR_DIM,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_PURPLE,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_YELLOW,
    PASS_THRESHOLD,
    card_close,
    card_open,
    date_range_picker,
    footer,
    get_daily,
    get_models,
    get_observations,
    get_scores,
    get_sessions,
    get_traces,
    html_bar_chart,
    html_grouped_bar_chart,
    html_sparkline,
    kpi_row,
    page_setup,
    section_label,
    sidebar_footer,
    sidebar_header,
    title,
    topbar,
)

page_setup("Wega Evals - Observability", "📡")

# ── Sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    sidebar_header()
    st.markdown(
        f"<div style='color:{COLOR_DIM}; font-size:11px;'>page · <b style='color:{COLOR_TEXT}'>observability</b></div>",
        unsafe_allow_html=True,
    )

    section_label("NAVIGATION", COLOR_DIM)
    st.link_button("🏠  Home", url="/", use_container_width=True)
    st.link_button("📊  Evaluation", url="/Evaluation", use_container_width=True)
    st.link_button("📡  Observability", url="/Observability", use_container_width=True)
    st.link_button("🩺  Diagnostic", url="/Diagnostic", use_container_width=True)

    if st.button("🔄  refresh data", use_container_width=True, key="nav_refresh"):
        st.cache_data.clear()
        st.rerun()

    section_label("DATE RANGE", COLOR_DIM)
    start_ts, end_ts, from_iso, to_iso = date_range_picker(default_days=30)

    sidebar_footer()

# ── Load data ────────────────────────────────────────────────────────

with st.spinner("// fetching telemetry from langfuse..."):
    traces_df = get_traces(from_iso, to_iso)
    obs_df = get_observations(from_iso, to_iso)
    daily_df, daily_models_df = get_daily(from_iso, to_iso)
    sessions_df = get_sessions(from_iso, to_iso)
    scores_df = get_scores(from_iso, to_iso)  # used for agent attribution only

score_trace_agent = (
    dict(zip(scores_df["trace_id"], scores_df["agent"])) if not scores_df.empty else {}
)

# ── Header ───────────────────────────────────────────────────────────

topbar("dashboard/observability", len(scores_df), len(traces_df), len(obs_df))
title(
    "Observability Dashboard",
    "Operational surface - cost · tokens · latency · errors · sessions · models.",
)

# ── KPI strip ────────────────────────────────────────────────────────

total_cost = float(traces_df["total_cost"].sum()) if not traces_df.empty else 0.0
if total_cost == 0 and not obs_df.empty:
    total_cost = float(obs_df["total_cost"].sum())

if not obs_df.empty and obs_df["total_tokens"].sum() > 0:
    total_tokens = int(obs_df["total_tokens"].sum())
elif not traces_df.empty and traces_df["total_tokens"].sum() > 0:
    total_tokens = int(traces_df["total_tokens"].sum())
elif not daily_models_df.empty:
    total_tokens = int(daily_models_df["total_usage"].sum())
else:
    total_tokens = 0

median_latency = float(traces_df["latency"].median()) if not traces_df.empty else 0.0
p95_latency = float(traces_df["latency"].quantile(0.95)) if not traces_df.empty else 0.0
error_count = int((obs_df["level"].isin(["ERROR", "WARNING"])).sum()) if not obs_df.empty else 0

kpi_row(
    [
        {
            "label": "traces",
            "value": f"{len(traces_df):,}",
            "sub": f"obs {len(obs_df):,}",
            "accent": COLOR_CYAN,
        },
        {
            "label": "total cost",
            "value": f"${total_cost:,.2f}",
            "sub": f"{total_tokens:,} tokens",
            "accent": COLOR_ORANGE,
        },
        {
            "label": "latency p50",
            "value": f"{median_latency:,.0f} ms",
            "sub": f"p95 {p95_latency:,.0f} ms",
            "accent": COLOR_PURPLE,
        },
        {
            "label": "sessions",
            "value": len(sessions_df),
            "sub": f"users {sessions_df['user_id'].nunique() if not sessions_df.empty else 0}",
            "accent": COLOR_YELLOW,
        },
        {
            "label": "errors",
            "value": error_count,
            "sub": "WARNING + ERROR levels",
            "accent": COLOR_RED if error_count else COLOR_GREEN,
        },
    ]
)

# ── Tabs ─────────────────────────────────────────────────────────────

tab_cost, tab_perf, tab_sessions, tab_models, tab_traces, tab_obs, tab_settings = st.tabs(
    ["cost", "performance", "sessions", "models", "traces", "observations", "settings"]
)

# ──────────────────  COST  ──────────────────

with tab_cost:
    if traces_df.empty and daily_df.empty and obs_df.empty:
        st.info("// no cost data available")

    c1, c2 = st.columns(2)
    with c1:
        card_open("DAILY COST", "/daily-cost", accent=COLOR_ORANGE, badge="$ usd")
        cost_series = pd.Series(dtype=float)
        if not daily_df.empty and daily_df["total_cost"].sum() > 0:
            cost_series = daily_df.set_index("date")["total_cost"]
        elif not traces_df.empty:
            tdf2 = traces_df.copy()
            tdf2["date"] = pd.to_datetime(tdf2["timestamp"]).dt.floor("D")
            cost_series = tdf2.groupby("date")["total_cost"].sum()
        elif not obs_df.empty:
            odf2 = obs_df.copy()
            odf2["date"] = pd.to_datetime(odf2["start_time"]).dt.floor("D")
            cost_series = odf2.groupby("date")["total_cost"].sum()

        if cost_series.empty:
            st.info("// no cost data")
        else:
            html_sparkline(cost_series.tolist(), color=COLOR_ORANGE, width=560, height=40)
            st.caption(
                f"sum ${cost_series.sum():,.2f}  ·  avg/day ${cost_series.mean():,.2f}  ·  "
                f"max ${cost_series.max():,.2f}"
            )
            # daily breakdown bars (last 14 days)
            daily_bars = cost_series.tail(14).copy()
            daily_bars.index = [str(d)[:10] for d in daily_bars.index]
            html_bar_chart(daily_bars, fmt="${:,.2f}", color=COLOR_ORANGE)
        card_close()

    with c2:
        card_open("DAILY TOKENS", "/daily-tokens", accent=COLOR_CYAN, badge="in / out")
        daily_tokens = pd.DataFrame()
        if not obs_df.empty and obs_df["total_tokens"].sum() > 0:
            odf2 = obs_df.copy()
            odf2["date"] = pd.to_datetime(odf2["start_time"]).dt.floor("D")
            daily_tokens = odf2.groupby("date")[["input_tokens", "output_tokens"]].sum()
        elif not traces_df.empty and traces_df["total_tokens"].sum() > 0:
            tdf2 = traces_df.copy()
            tdf2["date"] = pd.to_datetime(tdf2["timestamp"]).dt.floor("D")
            daily_tokens = tdf2.groupby("date")[["input_tokens", "output_tokens"]].sum()
        elif not daily_models_df.empty:
            ddf2 = daily_models_df.copy()
            ddf2["date"] = pd.to_datetime(ddf2["date"]).dt.floor("D")
            daily_tokens = (
                ddf2.groupby("date")[["input_usage", "output_usage"]]
                .sum()
                .rename(columns={"input_usage": "input_tokens", "output_usage": "output_tokens"})
            )

        if daily_tokens.empty:
            st.info("// no token data")
        else:
            # build dict-of-dicts {date: {input_tokens, output_tokens}} for last 14 days
            tail = daily_tokens.tail(14)
            series_by_label = {
                str(d)[:10]: {
                    "input": float(row["input_tokens"] or 0),
                    "output": float(row["output_tokens"] or 0),
                }
                for d, row in tail.iterrows()
            }
            html_grouped_bar_chart(
                series_by_label,
                colors={"input": COLOR_CYAN, "output": COLOR_ORANGE},
                fmt="{:,.0f}",
            )
            st.caption(
                f"in {int(daily_tokens['input_tokens'].sum()):,}  "
                f"·  out {int(daily_tokens['output_tokens'].sum()):,}"
            )
        card_close()

    c3, c4 = st.columns(2)
    with c3:
        card_open("COST BY AGENT", "/cost-agent", accent=COLOR_YELLOW, badge="$ usd")
        if not traces_df.empty and score_trace_agent:
            tdf = traces_df.copy()
            tdf["agent"] = tdf["trace_id"].map(score_trace_agent).fillna("(untracked)")
            by_agent = (
                tdf.groupby("agent")["total_cost"].sum().sort_values(ascending=False)
            )
            html_bar_chart(by_agent, fmt="${:,.2f}", color=COLOR_YELLOW)
        else:
            st.info("// need scores + traces to attribute cost")
        card_close()

    with c4:
        card_open("COST BY MODEL", "/cost-model", accent=COLOR_PURPLE, badge="$ usd")
        if not obs_df.empty and "model" in obs_df:
            by_model = (
                obs_df[obs_df["model"] != ""]
                .groupby("model")["total_cost"]
                .sum()
                .sort_values(ascending=False)
            )
            html_bar_chart(by_model, fmt="${:,.2f}", color=COLOR_PURPLE)
        elif not daily_models_df.empty:
            by_model = (
                daily_models_df.groupby("model")["total_cost"].sum().sort_values(ascending=False)
            )
            html_bar_chart(by_model, fmt="${:,.2f}", color=COLOR_PURPLE)
        else:
            st.info("// no model-level cost data")
        card_close()

    card_open("TOP 20 EXPENSIVE TRACES", "/expensive-traces", accent=COLOR_RED, badge="$ desc")
    if not traces_df.empty:
        top = traces_df.sort_values("total_cost", ascending=False).head(20)
        st.dataframe(
            top[
                [
                    "timestamp", "name", "total_cost", "total_tokens", "latency", "trace_id",
                ]
            ].reset_index(drop=True),
            use_container_width=True,
            column_config={
                "total_cost": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
                "total_tokens": st.column_config.NumberColumn("Tokens"),
                "latency": st.column_config.NumberColumn("Latency (ms)", format="%.0f"),
            },
        )
    card_close()

# ──────────────────  PERFORMANCE  ──────────────────

with tab_perf:
    if traces_df.empty:
        st.info("// no traces in this date range")

    c1, c2 = st.columns(2)
    with c1:
        card_open("LATENCY PERCENTILES", "/latency", accent=COLOR_CYAN, badge="ms")
        if not traces_df.empty:
            lat = traces_df["latency"].astype(float)
            perc = pd.DataFrame(
                {
                    "metric": ["p50", "p75", "p90", "p95", "p99", "max"],
                    "ms": [
                        lat.median(),
                        lat.quantile(0.75),
                        lat.quantile(0.90),
                        lat.quantile(0.95),
                        lat.quantile(0.99),
                        lat.max(),
                    ],
                }
            )
            st.dataframe(perc.set_index("metric").round(1), use_container_width=True)
        card_close()

    with c2:
        card_open("LATENCY TREND", "/latency-trend", accent=COLOR_PURPLE, badge="p50 / p95")
        if not traces_df.empty:
            tt = traces_df.copy()
            tt["date"] = pd.to_datetime(tt["timestamp"]).dt.floor("D")
            lat_trend = (
                tt.groupby("date")["latency"]
                .agg(p50="median", p95=lambda s: s.quantile(0.95))
            )
            st.markdown(
                f"<div style='color:{COLOR_DIM}; font-size:11px;'>p50 latency</div>",
                unsafe_allow_html=True,
            )
            html_sparkline(lat_trend["p50"].tolist(), color=COLOR_PURPLE, width=560, height=32)
            st.markdown(
                f"<div style='color:{COLOR_DIM}; font-size:11px; margin-top:6px;'>p95 latency</div>",
                unsafe_allow_html=True,
            )
            html_sparkline(lat_trend["p95"].tolist(), color=COLOR_ORANGE, width=560, height=32)
        card_close()

    c3, c4 = st.columns(2)
    with c3:
        card_open("LATENCY BY AGENT", "/latency-agent", accent=COLOR_ORANGE, badge="p50/p95")
        if not traces_df.empty and score_trace_agent:
            tdf = traces_df.copy()
            tdf["agent"] = tdf["trace_id"].map(score_trace_agent).fillna("(untracked)")
            agg = (
                tdf.groupby("agent")["latency"]
                .agg(p50="median", p95=lambda s: s.quantile(0.95), count="count")
                .round(0)
                .sort_values("p95", ascending=False)
            )
            st.dataframe(agg, use_container_width=True)
        card_close()

    with c4:
        card_open("ERROR / WARNING COUNTS", "/errors", accent=COLOR_RED, badge="levels")
        if not obs_df.empty and "level" in obs_df:
            levels = (
                obs_df[obs_df["level"] != ""]
                .groupby("level")
                .size()
            )
            if levels.empty:
                st.success("// no error/warning observations")
            else:
                html_bar_chart(levels, fmt="{:,.0f}", color=COLOR_RED)
        else:
            st.info("// no observation level data")
        card_close()

    card_open("SLOWEST 20 TRACES", "/slow-traces", accent=COLOR_RED, badge="latency desc")
    if not traces_df.empty:
        slow = traces_df.sort_values("latency", ascending=False).head(20)
        st.dataframe(
            slow[
                ["timestamp", "name", "latency", "total_tokens", "total_cost", "trace_id"]
            ].reset_index(drop=True),
            use_container_width=True,
            column_config={
                "latency": st.column_config.NumberColumn("Latency (ms)", format="%.0f"),
                "total_cost": st.column_config.NumberColumn("Cost ($)", format="$%.4f"),
            },
        )
    card_close()

# ──────────────────  SESSIONS  ──────────────────

with tab_sessions:
    c1, c2 = st.columns(2)
    with c1:
        card_open("SESSION VOLUME", "/sessions", accent=COLOR_CYAN, badge="daily")
        if not sessions_df.empty:
            sdf2 = sessions_df.copy()
            sdf2["date"] = pd.to_datetime(sdf2["created_at"]).dt.floor("D")
            daily_sessions = sdf2.groupby("date").size()
            daily_sessions.index = [str(d)[:10] for d in daily_sessions.index]
            html_bar_chart(daily_sessions.tail(14), fmt="{:,.0f}", color=COLOR_CYAN)
            st.caption(
                f"total {len(sessions_df)}  ·  users {sessions_df['user_id'].nunique()}"
            )
        else:
            st.info("// no sessions")
        card_close()

    with c2:
        card_open("TRACES PER SESSION", "/traces-per-session", accent=COLOR_PURPLE, badge="dist")
        if not traces_df.empty and "session_id" in traces_df:
            counts = (
                traces_df[traces_df["session_id"] != ""]
                .groupby("session_id")
                .size()
            )
            if counts.empty:
                st.info("// no traces tagged with session_id")
            else:
                dist = counts.value_counts().sort_index()
                dist.index = [f"{int(i)} traces" for i in dist.index]
                html_bar_chart(dist, fmt="{:,.0f}", color=COLOR_PURPLE)
                st.caption(f"avg {counts.mean():.1f}  ·  max {counts.max()}")
        card_close()

    card_open("RECENT SESSIONS", "/sessions-list", accent=COLOR_ORANGE, badge="list")
    if not sessions_df.empty:
        st.dataframe(
            sessions_df.sort_values("created_at", ascending=False).head(100),
            use_container_width=True,
        )
    card_close()

# ──────────────────  MODELS  ──────────────────

with tab_models:
    models_df = get_models()

    c1, c2 = st.columns(2)
    with c1:
        card_open("MODEL USAGE", "/model-usage", accent=COLOR_PURPLE, badge="tokens")
        if not obs_df.empty and "model" in obs_df:
            usage = (
                obs_df[obs_df["model"] != ""]
                .groupby("model")[["input_tokens", "output_tokens", "total_tokens"]]
                .sum()
                .sort_values("total_tokens", ascending=False)
            )
            st.dataframe(usage, use_container_width=True)
        else:
            st.info("// no observation data")
        card_close()

    with c2:
        card_open("MODEL COST SHARE", "/model-cost", accent=COLOR_ORANGE, badge="$ usd")
        if not obs_df.empty and "model" in obs_df:
            cost_share = (
                obs_df[obs_df["model"] != ""]
                .groupby("model")["total_cost"]
                .sum()
                .sort_values(ascending=False)
            )
            html_bar_chart(cost_share, fmt="${:,.2f}", color=COLOR_ORANGE)
        elif not daily_models_df.empty:
            cost_share = (
                daily_models_df.groupby("model")["total_cost"]
                .sum()
                .sort_values(ascending=False)
            )
            html_bar_chart(cost_share, fmt="${:,.2f}", color=COLOR_ORANGE)
        card_close()

    card_open("MODEL LATENCY", "/model-latency", accent=COLOR_CYAN, badge="ms")
    if not obs_df.empty and "model" in obs_df:
        mlat = (
            obs_df[obs_df["model"] != ""]
            .groupby("model")["latency"]
            .agg(p50="median", p95=lambda s: s.quantile(0.95), count="count")
            .round(0)
            .sort_values("p95", ascending=False)
        )
        st.dataframe(mlat, use_container_width=True)
    card_close()

    card_open("REGISTERED MODELS & PRICING", "/models", accent=COLOR_YELLOW, badge="catalog")
    if not models_df.empty:
        st.dataframe(models_df, use_container_width=True)
    else:
        st.info("// no model catalog returned")
    card_close()

# ──────────────────  TRACES  ──────────────────

with tab_traces:
    card_open("TRACES", "/traces", accent=COLOR_CYAN, badge=f"{len(traces_df)} rows")
    if not traces_df.empty:
        st.dataframe(
            traces_df.sort_values("timestamp", ascending=False).head(200).reset_index(drop=True),
            use_container_width=True,
        )
    card_close()

# ──────────────────  OBSERVATIONS  ──────────────────

with tab_obs:
    card_open("OBSERVATIONS", "/observations", accent=COLOR_PURPLE, badge=f"{len(obs_df)} rows")
    if not obs_df.empty:
        st.dataframe(
            obs_df.sort_values("start_time", ascending=False).head(200).reset_index(drop=True),
            use_container_width=True,
        )
    card_close()

# ──────────────────  SETTINGS  ──────────────────

with tab_settings:
    card_open("CONFIGURATION", "/settings", accent=COLOR_PURPLE, badge="env")
    cfg = {
        "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST", ""),
        "DATE_FROM": from_iso,
        "DATE_TO": to_iso,
        "EVAL_PASS_THRESHOLD": str(PASS_THRESHOLD),
        "CACHE_TTL": "120s telemetry · 300s sessions · 600s catalog",
    }
    st.dataframe(
        pd.DataFrame(cfg.items(), columns=["Key", "Value"]),
        use_container_width=True,
        hide_index=True,
    )
    card_close()

    errs = {
        k: v
        for k, v in st.session_state.items()
        if k.startswith("_") and k.endswith("_err")
    }
    if errs:
        card_open("FETCH ERRORS", "/errors", accent=COLOR_RED, badge=f"{len(errs)}")
        for k, v in errs.items():
            st.markdown(
                f"<div style='color:{COLOR_RED}; font-size:12px;'>{k}: {v}</div>",
                unsafe_allow_html=True,
            )
        card_close()

footer(PASS_THRESHOLD, len(scores_df), len(traces_df), len(obs_df))
