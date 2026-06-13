"""Shared Streamlit utilities for the Quantnik Evals dashboards.

Contains:
- QUANTNIK sunset-dark theme constants & global CSS
- Card / section / KPI helpers
- Cached Langfuse fetchers (scores, traces, observations, daily metrics,
  sessions, datasets, runs, models)
- Sidebar / top-bar / footer renderers
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import httpx
import pandas as pd
import streamlit as st

from quantnik_evals import langfuse_client as lf
from quantnik_evals.llm_judge import _ensure_ca_bundle


# ── Constants ─────────────────────────────────────────────────────────

PASS_THRESHOLD = float(os.getenv("EVAL_PASS_THRESHOLD", "0.7"))
BUILD_VERSION = "v0.4.2-a"
THEME_NAME = "sunset-dark CRT"

COLOR_ORANGE = "#FF7A45"
COLOR_CYAN = "#5CCFE6"
COLOR_GREEN = "#BAE67E"
COLOR_YELLOW = "#FFD580"
COLOR_PURPLE = "#C792EA"
COLOR_RED = "#F07178"
COLOR_DIM = "#5C6773"
COLOR_BG = "#0E1117"
COLOR_PANEL = "#161B26"
COLOR_TEXT = "#E6E1CF"


# ── Setup ─────────────────────────────────────────────────────────────


def bootstrap() -> None:
    """Idempotent setup: env + CA bundle. Call once at top of every page."""
    if not st.session_state.get("_quantnik_bootstrap_done"):
        from dotenv import load_dotenv

        load_dotenv()
        _ensure_ca_bundle()
        st.session_state["_quantnik_bootstrap_done"] = True


# ── Cached Langfuse fetchers ──────────────────────────────────────────


@st.cache_resource
def _client() -> httpx.Client:
    return lf.build_client()


@st.cache_data(ttl=120)
def get_scores(from_iso: str | None, to_iso: str | None) -> pd.DataFrame:
    from_ts = pd.Timestamp(from_iso).to_pydatetime() if from_iso else None
    to_ts = pd.Timestamp(to_iso).to_pydatetime() if to_iso else None
    return lf.fetch_scores(_client(), from_ts=from_ts, to_ts=to_ts)


@st.cache_data(ttl=120)
def get_traces(from_iso: str | None, to_iso: str | None) -> pd.DataFrame:
    from_ts = pd.Timestamp(from_iso).to_pydatetime() if from_iso else None
    to_ts = pd.Timestamp(to_iso).to_pydatetime() if to_iso else None
    try:
        return lf.fetch_traces(_client(), from_ts=from_ts, to_ts=to_ts)
    except Exception as e:  # noqa: BLE001
        st.session_state["_traces_err"] = str(e)
        return pd.DataFrame()


@st.cache_data(ttl=120)
def get_observations(from_iso: str | None, to_iso: str | None) -> pd.DataFrame:
    from_ts = pd.Timestamp(from_iso).to_pydatetime() if from_iso else None
    to_ts = pd.Timestamp(to_iso).to_pydatetime() if to_iso else None
    try:
        return lf.fetch_observations(_client(), from_ts=from_ts, to_ts=to_ts)
    except Exception as e:  # noqa: BLE001
        st.session_state["_obs_err"] = str(e)
        return pd.DataFrame()


@st.cache_data(ttl=120)
def get_daily(from_iso: str | None, to_iso: str | None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    from_ts = pd.Timestamp(from_iso).to_pydatetime() if from_iso else None
    to_ts = pd.Timestamp(to_iso).to_pydatetime() if to_iso else None
    try:
        days = lf.fetch_daily_metrics(_client(), from_ts=from_ts, to_ts=to_ts)
        return days, lf.daily_model_breakdown(days)
    except Exception as e:  # noqa: BLE001
        st.session_state["_daily_err"] = str(e)
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=300)
def get_sessions(from_iso: str | None, to_iso: str | None) -> pd.DataFrame:
    from_ts = pd.Timestamp(from_iso).to_pydatetime() if from_iso else None
    to_ts = pd.Timestamp(to_iso).to_pydatetime() if to_iso else None
    try:
        return lf.fetch_sessions(_client(), from_ts=from_ts, to_ts=to_ts)
    except Exception as e:  # noqa: BLE001
        st.session_state["_sessions_err"] = str(e)
        return pd.DataFrame()


@st.cache_data(ttl=600)
def get_datasets() -> pd.DataFrame:
    try:
        return lf.fetch_datasets(_client())
    except Exception as e:  # noqa: BLE001
        st.session_state["_datasets_err"] = str(e)
        return pd.DataFrame()


@st.cache_data(ttl=600)
def get_dataset_runs(name: str) -> pd.DataFrame:
    try:
        return lf.fetch_dataset_runs(name, _client())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)
def get_models() -> pd.DataFrame:
    try:
        return lf.fetch_models(_client())
    except Exception as e:  # noqa: BLE001
        st.session_state["_models_err"] = str(e)
        return pd.DataFrame()


# ── Theme / CSS ───────────────────────────────────────────────────────


def _css() -> str:
    return f"""
<style>
  html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stDataFrame {{
      font-family: 'JetBrains Mono','IBM Plex Mono','Fira Code',Menlo,Consolas,monospace !important;
      color: {COLOR_TEXT};
      letter-spacing: 0.2px;
  }}
  .stApp {{
      background:
          radial-gradient(ellipse at top left, rgba(255,122,69,0.06), transparent 60%),
          radial-gradient(ellipse at bottom right, rgba(92,207,230,0.05), transparent 60%),
          {COLOR_BG};
  }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  .block-container {{ padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }}
  section[data-testid="stSidebar"] {{ background: {COLOR_PANEL}; border-right: 1px solid #2A303C; }}

  .quantnik-topbar {{
      display:flex; justify-content:space-between; align-items:center;
      padding:6px 10px; margin-bottom:8px;
      border:1px solid #2A303C; border-radius:4px; background:{COLOR_PANEL}; font-size:12px;
  }}
  .quantnik-topbar .crumb {{ color:{COLOR_DIM}; }}
  .quantnik-topbar .crumb b {{ color:{COLOR_TEXT}; }}
  .quantnik-chip {{
      display:inline-block; padding:2px 8px; margin-left:8px;
      border:1px solid #2A303C; border-radius:3px; font-size:11px; color:{COLOR_DIM};
  }}
  .quantnik-chip.live  {{ color:{COLOR_GREEN};  border-color:{COLOR_GREEN}; }}
  .quantnik-chip.warn  {{ color:{COLOR_YELLOW}; border-color:{COLOR_YELLOW}; }}
  .quantnik-chip.alert {{ color:{COLOR_ORANGE}; border-color:{COLOR_ORANGE}; }}
  .quantnik-chip.model {{ color:{COLOR_PURPLE}; border-color:{COLOR_PURPLE}; }}

  div[data-baseweb="tab-list"] {{ gap:0; border-bottom:1px solid #2A303C; overflow-x:auto; }}
  div[data-baseweb="tab"] {{
      background:transparent !important; color:{COLOR_DIM} !important;
      border-radius:0 !important; padding:6px 14px !important;
      border-bottom:2px solid transparent !important; font-size:12px !important; white-space:nowrap;
  }}
  div[data-baseweb="tab"][aria-selected="true"] {{
      color:{COLOR_ORANGE} !important; border-bottom:2px solid {COLOR_ORANGE} !important;
  }}

  .kpi-row {{ display:grid; grid-template-columns:repeat(var(--cols,5),1fr); gap:10px; margin:6px 0 14px 0; }}
  .kpi {{
      background:{COLOR_PANEL}; border:1px solid #2A303C;
      border-top:2px solid var(--accent,{COLOR_ORANGE}); padding:10px 14px;
      border-radius:3px; min-height:84px;
  }}
  .kpi .label {{ color:{COLOR_DIM}; font-size:11px; text-transform:uppercase; letter-spacing:1px; }}
  .kpi .value {{ color:var(--accent,{COLOR_ORANGE}); font-size:26px; font-weight:600; line-height:1.1; margin-top:4px; }}
  .kpi .sub   {{ color:{COLOR_DIM}; font-size:11px; margin-top:6px; }}

  .quantnik-card {{
      background:{COLOR_PANEL}; border:1px solid #2A303C;
      border-top:2px solid var(--accent,{COLOR_ORANGE});
      border-radius:3px; padding:12px 14px; margin-bottom:12px;
  }}
  .quantnik-card .head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
  .quantnik-card .head .title {{ color:{COLOR_DIM}; font-size:12px; letter-spacing:0.5px; }}
  .quantnik-card .head .title b {{ color:{COLOR_TEXT}; }}
  .quantnik-card .head .badge {{ color:{COLOR_DIM}; font-size:11px; border:1px solid #2A303C; padding:1px 8px; border-radius:2px; }}

  .quantnik-footer {{
      display:flex; justify-content:space-between; align-items:center;
      margin-top:14px; padding:6px 10px; border-top:1px solid #2A303C;
      color:{COLOR_DIM}; font-size:11px;
  }}
  .stDataFrame, .stTable {{ background:{COLOR_PANEL} !important; }}
  [data-testid="stMetricValue"] {{ font-family:inherit !important; color:{COLOR_ORANGE}; }}

  .caret {{
      display:inline-block; width:8px; height:16px; background:{COLOR_ORANGE};
      margin-left:6px; vertical-align:middle; animation:blink 1s steps(2,start) infinite;
  }}
  @keyframes blink {{ to {{ visibility:hidden; }} }}

  .nav-card {{
      display:block; background:{COLOR_PANEL}; border:1px solid #2A303C;
      border-top:3px solid var(--accent,{COLOR_ORANGE});
      border-radius:4px; padding:18px 20px; margin-bottom:14px;
      text-decoration:none; color:{COLOR_TEXT};
      transition: transform 0.1s ease, border-color 0.1s ease;
  }}
  .nav-card:hover {{ transform: translateY(-2px); border-color:{COLOR_ORANGE}; }}
  .nav-card .nav-title {{ font-size:18px; font-weight:700; color:var(--accent,{COLOR_ORANGE}); }}
  .nav-card .nav-sub   {{ font-size:12px; color:{COLOR_DIM}; margin-top:4px; }}
  .nav-card .nav-list  {{ font-size:11px; color:{COLOR_DIM}; margin-top:10px; line-height:1.7; }}
</style>
"""


def page_setup(page_title: str, icon: str = "📊") -> None:
    """Call at top of every page after import."""
    st.set_page_config(
        page_title=page_title,
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    bootstrap()
    st.markdown(_css(), unsafe_allow_html=True)


# ── UI helpers ────────────────────────────────────────────────────────


def card_open(title: str, route: str, accent: str = COLOR_ORANGE, badge: str | None = None) -> None:
    """Render a styled header bar for a panel. Fully self-contained HTML."""
    badge_html = (
        f'<span style="color:{COLOR_DIM}; font-size:11px; border:1px solid #2A303C;'
        f' padding:1px 8px; border-radius:2px;">{badge}</span>'
        if badge
        else ""
    )
    html = (
        f'<div style="display:flex; justify-content:space-between; align-items:center;'
        f" margin:14px 0 6px 0; padding:6px 10px; border-left:3px solid {accent};"
        f' background:{COLOR_PANEL};">'
        f'<div style="color:{COLOR_DIM}; font-size:12px;">'
        f'// <b style="color:{COLOR_TEXT}">{title}</b> '
        f'· <span style="color:{COLOR_DIM}">{route}</span>'
        f"</div>"
        f"{badge_html}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def card_close() -> None:
    """No-op: card_open emits self-contained HTML. Kept for call-site symmetry."""
    return


def section_label(text: str, color: str = COLOR_ORANGE) -> None:
    st.markdown(
        f"<div style='color:{color}; font-size:12px; margin:10px 0 4px 0;'>// {text}</div>",
        unsafe_allow_html=True,
    )


def topbar(page: str, score_count: int, trace_count: int, obs_count: int) -> None:
    last_refresh = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    langfuse_host = (
        os.getenv("LANGFUSE_HOST", "")
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )
    live_cls = "live" if (score_count or trace_count) else "warn"
    live_txt = "LIVE" if (score_count or trace_count) else "EMPTY"
    html = (
        f'<div class="quantnik-topbar">'
        f'<div class="crumb">~/<b>quantnik-evals</b>/<b>{page}</b></div>'
        f"<div>"
        f'<span class="quantnik-chip">refresh {last_refresh}</span>'
        f'<span class="quantnik-chip">scores {score_count}</span>'
        f'<span class="quantnik-chip">traces {trace_count}</span>'
        f'<span class="quantnik-chip">obs {obs_count}</span>'
        f'<span class="quantnik-chip model">langfuse {langfuse_host or "n/a"}</span>'
        f'<span class="quantnik-chip {live_cls}">{live_txt}</span>'
        f"</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def title(text: str, subtitle: str = "") -> None:
    sub = (
        f"<div style='color:{COLOR_DIM}; font-size:12px; margin-bottom:14px;'>{subtitle}</div>"
        if subtitle
        else ""
    )
    st.markdown(
        f"<h2 style='margin:0 0 4px 0; color:{COLOR_TEXT};'>{text}<span class='caret'></span></h2>{sub}",
        unsafe_allow_html=True,
    )


def footer(threshold: float, score_count: int, trace_count: int, obs_count: int) -> None:
    html = (
        f'<div class="quantnik-footer">'
        f"<div>"
        f"<span style='color:{COLOR_GREEN}'>●</span> dashboard ready"
        f"&nbsp;·&nbsp; langfuse connected"
        f"&nbsp;·&nbsp; scores {score_count}"
        f"&nbsp;·&nbsp; traces {trace_count}"
        f"&nbsp;·&nbsp; obs {obs_count}"
        f"&nbsp;·&nbsp; threshold {threshold:.2f}"
        f"</div>"
        f"<div>{THEME_NAME} &nbsp;·&nbsp; {BUILD_VERSION}</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def sidebar_header() -> None:
    st.markdown(
        f"<div style='color:{COLOR_ORANGE}; font-size:18px; font-weight:700;'>QUANTNIK-EVALS_</div>"
        f"<div style='color:{COLOR_DIM}; font-size:11px; margin-bottom:14px;'>CONSOLE  ·  workbench</div>",
        unsafe_allow_html=True,
    )


def sidebar_footer() -> None:
    html = (
        f"<div style='margin-top:20px; padding-top:10px; border-top:1px solid #2A303C;"
        f" color:{COLOR_DIM}; font-size:11px;'>"
        f"build  <span style='color:{COLOR_TEXT}'>{BUILD_VERSION}</span><br/>"
        f"theme  <span style='color:{COLOR_TEXT}'>{THEME_NAME}</span><br/>"
        f"<span style='color:{COLOR_GREEN}'>● </span>agent online &nbsp;"
        f"<span style='color:{COLOR_ORANGE}'>quantnik</span>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def date_range_picker(default_days: int = 30) -> Tuple[pd.Timestamp, pd.Timestamp, str, str]:
    today = datetime.now(timezone.utc).date()
    default_from = today - timedelta(days=default_days)
    date_range = st.date_input(
        "date range",
        value=(default_from, today),
        label_visibility="collapsed",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start = pd.Timestamp(date_range[0], tz="UTC")
        end = pd.Timestamp(date_range[1], tz="UTC") + pd.Timedelta(days=1)
    else:
        start = pd.Timestamp(default_from, tz="UTC")
        end = pd.Timestamp(today, tz="UTC") + pd.Timedelta(days=1)
    return start, end, start.isoformat(), end.isoformat()


# ── HTML/CSS chart helpers (no JS, no images - works under strict proxies) ──

def _accent_for(value: float, threshold: float | None = None) -> str:
    if threshold is None:
        return COLOR_CYAN
    if value >= threshold:
        return COLOR_GREEN
    if value >= threshold * 0.6:
        return COLOR_YELLOW
    return COLOR_RED


def html_bar_chart(
    data: dict[str, float] | pd.Series,
    *,
    threshold: float | None = None,
    fmt: str = "{:.2f}",
    label_width: int = 140,
    color: str | None = None,
    max_value: float | None = None,
) -> None:
    """Horizontal bar chart rendered as pure HTML/CSS divs."""
    if isinstance(data, pd.Series):
        items = [(str(k), float(v)) for k, v in data.items()]
    else:
        items = [(str(k), float(v)) for k, v in data.items()]
    if not items:
        st.markdown(
            f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no data</div>",
            unsafe_allow_html=True,
        )
        return
    mx = max_value if max_value is not None else max((v for _, v in items), default=1)
    if mx <= 0:
        mx = 1
    rows = []
    for label, value in items:
        pct = max(0.0, min(100.0, (value / mx) * 100))
        bar_color = color or _accent_for(value, threshold)
        rows.append(
            f'<div style="display:flex; align-items:center; margin:3px 0; font-family:monospace; font-size:12px;">'
            f'<div style="width:{label_width}px; color:{COLOR_TEXT}; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{label}</div>'
            f'<div style="flex:1; background:#0E1117; border:1px solid #2A303C; height:18px; position:relative;">'
            f'<div style="width:{pct:.1f}%; background:{bar_color}; height:100%;"></div></div>'
            f'<div style="width:80px; text-align:right; color:{bar_color}; padding-left:8px;">{fmt.format(value)}</div>'
            f"</div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def html_grouped_bars(
    df: pd.DataFrame,
    *,
    label_col: str | None = None,
    value_cols: list[str] | None = None,
    colors: list[str] | None = None,
    fmt: str = "{:,.0f}",
    label_width: int = 140,
    max_value: float | None = None,
) -> None:
    """Stacked-by-row grouped bar chart in HTML/CSS."""
    if df.empty:
        st.markdown(
            f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no data</div>",
            unsafe_allow_html=True,
        )
        return
    if value_cols is None:
        value_cols = [c for c in df.columns if c != label_col and pd.api.types.is_numeric_dtype(df[c])]
    if not value_cols:
        st.markdown(
            f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no numeric columns</div>",
            unsafe_allow_html=True,
        )
        return
    palette = colors or [COLOR_CYAN, COLOR_ORANGE, COLOR_PURPLE, COLOR_YELLOW, COLOR_GREEN]

    if label_col is None:
        labels = [str(i) for i in df.index]
    else:
        labels = [str(v) for v in df[label_col]]
    sub = df[value_cols].fillna(0).astype(float)
    mx = max_value if max_value is not None else float(sub.values.max() or 1)
    if mx <= 0:
        mx = 1

    legend = " ".join(
        f'<span style="color:{palette[i % len(palette)]};">■</span> <span style="color:{COLOR_DIM};">{c}</span>'
        for i, c in enumerate(value_cols)
    )
    out = [f'<div style="font-family:monospace; font-size:11px; margin-bottom:6px;">{legend}</div>']
    for label, row in zip(labels, sub.itertuples(index=False, name=None)):
        bars = ""
        for i, (col, val) in enumerate(zip(value_cols, row)):
            pct = max(0.0, min(100.0, (val / mx) * 100))
            c = palette[i % len(palette)]
            bars += (
                f'<div style="display:flex; align-items:center; margin:1px 0; font-family:monospace; font-size:11px;">'
                f'<div style="width:60px; color:{COLOR_DIM};">{col}</div>'
                f'<div style="flex:1; background:#0E1117; border:1px solid #2A303C; height:14px;">'
                f'<div style="width:{pct:.1f}%; background:{c}; height:100%;"></div></div>'
                f'<div style="width:90px; text-align:right; color:{c}; padding-left:8px;">{fmt.format(val)}</div>'
                f"</div>"
            )
        out.append(
            f'<div style="margin:6px 0; padding:6px 8px; border-left:2px solid {COLOR_PANEL};">'
            f'<div style="color:{COLOR_TEXT}; font-size:12px; font-weight:600;">{label}</div>'
            f"{bars}</div>"
        )
    st.markdown("".join(out), unsafe_allow_html=True)


def html_sparkline(
    values: list[float] | pd.Series,
    *,
    width: int = 220,
    height: int = 36,
    color: str = COLOR_CYAN,
    threshold: float | None = None,
) -> None:
    """Inline SVG sparkline (single-line trend visual). SVG is HTML-native."""
    if isinstance(values, pd.Series):
        vals = [float(v) for v in values.dropna().tolist()]
    else:
        vals = [float(v) for v in values if pd.notna(v)]
    if not vals:
        st.markdown(
            f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no data</div>",
            unsafe_allow_html=True,
        )
        return
    mn, mx = min(vals), max(vals)
    span = (mx - mn) or 1
    step = width / max(len(vals) - 1, 1)
    pts = " ".join(
        f"{i * step:.1f},{height - ((v - mn) / span) * height:.1f}" for i, v in enumerate(vals)
    )
    th_line = ""
    if threshold is not None and mn <= threshold <= mx:
        y = height - ((threshold - mn) / span) * height
        th_line = (
            f'<line x1="0" y1="{y:.1f}" x2="{width}" y2="{y:.1f}" '
            f'stroke="{COLOR_DIM}" stroke-dasharray="3 3" stroke-width="1"/>'
        )
    svg = (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="vertical-align:middle;">'
        f"{th_line}"
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f"</svg>"
    )
    st.markdown(svg, unsafe_allow_html=True)


def html_grouped_bar_chart(
    series_by_label: dict[str, dict[str, float]],
    *,
    colors: dict[str, str] | None = None,
    label_width: int = 100,
    fmt: str = "{:,.0f}",
) -> None:
    """Side-by-side grouped bars per category row."""
    if not series_by_label:
        st.markdown(
            f"<div style='color:{COLOR_DIM}; font-size:12px;'>// no data</div>",
            unsafe_allow_html=True,
        )
        return
    all_series = sorted({s for groups in series_by_label.values() for s in groups})
    palette = colors or {
        s: c
        for s, c in zip(
            all_series,
            [COLOR_CYAN, COLOR_ORANGE, COLOR_PURPLE, COLOR_YELLOW, COLOR_GREEN, COLOR_RED],
        )
    }
    mx = max(
        (v for groups in series_by_label.values() for v in groups.values() if v is not None),
        default=1,
    ) or 1

    legend = " ".join(
        f'<span style="color:{palette.get(s, COLOR_CYAN)};">■</span> '
        f'<span style="color:{COLOR_DIM}; margin-right:8px;">{s}</span>'
        for s in all_series
    )
    out = [f'<div style="font-family:monospace; font-size:11px; margin:4px 0 8px 0;">{legend}</div>']
    for label, groups in series_by_label.items():
        bars = ""
        for s in all_series:
            val = float(groups.get(s, 0) or 0)
            pct = max(0.0, min(100.0, (val / mx) * 100))
            c = palette.get(s, COLOR_CYAN)
            bars += (
                f'<div style="display:flex; align-items:center; margin:1px 0; font-family:monospace; font-size:11px;">'
                f'<div style="width:60px; color:{COLOR_DIM};">{s}</div>'
                f'<div style="flex:1; background:#0E1117; border:1px solid #2A303C; height:12px;">'
                f'<div style="width:{pct:.1f}%; background:{c}; height:100%;"></div></div>'
                f'<div style="width:90px; text-align:right; color:{c}; padding-left:8px;">{fmt.format(val)}</div>'
                f"</div>"
            )
        out.append(
            f'<div style="margin:6px 0; padding:6px 8px; border-left:2px solid {COLOR_PANEL};">'
            f'<div style="color:{COLOR_TEXT}; font-size:12px; font-weight:600;">{label}</div>'
            f"{bars}</div>"
        )
    st.markdown("".join(out), unsafe_allow_html=True)


def kpi_row(tiles: list[dict], cols: int = 5) -> None:
    """Render a KPI row. Each tile dict: {label, value, sub, accent}."""
    parts: list[str] = []
    for t in tiles:
        accent = t.get("accent", COLOR_ORANGE)
        value_style = f"color:{accent}" if t.get("color_value", True) else ""
        parts.append(
            f'<div class="kpi" style="--accent:{accent}">'
            f'<div class="label">{t["label"]}</div>'
            f'<div class="value" style="{value_style}">{t["value"]}</div>'
            f'<div class="sub">{t.get("sub","")}</div>'
            f"</div>"
        )
    html = f'<div class="kpi-row" style="--cols:{cols}">{"".join(parts)}</div>'
    st.markdown(html, unsafe_allow_html=True)
