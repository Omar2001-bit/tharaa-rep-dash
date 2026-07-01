import streamlit as st
from datetime import date

from config import (
    DEFAULT_BEFORE_START, DEFAULT_BEFORE_END,
    DEFAULT_AFTER_START,  DEFAULT_AFTER_END,
    PROPERTY_ID,
)
from panels import (
    tab1_conversion,
    tab2_channels,
    tab3_funnel,
    tab5_behavioral,
    tab6_dimensions,
    tab7_infrastructure,
)
from utils.charts import inject_styles, period_legend

st.set_page_config(
    page_title="Tharaa Shop — GA4 Audit Dashboard",
    page_icon="📊",
    layout="wide",
)

inject_styles()

st.title("Tharaa Shop — Before vs After GA4 Audit")
st.caption(f"Property: {PROPERTY_ID}  |  Data via Google Analytics Data API")

# ── Date pickers ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Date Periods")

    st.subheader("Before Period")
    b_start = st.date_input("Start", value=date.fromisoformat(DEFAULT_BEFORE_START), key="b_start")
    b_end   = st.date_input("End",   value=date.fromisoformat(DEFAULT_BEFORE_END),   key="b_end")

    st.subheader("After Period")
    a_start = st.date_input("Start", value=date.fromisoformat(DEFAULT_AFTER_START), key="a_start")
    a_end   = st.date_input("End",   value=date.fromisoformat(DEFAULT_AFTER_END),   key="a_end")

    if b_end >= a_start:
        st.error("Periods overlap — before end must be before after start.")
        st.stop()

    if st.button("Clear cache", help="Force refresh all GA4 data"):
        st.cache_data.clear()
        st.success("Cache cleared.")

    st.divider()
    st.markdown(f"""
    <div class="sidebar-chip sidebar-before">● Before<br>
    <small>{b_start} → {b_end}</small></div>
    <div class="sidebar-chip sidebar-after">● After<br>
    <small>{a_start} → {a_end}</small></div>
    """, unsafe_allow_html=True)

before = (str(b_start), str(b_end))
after  = (str(a_start), str(a_end))

period_legend(before, after)

# ── Tab layout ────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "1 · Conversions",
    "2 · Behavioral",
    "3 · Channels",
    "4 · Funnel",
    "5 · Dimensions & Products",
    "6 · Infrastructure",
])

with tabs[0]:
    tab1_conversion.render(before, after)

with tabs[1]:
    tab5_behavioral.render(before, after)

with tabs[2]:
    tab2_channels.render(before, after)

with tabs[3]:
    tab3_funnel.render(before, after)

with tabs[4]:
    tab6_dimensions.render(before, after)

with tabs[5]:
    tab7_infrastructure.render(before, after)
