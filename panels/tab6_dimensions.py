import streamlit as st
import plotly.express as px
from ga4_client import run_report, string_filter, merge_periods, and_filter, not_filter
from utils.formatters import num, egp, pct
from utils.charts import callout, kpi

CUSTOMER_DIMS = [
    ("customEvent:login_status",             "Login Status"),
    ("customUser:order_count_bucket",        "Order Count Bucket"),
]


def _blank_pct(df, dim_col, val_col):
    total = df[val_col].sum()
    if total == 0:
        return 0.0
    blank = df[df[dim_col].isin(["(not set)", ""])][val_col].sum()
    return blank / total * 100


def _param_findings(df, label_col, primary_col, sessions_col=None, transactions_col=None):
    """Computed, data-driven bullets from a dimension breakdown — not static copy."""
    if df.empty:
        return ["No data available yet for this parameter."]

    total = df[primary_col].sum()
    if total == 0:
        return [f"`{label_col.split(':')[-1]}` values exist but none carry any {primary_col} yet."]

    findings = []
    ranked = df.sort_values(primary_col, ascending=False)
    top = ranked.iloc[0]
    top_pct = top[primary_col] / total * 100
    findings.append(
        f"**{top[label_col]}** accounts for **{top_pct:.0f}%** of the total "
        f"(**{num(int(top[primary_col]))}** of **{num(int(total))}**)."
    )

    if sessions_col and transactions_col:
        cvr_df = df[df[sessions_col] > 0].copy()
        if len(cvr_df) >= 2:
            cvr_df["CVR"] = cvr_df[transactions_col] / cvr_df[sessions_col] * 100
            best = cvr_df.loc[cvr_df["CVR"].idxmax()]
            worst = cvr_df.loc[cvr_df["CVR"].idxmin()]
            if best[label_col] != worst[label_col]:
                findings.append(
                    f"**{best[label_col]}** converts at **{best['CVR']:.1f}%**, vs "
                    f"**{worst[label_col]}** at **{worst['CVR']:.1f}%** — the widest gap across values."
                )
    return findings


def _render_param_section(number, title, tag, narrative, dim, dim_label, after,
                           metrics, sessions_col=None, transactions_col=None,
                           primary_col=None, event_filter=None, revenue_col=None):
    badge = "💰 Revenue" if tag == "revenue" else "💵 Cost"
    st.subheader(f"{number} — {title}  ·  {badge}")

    try:
        kwargs = dict(dimensions=(dim,), metrics=metrics, single=after,
                      order_by_metric=primary_col, limit=20)
        if event_filter:
            kwargs["dim_filter"] = string_filter("eventName", event_filter)
        df, _ = run_report(**kwargs)
        df = df[~df[dim].isin(["(not set)", ""])]

        findings = _param_findings(df, dim, primary_col, sessions_col, transactions_col)
        st.markdown("**Key Findings**")
        for f in findings:
            st.markdown(f"- {f}")

        st.markdown("**Recommended Action**")
        callout(narrative, kind="info")

        if not df.empty:
            fig = px.bar(
                df.sort_values(primary_col, ascending=False).head(15),
                x=dim, y=primary_col,
                title=f"{dim_label} Breakdown",
                labels={dim: dim_label},
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

            if revenue_col and revenue_col in df.columns:
                table = df.sort_values(primary_col, ascending=False).head(10).rename(columns={
                    dim: dim_label,
                    revenue_col: "Revenue (EGP)",
                })
                table["Revenue (EGP)"] = table["Revenue (EGP)"].apply(egp)
                st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.info(f"No data for {dim_label} yet.")
    except Exception as e:
        st.error(f"GA4 query failed: {e}")

    st.divider()


def render(before: tuple, after: tuple):
    # ── 6.1 Customer Segmentation Dimensions ─────────────────────────────────
    st.subheader("6.1 — Customer Segmentation Dimensions (After Period Only)")
    callout(
        "customer_value_tier is not yet registered in GA4 Admin — it will show '(not set)' "
        "until the agency registers it. All other dims are live.",
        kind="warning",
    )

    grid = st.columns(2)
    for i, (dim, label) in enumerate(CUSTOMER_DIMS):
        with grid[i % 2]:
            st.markdown(f"**{label}**")
            try:
                df2, _ = run_report(
                    dimensions=(dim,),
                    metrics=("sessions", "transactions"),
                    single=after,
                    order_by_metric="sessions",
                )
                df2 = df2[~df2[dim].isin(["(not set)", ""])]
                if not df2.empty:
                    fig = px.pie(df2, names=dim, values="sessions",
                                 title=f"{label} Distribution", hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"No data for {label} yet.")
            except Exception as e:
                st.error(f"{e}")

    st.divider()

    # ── 6.3 Video Engagement ──────────────────────────────────────────────────
    st.subheader("6.2 — Video Engagement (After Period Only)")
    st.caption("Home page hero video — did customers watch it or scroll past?")
    try:
        df3, _ = run_report(
            dimensions=("eventName",),
            metrics=("eventCount",),
            single=after,
            dim_filter=string_filter("eventName", "video_start"),
        )
        video_events = ["video_start", "video_progress", "video_stop", "video_complete", "video_seek"]
        df_v, _ = run_report(
            dimensions=("eventName",),
            metrics=("eventCount",),
            single=after,
        )
        df_v = df_v[df_v["eventName"].isin(video_events)].set_index("eventName")

        steps = [e for e in video_events if e in df_v.index]
        vals  = [int(df_v.loc[e, "eventCount"]) for e in steps]
        if any(v > 0 for v in vals):
            from utils.charts import funnel_chart
            st.plotly_chart(funnel_chart(steps, vals, "Video Engagement Funnel"), use_container_width=True)
        else:
            st.info("No video events yet in the after period.")

    except Exception as e:
        st.error(f"GA4 query failed: {e}")

    st.divider()

    # ── 6.3 Top Search Terms ──────────────────────────────────────────────────
    _render_param_section(
        number="6.3", title="Top Search Terms", tag="revenue",
        narrative=(
            "search_term captures the literal words shoppers type — the rawest, least-filtered "
            "demand signal on the site. High-volume terms with no dedicated collection or "
            "prominent merchandising are missed revenue: turning the top terms into landing "
            "pages, homepage features, or restock priorities captures demand that's already "
            "proven to exist instead of hoping shoppers stumble onto it browsing."
        ),
        dim="customEvent:search_term", dim_label="Search Term", after=after,
        metrics=("eventCount",), primary_col="eventCount",
    )

    # ── 6.4 Variant Demand via Swatch Selection ──────────────────────────────
    _render_param_section(
        number="6.4", title="Variant Demand via Swatch Selection", tag="revenue",
        narrative=(
            "Every swatch value logged is the exact color or material a shopper actively "
            "selected, not just viewed — a sharper restock and merchandising-priority signal "
            "than raw product views. Colors and materials dominating this list deserve "
            "inventory priority and homepage/ad placement; ones barely appearing are candidates "
            "to phase out or bundle-discount before they tie up cash in slow-moving stock."
        ),
        dim="customEvent:swatch_value", dim_label="Swatch Value", after=after,
        metrics=("eventCount",), primary_col="eventCount",
    )

    # ── 6.5 Manual Sort Override Rate ─────────────────────────────────────────
    _render_param_section(
        number="6.5", title="Manual Sort Override Rate", tag="revenue",
        narrative=(
            "Every time a shopper overrides the default sort order, they're telling you the "
            "default isn't surfacing what they want. Price-ascending consistently outranking "
            "every other manual sort is a direct price-sensitivity signal — worth testing a "
            "default sort that leads with value/promo items, or surfacing a visible price "
            "filter earlier, instead of leaving shoppers to dig for it themselves."
        ),
        dim="customEvent:sort_value", dim_label="Sort Value", after=after,
        metrics=("eventCount",), primary_col="eventCount",
    )

    st.markdown("**Sort Override by Collection Page**")
    st.caption("Which collection pages shoppers manually re-sort, and how — broken out per page.")
    try:
        no_blank = and_filter(
            not_filter(string_filter("customEvent:sort_value", "(not set)")),
            not_filter(string_filter("customEvent:sort_value", "")),
        )
        df_page, _ = run_report(
            dimensions=("pagePath", "customEvent:sort_value"),
            metrics=("eventCount",),
            single=after,
            dim_filter=no_blank,
            order_by_metric="eventCount",
            limit=500,
        )
        if not df_page.empty:
            top_pages = (
                df_page.groupby("pagePath")["eventCount"].sum()
                .sort_values(ascending=False)
                .head(8)
                .index
            )
            page_cols = st.columns(2)
            for i, page in enumerate(top_pages):
                page_df = df_page[df_page["pagePath"] == page].sort_values("eventCount", ascending=False)
                fig = px.bar(
                    page_df, x="customEvent:sort_value", y="eventCount",
                    title=page,
                    labels={"customEvent:sort_value": "Sort Value", "eventCount": "Events"},
                )
                fig.update_xaxes(tickangle=45)
                with page_cols[i % 2]:
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No per-page sort override data yet.")
    except Exception as e:
        st.error(f"GA4 query failed: {e}")

    st.divider()

    # ── 6.6 Category Link Click Demand ────────────────────────────────────────
    _render_param_section(
        number="6.6", title="Category Link Click Demand", tag="revenue",
        narrative=(
            "link_text captures the exact category or collection label a shopper clicked — a "
            "direct read on which product categories pull the most interest before they even "
            "land on a listing page. The categories dominating this list deserve the most "
            "prominent homepage real estate and ad creative; ones barely clicked are candidates "
            "to demote, rename, or merge into a stronger-performing category."
        ),
        dim="customEvent:link_text", dim_label="Link Text", after=after,
        metrics=("eventCount",), primary_col="eventCount",
    )

    # ── 6.7 Ecommerce Item Field Population ───────────────────────────────────
    st.subheader("6.7 — Ecommerce Item Field Population")
    callout(
        "Before: item_list_name was 100% blank due to wrong field names in Shopify's "
        "native pixel. After: custom pixel maps the field correctly.",
        kind="info",
    )

    dim, label = "itemListName", "List Name"
    try:
        df_b, _ = run_report(
            dimensions=(dim,), metrics=("itemsViewed",),
            single=before, limit=500,
        )
        df_a, _ = run_report(
            dimensions=(dim,), metrics=("itemsViewed",),
            single=after, limit=500,
        )
        blank_before = _blank_pct(df_b, dim, "itemsViewed")
        blank_after  = _blank_pct(df_a, dim, "itemsViewed")

        kpi(st.container(), f"% Blank — {label}",
            blank_before, blank_after, format_fn=pct, good="down",
            note="Before: 100% blank (wrong field name). After: populated by custom pixel")

        col_b, col_a = st.columns(2)
        with col_b:
            st.markdown(f"**Before — {label} breakdown**")
            st.caption("Includes '(not set)' rows — shows just how empty this field was.")
            top_b = df_b.sort_values("itemsViewed", ascending=False).head(10)
            if not top_b.empty:
                st.dataframe(top_b.rename(columns={
                    dim: label, "itemsViewed": "Views",
                }), use_container_width=True, hide_index=True)
        with col_a:
            st.markdown(f"**After — {label} breakdown**")
            top_a = df_a[df_a[dim] != "(not set)"].sort_values("itemsViewed", ascending=False).head(10)
            if not top_a.empty:
                st.dataframe(top_a.rename(columns={
                    dim: label, "itemsViewed": "Views",
                }), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"{e}")

    st.divider()

    # ── 6.8 Product Enrichment Fields ─────────────────────────────────────────
    st.subheader("6.8 — New Product Enrichment Fields (After Period Only)")
    st.caption("Fields that had no equivalent in any previous tracking implementation.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Coupon code coverage on purchases**")
        try:
            df_coupon, _ = run_report(
                dimensions=("orderCoupon",),
                metrics=("transactions", "purchaseRevenue"),
                before=before, after=after,
                order_by_metric="transactions",
            )
            merged_c = merge_periods(df_coupon, ["orderCoupon"],
                                     ["transactions", "purchaseRevenue"])
            total_b = merged_c["transactions_before"].sum()
            total_a = merged_c["transactions_after"].sum()
            with_code_b = merged_c[merged_c["orderCoupon"] != "(not set)"]["transactions_before"].sum()
            with_code_a = merged_c[merged_c["orderCoupon"] != "(not set)"]["transactions_after"].sum()

            st.metric("Purchases with coupon tracked",
                      pct(with_code_a / total_a * 100 if total_a else 0),
                      delta=f"Before: {pct(with_code_b / total_b * 100 if total_b else 0)}",
                      delta_color="off")

            top_coupons = merged_c[merged_c["orderCoupon"] != "(not set)"].sort_values(
                "transactions_after", ascending=False
            ).head(10)
            top_coupons = top_coupons.rename(columns={
                "orderCoupon": "Coupon Code",
                "transactions_before": "Uses (Before)", "transactions_after": "Uses (After)",
                "purchaseRevenue_before": "Revenue (Before)", "purchaseRevenue_after": "Revenue (After)",
            })
            top_coupons["Revenue (Before)"] = top_coupons["Revenue (Before)"].apply(egp)
            top_coupons["Revenue (After)"]  = top_coupons["Revenue (After)"].apply(egp)
            st.dataframe(top_coupons, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"{e}")

    with col_b:
        st.markdown("**Shipping country distribution (after only)**")
        st.caption("Actual delivery destination — more reliable than IP-based country for Egypt/VPN users.")
        try:
            df_country, _ = run_report(
                dimensions=("customEvent:shipping_country",),
                metrics=("transactions", "purchaseRevenue"),
                single=after,
                order_by_metric="transactions",
                limit=50,
            )
            df_country = df_country[df_country["customEvent:shipping_country"] != "(not set)"]
            if not df_country.empty:
                fig = px.bar(
                    df_country.head(20),
                    x="customEvent:shipping_country", y="transactions",
                    title="Purchases by Shipping Country",
                    labels={"customEvent:shipping_country": "Country", "transactions": "Purchases"},
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No shipping_country data yet.")
        except Exception as e:
            st.error(f"{e}")

    st.divider()

    # ── 6.9 Item Variant & Quantity Coverage ──────────────────────────────────
    st.subheader("6.9 — Item Variant & Quantity Coverage")
    callout(
        "Before: item_variant always blank — no color/size tracking. "
        "After: variant title sent as item_variant. "
        "Quantity was present in native pixel but often wrong (always 1). "
        "After: custom pixel reads actual quantity from cart.",
        kind="info",
    )
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**item_variant blank % (on view_item)**")
        try:
            df_var_b, _ = run_report(
                dimensions=("itemVariant",),
                metrics=("itemsViewed",),
                single=before, limit=5000,
            )
            df_var_a, _ = run_report(
                dimensions=("itemVariant",),
                metrics=("itemsViewed",),
                single=after, limit=5000,
            )
            blank_b = _blank_pct(df_var_b, "itemVariant", "itemsViewed")
            blank_a = _blank_pct(df_var_a, "itemVariant", "itemsViewed")
            kpi(st.container(), "% Blank — item_variant",
                blank_b, blank_a, format_fn=pct, good="down",
                note="Before: 100% blank (color/size not tracked). After: variant title sent.")
            top_variants = df_var_a[
                ~df_var_a["itemVariant"].isin(["(not set)", "Default Title"])
            ].sort_values("itemsViewed", ascending=False).head(10)
            if not top_variants.empty:
                st.dataframe(top_variants.rename(columns={
                    "itemVariant": "Variant", "itemsViewed": "Views (After)",
                }), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"{e}")

    with col_b:
        st.markdown("**itemQuantity presence on add_to_cart (after only)**")
        try:
            df_qty, _ = run_report(
                dimensions=("itemName",),
                metrics=("itemsAddedToCart", "cartToViewRate"),
                single=after,
                order_by_metric="itemsAddedToCart",
                limit=20,
            )
            if not df_qty.empty:
                st.dataframe(df_qty.rename(columns={
                    "itemName": "Product",
                    "itemsAddedToCart": "Units Added to Cart",
                    "cartToViewRate": "Cart-to-View Rate",
                }), use_container_width=True, hide_index=True)
            else:
                st.info("No cart data available.")
        except Exception as e:
            st.error(f"{e}")

