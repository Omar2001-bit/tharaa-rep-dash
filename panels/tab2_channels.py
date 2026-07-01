import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from ga4_client import run_report, merge_periods, split_periods, contains_filter, or_filter, string_filter
from utils.formatters import num, pct, egp
from utils.charts import kpi, grouped_bar, callout

_BEFORE_COLOR = "#607d8b"
_AFTER_COLOR  = "#6ae499"
_CHART_BASE   = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#a8c4cc", size=12, family="Sora, sans-serif"),
    margin=dict(t=50, b=30, l=0, r=90),
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.08)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
)

# Channels that hide meaningful traffic in default grouping
_BEFORE_PROBLEM_CHANNELS = {
    "Referral":      "Hides: WhatsApp (8.1% CVR, EGP 76K+), Offline QR, ChatGPT, Shopify shareable links",
    "Unassigned":    "Hides: Meta Audience Network ads, bot/internal traffic, miscategorized UTMs",
    "Organic Social":"Fragmented: facebook, fb, instagram each in separate rows with inconsistent UTMs",
    "Direct":        "May include: offline QR scans with no UTM — attribution lost",
}

# Substrings that mark a channel as newly created in improved grouping
_NEW_CHANNEL_KEYWORDS = [
    "whatsapp", "offline", "qr", "ai referral", "chatgpt",
    "audience network", "shopify", "shareable",
]

BOT_SOURCES = ["pangle", "tagassistant", "hotjar", "googleapis"]


def _apply_improved_grouping(source: str, medium: str, campaign: str, default_channel: str) -> str:
    """Mirrors exact rule order of GA4 channel group 15071794161 (50 rules)."""
    s = source.strip()
    m = medium.strip()
    c = campaign.strip()
    d = default_channel.strip()

    # 1. Bot / Ad Fraud
    if re.fullmatch(r"pangleglobal\.com|pangle-global\.io|imasdk\.googleapis\.com|storage\.googleapis\.com", s, re.I):
        return "Bot / Ad Fraud"
    # 2. Internal / Testing
    if re.fullmatch(r"tagassistant\.google\.com|insights\.hotjar\.com|admin\.shopify\.com|adsmanager\.facebook\.com|statics\.teams\.cdn\.office\.net|mmm\.tiktok-row\.net|accounts\.google\.com|cpanel\.net|siteground\.com|app\.clickup\.com|127\.0\.0\.1", s, re.I) or "translate.goog" in s:
        return "Internal / Testing"
    # 3. Payment Gateway
    if re.fullmatch(r"accept\.paymob\.com|admin-egypt\.paytabs\.com", s, re.I):
        return "Payment Gateway"
    # 4. Shopify Apps
    if re.fullmatch(r"judge\.me|app\.judge\.me|judgeme|app\.fastbundle\.co|app\.ecomsend\.com|forms\.shopifyapps\.com|app\.trendtrack\.io", s, re.I):
        return "Shopify Apps"
    # 5. Paid (unattributed)
    if re.fullmatch(r"paid|cpc", m, re.I) and s == "(not set)":
        return "Paid (unattributed)"
    # 6. Meta paid (untagged)
    if s == "facebook" and m == "(not set)" and c != "(not set)":
        return "Meta paid (untagged)"
    # 7. Meta organic (untagged)
    if s == "facebook" and m == "(not set)" and c == "(not set)":
        return "Meta organic (untagged)"
    # 8. Google Free Product Listings: needs manualAdContent — skip in Python sim
    # 9. AI referral
    if re.fullmatch(r"chatgpt\.com|perplexity|perplexity\.ai|gemini\.google\.com", s, re.I):
        return "AI referral"
    # 10. Shopify campaigns
    if s == "shareable_link":
        return "Shopify campaigns"
    # 11. Offline QR
    if re.fullmatch(r"qrcode|offline|package", m, re.I) or re.fullmatch(r"package|bottle|bottel|pack", s, re.I):
        return "Offline QR"
    # 12. TikTok paid
    if s == "tiktok" and re.fullmatch(r"paid|cpc|video_ad", m, re.I):
        return "TikTok paid"
    # 13. TikTok organic
    if re.fullmatch(r"tiktok|tiktok\.com", s, re.I):
        return "TikTok organic"
    # 14. Meta paid (fb + placement mediums)
    if s == "fb" and re.fullmatch(r"Facebook_Mobile_Feed|Instagram_Stories|Facebook_Stories|Instagram_Reels|Facebook_Mobile_Reels|Facebook_Desktop_Feed|Instagram_Feed|Threads_Feed|Instagram_Explore|Facebook_Notification|Facebook_Right_Column|Others", m):
        return "Meta paid"
    # 15. Meta paid (explicit sources + paid/cpc/fb medium)
    if (re.fullmatch(r"facebook|fb|an|facebook\.com|l\.facebook\.com|lm\.facebook\.com|m\.facebook\.com|facebook-SiteLink", s, re.I) or "Facebook Catalog" in s) and re.fullmatch(r"paid|cpc|fb", m, re.I):
        return "Meta paid"
    # 16. Instagram paid
    if re.fullmatch(r"instagram|ig|IGShopping|instagram\.com", s, re.I) and re.fullmatch(r"paid|cpc|fb", m, re.I):
        return "Instagram paid"
    # 17. Instagram organic
    if re.fullmatch(r"instagram|ig|IGShopping|instagram\.com|l\.instagram\.com", s, re.I) and re.fullmatch(r"social|Social|organic|referral", m):
        return "Instagram organic"
    # 18. WhatsApp
    if re.fullmatch(r"l\.wl\.co|whatsapp|wa\.me", s, re.I):
        return "WhatsApp"
    # 19. Meta organic (all *.facebook.com + referral)
    if re.fullmatch(r"(([a-z0-9-]+\.)+)?facebook\.com", s, re.I) and m == "referral":
        return "Meta organic"
    # 20. Meta organic (facebook source + referral)
    if s == "facebook" and m == "referral":
        return "Meta organic"
    # 21. Threads organic
    if s == "threads.com":
        return "Threads organic"
    # 22. X organic
    if s == "t.co":
        return "X organic"
    # 23. Reddit
    if s == "reddit.com":
        return "Reddit"
    # 24. LinkedIn
    if s == "linkedin.com":
        return "LinkedIn"
    # 25. Pinterest
    if re.fullmatch(r"([a-z]+\.)?pinterest\.com", s, re.I):
        return "Pinterest"
    # 26. Zalo
    if s == "zalo":
        return "Zalo"
    # 27. Link Shortener
    if re.fullmatch(r"bit\.ly|tinyurl\.com|ow\.ly|t\.ly|short\.io", s, re.I):
        return "Link Shortener"
    # 28. Google Referral (google.com + referral, not google/organic)
    if s == "google.com" and m == "referral":
        return "Google Referral"
    # 29. Organic Search (alt engines — yandex, yahoo, search.app, brave, etc.)
    if re.fullmatch(r"search\.brave\.com|petalsearch\.com|search-dra\.dt\.dbankcloud\.com|search\.app|yandex\.ru|yandex\.com|yandex\.com\.tr|yahoo\.com", s, re.I):
        return "Organic Search"
    # 30. Email (Gmail explicit)
    if s == "mail.google.com":
        return "Email"
    # 31. Affiliates (explicit)
    if s == "affiliation.xtnd.net":
        return "Affiliates"
    # 32–50. Passthroughs — use GA4 default channel group
    _PASSTHROUGH = {
        "Cross-network", "Paid Shopping", "Paid Search", "Paid Social", "Direct",
        "Paid Video", "Paid Other", "Display", "Organic Shopping", "Organic Social",
        "Organic Video", "Organic Search", "Email", "Affiliates", "Referral",
        "Audio", "SMS", "Mobile Push Notifications", "AI Assistants",
    }
    if d in _PASSTHROUGH:
        return d

    return "Unassigned"


def render(before: tuple, after: tuple):
    # ── 2.1 Channel Distribution ────────────────────────────────────────────
    st.subheader("2.1 — Channel Distribution")

    _CUSTOM_GROUP_DIM = "sessionCustomChannelGroup:15071794161"
    _FULL_PERIOD = ("2025-11-01", after[1])  # full window covering all historical UTM mess

    callout(
        "Due to inconsistent UTM naming, many sessions landed in 'Unassigned' or had no "
        "recognizable source/medium. Below: what GA4 actually saw, and how those same sessions "
        "would have been classified had the Improved Channel Grouping been in place from the start.",
        kind="warning",
    )

    try:
        # Query full period: source + medium + campaign + default channel
        df_raw, _ = run_report(
            dimensions=(
                "sessionDefaultChannelGroup",
                "sessionSource",
                "sessionMedium",
                "sessionCampaignName",
            ),
            metrics=("sessions",),
            single=_FULL_PERIOD,
            order_by_metric="sessions",
            limit=2000,
        )

        if df_raw.empty:
            st.info("No data returned.")
        else:
            # Strip internal page-navigation noise only
            _INTERNAL_SOURCES = {"home", "product", "collection", "cart", "searchresults"}
            _INTERNAL_MEDIUMS = {"(not set)", "(none)", ""}
            _internal = (
                (df_raw["sessionSource"].isin(_INTERNAL_SOURCES) & df_raw["sessionMedium"].isin(_INTERNAL_MEDIUMS))
                | ((df_raw["sessionSource"] == "(not set)") & (df_raw["sessionMedium"] == "product-links"))
            )
            df_all = df_raw[~_internal].copy()

            # Apply improved grouping rules to every row
            df_all["Improved Channel"] = df_all.apply(
                lambda r: _apply_improved_grouping(
                    r["sessionSource"],
                    r["sessionMedium"],
                    r["sessionCampaignName"],
                    r["sessionDefaultChannelGroup"],
                ),
                axis=1,
            )

            # Build unified display table grouped by source+medium+channels
            tbl = (
                df_all
                .rename(columns={
                    "sessionDefaultChannelGroup": "GA4 Default Channel",
                    "sessionSource":             "Source",
                    "sessionMedium":             "Medium",
                })
                .groupby(
                    ["Source", "Medium", "GA4 Default Channel", "Improved Channel"],
                    as_index=False,
                )["sessions"].sum()
                .sort_values("sessions", ascending=False)
            )
            tbl["Sessions"] = tbl["sessions"].apply(lambda v: num(int(v)))
            tbl = tbl[["Source", "Medium", "Sessions", "GA4 Default Channel", "Improved Channel"]]

            # ── BEFORE badge ─────────────────────────────────────────────
            st.markdown("""
            <div style="display:flex;align-items:center;gap:10px;margin:24px 0 8px 0;">
                <span style="font-size:14px;font-weight:900;color:#ef9a9a;
                             background:rgba(239,83,80,0.12);border:1px solid rgba(239,83,80,0.30);
                             padding:4px 12px;border-radius:20px;">● BEFORE</span>
                <span style="font-size:13px;color:#9e9e9e;">
                    Every source/medium combination — what GA4's default grouping assigned them
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(
                tbl[["Source", "Medium", "Sessions", "GA4 Default Channel"]],
                use_container_width=True,
                hide_index=True,
            )

            # ── Transition ────────────────────────────────────────────────
            st.markdown("""
            <div style="margin:32px 0;padding:18px 22px;
                        background:rgba(100,255,218,0.05);
                        border-left:3px solid rgba(100,255,218,0.45);
                        border-radius:6px;font-size:14px;color:#b0bec5;line-height:1.8;">
                We analyzed what each source/medium combination actually represents
                and built the <strong style="color:#64ffda;">Improved Channel Grouping</strong> rules
                to classify them correctly — below is how these exact same sessions are
                classified going forward.
            </div>
            """, unsafe_allow_html=True)

            # ── AFTER badge ───────────────────────────────────────────────
            st.markdown("""
            <div style="display:flex;align-items:center;gap:10px;margin:24px 0 8px 0;">
                <span style="font-size:14px;font-weight:900;color:#90caf9;
                             background:rgba(66,165,245,0.12);border:1px solid rgba(66,165,245,0.30);
                             padding:4px 12px;border-radius:20px;">● WITH IMPROVED GROUPING</span>
                <span style="font-size:13px;color:#9e9e9e;">
                    Same sessions — now correctly classified by the new channel group rules
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(
                tbl[["Source", "Medium", "Sessions", "Improved Channel"]],
                use_container_width=True,
                hide_index=True,
            )

            still_unassigned = (tbl["Improved Channel"] == "Unassigned").sum()
            if still_unassigned:
                callout(
                    f"{still_unassigned} source/medium combination(s) remain Unassigned even under "
                    "the improved rules — these are genuinely unclassifiable with current UTM data.",
                    kind="warning",
                )
            else:
                callout(
                    "Every source/medium combination now has a named channel identity "
                    "under the improved grouping rules — zero traffic lost to Unassigned.",
                    kind="success",
                )

    except Exception as e:
        st.error(f"GA4 query failed: {e}")

    # ── New Named Channels (subsection) ──────────────────────────────────────
    st.markdown("---")
    st.markdown("#### New Channels Created by Improved Grouping")
    st.caption("These channels did not exist in GA4 default grouping — all traffic fell into Referral, Unassigned, or was invisible.")

    _NEW_CHANNELS_INFO = [
        {
            "Channel": "WhatsApp",
            "What it captures": "Traffic from WhatsApp broadcast links (l.wl.co, wa.me, whatsapp sources)",
            "Why it matters": "Highest-CVR channel (~8%). Was buried in generic 'Referral' — revenue completely unattributable.",
        },
        {
            "Channel": "Offline QR",
            "What it captures": "Physical packaging QR codes (qrcode/offline/package medium; package/bottle/pack source)",
            "Why it matters": "Proves product packaging drives digital traffic. No attribution existed before — sessions vanished into Direct.",
        },
        {
            "Channel": "Shopify campaigns",
            "What it captures": "Influencer & shareable link campaigns using Shopify's built-in shareable link feature (source: shareable_link)",
            "Why it matters": "Influencer ROI was invisible. Now every shareable-link click has its own named channel.",
        },
        {
            "Channel": "AI referral",
            "What it captures": "Traffic from ChatGPT, Perplexity, Gemini (AI product discovery)",
            "Why it matters": "New acquisition channel. Was classified as generic Referral — now tracked separately to monitor AI-driven discovery growth.",
        },
        {
            "Channel": "Paid (unattributed)",
            "What it captures": "Sessions where medium is paid/cpc but source is (not set) — ad click with no source tag",
            "Why it matters": "Isolates spend that fired but lost its source attribution. Makes broken tracking visible instead of hiding in Unassigned.",
        },
        {
            "Channel": "Google Free Product Listings",
            "What it captures": "Google Shopping free listings identified by ad content parameter sag_organic",
            "Why it matters": "Free Shopping traffic was merged with paid Shopping. Now separated — shows organic Google product surface performance.",
        },
        {
            "Channel": "Meta paid",
            "What it captures": "facebook/fb/an/Facebook_Right_Column sources + paid/cpc/fb medium (Meta Audience Network included)",
            "Why it matters": "Was split across Paid Social, Unassigned, and (not set). All Meta paid variants now land in one named channel.",
        },
        {
            "Channel": "Instagram paid",
            "What it captures": "instagram/ig/IGShopping/instagram.com sources + paid/cpc/fb medium",
            "Why it matters": "Instagram paid was indistinguishable from Facebook paid. Now tracked as its own channel for separate ROI visibility.",
        },
        {
            "Channel": "Instagram organic",
            "What it captures": "instagram/ig/IGShopping/instagram.com sources + social/organic medium",
            "Why it matters": "Instagram organic traffic was merged into generic 'Organic Social'. Now separated for platform-specific reporting.",
        },
        {
            "Channel": "Meta organic",
            "What it captures": "m.facebook.com / l.facebook.com / lm.facebook.com + referral medium (organic Facebook link clicks)",
            "Why it matters": "Facebook link shares appeared as 'Referral' with no identity. Now clearly labeled as Meta organic reach.",
        },
        {
            "Channel": "Meta paid (untagged)",
            "What it captures": "Facebook source + no UTM medium + campaign present (Meta auto-tag partial failure)",
            "Why it matters": "Isolates partially-tagged Meta spend so ad budget isn't lost in Unassigned.",
        },
        {
            "Channel": "Meta organic (untagged)",
            "What it captures": "Facebook source + no UTM medium + no campaign (pure organic, no tags at all)",
            "Why it matters": "Separates organic Facebook reach from paid — previously both fell into (not set) / Unassigned.",
        },
        {
            "Channel": "Reddit",
            "What it captures": "Traffic from reddit.com — community posts and threads linking to Tharaa",
            "Why it matters": "Was merged into generic 'Organic Social'. Now tracked separately to see if Reddit community drives conversions.",
        },
        {
            "Channel": "LinkedIn",
            "What it captures": "Traffic from linkedin.com — professional network link clicks",
            "Why it matters": "Was merged into generic 'Organic Social'. Named channel allows B2B or professional segment tracking.",
        },
        {
            "Channel": "Pinterest",
            "What it captures": "Traffic from pinterest.com and country subdomains (ph.pinterest.com etc.)",
            "Why it matters": "Was merged into 'Organic Social'. Pinterest drives product discovery — named channel shows visual commerce impact.",
        },
        {
            "Channel": "Zalo",
            "What it captures": "Traffic from Zalo (Vietnamese messaging app, similar to WhatsApp — source: zalo)",
            "Why it matters": "Emerging messaging channel. Previously unidentified. Named for separate tracking alongside WhatsApp.",
        },
        {
            "Channel": "Link Shortener",
            "What it captures": "Traffic via bit.ly, tinyurl, ow.ly, t.ly, short.io link shorteners",
            "Why it matters": "3K+ sessions came through shortened links (WhatsApp shares, email, social posts). Now visible instead of buried in Organic Social.",
        },
        {
            "Channel": "Google Referral",
            "What it captures": "Traffic from google.com with referral medium — clicks from Google Docs, Maps, or other Google products",
            "Why it matters": "Distinguished from google/organic (search). Shows traffic from shared Google docs or Maps listings.",
        },
    ]

    st.dataframe(
        pd.DataFrame(_NEW_CHANNELS_INFO),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ── 2.2 WhatsApp Channel ────────────────────────────────────────────────
    st.subheader("2.2 — WhatsApp as Standalone Channel")
    callout(
        "WhatsApp is Tharaa's highest-converting channel (~7–8% CVR) — yet before the audit it was "
        "completely invisible, buried inside generic 'Referral'. "
        "The improved channel grouping introduces a dedicated 'WhatsApp' channel, "
        "making revenue and conversion fully attributable for the first time.",
        kind="info",
    )

    _WA_BEFORE = ("2025-11-01", "2026-05-31")
    _WA_FILTER = or_filter(
        contains_filter("sessionSource", "l.wl.co"),
        contains_filter("sessionSource", "whatsapp"),
        contains_filter("sessionSource", "wa.me"),
    )

    col_b, col_a = st.columns(2)

    # ── BEFORE: WhatsApp sources → default channel group (Referral) ──────
    with col_b:
        st.markdown("### Before")
        st.caption("Nov 2025 – May 2026 · sessionDefaultChannelGroup")
        callout(
            "All WhatsApp link traffic appears as 'Referral'. "
            "High CVR is invisible — no way to identify it as WhatsApp.",
            kind="warning",
        )
        try:
            df_wa_b, _ = run_report(
                dimensions=("sessionSource", "sessionDefaultChannelGroup"),
                metrics=("sessions", "transactions", "purchaseRevenue"),
                single=_WA_BEFORE,
                dim_filter=_WA_FILTER,
                order_by_metric="sessions",
            )
            if not df_wa_b.empty:
                total_b_sessions = int(df_wa_b["sessions"].sum())
                total_b_txn      = int(df_wa_b["transactions"].sum())
                total_b_rev      = df_wa_b["purchaseRevenue"].sum()
                cvr_b            = total_b_txn / total_b_sessions * 100 if total_b_sessions else 0

                k1, k2, k3 = st.columns(3)
                k1.metric("Sessions",  num(total_b_sessions))
                k2.metric("Purchases", num(total_b_txn))
                k3.metric("CVR",       f"{cvr_b:.1f}%")

                df_wa_b = df_wa_b.rename(columns={
                    "sessionSource":               "Source",
                    "sessionDefaultChannelGroup":  "Default Channel",
                    "sessions":                    "Sessions",
                    "transactions":                "Purchases",
                    "purchaseRevenue":             "Revenue (EGP)",
                })
                df_wa_b["Revenue (EGP)"] = df_wa_b["Revenue (EGP)"].apply(egp)
                df_wa_b["Sessions"]      = df_wa_b["Sessions"].apply(num)
                df_wa_b["Purchases"]     = df_wa_b["Purchases"].apply(num)
                st.dataframe(df_wa_b[["Source", "Default Channel", "Sessions", "Purchases", "Revenue (EGP)"]],
                             use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"GA4 query failed: {e}")

    # ── AFTER: same sources → improved channel group (WhatsApp) ──────────
    with col_a:
        st.markdown("### After")
        st.caption(f"{after[0]} – {after[1]} · Improved channel grouping")
        callout(
            "Same sources now route to 'WhatsApp' via the custom channel group rule. "
            "Revenue and CVR are fully visible and attributable.",
            kind="success",
        )
        try:
            df_wa_a, _ = run_report(
                dimensions=("sessionSource", "sessionCustomChannelGroup:15071794161"),
                metrics=("sessions", "transactions", "purchaseRevenue"),
                single=after,
                dim_filter=_WA_FILTER,
                order_by_metric="sessions",
            )
            if not df_wa_a.empty:
                total_a_sessions = int(df_wa_a["sessions"].sum())
                total_a_txn      = int(df_wa_a["transactions"].sum())
                total_a_rev      = df_wa_a["purchaseRevenue"].sum()
                cvr_a            = total_a_txn / total_a_sessions * 100 if total_a_sessions else 0

                k1, k2, k3 = st.columns(3)
                k1.metric("Sessions",  num(total_a_sessions))
                k2.metric("Purchases", num(total_a_txn))
                k3.metric("CVR",       f"{cvr_a:.1f}%")

                df_wa_a = df_wa_a.rename(columns={
                    "sessionSource":                          "Source",
                    "sessionCustomChannelGroup:15071794161":  "Improved Channel",
                    "sessions":                               "Sessions",
                    "transactions":                           "Purchases",
                    "purchaseRevenue":                        "Revenue (EGP)",
                })
                df_wa_a["Revenue (EGP)"] = df_wa_a["Revenue (EGP)"].apply(egp)
                df_wa_a["Sessions"]      = df_wa_a["Sessions"].apply(num)
                df_wa_a["Purchases"]     = df_wa_a["Purchases"].apply(num)
                st.dataframe(df_wa_a[["Source", "Improved Channel", "Sessions", "Purchases", "Revenue (EGP)"]],
                             use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"GA4 query failed: {e}")

    st.divider()

    # ── 2.3 Traffic Quality: Bot Removal ─────────────────────────────────────
    st.subheader("2.3 — Traffic Quality: Bot Removal")
    _FULL_BEFORE = ("2025-11-01", "2026-05-31")
    st.caption("Before period hardcoded Nov 2025 – May 2026 (full window of broken tracking). After = current audit period.")

    callout(
        "Bot/junk sources (Pangle, Tag Assistant, Hotjar, googleapis) were identified as inflated, "
        "misleading traffic and are excluded from the after period.",
        kind="info",
    )

    # ── Bot & Junk Sources ────────────────────────────────────────────────
    st.markdown("**Bot & Junk Sources** (Pangle, Tag Assistant, Hotjar, googleapis)")
    try:
        filt = or_filter(*[contains_filter("sessionSource", s) for s in BOT_SOURCES])
        df3, _ = run_report(
            dimensions=("sessionSource",),
            metrics=("sessions", "transactions"),
            before=_FULL_BEFORE, after=after,
            dim_filter=filt,
            order_by_metric="sessions",
        )
        merged3 = merge_periods(df3, ["sessionSource"], ["sessions", "transactions"])

        bot_kpi = st.columns(2)
        kpi(bot_kpi[0], "Total Bot/Junk Sessions",
            int(merged3["sessions_before"].sum()), int(merged3["sessions_after"].sum()),
            format_fn=num, good="down",
            note="Pangle, Tag Assistant, Hotjar, googleapis")
        kpi(bot_kpi[1], "Bot Transactions Removed",
            int(merged3["transactions_before"].sum()), int(merged3["transactions_after"].sum()),
            format_fn=num, good="down",
            note="Bot-attributed purchases eliminated from reports")

        merged3 = merged3.rename(columns={
            "sessionSource": "Source",
            "sessions_before": "Sessions (Before)", "sessions_after": "Sessions (After)",
            "transactions_before": "Purchases (Before)", "transactions_after": "Purchases (After)",
        })
        for c in ["Sessions (Before)", "Sessions (After)", "Purchases (Before)", "Purchases (After)"]:
            merged3[c] = merged3[c].apply(num)
        st.dataframe(
            merged3[["Source", "Sessions (Before)", "Sessions (After)",
                      "Purchases (Before)", "Purchases (After)"]],
            use_container_width=True, hide_index=True,
        )
        callout("Pangle alone generated 43,481 junk sessions in November 2025. "
                "Annotate that period in GA4 manually.", kind="warning")

    except Exception as e:
        st.error(f"GA4 query failed: {e}")
