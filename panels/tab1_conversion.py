import streamlit as st
import pandas as pd
from ga4_client import run_report
from utils.formatters import num, pct
from utils.charts import kpi, callout

# ── Tooltip descriptions: what user action fires each event ───────────────────
_EVENT_TRIGGERS = {
    # GA4 auto-tracked
    "page_view":                     "User loads any page — fires automatically on every navigation",
    "session_start":                 "User starts a new session — first event of each visit",
    "first_visit":                   "User visits the site for the very first time on this device",
    "user_engagement":               "User actively interacts with the page for a minimum time threshold",
    "click":                         "User clicks an outbound or cross-domain tracked link",
    "scroll":                        "User scrolls to 90% of the page (GA4 enhanced measurement auto-event)",
    "form_start":                    "User focuses on a form field for the first time",
    "form_submit":                   "User submits a form on the page",
    "file_download":                 "User clicks a downloadable file link",
    "video_start":                   "User presses play on an embedded video",
    "video_progress":                "Video playback reaches a 10%, 25%, 50%, or 75% milestone",
    "video_complete":                "Video plays all the way to the end",
    # Old tracking — reimplemented as better events
    "PageScroll":                    "Old tracking event — fired when user scrolled the page. Replaced by scroll_depth (25/50/75/90% milestones with depth label)",
    "TimeOnPage":                    "Old tracking event — fired based on time on page. Replaced by time_on_page_milestone (30s, 60s, 2min, 5min — each fires separately)",
    "login":                         "Old generic login event with no parameters. Replaced by login_success which sets user_id for cross-device stitching",
    "search":                        "Old generic search event — no query text captured. Replaced by search_query which records exactly what the user typed",
    "checkout_progress":             "Old checkout step tracker — fired at each stage. Replaced by checkout_step custom parameter on begin_checkout events",
    # Ecommerce
    "view_item":                     "User opens a product detail page",
    "view_item_list":                "User views a collection or category page — fires when the product grid loads",
    "add_to_cart":                   "User clicks Add to Cart on any product",
    "view_cart":                     "User opens the cart drawer or navigates to the cart page",
    "begin_checkout":                "User clicks Checkout to start the checkout flow",
    "remove_from_cart":              "User removes an item from the cart",
    "add_shipping_info":             "User selects or confirms a shipping method during checkout",
    "add_payment_info":              "User enters or selects their payment method during checkout",
    "purchase":                      "User completes an order — fires when the order confirmation page loads",
    # Search
    "search_query":                  "User types and submits a search — captures the exact search term entered",
    "search_no_results":             "User searches and the results page returns zero matching products",
    "search_result_click":           "User clicks a product from the search results list",
    "search_autocomplete_click":     "User selects a suggestion from the search autocomplete dropdown",
    "search_drawer_open":            "User clicks the search icon to open the search panel",
    "search_drawer_close":           "User closes or dismisses the search panel",
    # Navigation
    "navigation_click":              "User clicks a link in the main navigation menu",
    "hamburger_menu_open":           "User taps the hamburger icon to open the mobile side menu",
    "hamburger_menu_close":          "User closes the mobile hamburger menu",
    "mega_menu_open":                "User hovers or taps to open a mega-menu dropdown section",
    "logo_click":                    "User clicks the Tharaa logo — typically navigates back to the homepage",
    "footer_link_click":             "User clicks any link in the site footer",
    "back_to_top_click":             "User clicks the back-to-top button after scrolling down",
    "mobile_toolbar_tap":            "User taps an icon in the mobile bottom navigation bar",
    "announcement_bar_click":        "User clicks the promotional announcement bar at the top of the page",
    "announcement_bar_close":        "User dismisses or closes the announcement bar",
    # Product page
    "swatch_click":                  "User clicks a color or material swatch to select a product variant",
    "size_chosen":                   "User selects a size option on a product page",
    "product_tab_click":             "User clicks a tab (e.g. Description, Reviews, Shipping) on a product page",
    "product_image_click":           "User clicks the main product image to view it larger",
    "thumbnail_click":               "User clicks a thumbnail in the product image gallery",
    "product_thumbnail_click":       "User clicks a thumbnail in the product image gallery",
    "lightbox_open":                 "User opens a product image in fullscreen/lightbox mode",
    "quick_view_open":               "User opens the quick view popup on a product card in a listing",
    "quick_shop_open":               "User opens the quick shop panel on a product card",
    "size_guide_open":               "User opens the size guide popup or modal on a product page",
    "sticky_atc_visible":            "The sticky Add-to-Cart bar becomes visible as user scrolls down the product page",
    "out_of_stock_viewed":           "User views a product detail page where the item is currently out of stock",
    "accordion_open":                "User expands a collapsible section (e.g. Details, Care, FAQ) on a product page",
    "product_card_click":            "User clicks a product card anywhere in a collection or listing page",
    "filter_applied":                "User applies a filter (e.g. color, size, price range) on a collection page",
    "filter_removed":                "User unchecks or removes a single active filter",
    "filter_reset":                  "User clicks Reset/Clear to remove all active filters at once",
    "sort_changed":                  "User changes the sort order (e.g. Price: Low to High) on a listing page",
    "view_mode_toggle":              "User switches between grid view and list view on a collection page",
    "pagination_click":              "User clicks a page number or next/prev arrow to browse more products",
    # Cart
    "cart_drawer_open":              "User opens the cart sidebar drawer (e.g. by clicking the cart icon in the header)",
    "cart_drawer_close":             "User closes the cart sidebar drawer",
    "cart_item_remove":              "User clicks the remove button on an item inside the cart drawer",
    "cart_item_quantity_change":     "User changes the quantity of an item in the cart using + or − controls",
    "discount_code_submitted":       "User types a discount or promo code and clicks Apply",
    "cart_value_milestone":          "User's cart total crosses a threshold (e.g. EGP 500, 1000, 2000) while adding items",
    "free_shipping_progress_milestone": "User's cart value reaches a milestone toward the free-shipping minimum",
    "gift_wrap_toggled":             "User toggles the gift wrap option on or off in the cart",
    "cart_checkout_click":           "User clicks the Checkout button inside the cart drawer",
    "cart_note_added":               "User types a note or special instruction in the cart",
    "cart_terms_agreed":             "User ticks the terms and conditions checkbox before proceeding to checkout",
    # Engagement
    "time_on_page_milestone":        "User stays on the current page for 30s, 60s, 2min, or 5min — each threshold fires a separate event",
    "tab_inactive":                  "User switches to another browser tab or minimizes the window while on the site",
    "tab_return":                    "User switches back to the Tharaa tab after being away",
    "scroll_depth":                  "User scrolls to 25%, 50%, 75%, or 90% of the current page — each threshold fires separately",
    # Video
    "video_stop":                    "User pauses or manually stops a video before it finishes",
    "video_seek":                    "User scrubs the video timeline to jump to a different position",
    # Social & Reviews
    "review_image_clicked":          "User clicks a photo attached to a customer product review",
    "new_customer_product_review":   "A customer submits a new review on a product page",
    "google_review_user_intent":     "User clicks or interacts with a Google review prompt or widget on the page",
    "wishlist_add":                  "User clicks the heart/wishlist icon to save a product to their wishlist",
    "wishlist_remove":               "User removes a product from their saved wishlist",
    "wishlist_product_click":        "User clicks a product from their wishlist page to view it",
    "wishlist_page_view":            "User navigates to their wishlist/saved items page",
    "cart_upsell_click":             "User clicks an upsell suggestion shown in the cart (e.g. 'You might also like')",
    "product_recommendation_click":  "User clicks on a recommended product shown in a recommendation widget",
    "product_recommendation_view":   "A product recommendation widget enters the user's visible viewport",
    "recently_viewed_click":         "User clicks a product from the recently viewed section",
    # Lead Gen & Account
    "contact_form_submit":           "User fills in and submits the contact/inquiry form",
    "whatsapp_support_needed":       "User clicks the WhatsApp chat button to request customer support",
    "back_in_stock_submit":          "User submits their email to be notified when a product is restocked",
    "footer_newsletter_submit":      "User subscribes to the newsletter via the signup form in the site footer",
    "newsletter_section_submit":     "User subscribes to the newsletter via a dedicated section on a page",
    "sign_up":                       "User completes the account registration form and creates a new account",
    "login_success":                 "User enters correct credentials and successfully logs in — triggers user_id stitching across devices",
    "login_attempt":                 "User submits the login form (fires regardless of whether the login succeeds or fails)",
    "account_sidebar_open":          "User opens the account sidebar or profile drawer",
    "order_note_added":              "User adds a note or special instructions to their order during checkout",
    # Consent
    "cookie_consent_accepted":       "User clicks Accept on the cookie consent banner",
    "cookie_consent_declined":       "User clicks Decline or rejects tracking on the consent banner",
    # Cart / checkout
    "quantity_change":               "User increases or decreases the quantity of a product",
    "product_lightbox_open":         "User hovers over or clicks the main product image on a product page to open it fullscreen",
    "checkout_from_cart_slider":     "User moves to checkout directly from the cart slider without going to the cart page",
    "cart_slider_opened":            "User opens the cart slider",
    "view_search_results":           "User views the search results page after submitting a query",
    "wishlist_page_view":            "User visits their wishlist page",
    "wishlist_visit":                "User visits a wishlist page",
}

# Events to hide from the table entirely (junk, third-party widgets, duplicates, noisy)
_EXCLUDED_EVENTS = {
    "variant_dropdown_open",
    "time_on_page",
    "social_follow_click",
    "social_share",
    "search_autocomplete_query",
    "review_stars_clicked",
    "product_share",
    "home_page_return",
    "exit_intent_popup_view",
    "consent_update",
    "Poll Closed",
    "Poll Completed",
    "Poll Opened",
    "Poll Submission",
    "Slide Viewed",
    "wishlist_visit",
}

# Events only in before that have named replacements in the new implementation
_REIMPLEMENTED_AS = {
    "PageScroll":        "scroll_depth",
    "TimeOnPage":        "time_on_page_milestone",
    "login":             "login_success",
    "search":            "search_query",
    "checkout_progress": "checkout_step (custom param)",
}

_TYPE_ORDER = {"Essential Ecom Events": 0, "Custom pixel / custom layer": 1, "Reimplemented": 2, "Removed false events": 3}

# Necessary ecommerce events that simply weren't implemented before — still Essential Ecom Events, not custom pixel additions
_ESSENTIAL_ECOM_MISSING_BEFORE = {"add_shipping_info", "view_cart", "view_item_list"}


def render(before: tuple, after: tuple):
    # ── 1.1 Headline KPIs ──────────────────────────────────────────────────
    st.subheader("1.1 — Conversion Accuracy (Headline KPIs)")
    callout(
        "Key event collapse is intentional. Before count included PageScroll (555K), "
        "TimeOnPage (328K), and 5 other non-purchase events marked as conversions. "
        "After count = real purchases only.",
        kind="info",
    )

    try:
        METRICS = ("conversions", "sessions", "sessionConversionRate",
                   "transactions", "purchaseRevenue", "averagePurchaseRevenue")

        df_b, _ = run_report(dimensions=(), metrics=METRICS, single=before)
        df_a, _ = run_report(dimensions=(), metrics=METRICS, single=after)

        def _get(frame, col):
            return float(frame[col].sum()) if not frame.empty and col in frame.columns else 0.0

        cols = st.columns(2)
        kpi(cols[0], "Key Events (Conversions)",
            _get(df_b, "conversions"), _get(df_a, "conversions"),
            format_fn=num, good="down",
            note="Drop from ~1M → ~3,100 = correct")
        kpi(cols[1], "Session Conversion Rate",
            _get(df_b, "sessionConversionRate"), _get(df_a, "sessionConversionRate"),
            format_fn=lambda v: pct(v * 100), good="up",
            note="Now reflects real purchases ÷ real sessions")

    except Exception as e:
        st.error(f"GA4 query failed: {e}")

    st.markdown("""
**Before:** Google Ads Smart Bidding was optimizing toward 8 different key events — including
PageScroll, TimeOnPage, add_to_cart, and search — none of which represent actual revenue.
This caused the bidding algorithm to chase high-volume, zero-value signals, inflating reported
conversions by ~350,000 while actual purchases were buried in the noise.

**After:** GA4 Purchase is now the only event set up as a key event and should be imported alone
(or with some other bottom of funnel events, such as begin checkout, add shipping info, add
payment info) into Google Ads, so Smart Bidding is trained exclusively on actual purchase signals.
""")

    st.divider()

    # ── 1.2 Complete Event Transformation Map ──────────────────────────────
    st.subheader("1.2 — Complete Event Transformation Map")
    callout(
        "Before: 9 non-purchase events incorrectly marked as key events — inflating conversion count. "
        "After: those removed, 60+ behavioral events added by custom pixel. "
        "Hover the 'What triggers this' column to see what user action fires each event.",
        kind="info",
    )

    try:
        df_b, _ = run_report(
            dimensions=("eventName",), metrics=("eventCount",),
            single=before, order_by_metric="eventCount", limit=500,
        )
        df_a, _ = run_report(
            dimensions=("eventName",), metrics=("eventCount",),
            single=after, order_by_metric="eventCount", limit=500,
        )

        merged = pd.merge(
            df_b.rename(columns={"eventCount": "eventCount_before"}),
            df_a.rename(columns={"eventCount": "eventCount_after"}),
            on="eventName", how="outer",
        ).fillna(0)
        merged["eventCount_before"] = merged["eventCount_before"].astype(int)
        merged["eventCount_after"]  = merged["eventCount_after"].astype(int)

        # ── KPI summary ───────────────────────────────────────────────────
        countable = merged[~merged["eventName"].isin(_EXCLUDED_EVENTS)]
        b_unique        = int((countable["eventCount_before"] > 0).sum())
        a_unique        = int((countable["eventCount_after"] > 0).sum())

        kpi_cols = st.columns(1)
        kpi(kpi_cols[0], "Unique Events Tracked",
            b_unique, a_unique, format_fn=num, good="up",
            note="Growth driven by custom pixel adding 60+ behavioral events")

        # ── Build classified event table ──────────────────────────────────
        rows = []
        for _, row in merged.iterrows():
            name  = row["eventName"]
            if name in _EXCLUDED_EVENTS:
                continue
            b_cnt = row["eventCount_before"]
            a_cnt = row["eventCount_after"]

            if b_cnt > 0 and a_cnt > 0:
                before_status = "Firing"
                after_status  = "Firing"
                event_type    = "Essential Ecom Events"
            elif b_cnt == 0 and a_cnt > 0:
                before_status = "Didn't exist"
                after_status  = "Firing"
                event_type    = (
                    "Essential Ecom Events" if name in _ESSENTIAL_ECOM_MISSING_BEFORE
                    else "Custom pixel / custom layer"
                )
            elif b_cnt > 0 and a_cnt == 0:
                replacement   = _REIMPLEMENTED_AS.get(name)
                before_status = "Firing"
                if replacement:
                    after_status = f"→ {replacement}"
                    event_type   = "Reimplemented"
                else:
                    after_status = "Removed"
                    event_type   = "Removed false events"
            else:
                continue

            rows.append({
                "Event":              name,
                "Before":             before_status,
                "After":              after_status,
                "Type":               event_type,
                "What triggers this": _EVENT_TRIGGERS.get(name, "—"),
            })

        display = pd.DataFrame(rows)
        display["_sort"] = display["Type"].map(_TYPE_ORDER)
        display = (
            display
            .sort_values(["_sort", "Event"])
            .drop(columns="_sort")
            .reset_index(drop=True)
        )

        def _color_status(val):
            if val == "Firing":
                return "color: #4caf50; font-weight: 700;"
            if val == "Didn't exist":
                return "color: #f44336; font-weight: 700;"
            if val == "Removed":
                return "color: #ffc107; font-weight: 700;"
            return ""

        st.markdown("#### All Events — Before vs After")
        st.dataframe(
            display.style.map(_color_status, subset=["Before", "After"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Event":              st.column_config.TextColumn("Event",              width="medium"),
                "Before":             st.column_config.TextColumn("Before",             width="small"),
                "After":              st.column_config.TextColumn("After",              width="medium"),
                "Type":               st.column_config.TextColumn("Type",               width="medium"),
                "What triggers this": st.column_config.TextColumn("What triggers this", width="large"),
            },
        )

    except Exception as e:
        st.error(f"GA4 query failed: {e}")
