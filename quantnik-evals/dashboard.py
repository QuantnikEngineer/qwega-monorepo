"""Quantnik Evals Console - single-page Streamlit app.

Routes between three views via st.session_state["view"]:
- "home"  -- landing page with workspace cards
- "eval"  -- evaluation dashboard (scores, dimensions, runs, ...)
- "obs"   -- observability dashboard (cost, latency, sessions, ...)

Run with:  streamlit run dashboard.py
"""

from __future__ import annotations

import streamlit as st

from quantnik_evals.dashboard_common import (
    COLOR_CYAN,
    COLOR_DIM,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_PANEL,
    COLOR_PURPLE,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_YELLOW,
    PASS_THRESHOLD,
    card_close,
    card_open,
    date_range_picker,
    footer,
    get_observations,
    get_scores,
    get_traces,
    kpi_row,
    page_setup,
    section_label,
    sidebar_footer,
    sidebar_header,
    title,
    topbar,
)
from quantnik_evals.views import evaluation_view, observability_view


# ── Page setup + routing state ──────────────────────────────────────

page_setup("Quantnik Evals Console", "🧭")

if "view" not in st.session_state:
    st.session_state["view"] = "home"


def _set_view(name: str) -> None:
    st.session_state["view"] = name


# ── Sidebar ─────────────────────────────────────────────────────────

with st.sidebar:
    sidebar_header()

    current = st.session_state["view"]
    st.markdown(
        f"<div style='color:{COLOR_DIM}; font-size:11px;'>page · "
        f"<b style='color:{COLOR_TEXT}'>{current}</b></div>",
        unsafe_allow_html=True,
    )

    section_label("NAVIGATION", COLOR_DIM)
    st.button(
        "🏠  Home",
        use_container_width=True,
        key="nav_home",
        on_click=_set_view,
        args=("home",),
    )
    st.button(
        "📊  Evaluation",
        use_container_width=True,
        key="nav_eval",
        on_click=_set_view,
        args=("eval",),
    )
    st.button(
        "📡  Observability",
        use_container_width=True,
        key="nav_obs",
        on_click=_set_view,
        args=("obs",),
    )

    if st.button("🔄  refresh data", use_container_width=True, key="nav_refresh"):
        st.cache_data.clear()
        st.rerun()

    section_label("DATE RANGE", COLOR_DIM)
    start_ts, end_ts, from_iso, to_iso = date_range_picker(default_days=30)

    if st.session_state["view"] == "eval":
        section_label("PASS THRESHOLD", COLOR_DIM)
        threshold = st.slider(
            "pass threshold",
            0.0,
            1.0,
            PASS_THRESHOLD,
            0.05,
            label_visibility="collapsed",
        )
    else:
        threshold = PASS_THRESHOLD


# ── Load shared data once ───────────────────────────────────────────

with st.spinner("// fetching telemetry from langfuse..."):
    scores_df = get_scores(from_iso, to_iso)
    traces_df = get_traces(from_iso, to_iso)
    obs_df = get_observations(from_iso, to_iso)


# ── Sidebar filters for evaluation view ─────────────────────────────

with st.sidebar:
    if st.session_state["view"] == "eval":
        agents_all = sorted(scores_df["agent"].unique()) if not scores_df.empty else []
        section_label("AGENTS", COLOR_DIM)
        selected_agents = st.multiselect(
            "agents",
            agents_all,
            default=agents_all,
            label_visibility="collapsed",
            key="eval_agents",
        )
        section_label("DIMENSIONS", COLOR_DIM)
        if not scores_df.empty:
            dims_all = sorted(
                scores_df[scores_df["agent"].isin(selected_agents)]["dimension"].unique()
            )
        else:
            dims_all = []
        selected_dims = st.multiselect(
            "dimensions",
            dims_all,
            default=dims_all,
            label_visibility="collapsed",
            key="eval_dims",
        )
    else:
        selected_agents = sorted(scores_df["agent"].unique()) if not scores_df.empty else []
        selected_dims = (
            sorted(scores_df["dimension"].unique()) if not scores_df.empty else []
        )

    sidebar_footer()


# ── Render the active view ──────────────────────────────────────────

view = st.session_state["view"]

if view == "eval":
    evaluation_view.render(
        start_ts=start_ts,
        end_ts=end_ts,
        threshold=threshold,
        scores_df=scores_df,
        traces_df=traces_df,
        obs_df=obs_df,
        selected_agents=selected_agents,
        selected_dims=selected_dims,
    )

elif view == "obs":
    observability_view.render(
        from_iso=from_iso,
        to_iso=to_iso,
        scores_df=scores_df,
        traces_df=traces_df,
        obs_df=obs_df,
    )

else:
    # ── HOME ───────────────────────────────────────────────────────
    topbar("home", len(scores_df), len(traces_df), len(obs_df))
    title(
        "Quantnik Evals Console",
        "Pick a workspace below or use the sidebar buttons to navigate.",
    )

    total_cost = float(traces_df["total_cost"].sum()) if not traces_df.empty else 0.0
    if total_cost == 0 and not obs_df.empty:
        total_cost = float(obs_df["total_cost"].sum())

    if not obs_df.empty and obs_df["total_tokens"].sum() > 0:
        total_tokens = int(obs_df["total_tokens"].sum())
    elif not traces_df.empty and traces_df["total_tokens"].sum() > 0:
        total_tokens = int(traces_df["total_tokens"].sum())
    else:
        total_tokens = 0

    dim_scores = (
        scores_df[scores_df["dimension"] != "overall"]
        if not scores_df.empty
        else scores_df
    )
    pass_rate = (
        (dim_scores["score"] >= PASS_THRESHOLD).mean() * 100
        if not dim_scores.empty
        else 0.0
    )
    avg_score = dim_scores["score"].mean() if not dim_scores.empty else 0.0
    pass_color = COLOR_GREEN if pass_rate >= PASS_THRESHOLD * 100 else COLOR_RED

    kpi_row(
        [
            {
                "label": "evaluations",
                "value": len(scores_df["trace_id"].unique()) if not scores_df.empty else 0,
                "sub": f"{len(scores_df)} score points",
                "accent": COLOR_CYAN,
            },
            {
                "label": "pass rate",
                "value": f"{pass_rate:.0f}%",
                "sub": f"avg {avg_score:.2f} · thr {PASS_THRESHOLD:.2f}",
                "accent": pass_color,
            },
            {
                "label": "traces",
                "value": f"{len(traces_df):,}",
                "sub": f"obs {len(obs_df):,}",
                "accent": COLOR_PURPLE,
            },
            {
                "label": "total cost",
                "value": f"${total_cost:,.2f}",
                "sub": f"{total_tokens:,} tokens",
                "accent": COLOR_ORANGE,
            },
            {
                "label": "agents",
                "value": len(scores_df["agent"].unique()) if not scores_df.empty else 0,
                "sub": "across evaluations",
                "accent": COLOR_YELLOW,
            },
        ]
    )

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown(
            (
                f'<div style="background:{COLOR_PANEL}; border:1px solid #2A303C;'
                f' border-top:3px solid {COLOR_ORANGE}; border-radius:4px;'
                f' padding:18px 20px; margin-bottom:10px;">'
                f'<div style="font-size:18px; font-weight:700; color:{COLOR_ORANGE};">'
                f'// EVALUATION</div>'
                f'<div style="font-size:12px; color:{COLOR_DIM}; margin-top:4px;">'
                f"quality surface · scores · dimensions · runs</div>"
                f'<div style="font-size:11px; color:{COLOR_DIM}; margin-top:10px; line-height:1.7;">'
                f"· overall scores per agent &amp; pass/fail<br/>"
                f"· agent × dimension heatmap<br/>"
                f"· score trends over time<br/>"
                f"· quality vs cost &amp; latency<br/>"
                f"· pareto table (score-per-$)<br/>"
                f"· dataset runs history<br/>"
                f"· failed evaluations drilldown<br/>"
                f"· raw scores + csv export"
                f"</div></div>"
            ),
            unsafe_allow_html=True,
        )
        st.button(
            "open Evaluation →",
            use_container_width=True,
            key="open_eval",
            on_click=_set_view,
            args=("eval",),
            type="primary",
        )

    with c2:
        st.markdown(
            (
                f'<div style="background:{COLOR_PANEL}; border:1px solid #2A303C;'
                f' border-top:3px solid {COLOR_CYAN}; border-radius:4px;'
                f' padding:18px 20px; margin-bottom:10px;">'
                f'<div style="font-size:18px; font-weight:700; color:{COLOR_CYAN};">'
                f"// OBSERVABILITY</div>"
                f'<div style="font-size:12px; color:{COLOR_DIM}; margin-top:4px;">'
                f"operational surface · cost · perf · ops</div>"
                f'<div style="font-size:11px; color:{COLOR_DIM}; margin-top:10px; line-height:1.7;">'
                f"· daily cost &amp; token usage<br/>"
                f"· cost by agent / by model<br/>"
                f"· top expensive traces<br/>"
                f"· latency percentiles (p50…p99)<br/>"
                f"· latency trend &amp; per-agent breakdown<br/>"
                f"· error / warning counts<br/>"
                f"· sessions volume &amp; users<br/>"
                f"· model usage, cost share, pricing"
                f"</div></div>"
            ),
            unsafe_allow_html=True,
        )
        st.button(
            "open Observability →",
            use_container_width=True,
            key="open_obs",
            on_click=_set_view,
            args=("obs",),
            type="primary",
        )

    if not scores_df.empty:
        card_open("RECENT ACTIVITY", "/recent", accent=COLOR_PURPLE, badge="last 10")
        recent = scores_df.sort_values("created_at", ascending=False).head(10)
        st.dataframe(
            recent[["created_at", "agent", "dimension", "score", "trace_id"]].reset_index(
                drop=True
            ),
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
    else:
        st.info(
            "// no evaluation data yet - run `quantnik-eval --agent <name> run --dataset <name>` "
            "to populate Langfuse."
        )

    footer(PASS_THRESHOLD, len(scores_df), len(traces_df), len(obs_df))
