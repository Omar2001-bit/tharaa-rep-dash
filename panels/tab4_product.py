import streamlit as st
import plotly.express as px
from ga4_client import run_report, merge_periods, split_periods
from utils.formatters import egp, num, pct
from utils.charts import callout, kpi


def _blank_pct(df, dim_col, value_col):
    """Return % of value_col where dim_col is '(not set)'."""
    total = df[value_col].sum()
    if total == 0:
        return 0.0
    blank = df[df[dim_col] == "(not set)"][value_col].sum()
    return blank / total * 100


def render(before: tuple, after: tuple):
    # ── 4.1 Item Field Population ────────────────────────────────────────────
    st.subheader("4.1 — Ecommerce Item Field Population")
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

    # ── 4.2 Product Enrichment Fields ────────────────────────────────────────
    st.subheader("4.2 — New Product Enrichment Fields (After Period Only)")
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

    # ── 4.3 Item Variant & Quantity Coverage ─────────────────────────────────
    st.subheader("4.3 — Item Variant & Quantity Coverage")
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
        st.caption("Avg quantity should be > 1 if multiple units added per session.")
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

