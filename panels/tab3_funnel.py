import streamlit as st
from streamlit_sortables import sort_items
from ga4_client import run_report, run_funnel_report
from utils.formatters import num, pct
from utils.charts import funnel_chart, callout, BEFORE_COLOR, AFTER_COLOR

# Default funnel for each side. Drag-and-drop in the UI overrides these for the session;
# edit here to change the permanent default.
CUSTOM_FUNNEL_BEFORE = [
    "page_view",
    "view_item",
    "add_to_cart",
    "begin_checkout",
    "add_payment_info",
    "purchase",
]
CUSTOM_FUNNEL_AFTER = [
    "page_view",
    "view_item_list",
    "view_item",
    "add_to_cart",
    "view_cart",
    "begin_checkout",
    "add_shipping_info",
    "add_payment_info",
    "purchase",
]


def _load_period_events(period: tuple) -> list:
    """All events firing in a single period."""
    df, _ = run_report(
        dimensions=("eventName",), metrics=("eventCount",),
        single=period, order_by_metric="eventCount", limit=1000,
    )
    return sorted(df[df["eventCount"] > 0]["eventName"].tolist())


def _funnel_builder(side_key: str, period_label: str, period: tuple, all_names: list,
                     default_steps: list, color: str, const_name: str):
    funnel_key = f"{side_key}_funnel_steps"
    reset_n_key = f"{side_key}_reset_n"
    if reset_n_key not in st.session_state:
        st.session_state[reset_n_key] = 0
    if funnel_key not in st.session_state:
        st.session_state[funnel_key] = [s for s in default_steps if s in all_names]

    st.markdown(f"**{period_label}** · {len(all_names)} events available")

    search = st.text_input(
        "Search events", key=f"{side_key}_search",
        placeholder=f"type to search {len(all_names)} events…",
    )

    funnel = st.session_state[funnel_key]
    available = [e for e in all_names if e not in funnel]
    available_display = [e for e in available if search.lower() in e.lower()] if search else []

    pool_header = (
        f"Search results ({len(available_display)}/{len(available)})" if search
        else "Type above to find events"
    )
    sortable_input = [
        {"header": pool_header, "items": available_display},
        {"header": "Funnel Steps (drag to reorder)", "items": funnel},
    ]
    result = sort_items(
        sortable_input,
        multi_containers=True,
        direction="vertical",
        key=f"{side_key}_sortable_{st.session_state[reset_n_key]}_{search}",
    )
    steps = result[1]["items"]
    st.session_state[funnel_key] = steps

    if st.button("Reset to default", key=f"{side_key}_reset"):
        st.session_state[funnel_key] = [s for s in default_steps if s in all_names]
        st.session_state[reset_n_key] += 1
        st.rerun()

    if steps:
        if len(steps) >= 2:
            try:
                funnel_df = run_funnel_report(tuple(steps), period, is_open=False)
                if not funnel_df.empty and funnel_df["activeUsers"].sum() > 0:
                    st.plotly_chart(
                        funnel_chart(funnel_df["step"].tolist(), funnel_df["activeUsers"].tolist(),
                                     f"{period_label} Funnel (closed)", color=color),
                        use_container_width=True,
                    )
                    table = funnel_df.rename(columns={
                        "step": "Step", "activeUsers": "Users",
                        "completionRate": "Completion Rate",
                        "abandonments": "Abandoned", "abandonmentRate": "Abandonment Rate",
                    })
                    table["Users"]             = table["Users"].apply(num)
                    table["Completion Rate"]   = table["Completion Rate"].apply(lambda v: pct(v * 100))
                    table["Abandoned"]         = table["Abandoned"].apply(num)
                    table["Abandonment Rate"]  = table["Abandonment Rate"].apply(lambda v: pct(v * 100))
                    st.dataframe(table, use_container_width=True, hide_index=True)
                else:
                    st.info("No users completed step 1 of this funnel in this period.")
            except Exception as e:
                st.error(f"GA4 funnel query failed: {e}")
        else:
            st.info("Add at least one more event — a closed funnel needs 2+ sequential steps.")

        code_str = f"{const_name} = [\n" + "\n".join(f'    "{s}",' for s in steps) + "\n]"
        st.code(code_str, language="python")
    else:
        st.info("Drag events from the pool above into Funnel Steps to build this funnel.")


def render(before: tuple, after: tuple):
    # ── 3.1 — Custom Funnel Builder (Before vs After) ────────────────────────
    st.subheader("3.1 — Custom Funnel Builder")
    callout(
        "Closed funnels — GA4's real Funnel Reporting API, not raw event counts. Each step only "
        "counts users who completed every prior step in order, same user, sequentially. "
        "Each side pulls its own period's events into its own picker — Before and After can use "
        "entirely different events, since the old tracking didn't fire the same events as the new "
        "pixel. Build each funnel, then copy its code box into `CUSTOM_FUNNEL_BEFORE` / "
        "`CUSTOM_FUNNEL_AFTER` near the top of `panels/tab3_funnel.py` to hardcode it.",
        kind="info",
    )

    try:
        before_names = _load_period_events(before)
    except Exception as e:
        st.error(f"GA4 query failed (before period): {e}")
        before_names = []

    try:
        after_names = _load_period_events(after)
    except Exception as e:
        st.error(f"GA4 query failed (after period): {e}")
        after_names = []

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        _funnel_builder("before", "Before Period", before, before_names,
                         CUSTOM_FUNNEL_BEFORE, BEFORE_COLOR, "CUSTOM_FUNNEL_BEFORE")
    with fcol2:
        _funnel_builder("after", "After Period", after, after_names,
                         CUSTOM_FUNNEL_AFTER, AFTER_COLOR, "CUSTOM_FUNNEL_AFTER")
