import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.formatters import delta_pct, num

# Optimizers brand palette
BRAND_GREEN   = "#6ae499"   # primary accent
BRAND_DARK    = "#0e1c26"   # dark bg
BRAND_DARKEST = "#020601"   # deepest black

BEFORE_COLOR  = "#607d8b"   # steel blue-grey — neutral historical state
AFTER_COLOR   = "#6ae499"   # brand green — improved state


# ── Global CSS ────────────────────────────────────────────────────────────────

def inject_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText, .stCaption,
    h1, h2, h3, h4, h5, h6, p, label, div, span, td, th, button {
        font-family: 'Sora', sans-serif !important;
    }

    /* KPI cards */
    .kpi-block { margin-bottom: 4px; }
    .kpi-label {
        font-size: 11px;
        font-weight: 700;
        color: #6ae499;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
        opacity: 0.75;
    }
    .kpi-cards {
        display: flex;
        gap: 6px;
        align-items: stretch;
    }
    .kpi-card {
        flex: 1;
        border-radius: 12px;
        padding: 14px 10px;
        text-align: center;
        min-width: 0;
    }
    .kpi-card-before {
        background: rgba(96,125,139,0.10);
        border: 1px solid rgba(96,125,139,0.30);
    }
    .kpi-card-after {
        background: rgba(106,228,153,0.08);
        border: 1px solid rgba(106,228,153,0.30);
    }
    .kpi-period {
        font-size: 9px;
        font-weight: 900;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        margin-bottom: 6px;
        font-family: 'Sora', sans-serif !important;
    }
    .kpi-period-before { color: #90a4ae; }
    .kpi-period-after  { color: #6ae499; }
    .kpi-value {
        font-size: 20px;
        font-weight: 800;
        color: #e8f0f4;
        line-height: 1;
        word-break: break-all;
        font-family: 'Sora', sans-serif !important;
    }
    .kpi-delta-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0 6px;
        min-width: 52px;
    }
    .kpi-arrow { font-size: 18px; line-height: 1; }
    .kpi-pct   { font-size: 11px; font-weight: 800; margin-top: 2px; }
    .kpi-note {
        font-size: 11px;
        color: #607d8b;
        margin-top: 8px;
        line-height: 1.4;
        padding: 0 2px;
    }

    /* Callouts */
    .dash-callout {
        border-radius: 12px;
        padding: 15px 19px;
        margin: 6px 0 14px 0;
        font-size: 14px;
        line-height: 1.75;
        font-family: 'Sora', sans-serif !important;
    }
    .dash-callout-info    { background:rgba(106,228,153,.08); border-left:3px solid #6ae499; color:#a8edca; }
    .dash-callout-warning { background:rgba(255,183,77,.10);  border-left:3px solid #ffb74d; color:#ffe0a0; }
    .dash-callout-success { background:rgba(106,228,153,.12); border-left:3px solid #6ae499; color:#6ae499; }
    .dash-callout-error   { background:rgba(244,67,54,.10);   border-left:3px solid #f44336; color:#ef9a9a; }

    /* Period legend chips */
    .period-legend { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px; }
    .period-chip {
        display:inline-flex; align-items:center; gap:5px;
        padding:4px 12px; border-radius:20px;
        font-size:11px; font-weight:700;
        font-family: 'Sora', sans-serif !important;
    }
    .chip-before {
        background:rgba(96,125,139,0.12);
        color:#90a4ae;
        border:1px solid rgba(96,125,139,0.28);
    }
    .chip-after {
        background:rgba(106,228,153,0.10);
        color:#6ae499;
        border:1px solid rgba(106,228,153,0.28);
    }

    /* Table styling */
    [data-testid="stDataFrame"] thead th {
        background-color: #0b1520 !important;
        color: #6ae499 !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        font-family: 'Sora', sans-serif !important;
    }
    [data-testid="stDataFrame"] tbody tr:nth-child(even) td {
        background-color: rgba(106,228,153,0.02) !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #0b1520 !important; }
    .sidebar-chip {
        border-radius: 10px; padding: 6px 10px;
        font-size: 12px; margin-bottom: 6px;
        font-family: 'Sora', sans-serif !important;
    }
    .sidebar-before { background:rgba(96,125,139,0.12); color:#90a4ae; border:1px solid rgba(96,125,139,0.25); }
    .sidebar-after  { background:rgba(106,228,153,0.10); color:#6ae499; border:1px solid rgba(106,228,153,0.25); }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #6ae499 !important;
        border-bottom-color: #6ae499 !important;
    }

    /* Subheader accent */
    h3 { color: #e8f0f4 !important; }
    h4 { color: #a8edca !important; }

    /* Metric overrides */
    [data-testid="stMetricValue"] { font-family: 'Sora', sans-serif !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"] { font-family: 'Sora', sans-serif !important; }
    </style>
    """, unsafe_allow_html=True)


# ── Period legend ─────────────────────────────────────────────────────────────

def period_legend(before: tuple, after: tuple):
    st.markdown(f"""
    <div class="period-legend">
        <span class="period-chip chip-before">● Before &nbsp; {before[0]} → {before[1]}</span>
        <span class="period-chip chip-after">● After &nbsp;&nbsp; {after[0]} → {after[1]}</span>
    </div>
    """, unsafe_allow_html=True)


# ── KPI before/after card ─────────────────────────────────────────────────────

def kpi(col, label: str, before_val: float, after_val: float,
        format_fn=None, good: str = "up", note: str = None):
    fmt = format_fn or num
    d = delta_pct(before_val, after_val)
    is_good = (good == "up" and after_val >= before_val) or \
              (good == "down" and after_val <= before_val)
    delta_color = "#6ae499" if is_good else "#ef5350"

    if after_val > before_val:
        arrow = "↑"
    elif after_val < before_val:
        arrow = "↓"
    else:
        arrow = "→"

    note_html = f'<div class="kpi-note">{note}</div>' if note else ""

    html = f"""
    <div class="kpi-block">
        <div class="kpi-label">{label}</div>
        <div class="kpi-cards">
            <div class="kpi-card kpi-card-before">
                <div class="kpi-period kpi-period-before">Before</div>
                <div class="kpi-value">{fmt(before_val)}</div>
            </div>
            <div class="kpi-delta-wrap">
                <span class="kpi-arrow" style="color:{delta_color}">{arrow}</span>
                <span class="kpi-pct"   style="color:{delta_color}">{abs(d):.1f}%</span>
            </div>
            <div class="kpi-card kpi-card-after">
                <div class="kpi-period kpi-period-after">After</div>
                <div class="kpi-value">{fmt(after_val)}</div>
            </div>
        </div>
        {note_html}
    </div>
    """
    with col:
        st.markdown(html, unsafe_allow_html=True)


# ── Callout ───────────────────────────────────────────────────────────────────

def callout(text: str, kind: str = "info"):
    icons = {"info": "ℹ️", "warning": "⚠️", "success": "✅", "error": "❌"}
    icon = icons.get(kind, "ℹ️")
    st.markdown(
        f'<div class="dash-callout dash-callout-{kind}">{icon}&nbsp; {text}</div>',
        unsafe_allow_html=True,
    )


# ── Charts ────────────────────────────────────────────────────────────────────

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#a8c4cc", size=12, family="Sora, sans-serif"),
    legend=dict(orientation="h", y=1.08, x=0, font=dict(size=12, family="Sora, sans-serif")),
    margin=dict(t=60, b=40, l=0, r=0),
    height=420,
    xaxis=dict(gridcolor="rgba(106,228,153,0.06)", zerolinecolor="rgba(106,228,153,0.08)"),
    yaxis=dict(gridcolor="rgba(106,228,153,0.06)", zerolinecolor="rgba(106,228,153,0.08)"),
)


def grouped_bar(df: pd.DataFrame, x_col: str, before_col: str, after_col: str,
                title: str = "", x_label: str = "", y_label: str = "",
                horizontal: bool = False) -> go.Figure:
    fig = go.Figure()
    orientation = "h" if horizontal else "v"
    x_b = df[before_col] if horizontal else df[x_col]
    y_b = df[x_col]      if horizontal else df[before_col]
    x_a = df[after_col]  if horizontal else df[x_col]
    y_a = df[x_col]      if horizontal else df[after_col]

    fig.add_trace(go.Bar(
        name="Before", x=x_b, y=y_b,
        marker_color=BEFORE_COLOR,
        marker_line_width=0,
        orientation=orientation,
        opacity=0.80,
    ))
    fig.add_trace(go.Bar(
        name="After", x=x_a, y=y_a,
        marker_color=AFTER_COLOR,
        marker_line_width=0,
        orientation=orientation,
        opacity=0.90,
    ))
    layout = {**_LAYOUT, "title": dict(text=title, font=dict(size=14, color="#a8edca", family="Sora, sans-serif")),
              "barmode": "group",
              "xaxis_title": x_label, "yaxis_title": y_label}
    fig.update_layout(**layout)
    return fig


def funnel_chart(steps: list, values: list, title: str = "", color: str = None) -> go.Figure:
    fig = go.Figure(go.Funnel(
        y=steps, x=values,
        textinfo="value+percent previous",
        marker_color=color or AFTER_COLOR,
        connector=dict(line=dict(color="rgba(106,228,153,0.15)", width=1)),
    ))
    layout = {**_LAYOUT, "title": dict(text=title, font=dict(size=14, color="#a8edca", family="Sora, sans-serif")), "height": 420}
    fig.update_layout(**layout)
    return fig


def donut(labels: list, values: list, title: str = "") -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.48,
        textinfo="label+percent",
        marker=dict(line=dict(color="rgba(0,0,0,0.3)", width=1)),
    ))
    layout = {**_LAYOUT, "title": dict(text=title, font=dict(size=14, color="#a8edca", family="Sora, sans-serif")), "height": 360,
              "margin": dict(t=60, b=20, l=0, r=0)}
    fig.update_layout(**layout)
    return fig
