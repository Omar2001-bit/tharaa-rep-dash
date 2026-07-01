import re
import streamlit as st
import pandas as pd
from ga4_client import run_report, merge_periods

CONSENT_TABLE = [
    ("analytics_storage",      "hardcoded GRANTED", "DENIED default → updates on accept ✅"),
    ("ad_storage",             "hardcoded GRANTED", "DENIED default → updates on accept ✅"),
    ("ad_user_data",           "hardcoded GRANTED", "DENIED default → updates on accept ✅"),
    ("ad_personalization",     "hardcoded GRANTED", "DENIED default → updates on accept ✅"),
    ("functionality_storage",  "not set",           "DENIED default ✅"),
    ("personalization_storage","not set",           "DENIED default ✅"),
    ("security_storage",       "not set",           "GRANTED default ✅"),
]

TOOL_STATUS = [
    ("Microsoft Clarity",  "Not running (GTM dormant)",      "Active, consent-gated ✅"),
    ("Hotjar",             "Running unconditionally ⚠️",     "Running, consent-gated ✅"),
    ("GA4",                "Via WPM, hardcoded granted ⚠️",  "Via GTM, consent-gated ✅"),
]


def render(before: tuple, after: tuple):
    # ── 7.1 Consent Mode Status ───────────────────────────────────────────────
    st.subheader("7.1 — Consent Mode v2 Status")

    consent_df = pd.DataFrame(CONSENT_TABLE, columns=["Signal", "Before", "After"])
    st.dataframe(consent_df, use_container_width=True, hide_index=True)

    st.markdown("**Analytics Tools — Before vs After**")
    tools_df = pd.DataFrame(TOOL_STATUS, columns=["Tool", "Before", "After"])
    st.dataframe(tools_df, use_container_width=True, hide_index=True)


    st.divider()

    # ── 7.2 Checkout Token Redaction verification ─────────────────────────────
    st.subheader("7.2 — Checkout Token Redaction")
    st.caption("Checkout URLs contain per-session tokens — these are redacted before reaching GA4.")

    try:
        df4, _ = run_report(
            dimensions=("pagePath",),
            metrics=("sessions",),
            before=before, after=after,
            limit=100,
        )
        merged4 = merge_periods(df4, ["pagePath"], ["sessions"])
        token_pat = re.compile(r"/checkouts/[a-z0-9]{20,}", re.IGNORECASE)
        merged4["Has Token?"] = merged4["pagePath"].apply(
            lambda p: "⚠️ Raw token" if token_pat.search(str(p)) else "✅ Clean"
        )
        exposed = merged4[merged4["Has Token?"] == "⚠️ Raw token"]
        if exposed.empty:
            st.success("No raw checkout tokens found in page paths — redaction working correctly.")
        else:
            st.warning(f"{len(exposed)} page paths with raw checkout tokens still visible:")
            st.dataframe(exposed[["pagePath", "sessions_before", "sessions_after", "Has Token?"]],
                         use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"GA4 query failed: {e}")
