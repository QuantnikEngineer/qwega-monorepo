"""Diagnostic page - verifies Streamlit chart rendering & data fetches."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Diagnostic", page_icon="🩺", layout="wide")

with st.sidebar:
    st.markdown("### Navigation")
    st.link_button("🏠  Home", url="/", use_container_width=True)
    st.link_button("📊  Evaluation", url="/Evaluation", use_container_width=True)
    st.link_button("📡  Observability", url="/Observability", use_container_width=True)
    st.link_button("🩺  Diagnostic", url="/Diagnostic", use_container_width=True)

st.title("🩺 Diagnostic")

st.subheader("1a. Plain Streamlit chart (Vega/Altair JS)")
try:
    demo = pd.DataFrame({"a": [3, 1, 4, 1, 5, 9, 2, 6], "b": [2, 7, 1, 8, 2, 8, 1, 8]})
    st.bar_chart(demo)
    st.line_chart(demo)
    st.success("Plain charts rendered (means Vega/Altair JS is allowed).")
except Exception as e:
    st.error(f"Plain chart failed: {e!r}")
    st.code(traceback.format_exc())

st.subheader("1b. Matplotlib chart (server-side PNG — no JS)")
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.bar(["a", "b", "c", "d", "e", "f", "g", "h"], [3, 1, 4, 1, 5, 9, 2, 6])
    ax.set_title("matplotlib bar chart")
    st.pyplot(fig, clear_figure=True)

    fig2, ax2 = plt.subplots(figsize=(8, 3))
    ax2.plot([1, 2, 3, 4, 5], [2, 7, 1, 8, 2], marker="o")
    ax2.plot([1, 2, 3, 4, 5], [3, 1, 4, 1, 5], marker="x")
    ax2.set_title("matplotlib line chart")
    st.pyplot(fig2, clear_figure=True)

    st.success("Matplotlib renders -> charts work as PNG. We'll switch the app to matplotlib.")
except Exception as e:
    st.error(f"Matplotlib chart failed: {e!r}")
    st.code(traceback.format_exc())

st.subheader("1d. Pure HTML/CSS bar chart (no JS, no image)")
try:
    bars = [("api", 80, "#5CCFE6"), ("auth", 45, "#BAE67E"),
            ("db", 92, "#FF7A45"), ("cache", 30, "#C792EA")]
    rows_html = ""
    for label, pct, color in bars:
        rows_html += (
            f'<div style="display:flex;align-items:center;margin:4px 0;font-family:monospace;">'
            f'<div style="width:80px;color:#E6E1CF;">{label}</div>'
            f'<div style="flex:1;background:#161B26;border:1px solid #2A303C;height:18px;">'
            f'<div style="width:{pct}%;background:{color};height:100%;"></div></div>'
            f'<div style="width:60px;text-align:right;color:#E6E1CF;">{pct}</div>'
            f"</div>"
        )
    st.markdown(rows_html, unsafe_allow_html=True)
    st.caption("If you see colored bars above, HTML/CSS visualizations work.")
except Exception as e:
    st.error(f"HTML/CSS bars failed: {e!r}")

st.subheader("1c. st.image (the simplest possible visual)")
try:
    import io

    fig3, ax3 = plt.subplots(figsize=(6, 2))
    ax3.text(0.5, 0.5, "If you see this image, st.image works",
             ha="center", va="center", fontsize=14)
    ax3.set_axis_off()
    buf = io.BytesIO()
    fig3.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    st.image(buf, caption="rendered via st.image")
except Exception as e:
    st.error(f"st.image failed: {e!r}")
    st.code(traceback.format_exc())

st.subheader("2. Environment")
st.json(
    {
        "python": sys.version,
        "streamlit": __import__("streamlit").__version__,
        "pandas": pd.__version__,
        "cwd": os.getcwd(),
        "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST", "(unset)"),
        "SSL_CERT_FILE": os.getenv("SSL_CERT_FILE", "(unset)"),
        "EVAL_PASS_THRESHOLD": os.getenv("EVAL_PASS_THRESHOLD", "(unset)"),
    }
)

st.subheader("3. Langfuse fetch (last 7 days)")

from_ts = datetime.now(timezone.utc) - timedelta(days=7)
to_ts = datetime.now(timezone.utc)

try:
    from quantnik_evals import langfuse_client as lf

    client = lf.build_client()
    st.write("`build_client()` OK ·", "base_url =", client.base_url)

    scores = lf.fetch_scores(client, from_ts=from_ts, to_ts=to_ts)
    st.write(f"**scores**: {len(scores)} rows  ·  cols: {list(scores.columns)}")
    if not scores.empty:
        st.dataframe(scores.head(5))

    traces = lf.fetch_traces(client, from_ts=from_ts, to_ts=to_ts)
    st.write(f"**traces**: {len(traces)} rows  ·  cols: {list(traces.columns)}")
    if not traces.empty:
        st.dataframe(traces.head(5))

    obs = lf.fetch_observations(client, from_ts=from_ts, to_ts=to_ts)
    st.write(f"**observations**: {len(obs)} rows  ·  cols: {list(obs.columns)}")
    if not obs.empty:
        st.dataframe(obs.head(5))

    daily = lf.fetch_daily_metrics(client, from_ts=from_ts, to_ts=to_ts)
    st.write(f"**daily**: {len(daily)} rows")
    if not daily.empty:
        st.dataframe(daily.head(5))

    st.success("Langfuse fetchers OK.")
except Exception as e:
    st.error(f"Langfuse fetch failed: {e!r}")
    st.code(traceback.format_exc())

st.subheader("4. Chart on real Langfuse score data")
try:
    if not scores.empty:
        scores2 = scores.copy()
        scores2["created_at"] = pd.to_datetime(scores2["created_at"], utc=True, errors="coerce")
        scores2["date"] = scores2["created_at"].dt.date
        chart = scores2.groupby(["date", "agent"])["score"].mean().reset_index()
        wide = chart.pivot(index="date", columns="agent", values="score")
        st.line_chart(wide)
        st.success("Real-data chart rendered.")
    else:
        st.info("No score rows to chart.")
except Exception as e:
    st.error(f"Real-data chart failed: {e!r}")
    st.code(traceback.format_exc())

st.subheader("5. st.bar_chart with color=column (the suspect pattern)")
try:
    bool_df = pd.DataFrame(
        {"Agent": ["a", "b", "c", "d"], "Score": [0.8, 0.5, 0.9, 0.3]}
    )
    bool_df["Pass"] = bool_df["Score"] >= 0.7
    st.bar_chart(bool_df, x="Agent", y="Score", color="Pass")
    st.success("Bool-color bar chart rendered.")
except Exception as e:
    st.error(f"Bool-color chart failed: {e!r}")
    st.code(traceback.format_exc())
