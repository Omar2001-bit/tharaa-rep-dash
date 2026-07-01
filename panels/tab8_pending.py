import streamlit as st
import pandas as pd
from admin_client import (
    get_property_info, get_data_retention, list_google_ads_links,
    list_audiences, list_custom_dimensions, list_custom_metrics,
)
from utils.charts import callout

# ── Pending actions master list ───────────────────────────────────────────────
PENDING_ACTIONS = [
    # Category, Action, Owner, Priority, Notes
    # ── CRITICAL — privacy violations confirmed live ──────────────────────────
    ("🚨 CRITICAL",    "Disable customer email/name sending to Google (Shopify → Google channel)",
     "Client",   "🔴 High",   "Logged-in customer real email + name flows to GA4, Google Ads, Merchant Center on EVERY page. Shopify Admin → Sales Channels → Google → Settings → Customer data sharing → OFF. 5 min fix."),
    ("🚨 CRITICAL",    "Disable Meta Advanced Matching (hashes emails pre-consent)",
     "Client",   "🔴 High",   "Meta Pixel sends hashed email on every page load BEFORE any consent interaction. Confirmed via live network inspection. Meta Events Manager → Data Sources → Pixel → Settings → Advanced Matching → Toggle OFF. 2 min fix."),
    ("🚨 CRITICAL",    "Enable Meta Conversions API for iOS (EGP 1.1M invisible to Meta)",
     "Client",   "🔴 High",   "15.8% of sessions (100,015) from iOS Safari — Apple Link Tracking Protection strips Meta click IDs. Estimated EGP 1,101,734 invisible to Meta bidding. Shopify Admin → Facebook & Instagram → Settings → Conversions API. 10 min."),
    # ── Google Ads — conversion action cleanup ────────────────────────────────
    ("Google Ads",     "Demote 3 of 4 Primary conversion actions to Secondary",
     "Client",   "🔴 High",   "4 actions simultaneously Primary: GA4 purchase import, duplicate lowercase 'purchase', thank-you page tag, Google Shopping App Purchase. Every real purchase counted 4× in Smart Bidding. Keep only GA4 Purchase import as Primary."),
    ("Google Ads",     "Set product page view conversion label to Secondary",
     "Client",   "🔴 High",   "Google Ads fires a conversion label on every product page view — registering browsing as purchasing in Smart Bidding. Google Ads → Goals → Conversions → set to Secondary."),
    ("Google Ads",     "Create GA4 conversion action: purchase (value-based)",
     "Agency",   "🔴 High",   "Old conversion action tracked false events"),
    ("Google Ads",     "Create GA4 conversion action: begin_checkout",
     "Agency",   "🟡 Medium", "Mid-funnel signal for Smart Bidding"),
    ("Google Ads",     "Create GA4 conversion action: add_to_cart",
     "Agency",   "🟡 Medium", "Top-funnel signal for Smart Bidding"),
    ("Google Ads",     "Pause old WPM-based conversion actions",
     "Agency",   "🔴 High",   "Prevent double-counting"),
    ("Google Ads",     "Switch TikTok campaigns from Traffic → Conversions objective",
     "Client",   "🟡 Medium", "TikTok campaigns running 'Traffic' objective — optimizing for clicks not purchases. Duplicate campaigns, switch to Conversions → Complete Payment, pause old after 3-5 days stable."),
    # ── GA4 Admin ─────────────────────────────────────────────────────────────
    ("GA4 Admin",      "Register customer_value_tier custom dimension (event-scoped)",
     "Agency",   "🔴 High",   "Blocks Panel 6.2 tier data"),
    ("GA4 Admin",      "Register destination_hint custom dimension (event-scoped)",
     "Agency",   "🔴 High",   "Blocks Panel 5.3 destination table"),
    ("GA4 Admin",      "Annotate Nov 2025 in GA4 (Pangle contamination period)",
     "Agency",   "🟡 Medium", "43,481 bot sessions inflate Nov metrics"),
    ("GA4 Admin",      "Set data retention to 14 months",
     "Agency",   "🟡 Medium", "Currently defaults; verify in Admin"),
    # ── Pixel / GTM ───────────────────────────────────────────────────────────
    ("Pixel / GTM",    "Set PIXEL_DEBUG = false in custom pixel",
     "Agency",   "🔴 High",   "Console noise + minor perf impact"),
    ("Pixel / GTM",    "Verify consent banner → dataLayer event connection with live test",
     "Agency",   "🔴 High",   "Cannot confirm consent mode without live test"),
    ("Pixel / GTM",    "Move TikTok Pixel from Shopify WPM → GTM",
     "Client",   "🔴 High",   "Required for consent gating"),
    ("Pixel / GTM",    "Move Meta Pixel from Shopify WPM → GTM",
     "Client",   "🔴 High",   "Required for consent gating"),
    ("Pixel / GTM",    "Move Snapchat Pixel from Shopify WPM → GTM",
     "Client",   "🔴 High",   "Required for consent gating"),
    ("Pixel / GTM",    "Disable Pangle in TikTok Ads Manager",
     "Client",   "🔴 High",   "Prevents bot traffic recurrence"),
    ("Google Ads",     "Create GA4 conversion action: purchase (value-based)",
     "Agency",   "🔴 High",   "Old conversion action tracked false events"),
    ("Google Ads",     "Create GA4 conversion action: begin_checkout",
     "Agency",   "🟡 Medium", "Mid-funnel signal for Smart Bidding"),
    ("Google Ads",     "Create GA4 conversion action: add_to_cart",
     "Agency",   "🟡 Medium", "Top-funnel signal for Smart Bidding"),
    ("Google Ads",     "Pause old WPM-based conversion actions",
     "Agency",   "🔴 High",   "Prevent double-counting"),
    ("Shopify",        "Add checkout.tharaa.shop to GA4 cross-domain list",
     "Agency",   "🟡 Medium", "Verify still needed after fix; cross-domain linker active"),
    ("Shopify",        "Verify GDPR consent banner fires consent_accepted/declined events",
     "Agency/Client", "🔴 High", "Required for Consent Mode v2 compliance"),
    ("Shopify",        "Remove Hotjar from Shopify WPM (duplicate — now in GTM)",
     "Client",   "🟡 Medium", "Double-firing; WPM version not consent-gated"),
    ("GA4 Audiences",  "Create 'Abandoned Cart' audience (add_to_cart, no purchase, 7d)",
     "Agency",   "🟡 Medium", "High-intent remarketing segment"),
    ("GA4 Audiences",  "Create 'High Value Customer' audience (customer_value_tier=high)",
     "Agency",   "🟡 Medium", "Requires customer_value_tier registered first"),
    ("GA4 Audiences",  "Create 'WhatsApp Inquirers' audience (whatsapp_support_needed, 30d)",
     "Agency",   "🟡 Medium", "Engaged visitors with support intent"),
    ("Analytics",      "Implement GA4 → BigQuery export for long-term analysis",
     "Agency",   "🟢 Low",    "14-month retention limit; BigQuery for permanence"),
    ("Analytics",      "Set up Looker Studio report for client self-serve reporting",
     "Agency",   "🟢 Low",    "Client can monitor without dashboard access"),
    ("Analytics",      "Document all 60+ behavioral events in a measurement plan",
     "Agency",   "🟢 Low",    "For client handoff and future developers"),
    ("Analytics",      "Verify search_no_results event triggers correctly on Shopify",
     "Agency",   "🟡 Medium", "Needs QA on 0-result search page"),
    # ── Client UTM / campaign hygiene ─────────────────────────────────────────
    ("Campaigns",      "Add UTM labels to all WhatsApp broadcast links",
     "Client",   "🔴 High",   "1,352 sessions EGP 76,990 — zero campaign identity. source=whatsapp, medium=social, campaign=[broadcast-name]"),
    ("Campaigns",      "Standardize Meta UTMs: source=facebook (not fb), lowercase",
     "Client",   "🔴 High",   "EGP 257,550 split across fb/paid vs facebook/paid rows. Existing campaigns keep 'fb' until expire."),
    ("Campaigns",      "Standardize Instagram UTMs: source=instagram, lowercase",
     "Client",   "🟡 Medium", "EGP 478K+ split across 5 label combinations (ig/social, ig/paid, IGShopping/Social etc)"),
    ("Campaigns",      "Remove keyword field from Meta UTM templates",
     "Client",   "🟡 Medium", "Meta auto-inserts 15+ digit ad set IDs into utm_term → pollutes GA4 keyword report"),
    ("Campaigns",      "Add dynamic campaign name placeholder to all Meta ad URLs",
     "Client",   "🟡 Medium", "20,510 Facebook paid sessions show '(referral)' as campaign — EGP 270,286 unidentifiable"),
    ("Campaigns",      "Export Meta campaign ID→name mapping; provide to agency for GA4 Data Import",
     "Client",   "🟡 Medium", "557 rows of 18-digit number codes; top 4 = EGP 633,183 unreadable. Historical rows permanent."),
    ("Campaigns",      "Rename Maryam influencer campaign in Shopify Admin",
     "Client",   "🟡 Medium", "12,691 sessions EGP 169,059 under unidentifiable hash code. New shareable links use new name."),
    ("Campaigns",      "Standardize QR code UTMs: source=qrcode, medium=offline, campaign=[product-name]",
     "Client",   "🟡 Medium", "228 sessions EGP 5,959 under 'package/package' — unclassifiable"),
    ("Campaigns",      "Rule: add UTM labels BEFORE shortening bit.ly links",
     "Client",   "🟡 Medium", "1,915 sessions EGP 44,659 permanently unattributable. One product at 15.4% CVR — source unknown forever."),
    ("Campaigns",      "Audit all active paid campaigns for missing utm_source",
     "Client",   "🟡 Medium", "2,959 sessions show paid medium but no source — platform unidentified"),
    ("Campaigns",      "Establish campaign annotation habit in GA4",
     "Client",   "🟟 Medium", "Zero annotations in 7 months. Aug 2025 CVR drop (1.26% vs Sep 2.64%) unexplained."),
    # ── Server-side / advanced ────────────────────────────────────────────────
    ("Server-side",    "Implement refund tracking (Shopify webhook → Measurement Protocol)",
     "Agency",   "🟢 Low",    "Browser pixel cannot receive refund events. Requires server-side: Shopify refund webhook → MP or GTM server container."),
    ("Server-side",    "Add view_promotion / select_promotion (requires theme publisher)",
     "Agency",   "🟢 Low",    "Pixel is subscribed but no theme-level publisher exists. Theme/app dev must publish custom_view_promotion and custom_select_promotion events."),
    ("Server-side",    "Add select_item event (requires theme publisher)",
     "Agency",   "🟢 Low",    "Pixel subscribed to custom_select_item but Shopify native doesn't include it. Theme developer must publish."),
]


def render(before: tuple, after: tuple):
    st.header("Pending Actions Tracker")

    callout(
        "🚨 CRITICAL (2 client actions): Customer real emails/names flow to Google on every page. "
        "Meta Advanced Matching hashes emails pre-consent on every page load. "
        "Both confirmed live. Fix takes under 10 minutes each.",
        kind="error",
    )
    callout(
        "36 items across 8 categories. "
        "Red = blocking analytics accuracy or active privacy risk. "
        "Yellow = important but non-blocking. Green = optional enhancement.",
        kind="warning",
    )

    # ── Editable tracker ──────────────────────────────────────────────────────
    st.subheader("8.1 — Action Items")

    df = pd.DataFrame(PENDING_ACTIONS, columns=["Category", "Action", "Owner", "Priority", "Notes"])
    df.insert(0, "Done", False)

    priority_order = {"🔴 High": 0, "🟡 Medium": 1, "🟢 Low": 2}
    df["_sort"] = df["Priority"].map(priority_order)
    df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cats = ["All"] + sorted(df["Category"].unique().tolist())
        cat_sel = st.selectbox("Filter by category", cats)
    with col_f2:
        owners = ["All"] + sorted(df["Owner"].unique().tolist())
        owner_sel = st.selectbox("Filter by owner", owners)

    display = df.copy()
    if cat_sel != "All":
        display = display[display["Category"] == cat_sel]
    if owner_sel != "All":
        display = display[display["Owner"] == owner_sel]

    edited = st.data_editor(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Done": st.column_config.CheckboxColumn("✅", width="small"),
            "Priority": st.column_config.TextColumn("Priority", width="medium"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
        },
        disabled=["Category", "Action", "Owner", "Priority", "Notes"],
    )

    done_count = edited["Done"].sum()
    total = len(edited)
    st.progress(done_count / total if total else 0,
                text=f"{done_count}/{total} items marked done in this view")

    # Summary counts
    high_open   = len(display[(display["Priority"] == "🔴 High") & ~edited["Done"]])
    medium_open = len(display[(display["Priority"] == "🟡 Medium") & ~edited["Done"]])
    low_open    = len(display[(display["Priority"] == "🟢 Low") & ~edited["Done"]])

    m1, m2, m3 = st.columns(3)
    m1.metric("🔴 High open",   high_open)
    m2.metric("🟡 Medium open", medium_open)
    m3.metric("🟢 Low open",    low_open)

    st.divider()

    # ── GA4 Property Settings from Admin API ─────────────────────────────────
    st.subheader("8.2 — GA4 Property Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Property Info**")
        try:
            info = get_property_info()
            st.json({
                "displayName":      info.get("display_name", "—"),
                "timeZone":         info.get("time_zone", "—"),
                "currencyCode":     info.get("currency_code", "—"),
                "industryCategory": info.get("industry_category", "—"),
            })
            if info.get("currency_code") != "EGP":
                callout("Currency not set to EGP — update in GA4 Admin → Property Settings.", kind="error")
            if info.get("time_zone") != "Africa/Cairo":
                callout("Timezone not Africa/Cairo — all timestamps may be off.", kind="error")
        except Exception as e:
            st.error(f"Admin API: {e}")

    with col2:
        st.markdown("**Data Retention**")
        try:
            retention = get_data_retention()
            event_months = retention.get("event_data_retention", "—")
            st.json({"eventDataRetention": event_months, "resetOnNewActivity": retention.get("reset_user_data_on_new_activity", "—")})
            if "FOURTEEN" not in str(event_months):
                callout("Event retention not at 14 months — update in Admin → Data Settings → Data Retention.", kind="warning")
        except Exception as e:
            st.error(f"Admin API: {e}")

    st.markdown("**Google Ads Links**")
    try:
        ads_links = list_google_ads_links()
        if ads_links:
            rows = [{"Customer ID": l.get("customerId", "—"),
                     "Can Manage Clients": l.get("canManageClients", "—"),
                     "Ads Personalization": l.get("adsPersonalizationEnabled", "—")}
                    for l in ads_links]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            callout("No Google Ads links found — conversion data won't flow to Google Ads.", kind="error")
    except Exception as e:
        st.error(f"Admin API: {e}")

    st.divider()

    # ── Custom Dimensions Status ──────────────────────────────────────────────
    st.subheader("8.3 — Custom Dimensions in GA4 Admin")

    EXPECTED_DIMS = {
        "content_group":           "event",
        "landing_page_clean":      "event",
        "checkout_step":           "event",
        "login_status":            "event",
        "payment_type":            "event",
        "shipping_tier":           "event",
        "shipping_country":        "event",
        "destination_hint":        "event",
        "customer_type":           "user",
        "order_count_bucket":      "user",
        "email_marketing_consent": "user",
        "order_value_bucket":      "user",
        "customer_value_tier":     "user",
    }
    PENDING_DIMS: set = set()

    try:
        dims = list_custom_dimensions()
        registered = {d.get("parameterName", ""): d for d in dims}

        rows = []
        for param, scope in EXPECTED_DIMS.items():
            status = "✅ Registered" if param in registered else "❌ Missing"
            if param in PENDING_DIMS and param not in registered:
                status = "⚠️ Pending (agency action)"
            rows.append({
                "Parameter Name": param,
                "Scope": scope,
                "Status": status,
            })
        dim_df = pd.DataFrame(rows)

        def _color(row):
            if "❌" in row["Status"]:
                return ["background-color: #ffcccc"] * len(row)
            if "⚠️" in row["Status"]:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(dim_df.style.apply(_color, axis=1),
                     use_container_width=True, hide_index=True)

        missing = [r["Parameter Name"] for _, r in dim_df.iterrows() if "❌" in r["Status"] or "⚠️" in r["Status"]]
        if missing:
            callout(
                f"Missing/pending dimensions: {', '.join(missing)}. "
                "Register in GA4 Admin → Custom Definitions → Create custom dimension → "
                "scope: Event → parameter name: <exact name above>.",
                kind="warning",
            )
    except Exception as e:
        st.error(f"Admin API: {e}")

    st.divider()

    # ── Audiences ─────────────────────────────────────────────────────────────
    st.subheader("8.4 — GA4 Audiences")

    try:
        audiences = list_audiences()
        if audiences:
            aud_rows = [{"Name": a.get("displayName", "—"),
                         "Description": a.get("description", "—")}
                        for a in audiences]
            st.dataframe(pd.DataFrame(aud_rows), use_container_width=True, hide_index=True)
            st.caption(f"{len(audiences)} audiences configured.")
        else:
            callout("No custom audiences yet — create remarketing audiences in GA4 Admin → Audiences.", kind="warning")
    except Exception as e:
        st.error(f"Admin API: {e}")
