"""Evaluation view (single-page app section).

Surfaces quality metrics: scores, pass/fail, dimension stats, trends,
quality-vs-cost, dataset runs, failures, and raw score data.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from quantnik_evals.dashboard_common import (
    COLOR_CYAN,
    COLOR_DIM,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_PURPLE,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_YELLOW,
    card_close,
    card_open,
    footer,
    get_dataset_runs,
    get_datasets,
    html_bar_chart,
    html_sparkline,
    kpi_row,
    section_label,
    title,
    topbar,
)


def render(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    threshold: float,
    scores_df: pd.DataFrame,
    traces_df: pd.DataFrame,
    obs_df: pd.DataFrame,
    selected_agents: list[str],
    selected_dims: list[str],
) -> None:
    """Render the Evaluation page body (no sidebar, no page_setup)."""

    # ── Filter scores ────────────────────────────────────────────────
    if not scores_df.empty:
        mask = (
            scores_df["agent"].isin(selected_agents)
            & scores_df["dimension"].isin(selected_dims)
            & (scores_df["created_at"] >= start_ts)
            & (scores_df["created_at"] < end_ts)
        )
        filtered_scores = scores_df[mask].copy()
    else:
        filtered_scores = scores_df

    overall_scores = (
        filtered_scores[filtered_scores["dimension"] == "overall"]
        if not filtered_scores.empty
        else filtered_scores
    )
    dim_scores = (
        filtered_scores[filtered_scores["dimension"] != "overall"]
        if not filtered_scores.empty
        else filtered_scores
    )
    score_trace_agent = (
        dict(zip(filtered_scores["trace_id"], filtered_scores["agent"]))
        if not filtered_scores.empty
        else {}
    )

    # ── Header ───────────────────────────────────────────────────────
    topbar("dashboard/evaluation", len(scores_df), len(traces_df), len(obs_df))
    title(
        "Evaluation Dashboard",
        "Quality surface - scores · dimensions · pass-rates · regressions · runs.",
    )

    # ── KPI strip ────────────────────────────────────────────────────
    total_evals = len(filtered_scores["trace_id"].unique()) if not filtered_scores.empty else 0
    avg_score = dim_scores["score"].mean() if not dim_scores.empty else 0.0
    pass_rate = (dim_scores["score"] >= threshold).mean() * 100 if not dim_scores.empty else 0.0
    pass_count = int((dim_scores["score"] >= threshold).sum()) if not dim_scores.empty else 0
    fail_count = int((dim_scores["score"] < threshold).sum()) if not dim_scores.empty else 0
    pass_color = COLOR_GREEN if pass_rate >= threshold * 100 else COLOR_RED
    agents_active = len(filtered_scores["agent"].unique()) if not filtered_scores.empty else 0
    dims_active = len(filtered_scores["dimension"].unique()) if not filtered_scores.empty else 0

    kpi_row(
        [
            {
                "label": "evaluations",
                "value": total_evals,
                "sub": f"{len(filtered_scores)} score points",
                "accent": COLOR_CYAN,
            },
            {
                "label": "avg score",
                "value": f"{avg_score:.2f}",
                "sub": f"pass {pass_count} · fail {fail_count}",
                "accent": COLOR_YELLOW,
            },
            {
                "label": "pass rate",
                "value": f"{pass_rate:.0f}%",
                "sub": f"thr {threshold:.2f}",
                "accent": pass_color,
            },
            {
                "label": "agents",
                "value": agents_active,
                "sub": f"{len(selected_agents)} selected",
                "accent": COLOR_PURPLE,
            },
            {
                "label": "dimensions",
                "value": dims_active,
                "sub": f"{len(selected_dims)} selected",
                "accent": COLOR_ORANGE,
            },
        ]
    )

    # ── Tabs ─────────────────────────────────────────────────────────
    tab_overview, tab_trends, tab_quality, tab_runs, tab_drill, tab_raw = st.tabs(
        ["overview", "trends", "quality vs cost", "runs", "drilldown", "raw"]
    )

    # ── OVERVIEW ─────────────────────────────────────────────────────
    with tab_overview:
        if filtered_scores.empty:
            st.warning(
                "No evaluation scores in this date range.\n\nRun an evaluation first:\n```\n"
                "quantnik-eval --agent cara run --dataset cara-eval\n```"
            )
        else:
            c1, c2 = st.columns(2)
            with c1:
                card_open("OVERALL SCORES", "/agent-overall", accent=COLOR_ORANGE, badge="bar")
                if not overall_scores.empty:
                    agent_overall = (
                        overall_scores.groupby("agent")["score"]
                        .mean()
                        .sort_values(ascending=False)
                    )
                    html_bar_chart(agent_overall, threshold=threshold, fmt="{:.2f}", max_value=1.0)
                elif not dim_scores.empty:
                    agent_avg = (
                        dim_scores.groupby("agent")["score"]
                        .mean()
                        .sort_values(ascending=False)
                    )
                    html_bar_chart(agent_avg, threshold=threshold, fmt="{:.2f}", max_value=1.0)
                card_close()

            with c2:
                card_open(
                    "PASS / FAIL",
                    "/pass-fail",
                    accent=COLOR_GREEN,
                    badge=f"thr {threshold:.2f}",
                )
                if not dim_scores.empty:
                    pf = dim_scores.copy()
                    pf["result"] = pf["score"].apply(
                        lambda x: "Pass" if x >= threshold else "Fail"
                    )
                    pf_summary = pf.groupby(["agent", "result"]).size().reset_index(name="count")
                    pf_wide = (
                        pf_summary.pivot(index="agent", columns="result", values="count")
                        .fillna(0)
                        .astype(int)
                    )
                    for c in ["Pass", "Fail"]:
                        if c not in pf_wide.columns:
                            pf_wide[c] = 0
                    pf_wide["Total"] = pf_wide["Pass"] + pf_wide["Fail"]
                    pf_wide["Pass Rate"] = (
                        (pf_wide["Pass"] / pf_wide["Total"] * 100).round(1).astype(str) + "%"
                    )
                    st.dataframe(pf_wide, use_container_width=True)
                card_close()

            c3, c4 = st.columns(2)
            with c3:
                card_open("AGENT × DIMENSION", "/heatmap", accent=COLOR_CYAN, badge="matrix")
                if not dim_scores.empty:
                    heatmap_data = (
                        dim_scores.groupby(["agent", "dimension"])["score"].mean().reset_index()
                    )
                    heatmap_pivot = heatmap_data.pivot(
                        index="agent", columns="dimension", values="score"
                    )

                    def color_score(val: float) -> str:
                        if pd.isna(val):
                            return ""
                        if val >= threshold:
                            return (
                                f"background-color: rgba(186,230,126,0.25); color: {COLOR_GREEN};"
                            )
                        return f"background-color: rgba(240,113,120,0.20); color: {COLOR_RED};"

                    styled = heatmap_pivot.style.format("{:.2f}").map(color_score)
                    st.dataframe(styled, use_container_width=True)
                card_close()

            with c4:
                card_open("DIMENSION STATS", "/dimensions", accent=COLOR_YELLOW, badge="table")
                if not dim_scores.empty:
                    dim_stats = (
                        dim_scores.groupby("dimension")["score"]
                        .agg(["mean", "min", "max", "count"])
                        .round(2)
                    )
                    dim_stats.columns = ["Mean", "Min", "Max", "Count"]
                    dim_stats["Status"] = dim_stats["Mean"].apply(
                        lambda x: "PASS" if x >= threshold else "FAIL"
                    )
                    st.dataframe(dim_stats, use_container_width=True)
                card_close()

    # ── TRENDS ───────────────────────────────────────────────────────
    with tab_trends:
        card_open("SCORE TRENDS PER AGENT", "/trends", accent=COLOR_PURPLE, badge="lines")
        if dim_scores.empty:
            st.info("// no scores in this date range")
        else:
            trend_data = dim_scores.copy()
            trend_data["date"] = pd.to_datetime(trend_data["created_at"]).dt.floor("D")
            for agent in sorted(dim_scores["agent"].unique()):
                agent_data = trend_data[trend_data["agent"] == agent]
                if agent_data.empty:
                    continue
                section_label(agent, COLOR_ORANGE)
                pivot = agent_data.groupby(["date", "dimension"])["score"].mean().reset_index()
                pivot_wide = pivot.pivot(index="date", columns="dimension", values="score")
                spark_rows = []
                for dim_name in pivot_wide.columns:
                    series = pivot_wide[dim_name].dropna().tolist()
                    if not series:
                        continue
                    mean_v = sum(series) / len(series)
                    spark_rows.append((dim_name, series, mean_v))
                if not spark_rows:
                    st.markdown(
                        f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no data</div>",
                        unsafe_allow_html=True,
                    )
                    continue
                for dim_name, series, mean_v in spark_rows:
                    color = COLOR_GREEN if mean_v >= threshold else COLOR_RED
                    st.markdown(
                        f'<div style="display:flex; align-items:center; margin:3px 0;'
                        f' font-family:monospace; font-size:12px;">'
                        f'<div style="width:160px; color:{COLOR_TEXT};">{dim_name}</div></div>',
                        unsafe_allow_html=True,
                    )
                    html_sparkline(series, color=color, threshold=threshold, width=280, height=24)
                    st.markdown(
                        f"<div style='color:{color}; font-size:12px; margin-top:-22px;"
                        f" padding-left:460px;'>mean {mean_v:.2f}</div>",
                        unsafe_allow_html=True,
                    )
        card_close()

        card_open("AGENT MEAN TREND", "/agent-trend", accent=COLOR_CYAN, badge="aggregate")
        if not dim_scores.empty:
            ds = dim_scores.copy()
            ds["date"] = pd.to_datetime(ds["created_at"]).dt.floor("D")
            agent_trend = (
                ds.groupby(["date", "agent"])["score"]
                .mean()
                .reset_index()
                .pivot(index="date", columns="agent", values="score")
            )
            for agent in agent_trend.columns:
                series = agent_trend[agent].dropna().tolist()
                if not series:
                    continue
                mean_v = sum(series) / len(series)
                color = COLOR_GREEN if mean_v >= threshold else COLOR_RED
                st.markdown(
                    f"<div style='font-family:monospace; font-size:12px; margin:6px 0 2px 0;'>"
                    f"<span style='color:{COLOR_TEXT};'>{agent}</span> &nbsp;"
                    f"<span style='color:{color};'>mean {mean_v:.2f}</span></div>",
                    unsafe_allow_html=True,
                )
                html_sparkline(series, color=color, threshold=threshold, width=480, height=28)
        card_close()

    # ── QUALITY vs COST ──────────────────────────────────────────────
    with tab_quality:
        if filtered_scores.empty or traces_df.empty:
            st.info("// need both scores and traces to compute quality-vs-cost")
        else:
            if not overall_scores.empty:
                tscore = (
                    overall_scores.groupby("trace_id")["score"]
                    .mean()
                    .rename("score")
                    .reset_index()
                )
            else:
                tscore = (
                    dim_scores.groupby("trace_id")["score"]
                    .mean()
                    .rename("score")
                    .reset_index()
                )
            joined = traces_df.merge(tscore, on="trace_id", how="inner")
            joined["agent"] = joined["trace_id"].map(score_trace_agent).fillna("(untracked)")

            c1, c2 = st.columns(2)
            with c1:
                card_open(
                    "SCORE per $ (HIGHER BETTER)",
                    "/score-per-cost",
                    accent=COLOR_ORANGE,
                    badge="bar",
                )
                if not joined.empty:
                    per_agent = joined.groupby("agent").agg(
                        score=("score", "mean"), cost=("total_cost", "sum")
                    )
                    cost_safe = per_agent["cost"].where(per_agent["cost"] > 0)
                    per_agent["score_per_$"] = (per_agent["score"] / cost_safe).fillna(0)
                    series = per_agent["score_per_$"].sort_values(ascending=False)
                    html_bar_chart(series, fmt="{:.3f}")
                card_close()
            with c2:
                card_open(
                    "MEAN LATENCY by AGENT (LOWER BETTER)",
                    "/latency-agent-bar",
                    accent=COLOR_CYAN,
                    badge="bar",
                )
                if not joined.empty:
                    lat_by_agent = (
                        joined.groupby("agent")["latency"].median().sort_values(ascending=True)
                    )
                    html_bar_chart(lat_by_agent, fmt="{:,.0f} ms", color=COLOR_CYAN)
                card_close()

            card_open("PARETO TABLE", "/pareto", accent=COLOR_GREEN, badge="best score/$")
            if not joined.empty:
                pareto = (
                    joined.groupby("agent")
                    .agg(
                        score=("score", "mean"),
                        cost=("total_cost", "sum"),
                        latency_p50=("latency", "median"),
                        n=("trace_id", "count"),
                    )
                    .round(3)
                    .sort_values(["score", "cost"], ascending=[False, True])
                )
                cost_safe = pareto["cost"].where(pareto["cost"] > 0)
                pareto["score_per_$"] = (pareto["score"] / cost_safe).astype(float).round(2)
                st.dataframe(pareto, use_container_width=True)
            card_close()

    # ── RUNS ─────────────────────────────────────────────────────────
    with tab_runs:
        card_open("DATASETS", "/datasets", accent=COLOR_PURPLE, badge="catalog")
        datasets_df = get_datasets()
        if datasets_df.empty:
            st.info("// no datasets registered in Langfuse")
        else:
            st.dataframe(datasets_df, use_container_width=True)
        card_close()

        if not datasets_df.empty:
            names = datasets_df["name"].tolist()
            chosen = st.selectbox("dataset", names, index=0, key="dataset_select")
            runs_df = get_dataset_runs(chosen)

            card_open(
                f"RUNS · {chosen}", "/runs", accent=COLOR_ORANGE, badge=f"{len(runs_df)} runs"
            )
            if runs_df.empty:
                st.info("// no runs yet")
            else:
                st.dataframe(
                    runs_df.sort_values("created_at", ascending=False),
                    use_container_width=True,
                )
            card_close()

    # ── DRILLDOWN ────────────────────────────────────────────────────
    with tab_drill:
        card_open("AGENT BREAKDOWN", "/agent-stats", accent=COLOR_ORANGE, badge="per-agent")
        if not dim_scores.empty:
            agent_stats = (
                dim_scores.groupby("agent")["score"]
                .agg(["mean", "min", "max", "count"])
                .round(2)
            )
            agent_stats.columns = ["Mean", "Min", "Max", "Count"]
            agent_stats["Status"] = agent_stats["Mean"].apply(
                lambda x: "PASS" if x >= threshold else "FAIL"
            )
            st.dataframe(agent_stats, use_container_width=True)
        card_close()

        card_open("FAILED EVALUATIONS", "/failures", accent=COLOR_RED, badge="below thr")
        if not filtered_scores.empty:
            fails = (
                filtered_scores[filtered_scores["score"] < threshold]
                .sort_values("score")
                .head(50)
            )
            if fails.empty:
                st.success("// no failing evaluations - all scores >= threshold")
            else:
                st.dataframe(
                    fails[
                        ["created_at", "agent", "dimension", "score", "comment", "trace_id"]
                    ].reset_index(drop=True),
                    use_container_width=True,
                    column_config={
                        "score": st.column_config.ProgressColumn(
                            "Score", min_value=0.0, max_value=1.0, format="%.2f"
                        ),
                        "created_at": st.column_config.DatetimeColumn(
                            "Time", format="YYYY-MM-DD HH:mm"
                        ),
                    },
                )
        card_close()

    # ── RAW ──────────────────────────────────────────────────────────
    with tab_raw:
        card_open("SCORES", "/scores", accent=COLOR_ORANGE, badge=f"{len(filtered_scores)} rows")
        if not filtered_scores.empty:
            st.dataframe(
                filtered_scores.sort_values("created_at", ascending=False)
                .head(200)
                .reset_index(drop=True),
                use_container_width=True,
                column_config={
                    "score": st.column_config.ProgressColumn(
                        "Score", min_value=0.0, max_value=1.0, format="%.2f"
                    ),
                    "created_at": st.column_config.DatetimeColumn(
                        "Time", format="YYYY-MM-DD HH:mm"
                    ),
                },
            )
            csv = filtered_scores.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇  download scores csv",
                data=csv,
                file_name=f"quantnik_scores_{datetime.now():%Y%m%d_%H%M%S}.csv",
                mime="text/csv",
            )
        card_close()

    footer(threshold, len(scores_df), len(traces_df), len(obs_df))
