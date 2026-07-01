import streamlit as st
import pandas as pd
import plotly.express as px
from ga4_client import run_report, run_funnel_report, string_filter
from utils.formatters import num
from utils.charts import callout

# Generated via a 76-agent fan-out, one agent per GA4 event, each given the event's exact
# trigger description and asked to write a revenue-gain or cost-cut use case for it.
EVENT_USE_CASES = {
    "navigation_click": {
        "category": "Navigation", "tag": "cost",
        "title": "Checkout-Page Navigation Leak",
        "narrative": "Nav clicks aren't all equal — one fired from the homepage is healthy browsing, one fired from cart or checkout is a shopper bailing on a near-finished purchase. The page-type breakdown shows exactly where these clicks concentrate, exposing whether the main menu is pulling users off the highest-intent pages. If checkout/cart nav clicks show up disproportionately and this event's conversion lift trails baseline, it justifies stripping or collapsing the nav on those steps to stop the leak before it costs more completed orders.",
        "secondary": "page_type", "secondary_param": "",
    },
    "hamburger_menu_open": {
        "category": "Navigation", "tag": "cost",
        "title": "Where Mobile Shoppers Get Stuck",
        "narrative": "Hamburger taps are a \"user is hunting for something\" signal -- shoppers don't open the side menu when the page already gives them what they need. The page_type breakdown shows where that hunting concentrates: heavy openings on product or cart pages mean people are abandoning the flow mid-intent to go find navigation, a friction point worth fixing (sticky category links, better PDP cross-nav) before it costs more checkouts. Pair with the conversion-lift comparison -- if menu-openers convert below baseline, it confirms this is a stuck-user signal, not casual browsing, and justifies prioritizing IA fixes on whichever page type spikes hardest.",
        "secondary": "page_type", "secondary_param": "",
    },
    "hamburger_menu_close": {
        "category": "Navigation", "tag": "cost",
        "title": "Mobile Navigation Friction Locator",
        "narrative": "hamburger_menu_close is a digital body-language signal — it shows whether a shopper popped open the mobile nav and actually went somewhere, or just closed it and gave up looking. The conversion-lift comparison tells you whether menu-closers convert worse than baseline, which separates \"found it and left the menu\" from \"couldn't find it and bailed.\" If closes cluster heavily on a specific page type, that's the page where shoppers are losing the thread — restructure the category list or add an on-page search prompt there before the friction costs more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "mega_menu_open": {
        "category": "Navigation", "tag": "revenue",
        "title": "Category Interest Signals Merchandising Priority",
        "narrative": "mega_menu_open fires the moment a shopper deliberately opens a category dropdown — a stronger intent signal than a passive pageview, since they're actively scanning for where to go next. The conversion-lift chart shows whether mega-menu explorers convert above baseline, which justifies investing more merchandising real estate (featured collections, best-seller picks) inside the dropdown rather than treating it as plain navigation chrome. The page-type breakdown shows where in the journey shoppers reach for the menu: heavy opens from collection or product pages flag people hunting for alternatives they can't easily find — a navigation gap worth fixing before it costs checkouts — while heavy opens from the homepage validate which top-level categories deserve the most prominent menu placement.",
        "secondary": "page_type", "secondary_param": "",
    },
    "logo_click": {
        "category": "Navigation", "tag": "cost",
        "title": "Checkout Bailout Early-Warning Signal",
        "narrative": "logo_click is a bail-back signal — a user abandoning their current page to retreat to the homepage instead of pushing forward. Breaking it down by page_type pinpoints where that retreat happens: if clicks cluster on cart or checkout, that's not casual navigation, it's mid-funnel abandonment in EGP terms. The conversion-lift comparison shows whether these escapees still convert elsewhere or are lost for good, telling you whether that page needs a UX fix before it costs more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "footer_link_click": {
        "category": "Navigation", "tag": "cost",
        "title": "Cart Exit Risk Via Footer",
        "narrative": "Footer clicks are usually low-intent housekeeping (policies, contact, socials), but the page_type breakdown reveals whether they spike on cart or checkout pages -- a sign shoppers are bailing mid-funnel to manually verify shipping cost, returns policy, or support info instead of trusting the checkout as-is. If the conversion-lift comparison shows this segment converts below baseline when fired from cart/checkout, that's a concrete case for moving that reassurance content (shipping estimate, returns terms, contact link) directly into the cart drawer so users stop navigating away and risking abandonment. If the spike is instead on home/collection pages, it's just passive browsing and not worth engineering effort.",
        "secondary": "page_type", "secondary_param": "",
    },
    "mobile_toolbar_tap": {
        "category": "Navigation", "tag": "cost",
        "title": "Checkout-Page Nav Distraction Signal",
        "narrative": "Every mobile_toolbar_tap is a shopper choosing to jump elsewhere via the bottom nav instead of acting on the page in front of them. The page-type breakdown shows exactly where that detour happens most — heavy taps from product or cart pages flag a specific template where shoppers are bailing on high-intent screens instead of completing the action, pointing straight at which page needs a clearer in-page CTA or nav redesign. The conversion-lift comparison confirms whether heavy toolbar users actually convert worse than baseline, telling you whether this friction is worth fixing before it costs more checkouts or is just normal browsing behavior to ignore.",
        "secondary": "page_type", "secondary_param": "",
    },
    "announcement_bar_click": {
        "category": "Navigation", "tag": "revenue",
        "title": "Promo Banner Conversion Validator",
        "narrative": "announcement_bar_click captures shoppers actively engaging with whatever sale, discount code, or shipping offer Tharaa is running site-wide in the top banner. The conversion-lift comparison tells you whether that specific offer is actually pulling its weight — if clickers convert well above baseline, keep and scale the offer (push it harder in ads/email); if lift is flat, the messaging is dead weight worth replacing. The page_type breakdown shows whether engagement concentrates on entry pages (home) or persists deep into collection/product/cart pages, which decides whether the banner copy can stay generic or needs a stronger, page-specific hook to keep converting shoppers further down the funnel.",
        "secondary": "page_type", "secondary_param": "",
    },
    "announcement_bar_close": {
        "category": "Navigation", "tag": "cost",
        "title": "Announcement Bar Friction Diagnostic",
        "narrative": "announcement_bar_close is a friction signal, not an engagement one — users are actively clearing the promo strip out of their way rather than reading it. The page_type breakdown shows whether dismissals cluster on entry pages (home/collection), where it's harmless noise, or spike on product/cart pages, where it's getting in the way of the purchase decision and worth suppressing there to protect checkout flow. The conversion-lift comparison tells you whether dismissers convert at, above, or below baseline, sizing whether this screen real estate is pulling its weight or should be shortened/redesigned to cut wasted space and message fatigue.",
        "secondary": "page_type", "secondary_param": "",
    },
    "search_drawer_open": {
        "category": "Search", "tag": "revenue",
        "title": "Search-First Shopper Intent Signal",
        "narrative": "search_drawer_open captures the moment a visitor abandons browsing and turns to search — one of the highest-intent actions on the site, since self-directed searchers usually know what they want. The conversion-lift comparison tells you whether these searchers close at a higher rate than baseline, which justifies promoting search more aggressively (sticky search icon, autocomplete, trending terms) as a primary conversion lever rather than a secondary tool. The page_type breakdown shows where that intent originates: if drawer opens cluster heavily on collection pages, it signals category filtering and merchandising aren't surfacing the right products, and prioritizing fixes there captures sales that would otherwise rely on the shopper finding search at all.",
        "secondary": "page_type", "secondary_param": "",
    },
    "search_drawer_close": {
        "category": "Search", "tag": "cost",
        "title": "Search Friction Costs Conversions",
        "narrative": "search_drawer_close fires when a shopper dismisses the search panel, often right after failing to find what they typed for. The conversion-lift comparison tells you whether closers convert below baseline — a sign of unresolved search intent worth fixing with better autocomplete, synonyms, or no-results handling — or above baseline, meaning search is just a quick-navigation habit and not a leak. Breaking closes out by page type pinpoints where abandonment concentrates (e.g. heavy closes on collection pages flag shoppers who can't find a size or variant), justifying a targeted search-relevance fix before it bleeds more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "search_query": {
        "category": "Search", "tag": "revenue",
        "title": "Site Search Reveals Hidden Demand",
        "narrative": "search_query captures the literal words shoppers type — the rawest, least-filtered demand signal on the site, often surfacing products, brands, or sizes that aren't merchandised prominently or stocked at all. The conversion-lift comparison shows whether these high-intent searchers convert above baseline; if they don't, the results page is burying matches and quietly costing sales worth fixing. The daily trend chart flags sudden spikes in search volume — a fast-rising term justifies fast-tracking that SKU into a homepage feature or restock order before the demand window closes.",
        "secondary": "trend", "secondary_param": "",
    },
    "search_no_results": {
        "category": "Search", "tag": "cost",
        "title": "Search Dead-Ends Leaking Revenue",
        "narrative": "search_no_results flags every search that dead-ends with zero matching products — a hard stop for shoppers who arrived with explicit purchase intent and lost it to a search-index miss (typos, Arabic/English mismatches, missing synonyms) or a genuine catalog gap. The conversion-lift comparison shows exactly how much revenue these dead-end sessions forfeit versus baseline, telling you whether the fix is search/autocorrect tuning or stocking the products people are actually typing for. The daily trend isolates spikes — a jump right after a campaign launch means paid traffic is being funneled at queries the catalog or search engine can't serve, a leak worth plugging before more ad spend gets wasted on it.",
        "secondary": "trend", "secondary_param": "",
    },
    "search_autocomplete_click": {
        "category": "Search", "tag": "revenue",
        "title": "Search-to-Purchase Fast Lane",
        "narrative": "Autocomplete clicks are the highest-intent search signal on the site — the shopper already knows what they want and skips straight to a specific product instead of browsing. The conversion-lift chart will likely confirm this cohort converts well above baseline, which justifies investing in autocomplete relevance (typo tolerance, Arabic/English matching, image thumbnails in the dropdown). The item breakdown shows exactly which products and collections get clicked most from suggestions, so merchandising can prioritize stock and pricing on those SKUs to capture demand the autocomplete data is already proving exists.",
        "secondary": "item", "secondary_param": "",
    },
    "product_card_click": {
        "category": "Product Discovery", "tag": "revenue",
        "title": "Where Product Discovery Converts Best",
        "narrative": "product_card_click marks the first real intent signal in the discovery funnel — a shopper engaging with a specific item instead of scrolling past it. The conversion-lift comparison confirms whether that click-level engagement actually predicts a sale, justifying continued investment in card design and grid placement. The page-type breakdown shows which surfaces — homepage, collection grids, search results — generate the highest volume and highest-converting clicks, so merchandising effort and prime real estate can be reallocated toward the surfaces that actually drive revenue instead of split evenly across the site.",
        "secondary": "page_type", "secondary_param": "",
    },
    "filter_applied": {
        "category": "Product Discovery", "tag": "revenue",
        "title": "Filter Demand Signals Inventory Gaps",
        "narrative": "filter_applied is a live read on exactly which attributes shoppers are hunting for — color, size, price band — concentrated on the collection pages where they go looking. The conversion-lift comparison shows whether filtering helps people zero in on a purchase or stalls them out instead, and the per-collection breakdown pinpoints which categories see the heaviest filter use. Use that to prioritize buying and restocking toward the sizes, colors, and price ranges shoppers are explicitly filtering for, and flag any collection with heavy filtering but weak resulting conversion as an assortment gap costing sales.",
        "secondary": "item", "secondary_param": "",
    },
    "filter_removed": {
        "category": "Product Discovery", "tag": "cost",
        "title": "Filter Friction Costs Conversions",
        "narrative": "filter_removed fires when a shopper undoes a filter they just set — a strong signal the narrowed result set was too sparse, mismatched, or just plain wrong, not that they were happily browsing. The conversion-lift comparison tells you whether these self-correctors still buy at baseline or drop off, exposing whether the filter taxonomy is actively bleeding sales. The page_type breakdown pinpoints which page types (collection vs. search vs. category) generate the most filter reversals, so you know exactly where to audit filter logic — loosening overly aggressive size/stock/price filters — before the friction costs more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "sort_changed": {
        "category": "Product Discovery", "tag": "revenue",
        "title": "Default Sort Order Friction",
        "narrative": "Every sort_changed fire is a shopper voting against the page's default ordering — they didn't trust \"Featured\" or \"Best Selling\" to surface what they want, so they forced Price or New In themselves. The page_type breakdown shows exactly which listing surfaces (collection vs. category vs. search results) get overridden most, telling merchandising precisely where the default sort logic is mismatched with demand instead of guessing site-wide. Pair that with the conversion-lift comparison to confirm resorting actually helps these shoppers buy rather than stalling them, then justify rebuilding the default sort rule on the worst-offending page type to capture that conversion without the manual detour.",
        "secondary": "page_type", "secondary_param": "",
    },
    "pagination_click": {
        "category": "Product Discovery", "tag": "revenue",
        "title": "Catalog Depth Signals Purchase Intent",
        "narrative": "Clicking past page one means the default product grid didn't close the sale on sight — this shopper is still hunting. The conversion-lift comparison tells you whether these diggers convert above baseline (worth investing in) or bail anyway (a friction tax worth fixing). The page-type breakdown shows which page types generate the heaviest pagination, so you know whether to prioritize better default sort/filters on collection pages or fix a bloated search-results grid — directing merchandising effort where it actually recovers lost conversions instead of guessing.",
        "secondary": "page_type", "secondary_param": "",
    },
    "swatch_click": {
        "category": "Product Page", "tag": "revenue",
        "title": "Variant Demand Signals Restock Priority",
        "narrative": "swatch_click captures the moment a shopper actively chooses a color or material — the clearest pre-purchase variant-preference signal on the product page. The conversion-lift comparison shows whether variant exploration actually predicts a sale, telling you whether to push swatch interaction harder in merchandising or treat it as low-intent browsing. The item breakdown ranks which specific products draw the heaviest swatch activity, sizing which SKUs' color/material options deserve restock priority or expanded inventory to capture that proven demand.",
        "secondary": "item", "secondary_param": "",
    },
    "size_chosen": {
        "category": "Product Page", "tag": "revenue",
        "title": "Size-Intent Signals: Per-Product Remarketing",
        "narrative": "Picking a size is the last cognitive step before add-to-cart, making size_chosen one of the strongest pre-purchase intent signals on the product page. The conversion-lift chart shows how much further these shoppers are along the funnel than the store average — a big lift means every size_chosen that never converts is a near-miss worth chasing, not a dead lead. Breaking the event down by specific product URL pinpoints exactly which SKUs rack up heavy size-selection volume but weak conversion, sizing a targeted remarketing push (dynamic retargeting, stock/fit-confidence messaging) on the products where recovering that intent is worth the most EGP.",
        "secondary": "item", "secondary_param": "",
    },
    "product_tab_click": {
        "category": "Product Page", "tag": "revenue",
        "title": "Deep Product Research Signals Intent",
        "narrative": "Clicking into Description, Reviews, or Shipping tabs is active research behavior, a stronger buying-intent signal than passive scrolling. The conversion-lift chart shows whether this digging correlates with meaningfully higher purchase rates, and the per-product breakdown pinpoints exactly which SKUs draw the heaviest research before checkout. Those are your high-consideration items — flag them for richer descriptions, more visible reviews, or clearer shipping/return copy to convert the rest of their traffic instead of losing undecided shoppers.",
        "secondary": "item", "secondary_param": "",
    },
    "product_image_click": {
        "category": "Product Page", "tag": "revenue",
        "title": "Visual Interest Ranks Top Products",
        "narrative": "Zooming into the main product image is a deliberate inspection move — in fashion ecommerce, shoppers do this to check fabric, print, or fit before committing, making it one of the sharpest pre-purchase intent signals on the page. The conversion-lift chart confirms how much more likely these zoomers are to buy versus the store baseline, validating whether image engagement deserves more weight in merchandising decisions. The item breakdown names exactly which products pull this behavior, so the team can prioritize those SKUs for homepage placement, ad creative, and restock — and flag high-zoom, low-convert products where better photos or added detail (size, material) could close the sale.",
        "secondary": "item", "secondary_param": "",
    },
    "product_thumbnail_click": {
        "category": "Product Page", "tag": "revenue",
        "title": "Gallery Engagement Flags High-Intent Products",
        "narrative": "product_thumbnail_click fires when a shopper actively cycles through extra angles of a specific item in the gallery — a stronger purchase-consideration signal than a passive product view. The conversion-lift comparison shows whether this digging-deeper behavior actually predicts a sale, telling you if the gallery is closing intent or just stalling it. Breaking it down by item surfaces exactly which SKUs draw the most gallery exploration, so you can feature the high-converting ones in ads and homepage placements, and flag high-interest-but-low-convert products as candidates for better photography before that interest leaks to a competitor.",
        "secondary": "item", "secondary_param": "",
    },
    "lightbox_open": {
        "category": "Product Page", "tag": "revenue",
        "title": "Visual Inspection Signals Purchase Readiness",
        "narrative": "lightbox_open is a deep-inspection signal — in fashion ecommerce, zooming into fullscreen images is how shoppers check fabric texture, fit, and detail before committing, so it sits close to purchase intent. The conversion-lift comparison confirms whether this scrutiny actually predicts buying or just window-shopping. The item breakdown names exactly which products draw the most zoom-ins, telling you where to invest in richer photography (extra angles, higher-res zoom) to convert that interest, and which high-traffic items are getting inspected heavily but still underperforming — a sign their current images are costing sales.",
        "secondary": "item", "secondary_param": "",
    },
    "quick_shop_open": {
        "category": "Product Page", "tag": "revenue",
        "title": "High-Intent Product Demand Signal",
        "narrative": "quick_shop_open fires when a shopper engages enough to preview a product without leaving the grid — a stronger intent signal than a hover or impression. The conversion-lift chart shows whether that fast-path browsing actually converts at a higher clip than store baseline, telling you if quick shop is closing sales or just feeding window-shopping. Breaking the event down by item pinpoints which specific products generate disproportionate quick-shop interest, so merchandising can prioritize those SKUs for homepage placement, ad spend, or restock before demand outpaces stock.",
        "secondary": "item", "secondary_param": "",
    },
    "sticky_atc_visible": {
        "category": "Product Page", "tag": "revenue",
        "title": "Engaged Scrollers, Untapped Remarketing List",
        "narrative": "sticky_atc_visible marks shoppers who scrolled deep enough on a product page to trigger the persistent Add-to-Cart bar — a strong proxy for serious browsing intent beyond a quick bounce. The conversion-lift chart tells you whether this scroll-depth signal actually predicts purchase, which sizes how aggressively to build a dynamic remarketing audience around it. The item breakdown surfaces which specific product pages rack up this high-intent signal without converting, flagging exactly which PDPs need a stronger above-the-fold pitch, price, or trust signal before that engaged traffic is wasted.",
        "secondary": "item", "secondary_param": "",
    },
    "out_of_stock_viewed": {
        "category": "Product Page", "tag": "revenue",
        "title": "Restock Priority From Lost Demand",
        "narrative": "out_of_stock_viewed fires when a shopper lands on a product page for an item that's currently unavailable — real purchase intent hitting a dead end instead of an add-to-cart. The conversion-lift comparison shows whether these shoppers still convert elsewhere on the site or just leave, quantifying how much revenue each stockout is actually bleeding. The item breakdown ranks exactly which out-of-stock SKUs are pulling the most product-page traffic, turning a vague \"we're out of stock\" problem into a prioritized, demand-sized restock list for merchandising.",
        "secondary": "item", "secondary_param": "",
    },
    "cart_drawer_open": {
        "category": "Cart Behavior", "tag": "cost",
        "title": "Cart Peek-to-Purchase Gap",
        "narrative": "Cart drawer opens are a softer signal than add-to-cart — plenty of shoppers pop it just to check contents, quantity, or shipping cost, not because they're ready to buy. The conversion-lift comparison tells you whether that glance actually correlates with purchase or mostly stalls out, and the page-type breakdown shows where the habit concentrates — product pages (last-second reassurance) versus collection or home (early-stage browsing). If lift is weak and opens cluster heavily on one page type, that's a friction point in the drawer itself — slow load, surprise shipping fees, confusing line items — worth fixing before it bleeds more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "cart_drawer_close": {
        "category": "Cart Behavior", "tag": "revenue",
        "title": "Sizing Cart Abandonment Remarketing",
        "narrative": "cart_drawer_close fires the moment a shopper reviews their cart in the sidebar and dismisses it without moving to checkout — a soft, easy-to-miss abandonment moment that sits upstream of a full cart-abandonment. The conversion-lift comparison tells you whether these dismissals are a precursor to drop-off or just normal browsing habit. Breaking the event down by cart value at the moment of close shows exactly how much EGP revenue is sitting in these dismissed carts, letting you segment and prioritize a remarketing or exit-discount trigger by cart-value tier instead of treating every drawer-close the same.",
        "secondary": "metric_avg", "secondary_param": "customEvent:cart_value",
    },
    "cart_item_remove": {
        "category": "Cart Behavior", "tag": "cost",
        "title": "Product-Level Cart Friction Signal",
        "narrative": "cart_item_remove captures an explicit, in-cart rejection of a specific product after it was already added to the basket — a sharper signal than silent abandonment. The item breakdown shows which SKUs get cut most often, flagging pricing, sizing, or imagery mismatches on those product pages worth fixing before they bleed more carts. The conversion-lift comparison tells you whether the removal is benign cart curation (shopper still checks out) or a precursor to full abandonment, which sizes how urgently to act on the worst-offending products.",
        "secondary": "item", "secondary_param": "",
    },
    "cart_item_quantity_change": {
        "category": "Cart Behavior", "tag": "revenue",
        "title": "Bulk-Buy Signal By Product",
        "narrative": "cart_item_quantity_change is a hands-on intent signal — shoppers nudging +/- mid-cart are actively reconsidering order size, not just browsing. The conversion-lift comparison shows whether this active cart engagement predicts a higher close rate than a passive add, telling you whether quantity-editors deserve a dedicated remarketing push. The item breakdown surfaces exactly which products draw repeat multi-unit edits, sizing a shortlist of SKUs worth pairing with quantity-discount or \"buy more, save more\" offers to lift average order value.",
        "secondary": "item", "secondary_param": "",
    },
    "discount_code_submitted": {
        "category": "Cart Behavior", "tag": "cost",
        "title": "Margin Leak vs Price-Sensitive Segment",
        "narrative": "discount_code_submitted flags shoppers actively negotiating price before checkout — the clearest price-sensitivity signal in the funnel. Breaking it down by customEvent:cart_value shows whether code-seeking concentrates in low-value carts (shoppers who need a nudge to convert, worth a threshold-triggered promo) or bleeds into high-value carts too (margin given away on orders that would've converted at full price anyway). Cross-reference with the conversion-lift chart: strongly positive lift means keep promoting codes to close hesitant carts; flat lift with high cart values means tighten code eligibility by order value to stop the leak.",
        "secondary": "metric_avg", "secondary_param": "customEvent:cart_value",
    },
    "cart_value_milestone": {
        "category": "Cart Behavior", "tag": "revenue",
        "title": "Cart Threshold AOV Optimizer",
        "narrative": "cart_value_milestone fires the instant a shopper's cart crosses an EGP threshold (500/1000/2000) while adding items, capturing real-time AOV momentum before checkout. Breaking it down by customEvent:threshold_value shows which specific milestone carries the strongest conversion lift — if crossing EGP 1000 converts far better than EGP 500, that's the number to anchor a free-shipping bar or gift-with-purchase to, nudging more carts up into the higher-AOV tier. If lift flattens or drops at EGP 2000, it flags a price-sensitivity ceiling worth countering with installment messaging before the cart stalls.",
        "secondary": "metric_avg", "secondary_param": "customEvent:threshold_value",
    },
    "free_shipping_progress_milestone": {
        "category": "Cart Behavior", "tag": "revenue",
        "title": "Free-Shipping Nudge Stage Optimizer",
        "narrative": "free_shipping_progress_milestone fires each time a shopper crosses a checkpoint (e.g. 25%, 50%, 75%, 90%) toward Tharaa's free-shipping minimum — a built-in upsell trigger this store never had visibility into before. The conversion-lift comparison shows whether clearing a milestone meaningfully outperforms baseline, which justifies investing in a persistent \"X EGP away from free shipping\" nudge across the funnel. Breaking the data down by which percent milestone fired pinpoints exactly where shoppers stall — if most hit 50% but few cross 90%, that's the evidence needed to either lower the free-shipping threshold or sharpen nudge copy at that specific gap to convert more near-miss carts.",
        "secondary": "metric_avg", "secondary_param": "customEvent:percent",
    },
    "cart_checkout_click": {
        "category": "Cart Behavior", "tag": "cost",
        "title": "Checkout Friction Early-Warning Signal",
        "narrative": "cart_checkout_click is the highest-intent near-miss signal in the funnel — the shopper has already committed to buy and pushed the button, so any gap between this event and an actual purchase is friction, not lost interest. The conversion-lift comparison shows whether checkout-clickers convert far above baseline (funnel is healthy) or only marginally above it, which flags a payment-method, shipping-cost, or COD-step problem worth fixing before it costs more checkouts and wastes the ad spend that already got the shopper this close. The page-type breakdown shows whether checkout intent is launched mostly from product pages (quick-buy shoppers who need a faster mobile checkout) or from the cart page (multi-item browsers), telling the team which entry point to prioritize when patching the leak.",
        "secondary": "page_type", "secondary_param": "",
    },
    "contact_form_submit": {
        "category": "Lead Generation", "tag": "revenue",
        "title": "High-Intent Lead Follow-Up Lever",
        "narrative": "A contact form submission is a discrete, taggable pool of shoppers who hit a question they couldn't self-serve and reached out before buying — about as warm as a lead gets pre-checkout. The conversion-lift comparison tells you whether these leads actually close at a higher rate than the store baseline; if they do, it justifies staffing same-day manual follow-up (call/WhatsApp) on every submission instead of letting inquiries sit in a shared inbox. The page_type breakdown shows whether inquiries cluster on product or cart pages — sizing, fit, or stock questions blocking checkout — versus a generic contact page, telling you whether to invest in PDP-level live chat or just speed up response time on existing channels.",
        "secondary": "page_type", "secondary_param": "",
    },
    "whatsapp_support_needed": {
        "category": "Lead Generation", "tag": "revenue",
        "title": "WhatsApp Support as Sales Recovery",
        "narrative": "whatsapp_support_needed fires when a shopper hits a wall mid-journey — a sizing doubt, shipping cost question, or payment confusion — and reaches for a human instead of bouncing. The conversion-lift chart tells you whether that rescue works: if WhatsApp clickers convert well above baseline, it proves the channel is recovering sales that would otherwise be lost, justifying heavier investment in WhatsApp staffing, faster response SLAs, or surfacing the button more aggressively; if they convert below baseline, it flags WhatsApp as a holding pen for shoppers about to abandon, meaning the underlying friction needs fixing on-site, not just a chat widget. The page_type breakdown pinpoints exactly where that friction concentrates — product, cart, or checkout — so the team knows which step to fix or where to staff support hardest.",
        "secondary": "page_type", "secondary_param": "",
    },
    "tab_inactive": {
        "category": "Engagement", "tag": "cost",
        "title": "Where Distraction Costs You Checkouts",
        "narrative": "tab_inactive catches the moment a shopper tabs away or minimizes — often to price-check a competitor, hunt a coupon, or just get pulled away mid-decision. The conversion-lift comparison tells you whether these distracted sessions still close at baseline or quietly die. The page-type breakdown is the fix: if tab-switching clusters on product pages it's comparison shopping you can counter with price-match or urgency messaging, but if it clusters on cart/checkout it's a friction point bleeding near-completed orders — worth fixing (sticky progress, saved-cart reminders) before it costs more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "tab_return": {
        "category": "Engagement", "tag": "revenue",
        "title": "Comparison-Shopper Win-Back Signal",
        "narrative": "tab_return flags users who alt-tabbed away from Tharaa — almost certainly to price-check a competitor or screenshot a product to a friend — then came back to keep shopping. The conversion-lift comparison shows whether these returners convert above baseline (a high-intent segment worth feeding into a retargeting or remarketing list) or below it (sales quietly leaking to comparison shopping). The page_type breakdown pinpoints where the hesitation happens — product pages signal price-checking a specific item, cart/checkout pages signal last-second comparison before payment — so you know exactly where to place a price-match badge or urgency nudge to close the sale before the next tab-away becomes a lost order.",
        "secondary": "page_type", "secondary_param": "",
    },
    "scroll_depth": {
        "category": "Engagement", "tag": "revenue",
        "title": "Deep Scroll Predicts Purchase Intent",
        "narrative": "Each scroll_depth fire (25/50/75/90%) marks how far a shopper actually consumes a page before bouncing or converting. The conversion-lift comparison tells you whether reaching the deeper thresholds (75-90%) is a real purchase-intent signal worth retargeting, or just noise — if deep scrollers convert well above baseline, that audience is worth a remarketing push and justifies investing more in below-the-fold content (reviews, sizing, social proof) that's clearly getting read. The page_type breakdown then pinpoints exactly which templates stall early — e.g. product pages losing most users before 50% means the CTA or key info needs to move higher, a fix worth making before it costs more checkouts.",
        "secondary": "page_type", "secondary_param": "",
    },
    "video_start": {
        "category": "Video", "tag": "revenue",
        "title": "Where Video Content Pays Off",
        "narrative": "Pressing play is a deliberate, attention-costly action — a shopper who fires video_start is telling you the product or story on screen earned more than a passive scroll-by. The conversion-lift comparison shows whether that attention actually converts above baseline, telling you if video is a real sales driver or just a vanity engagement metric. The page_type breakdown shows where video starts concentrate — home, collection, or product pages — so you can justify shifting video production budget toward whichever page type proves it converts, instead of spreading video assets evenly across the site.",
        "secondary": "page_type", "secondary_param": "",
    },
    "video_progress": {
        "category": "Video", "tag": "revenue",
        "title": "Watch-Depth Retargeting Trigger",
        "narrative": "video_progress fires at the 10/25/50/75% milestones, so it maps exactly how far shoppers watch before bailing. Breaking the conversion-lift comparison down by milestone (percent) shows which watch-depth actually correlates with buying — if 50%+ viewers convert far above baseline but 10-25% viewers don't, that threshold sizes a high-intent retargeting audience worth bidding harder on. It also flags whether most viewers bail before the 50% mark, which justifies shortening or re-cutting underperforming product videos before more views go to waste.",
        "secondary": "metric_avg", "secondary_param": "customEvent:percent",
    },
    "video_stop": {
        "category": "Video", "tag": "revenue",
        "title": "Right-Size Product Video Length",
        "narrative": "video_stop fires when a shopper pauses or quits a video before it ends, and the percent-watched breakdown pinpoints exactly where engagement drops off. If stops cluster in the final third and conversion lift matches finishers, viewers already got what they needed — sizing, fit, fabric — which justifies trimming the video to that length without hurting sales. If stops cluster in the first few seconds with weak conversion lift, the opening hook is failing and the video should be recut or pulled before it keeps dragging down product-page conversion.",
        "secondary": "metric_avg", "secondary_param": "customEvent:percent",
    },
    "video_complete": {
        "category": "Video", "tag": "revenue",
        "title": "Video Completers: Prime Retargeting Audience",
        "narrative": "video_complete fires when a shopper watches a product or brand video all the way through — the strongest passive engagement signal Tharaa has ever tracked, since the old broken pixel never measured video behavior at all. The conversion-lift comparison shows whether full-watch viewers convert meaningfully above baseline, which justifies building a paid remarketing audience out of video completers instead of casting a wider net at broader site visitors. The item breakdown pinpoints exactly which product or page videos pull people through to the end, telling merchandising and content teams which videos to replicate, promote harder in ads, or feature higher on the homepage.",
        "secondary": "item", "secondary_param": "",
    },
    "video_seek": {
        "category": "Video", "tag": "revenue",
        "title": "Video Hotspot Reveals Purchase Intent",
        "narrative": "Scrubbing the timeline means a shopper is hunting for specific content — sizing, fit-on-model, or a detail shot — instead of passively watching start to finish. Clustering seek_time values shows exactly which timestamp people jump straight to, pinpointing the segment that actually carries buying-relevant information. The conversion-lift chart confirms whether seekers convert better than passive viewers, justifying a re-cut that front-loads that high-interest moment instead of burying it after a slow intro.",
        "secondary": "metric_avg", "secondary_param": "customEvent:seek_time",
    },
    "review_image_clicked": {
        "category": "Social & Reviews", "tag": "revenue",
        "title": "Where Review Photos Drive Sales",
        "narrative": "review_image_clicked fires when a shopper opens a customer-submitted photo inside a product's review section — a high-intent trust check that real photos resolve (fit, color, true-to-life quality) better than star ratings or text ever can. The item breakdown shows exactly which products generate this behavior, so you can see which SKUs are converting photo-viewers at outsized rates and prioritize UGC photo collection and review-section prominence on those products, while flagging high-traffic items with thin or zero review imagery as easy wins to fix before launching paid spend toward them.",
        "secondary": "item", "secondary_param": "",
    },
    "new_customer_product_review": {
        "category": "Social & Reviews", "tag": "revenue",
        "title": "Social Proof Conversion Driver",
        "narrative": "Writing a review is a high-investment trust action — the conversion-lift chart shows whether reviewers convert above baseline, which validates spending on review-incentive campaigns (post-purchase discount codes, review nudges) as a real revenue lever rather than just a support nicety. The per-product breakdown pinpoints exactly which SKUs are earning organic reviews and which are starved of social proof, telling you which product pages need a targeted review-request push before they can convert skeptical, price-sensitive shoppers.",
        "secondary": "item", "secondary_param": "",
    },
    "google_review_user_intent": {
        "category": "Social & Reviews", "tag": "revenue",
        "title": "Trust-Gap Targeting For Reviews",
        "narrative": "google_review_user_intent fires when a shopper stops mid-browse to click into a Google review prompt or widget — a direct signal they need third-party validation before they'll trust the product enough to buy. The conversion-lift comparison shows whether that reassurance actually closes the sale or whether review-seekers bail anyway, flagging a trust gap worth fixing. The item breakdown names the exact product pages driving this behavior, so review-collection pushes and testimonial placement get prioritized on the SKUs shoppers trust least instead of spread evenly across the catalog.",
        "secondary": "item", "secondary_param": "",
    },
    "wishlist_add": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "High-Intent Remarketing Pool",
        "narrative": "wishlist_add is a near-miss signal — strong purchase intent parked for later, not lost. The conversion-lift chart shows how much more likely wishlist-savers are to eventually buy versus the store baseline, telling you whether this segment deserves a dedicated retargeting flow (price-drop alerts, back-in-stock pings, saved-item recovery emails) or is already converting fine unprompted. Breaking the data down by item exposes exactly which products rack up saves without sales — a ready-made restock and remarketing-creative priority list pulled from real shopper behavior instead of guesswork.",
        "secondary": "item", "secondary_param": "",
    },
    "wishlist_remove": {
        "category": "Wishlist & Recs", "tag": "cost",
        "title": "Suppress Dead-Wishlist Retargeting Spend",
        "narrative": "wishlist_remove marks saved intent evaporating — either the shopper already bought the item elsewhere or simply changed their mind, and the conversion-lift comparison tells you which: near-baseline conversion means a purchase likely happened, sub-baseline means real drop-off. Either way, these users should be pulled out of wishlist-reminder retargeting and abandonment emails immediately, so you stop paying to chase demand that's already gone. The item breakdown flags which specific products get abandoned most — a spike concentrated on one SKU is a cue to check its price, stock status, or competitor undercutting before that demand leaks for good.",
        "secondary": "item", "secondary_param": "",
    },
    "wishlist_product_click": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "Dormant Demand Reactivation",
        "narrative": "wishlist_product_click is the moment stalled purchase intent comes back to life — a shopper returning to click into an item they saved but never bought. The conversion-lift comparison shows how much closer this revival gets them to checkout versus a cold visitor, telling you whether wishlist re-engagement is worth investing in. The item breakdown names the exact SKUs pulling shoppers back from their wishlists, which should drive which products get featured in wishlist-abandonment remarketing emails and flag any high-click, low-purchase items worth a price or stock check.",
        "secondary": "item", "secondary_param": "",
    },
    "wishlist_page_view": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "Wishlist Revisit Remarketing Timing",
        "narrative": "wishlist_page_view catches users circling back to their saved items on their own initiative — a sharper purchase-intent signal than the original add, since it's active re-engagement, not passive browsing. The conversion-lift chart tells you whether this segment converts well above baseline, which justifies building a dedicated remarketing flow (price-drop alerts, low-stock nudges, abandoned-wishlist emails) for revisitors instead of treating wishlist as a dead-end feature. The daily trend line exposes how often and how clustered these revisits are, sizing the right cadence and send-window for triggered messages before that intent cools off and the sale is lost to a competitor.",
        "secondary": "trend", "secondary_param": "",
    },
    "cart_upsell_click": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "Cart Upsell Revenue Validator",
        "narrative": "cart_upsell_click captures the moment a shopper engages a \"you might also like\" suggestion inside the cart -- the cheapest possible spot to add a second item since checkout friction hasn't started yet. The conversion-lift comparison tells you whether upsell engagement is a real purchase-intent signal worth investing in (more prominent cart real estate, more SKUs surfaced) or just noise, justifying the call to expand or rework the recommendation logic. Breaking the clicks down by item exposes exactly which products are winning the upsell slot, so those pairings and merchandising rules can be replicated across the catalog to lift AOV.",
        "secondary": "item", "secondary_param": "",
    },
    "product_recommendation_click": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "Recommendation Widget's Revenue Proof",
        "narrative": "product_recommendation_click is the only way to know if the \"recommended for you\" widget actually sells product or just decorates the page. The conversion-lift comparison tells you whether clicking a rec meaningfully outpaces baseline purchase rate — if it does, that justifies keeping (or expanding) the engineering/app spend on the recommendation engine; if it doesn't, it flags the widget as dead weight worth cutting or retuning. Breaking clicks down by the specific product/page they fired on shows exactly which SKUs and product-page pairings the algorithm is surfacing successfully, so merchandising can lean into those placements and fix the ones that get clicks but no lift.",
        "secondary": "item", "secondary_param": "",
    },
    "product_recommendation_view": {
        "category": "Wishlist & Recs", "tag": "revenue",
        "title": "Cross-Sell Widget Placement ROI",
        "narrative": "product_recommendation_view only fires when a recommendation widget is actually scrolled into view, not just rendered in the DOM — so it measures real cross-sell exposure, not wasted impressions. The item breakdown shows exactly which pages and product templates get the most (and least) recommendation visibility, pinpointing high-traffic pages that lack a widget or bury it below the fold. Pair that with the conversion-lift chart: if exposed users convert meaningfully above baseline, it justifies rolling the widget out to every underperforming page type and prioritizing dev time on placement over other backlog items.",
        "secondary": "item", "secondary_param": "",
    },
    "login_attempt": {
        "category": "Account", "tag": "cost",
        "title": "Failed Logins, Lost Sales",
        "narrative": "login_attempt fires on every login submission, success or failure alike, so the real story lives in the login_status breakdown — a high failure rate flags an account-recovery UX bottleneck quietly costing checkouts from your highest-intent segment: returning customers with prior purchase history. The conversion-lift chart shows how much revenue rides on a smooth login flow, since these are pre-qualified buyers, not anonymous traffic. If login_status skews heavily toward failure, that justifies prioritizing a password-reset or OTP fix before more repeat-customer revenue leaks out.",
        "secondary": "value", "secondary_param": "customEvent:login_status",
    },
    "sign_up": {
        "category": "Account", "tag": "revenue",
        "title": "Account Creation Predicts Repeat LTV",
        "narrative": "sign_up is the single strongest retention signal on the site — an anonymous one-time shopper just became an identifiable, remarketable customer with order history attached. The conversion-lift comparison shows how much more likely new accounts are to purchase in this same session versus the store baseline, which justifies how aggressively to incentivize signup (account-only discount, faster reorder, early access) at the moment of highest intent. The page_type breakdown shows where people choose to create an account — heavy signups at checkout versus a dedicated account page tells you whether to keep pushing the guest-to-account conversion at the point of purchase or build a stronger standalone case for joining.",
        "secondary": "page_type", "secondary_param": "",
    },
    "order_note_added": {
        "category": "Account", "tag": "cost",
        "title": "Checkout Notes Size Fulfillment Overhead",
        "narrative": "Every order_note_added is free-text instructions someone in fulfillment has to read and manually act on before the order ships — direct labor cost that scales with volume. The cart-value breakdown shows whether these notes cluster on high-basket orders (gifting, bulk, custom requests worth the manual handling) or spread evenly across small orders (low-value noise), sizing whether a structured \"delivery instructions\" or \"this is a gift\" checkbox at checkout would cut review time without losing the orders that genuinely need a human touch. The conversion-lift chart shows whether note-writers are higher-value shoppers worth the extra handling cost in the first place.",
        "secondary": "metric_avg", "secondary_param": "customEvent:cart_value",
    },
    "cookie_consent_accepted": {
        "category": "Consent", "tag": "cost",
        "title": "Consent Rate Sizes Ad Targeting Reach",
        "narrative": "Every cookie_consent_accepted is a session where Meta/Google Ads retargeting and full GA4 attribution actually work — accepters are the only pool advertising spend can be efficiently optimized against. The daily trend shows whether the accept rate is stable or sliding, and a falling trend directly shrinks the audience paid campaigns can retarget, quietly inflating effective CAC even if ad spend stays flat. If accept rate dips after a banner copy or design change, that change is costing measurable ad efficiency and is worth reverting or re-testing.",
        "secondary": "trend", "secondary_param": "",
    },
    "cookie_consent_declined": {
        "category": "Consent", "tag": "cost",
        "title": "Declines Are Untargetable, Unattributed Revenue",
        "narrative": "cookie_consent_declined marks every session GA4 and ad platforms can't fully measure or retarget — these shoppers can still buy, but that revenue shows up as unattributed, and they're invisible to remarketing and lookalike audiences. The daily trend isolates whether the decline rate is rising (an early-warning sign the consent banner's wording, placement, or a regulatory change is bleeding measurable reach) or holding steady. A rising trend is the concrete case for testing softer consent copy or a clearer value exchange in the banner, since every extra decline is ad spend with no way to verify or optimize the resulting sale.",
        "secondary": "trend", "secondary_param": "",
    },
}

META_AUDIENCE_USE_CASES = {
    "navigation_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too generic to justify a standalone audience: clicking a main-nav link (Home, Shop, Collections, About, etc.) fires on nearly every session regardless of product interest, so it can't seed a meaningful retargeting or lookalike audience on its own. Once wired into Meta (via GTM-to-Pixel or CAPI), the destination pages it leads to are already captured with far more specific intent by page_view/ViewContent events, which would back any \"site engaged\" or category-interest Custom Audience instead. At best, navigation_click could pad a broad \"any site activity\" exclusion audience, but it adds no incremental signal beyond what page-view-based audiences already deliver.",
        "why_this_event": "The trigger condition is \"user clicked any link in the main nav\" — it tells you someone moved between sections of the site, not what they're interested in, and is fully redundant with the resulting page_view's URL/content data. Building an audience from the click itself rather than the resulting page view just adds noise without sharpening targeting.",
    },
    "hamburger_menu_open": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience. Hamburger-menu taps are a near-universal mobile UI interaction with no qualifying intent — nearly every mobile visitor touches it regardless of purchase interest, so a Custom Audience built from it would just approximate \"all mobile sessions,\" which a standard PageView/session-based top-of-funnel audience already covers at higher volume and with less engineering overhead. No retargeting, exclusion, or Lookalike-seed use case here beats what's already achievable from broader site-visit signals.",
        "why_this_event": "Tapping the hamburger icon is pure chrome/navigation, not product or purchase-related engagement, so it can't distinguish browsing intent levels — it's effectively noise sitting on top of (and redundant with) generic pageview-level traffic.",
    },
    "hamburger_menu_close": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth building a Custom Audience or optimization event from. Closing a hamburger menu carries no product, category, or purchase-intent signal — it's a UI-state toggle that fires for nearly every mobile session (anyone who opened the menu eventually closes it), so an audience seeded from it would just approximate \"all mobile visitors,\" which the existing PageView/session-based audiences already cover with cleaner semantics. It would also dilute Custom Audience quality and waste one of the 8 AEM-capped optimization event slots if mistakenly configured for optimization.",
        "why_this_event": "Closing the menu reflects navigation housekeeping, not interest or intent — it doesn't tell you what the user was looking for, viewed, or considering, unlike menu-item clicks or ViewContent, so it's pure noise for targeting versus a genuine behavioral signal.",
    },
    "mega_menu_open": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience. Mega-menu opens are pure navigation chrome (every visitor who explores the header triggers this repeatedly per session) -- no product, category, or purchase-intent signal attached. Even once wired via GTM/CAPI, this would just inflate a low-intent \"browsed site\" pool that's already covered by the automatic PageView signal Meta Pixel/WPM sends -- building a Custom Audience or optimization event on top of it adds no targeting precision over what PageView already provides.",
        "why_this_event": "Trigger condition is hover/tap on a nav dropdown -- it fires on casual browsing intent indistinguishable from a generic page visit, with no link to a specific product, category, or content viewed, so it carries no more signal than PageView while being noisier (fires multiple times per session). A real interest signal needs the user to land on or interact with specific content (e.g. ViewContent on a category/product page), which mega_menu_open never captures.",
    },
    "logo_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not recommended as an audience seed. logo_click fires identically for first-time browsers, lost users, and repeat buyers alike — it carries no product, category, or funnel-stage signal, so any Custom Audience built from it would just be a noisy subset of \"people who visited the site,\" duplicating what a standard PageView-based audience already covers with better volume and less plumbing. If used at all, it'd only make sense folded into a broad top-of-funnel \"all engaged visitors\" pool, never as a standalone retargeting or Lookalike seed.",
        "why_this_event": "Clicking the logo signals \"navigate home,\" not interest in any product, category, or purchase step — it's a generic UI escape-hatch click that happens regardless of intent (often even a misclick or habitual nav action), so it can't distinguish hot prospects from disengaged browsers the way ViewContent, AddToCart, or InitiateCheckout can.",
    },
    "footer_link_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience or optimization event. Footer links span policy pages, social icons, contact, FAQ, store locator, newsletter, etc. — clicking any one of them gives no consistent intent read, so a Custom Audience built off this event would mix high-intent (e.g., \"Track Order\") and zero-intent (e.g., \"Privacy Policy\") users indiscriminately. If anything, this data point should just feed a broader site-engagement/all-visitors audience already covered by pageview-based audiences, not get its own retargeting or Lookalike seed.",
        "why_this_event": "The trigger fires identically for any footer link clicked — policy pages, social icons, contact, careers, etc. — so it can't isolate a specific buyer intent the way a scoped event (e.g., a Contact-form submit or a \"Track Order\" click) would; it's structurally too coarse to be a clean targeting signal versus noise.",
    },
    "mobile_toolbar_tap": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "None recommended. mobile_toolbar_tap is a generic UI-chrome interaction (any icon: home, search, cart, wishlist, account) collapsed into one undifferentiated event name — it carries no specific intent signal Meta could optimize toward or segment on. Building a Custom Audience from \"people who tapped a nav icon\" would just approximate \"people who used the mobile site,\" which is already captured better by session/pageview-level signals, making it useless for retargeting, exclusion, or Lookalike seeding.",
        "why_this_event": "The trigger condition (tap any bottom-nav icon) bundles fundamentally different intents — search, cart, wishlist, account — into one event_name with no payload distinguishing which icon fired, so it's redundant with the specific, higher-signal events (Search, AddToCart, ViewContent, etc.) those taps actually lead to; it's pure navigation noise, not a distinct purchase-funnel signal.",
    },
    "announcement_bar_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Best folded into a broader \"engaged visitor\" Website Custom Audience (e.g. 25%+ scroll or 30+ sec session) rather than built standalone — once wired via GTM/CAPI it could tag a \"promo-aware\" segment for a short 7-day warm retargeting push during active sale periods, but it's too thin a signal to anchor a campaign on its own.",
        "why_this_event": "Clicking a sitewide top banner only shows curiosity about whatever promo/announcement is currently posted, not product or purchase intent, and it fires identically regardless of page/product context — that's too undifferentiated and redundant with stronger intent signals (ViewContent, AddToCart) to justify a dedicated Custom Audience or optimization event.",
    },
    "announcement_bar_close": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience. Closing a dismissible UI banner carries no purchase-funnel intent signal — fires for nearly every site visitor regardless of shopping behavior, indistinguishable from generic ViewContent/PageView traffic already captured. Building a Custom Audience or optimization event on this would just duplicate the broad \"all visitors\" pool at a worse match rate, wasting one of the 8 AEM-capped optimization event slots better spent on AddToCart/InitiateCheckout/Purchase.",
        "why_this_event": "Trigger condition (dismissing a promo banner) reflects UI housekeeping, not product or purchase interest — it doesn't correlate with funnel stage, so it adds noise rather than a distinct, actionable intent tier versus existing page-view-level signals.",
    },
    "search_drawer_open": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too weak/redundant to build a standalone Meta audience around. The only plausible use is folding it into a very broad \"site engagers\" Custom Audience (1-7 day window) alongside other micro-interactions, but on its own it shouldn't be a Conversions-objective optimization event or a dedicated retargeting segment — it'd just dilute audience quality with low-intent clicks. The actual search-submission event (with query term) is the one worth seeding audiences/Lookalikes from; this drawer-open event adds no incremental signal once that exists.",
        "why_this_event": "Clicking the search icon only opens a UI panel — it captures zero intent about what (or whether) the user is looking for anything, unlike an actual search-query event that reveals product/category interest. It's a precursor click, not a behavioral signal distinct enough from generic browsing to justify audience-building effort, and it's redundant with search_query once that's wired up.",
    },
    "search_drawer_close": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not recommended as an audience seed. Closing the search drawer fires for nearly every user who opens search regardless of outcome (found product, gave up, misclicked), so it carries no consistent intent signal worth isolating into a Custom Audience or optimization event. Any retargeting value is already better captured by search_query or post-search view_item/add_to_cart events, which encode actual intent rather than a UI dismissal.",
        "why_this_event": "The trigger condition (dismissing a panel) is intent-ambiguous -- it fires identically whether the user found what they wanted, found nothing, or closed it by accident -- so it can't distinguish hot prospects from noise the way the search query itself or a subsequent product view can.",
    },
    "search_query": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "Search",
        "audience_use_case": "Custom Audience of site searchers (7-30 day lookback) for retargeting with Dynamic Product Ads matched to search-term-implied categories — these users show explicit product intent but haven't converted, making them a strong warm-funnel segment for a Conversions-objective campaign. Search terms can also segment audiences by category interest (e.g., \"abaya\" vs \"dress\" searchers) to feed category-specific creative, and a Lookalike seeded from searchers who later purchased would find people with similar declared intent patterns.",
        "why_this_event": "Unlike ViewContent or page views, search_query captures self-declared, explicit intent — the exact term the shopper typed — which directly reveals product/category interest rather than inferring it from passive browsing, making it a cleaner, higher-signal basis for intent-based segmentation than nearby browse events.",
    },
    "search_no_results": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Weak standalone case. Best fit: small suppression/exclusion segment — pull zero-result searchers (short lookback, 7-14 day) out of broad catalog-sales or DPA retargeting campaigns, since they demonstrated unmet demand rather than confirmed product interest, so showing them generic \"shop now\" creative wastes spend. Could also feed a custom conversion used to monitor catalog-gap volume, but it's not something to optimize delivery toward. Not recommended as a primary Custom Audience or Lookalike seed — without the captured search term there's no product affinity to act on with Meta creative.",
        "why_this_event": "Trigger condition (search returned zero matches) signals failed/unmet intent, not product interest — opposite of what Meta's Search standard event or a retargeting audience needs, since there's no item to show back to the user via dynamic ads; it's more a catalog/inventory-gap signal for internal merchandising than an ad-targeting signal, and volume is a thin slice of an already-small search-using segment.",
    },
    "search_autocomplete_click": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "Search",
        "audience_use_case": "Once wired into Meta (via GTM Pixel migration or CAPI), this event seeds a short-window (1-7 day) Custom Audience of high-intent searchers for dynamic retargeting ads showing the products/categories tied to their selected suggestion -- these users have confirmed interest in a specific item, not just browsed passively, so retargeting CTR/CVR should outperform generic site-visitor retargeting. It also works as a Conversions-objective custom optimization event for top-of-funnel campaigns aimed at driving qualified search engagement before AddToCart, and as a Lookalike seed (1,000+ recommended) for prospecting users who behave like active intentful shoppers rather than casual browsers. Exclude recent purchasers of the same category to avoid wasted spend on converted users.",
        "why_this_event": "Clicking an autocomplete suggestion is a deliberate confirmation of interest in a specific term/product -- unlike raw keystrokes or a results-page view, it filters out abandoned/mistyped searches and isolates users who actively pursued a query, making it a cleaner intent signal than the broader \"search performed\" event for building a focused retargeting or lookalike seed.",
    },
    "product_card_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Feed product_card_click (with product_id/category in event params) via CAPI as a custom event, and build a Website Custom Audience of \"Engaged Browsers\" with a 14-30 day lookback window: users who clicked a specific product but haven't yet reached AddToCart/Purchase. Retarget this audience with Dynamic Product Ads showing the exact item(s) they clicked. Because volume is far higher than down-funnel events, it also works well as a Lookalike Audience seed when Purchase counts are too thin (sub-100) to hit Meta's optimization threshold reliably.",
        "why_this_event": "A card click is a deliberate, single-product selection out of several displayed options — stronger intent than a passive view_item_list impression but earlier/higher-volume than a PDP-load view_item, so it isolates \"actively interested browsers\" as a distinct mid-funnel cohort rather than duplicating the PDP-view signal. It doesn't map to ViewContent because Meta's catalog/DPA convention reserves that for actual content/PDP views with matched content_ids, not a pre-navigation click.",
    },
    "filter_applied": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a Website Custom Audience of \"filter_applied\" users over a 14-30 day window as a mid-funnel retargeting pool for DPA/Conversions campaigns, since refining filters (color/size/price) signals active product research beyond a passive page view. Layer this audience beneath ViewContent/AddToCart in a tiered retargeting structure (filter_applied = warm, AddToCart = hot) so ad spend and creative urgency scale with demonstrated intent. Can also seed a Lookalike for prospecting against \"active researchers\" rather than generic visitors, improving match quality over a broad ViewContent-based seed.",
        "why_this_event": "Applying a filter is a deliberate, effortful action (not a default page load) that reveals specific product attribute preference, so it isolates engaged shoppers from the much larger, noisier pool of all collection-page viewers captured by ViewContent. It sits cleanly between passive browsing and AddToCart in intent strength, making it a useful distinct retargeting tier once wired to Meta via GTM/CAPI.",
    },
    "filter_removed": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too ambiguous to anchor a Custom Audience on: removing a filter doesn't reliably signal rising or falling purchase intent — it could mean the shopper is broadening criteria to see more product, correcting a misclick, or abandoning the discovery flow entirely. Even if wired into GTM/CAPI, it'd be redundant with the much cleaner signals already available from filter_applied (narrowing = intent) and view_item/AddToCart (concrete product interest).",
        "why_this_event": "The trigger condition (un-checking one filter) carries no consistent directional intent signal — unlike filter_applied (narrowing = engaged shopper) or search (explicit need statement), filter_removed is direction-agnostic noise that doesn't distinguish a warming lead from someone giving up, so it's a poor standalone basis for retargeting or lookalike seeding.",
    },
    "sort_changed": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too noisy to anchor a dedicated audience. Sort-order changes happen mid-browse on collection pages already captured by ViewContent/page_view-equivalent events; building a separate Custom Audience or optimization event from this just duplicates the broader \"category browsers\" pool with no added intent signal. At best it could feed a low-priority attribute inside a broader browse-based Lookalike seed (e.g. tag price-sort users for a \"price-sensitive shopper\" creative variant), but it doesn't merit its own retargeting or exclusion audience.",
        "why_this_event": "Sorting is a UI-manipulation action on a listing page, not a product- or purchase-intent signal — it fires regardless of whether the user found anything they want, and it's already implied by the page-level ViewContent/listing-view event that fires alongside it, making it redundant rather than a distinct audience-worthy trigger.",
    },
    "pagination_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Pagination clicks only signal generic catalog-browsing engagement, not interest in any specific product or category, so they don't justify a standalone Meta audience or optimization event. At best they could be folded into a broad top-of-funnel \"engaged browser\" Custom Audience (7-14 day lookback) for cold prospecting, but that audience would be near-identical to one built from page_view/ViewContent fired on the same paginated listing pages, and a Lookalike seeded from it would carry weaker per-user purchase intent than one seeded from ViewContent or AddToCart.",
        "why_this_event": "The trigger fires on page-number/next-prev arrow clicks within product listing pages and carries no item_id, category, or value payload, so it can't separate a shopper closing in on a purchase from one idly scrolling through pages. It also fires on essentially every listing page view already captured by page_view/ViewContent, making it redundant noise rather than an incremental targeting signal.",
    },
    "swatch_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a short-window (3-7 day) Custom Audience of \"engaged product browsers\" who fired swatch_click but didn't reach InitiateCheckout/Purchase, then exclude recent purchasers — this segment shows above-baseline intent (manually exploring color/material options vs. just landing on the page) so dynamic retargeting ads showing the swatched variant should outperform generic ViewContent retargeting. It's a weaker signal than AddToCart so size the bid/budget accordingly, and treat it as a supplementary mid-funnel layer rather than a primary optimization event given the volume needed (~100 conversions) to get reliable custom-event optimization signal.",
        "why_this_event": "Unlike a passive page view, swatch_click requires an active decision to evaluate a specific color/material variant — it filters out drive-by traffic and isolates shoppers actively weighing a purchase option, which is a cleaner mid-funnel intent signal than ViewContent alone and distinct enough from AddToCart to warrant its own audience tier rather than being folded into either.",
    },
    "size_chosen": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "CustomizeProduct",
        "audience_use_case": "Once wired (GTM or CAPI), use size_chosen as a mid-funnel CustomizeProduct event seeding a 3-7 day \"configured but didn't cart\" retargeting Custom Audience -- these shoppers picked a specific size for themselves but stalled before AddToCart, so dynamic product ads nudging them back convert well. It also works as a secondary Conversions-objective optimization event (alongside Purchase/AddToCart) when raw Purchase volume is too thin to hit the ~30-conversion threshold, giving Meta's algorithm more mid-funnel signal. Layer it as an exclusion against a broader ViewContent prospecting audience to avoid wasting spend on people who already engaged deeper.",
        "why_this_event": "Choosing a size is a deliberate, self-relevant action (committing to \"this item, my size\") that filters out passive scrollers caught by ViewContent, making it a sharper mid-intent checkpoint between ViewContent and AddToCart. It maps directly to Meta's CustomizeProduct definition (selecting a variant like size/color before adding to cart), so it inherits standard-event tooling rather than needing a one-off custom conversion.",
    },
    "product_tab_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "At best this could seed a narrow \"engaged product researchers\" Custom Audience (e.g. 7-day lookback) layered on top of the ViewContent audience for slightly tighter retargeting, or contribute as a secondary signal in a Lookalike seed alongside add_to_cart users. But it's marginal: the audience would just be a noisy subset of people who already triggered view_item/ViewContent on the same page, with no reliable intent differentiation, so it doesn't justify a dedicated optimization event or standalone audience given the 8-event AEM optimization cap.",
        "why_this_event": "Tab clicks (Description/Reviews/Shipping) are a generic UI affordance interaction, not a funnel step -- a Shipping-tab click can just as easily signal cost hesitation/abandonment as purchase intent, and a Reviews-tab click overlaps with curiosity rather than commitment. The product page view itself (ViewContent) already captures \"interested in this product\" more reliably and at far higher, cleaner volume.",
    },
    "product_image_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build mid-funnel \"Engaged Product Viewers\" Custom Audience (7-14 day lookback) from users who clicked the main image to enlarge it but didn't AddToCart -- richer-intent pool than raw ViewContent traffic, used for dynamic product ad retargeting (same item carousel) optimizing toward Purchase, with recent purchasers excluded. Also viable as a secondary custom conversion event layered alongside ViewContent/AddToCart to give Advantage+ catalog campaigns a finer engagement-quality signal for ranking warm prospects, and as a higher-quality Lookalike seed than generic page-view traffic since it filters out instant bounces.",
        "why_this_event": "Clicking to enlarge the main image is a deliberate, active inspection action (fabric, fit, color detail) distinct from the passive page load that auto-fires ViewContent even on instant bounces -- for a fashion/lifestyle store this close-look behavior is a meaningfully stronger purchase-consideration filter than mere product-page presence, making it worth a separate, tighter audience rather than folding into generic ViewContent.",
    },
    "product_thumbnail_click": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too granular to seed its own audience. At best it'd be folded into a broader \"high PDP engagement\" custom audience alongside scroll-depth/time-on-page events, layered onto an existing ViewContent retargeting audience (e.g., 7-day PDP visitors) as a quality filter rather than a standalone seed. Not justified as a dedicated Custom Audience or Lookalike seed on its own.",
        "why_this_event": "Thumbnail clicks are a micro-interaction nested inside an already-counted ViewContent (product page view) — they fire too frequently and add no incremental intent signal beyond \"viewed this product,\" making them redundant noise rather than a distinct targeting trigger.",
    },
    "lightbox_open": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Custom Audience of \"engaged product viewers\" -- visitors who opened a product image lightbox in the last 14-30 days, excluding recent purchasers -- retargeted with dynamic product ads (carousel of the viewed item + similar styles) on Instagram/Facebook. This sits between ViewContent and AddToCart in the funnel: it flags shoppers evaluating fabric/print/fit closely, so ad spend can prioritize them over flat page-view traffic. Once volume is sufficient it's also a workable Lookalike seed for \"high-consideration browser\" prospecting, distinct from a generic ViewContent-based lookalike.",
        "why_this_event": "Opening the lightbox is a deliberate extra click beyond just landing on the product page -- it means the shopper is zooming in to inspect material/print/fit detail, which is a meaningfully stronger consideration signal than passive ViewContent and worth isolating rather than lumping into generic page-view retargeting.",
    },
    "quick_shop_open": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "ViewContent",
        "audience_use_case": "Feed quick_shop_open into the dynamic-product-ad ViewContent pool: a 7-14 day Website Custom Audience of users who opened a quick-shop panel for specific SKUs but never reached InitiateCheckout, retargeted with catalog ads showing the exact product they peeked at. It also works as a broader top-of-funnel ViewContent signal for Lookalike seeding (1-3% LAL) once volume is high enough, since it captures product-level curiosity across many SKUs without requiring a full PDP load.",
        "why_this_event": "Opening the quick-shop panel is a deliberate click on a specific product card (not a passive impression or hover), so it carries real per-SKU intent comparable to a PDP visit — exactly what ViewContent is meant to capture — while firing far more often than full PDP navigations since it's the lower-friction path shoppers take straight from collection grids.",
    },
    "sticky_atc_visible": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience. Sticky ATC bar visibility is a scroll-position trigger, not a deliberate action, and it likely fires for the large majority of anyone who scrolls even moderately down a PDP — making any Custom Audience built from it nearly as broad and low-intent as a generic ViewContent/PDP-visit audience, just with extra pixel/CAPI overhead. If kept, fold it as a minor signal into a broader \"engaged PDP viewer\" segment rather than building or optimizing a standalone campaign on it.",
        "why_this_event": "Trigger condition is purely scroll-distance based (bar appears once user passes a fixed scroll point), not an intent-bearing interaction like adding to cart or clicking the bar — so it's redundant noise layered on top of existing PDP view/scroll signals rather than a distinct purchase-intent marker.",
    },
    "out_of_stock_viewed": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a Custom Audience (14-30 day lookback) from out_of_stock_viewed, segmented by product/category via event parameters, and run it as a \"back in stock\" / cross-sell remarketing campaign showing similar in-stock items or the same SKU once replenished — these users already showed strong product-level intent but hit a dead end, so a normal \"Shop Now\" ViewContent retarget would waste spend sending them back to an unbuyable PDP. Equally valuable as a suppression list layered onto prospecting/retargeting campaigns for that specific product, and as a refined custom-conversion signal to monitor per SKU for high-demand items worth restocking before scaling ad spend on them.",
        "why_this_event": "The trigger condition (PDP view + zero stock) carries a different intent signal than a normal product view — it's \"wanted this, couldn't get it\" rather than generic browsing — and that distinction is lost if folded into the standard ViewContent stream Shopify's native pixel already sends, so it needs its own custom event to be addressable and not buried in noise.",
    },
    "cart_drawer_open": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a custom-event-seeded Website Custom Audience of users who opened the cart drawer in the last 3-7 days, then exclude anyone who also fired Purchase in that window -- this is a tight \"cart-engaged, no purchase\" warm retargeting pool for dynamic product ads (showing the actual cart contents) in a Conversions-objective campaign. It can run alongside an AddToCart-based audience but with a shorter lookback since drawer-opens skew toward near-term checkout consideration, not just product interest.",
        "why_this_event": "Opening the cart drawer is a deliberate check-in on what's already committed to purchase — distinct from AddToCart (the act of adding), it signals active reconsideration close to checkout, occurring late enough in the funnel to be a tighter, hotter retargeting trigger than generic cart-add events alone.",
    },
    "cart_drawer_close": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not recommended as a standalone audience-building event. Closing the cart drawer is directionally ambiguous — it fires identically whether someone just added an item and is continuing to browse, finished reviewing and is heading to checkout via a different path, or opened the drawer by accident and dismissed it. Because it can't reliably distinguish rising intent from abandonment, it shouldn't seed a dedicated Custom Audience or feed Conversions-objective optimization; at most it could be folded as a minor signal into a broader \"cart engagement\" custom audience alongside add_to_cart and view_cart.",
        "why_this_event": "The trigger condition (closing a UI drawer) is a chrome interaction, not a commerce action — it carries no inherent intent direction and is largely redundant with the add_to_cart/view_cart events that already capture the meaningful cart-engagement signal, making it noise rather than a distinct targeting input.",
    },
    "cart_item_remove": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a short-window (1-3 day) Custom Audience from cart_item_remove and use it as an EXCLUSION layer on top of the standard AddToCart/cart abandonment retargeting campaign — suppress dynamic product ads for the specific SKU the user explicitly removed, instead of wasting spend re-showing it. Pair with a separate \"win-back\" ad set offering a discount/voucher to this same audience, since explicit removal often signals price objection rather than total disinterest, and that's a distinct creative angle from a generic abandoned-cart nudge.",
        "why_this_event": "Unlike passive non-conversion (item just sitting unpurchased), a click on \"remove\" is an explicit, deliberate rejection signal — it tells Meta the user actively decided against that product, which is qualitatively different intent than someone who simply navigated away, so it's the right trigger for exclusion/suppression logic rather than inclusion-based retargeting.",
    },
    "cart_item_quantity_change": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not eligible as its own audience. Quantity bumps merge two opposite-intent actions (increasing = warming up, decreasing = backing off) into one undifferentiated event_name, so it can't cleanly seed a retargeting or Lookalike audience without misclassifying cooling shoppers as hot ones. Any cart-engagement audience is better built off add_to_cart/view_cart, which already capture the relevant intent without this noise; quantity-change data is more useful as a Conversions API enrichment parameter on those events than as a standalone Meta event.",
        "why_this_event": "The trigger fires identically whether a shopper raises or lowers quantity, so the event alone can't distinguish rising purchase intent from cart abandonment-in-progress — a directionless mixed-intent signal is too unreliable to anchor audience or optimization logic on, versus the cleaner unambiguous intent already captured by add_to_cart.",
    },
    "discount_code_submitted": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a short-window (3-7 day) Custom Audience of users who submitted a discount code (via CAPI once wired through GTM/Pixel) but did NOT fire Purchase in the same window — these are price-sensitive near-converters worth a retargeting push reinforcing the discount or offering a slightly better one to close the sale. Layer it as an exclusion against a broader cart-abandonment campaign so messaging stays specific (\"don't lose your discount\" vs generic \"items in your cart\"). Not large/clean enough on its own to be a primary Conversions-objective optimization event — best used as a retargeting/messaging-split segment layered on top of InitiateCheckout/AddToCart audiences.",
        "why_this_event": "Submitting a discount code isolates a specific high-intent, price-sensitive sub-segment of checkout traffic (vs. the generic InitiateCheckout/AddPaymentInfo crowd), so ads can speak directly to that price anxiety instead of generic cart-abandonment messaging — but it's a refinement layer, not a standalone funnel stage, so it shouldn't replace standard checkout events as the primary optimization signal.",
    },
    "cart_value_milestone": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Use the EGP-1000+ (or 2000+) milestone tier as a Custom Audience seed for high-value-intent shoppers, retargeted within a 1-3 day hot window with free-shipping nudges or bundle upsell ads to push them to checkout before cart value decays. The higher tiers also work well as a Lookalike seed (once volume hits 1,000+), since users who build a large basket are a stronger predictor of high-AOV customers than generic cart adders, improving prospecting efficiency for a Conversions-objective campaign targeting bigger basket sizes.",
        "why_this_event": "Crossing a cart-VALUE threshold (not just adding any item) isolates shoppers building a meaningfully large basket — a distinct, higher-intent signal that plain AddToCart can't differentiate since it fires identically for a EGP 50 item or a EGP 2000 cart. That value-tier distinction is exactly what's needed to separate \"casual browser\" noise from \"high-AOV prospect\" signal for targeting.",
    },
    "free_shipping_progress_milestone": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once wired into Meta (via GTM-hosted Pixel or CAPI), this becomes a custom conversion event seeding a \"high cart-value, no purchase\" Custom Audience with a short 3-7 day lookback — users who crossed a free-shipping value threshold but didn't convert, targeted with dynamic ads reminding them how close they are to free shipping or completing checkout. The same population is a strong Lookalike seed, since reaching the threshold correlates with higher AOV/LTV than generic AddToCart, and it can also serve as an exclusion segment to keep \"near-threshold\" shoppers out of low-intent prospecting campaigns.",
        "why_this_event": "Unlike AddToCart, which fires on any single item add regardless of value, this event triggers specifically when cart value crosses an economic threshold tied to a real incentive (free shipping) — a cleaner proxy for elevated purchase intent and cart value than item-count-based signals, making it a sharper basis for value-tiered retargeting and lookalikes.",
    },
    "cart_checkout_click": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "InitiateCheckout",
        "audience_use_case": "Build a hot cart-abandonment retargeting Custom Audience (1-3 day lookback) of users who clicked checkout but didn't complete Purchase within that window — serve discount/urgency creative or shipping-cost reassurance to recover near-converted carts. Also usable as the InitiateCheckout optimization event for a Conversions-objective campaign when raw Purchase volume is too thin to optimize on directly, and as an exclusion audience (clicked checkout, no purchase) layered onto upper-funnel prospecting to avoid wasting spend on people already deep in-funnel through other channels.",
        "why_this_event": "Clicking Checkout is an explicit, active commitment to transact — distinct from passive cart drawer views or AddToCart (which only signals interest) — making it the cleanest pre-purchase intent marker for short-window hot retargeting. It's the precise trigger Meta's InitiateCheckout definition expects (\"starts the checkout flow\"), so it maps cleanly rather than needing a custom event.",
    },
    "contact_form_submit": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "Contact",
        "audience_use_case": "Build a 14-30 day retargeting Custom Audience of contact-form submitters who haven't yet purchased (once wired via GTM/CAPI), and serve them a message addressing common pre-sale questions (sizing, customization, delivery to Egypt) or a light incentive to convert -- these are warm, high-intent leads who already engaged 1:1 with the brand. Also use it as an exclusion segment on prospecting/Advantage+ campaigns to avoid spending on people already in a support/sales conversation, and optionally set as a secondary Conversions-objective optimization event once volume clears Meta's signal thresholds.",
        "why_this_event": "Submitting the contact form is an explicit, effortful action (typing a question and hitting send) that signals unresolved purchase intent or a specific need, making it a far cleaner high-intent marker than passively viewing a contact/FAQ page. It maps directly to Meta's \"Contact\" standard event definition (a direct contact attempt between customer and business), so it auto-populates as a Conversions-objective option once piped in rather than needing a custom event setup.",
    },
    "whatsapp_support_needed": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "Contact",
        "audience_use_case": "Build a Website Custom Audience seeded by whatsapp_support_needed with a 14-30 day lookback window for warm retargeting — these are users who hit a question or friction point but didn't necessarily convert, so serve them reassurance-focused creative (sizing guides, return policy, delivery times) or a small incentive to push them back to checkout. Secondarily, this event can seed a Lookalike Audience of \"engaged but unconverted\" shoppers once Purchase volume alone is too thin, since it captures real human intent rather than passive browsing. It can also feed a custom-conversion optimization event for a Conversions-objective campaign targeting pre-purchase question-askers specifically, separate from generic AddToCart abandoners.",
        "why_this_event": "Reaching for WhatsApp support means the shopper hit a real, named friction point (sizing, shipping, payment) serious enough to seek out a human — that's a much sharper, more diagnostic intent signal than passive browsing, and it maps cleanly to Meta's Contact standard event, giving it native optimization and audience tooling other on-site friction signals lack.",
    },
    "tab_inactive": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth wiring into Meta as an audience/optimization signal. Tab-switching or minimizing fires on huge swaths of sessions for reasons unrelated to purchase intent (price-comparison tabs, distraction, multitasking, ad blockers triggering visibility changes) and carries no directional signal about commercial intent. Even once Meta Pixel moves into GTM or fires via CAPI, sending this as a Custom Audience seed or custom conversion event would dilute audience quality and add noise rather than improve retargeting or Lookalike performance versus cleaner intent signals already available (ViewContent, AddToCart, InitiateCheckout).",
        "why_this_event": "Tab/window focus changes describe browser-level attention state, not interaction with the store -- it can't distinguish a high-intent shopper checking shipping costs elsewhere from someone who just got distracted, so it fails the \"meaningful, distinct\" bar versus on-site engagement or funnel events.",
    },
    "tab_return": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not worth a dedicated audience. tab_return fires on pure browser-focus behavior (alt-tabbing back) unrelated to product or purchase intent — could happen mid-checkout or just from someone parking the tab open while doing email. Building a Custom Audience or optimization event from it would mix high-intent and zero-intent users indiscriminately, diluting any retargeting pool versus using ViewContent/AddToCart-based audiences that actually encode product interest.",
        "why_this_event": "Trigger condition (tab regains focus) reflects browser/OS-level attention switching, not a site interaction with commerce signal — it's noise relative to events like ViewContent or session-engagement metrics that already capture genuine on-site interest with far less ambiguity.",
    },
    "scroll_depth": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Weak fit. Theoretically a \"scrolled 90% on PDP/content\" segment could feed a low-priority top-of-funnel engagement Custom Audience (7-day window) for cheap reach/Lookalike seeding, but it's not recommended as a standalone audience: fires identically on homepage, blog, cart, or PDP, so without combining with page-path data it's not actionable for product-level retargeting or as a Conversions-objective optimization event. ViewContent (PDP view) and AddToCart already capture stronger, product-tied intent more efficiently.",
        "why_this_event": "Scroll thresholds fire on every page type (homepage, blog, PDP, cart alike) with no product or purchase-intent context, so the trigger condition tells you someone scrolled, not what they were interested in — that's noise relative to page_view/ViewContent and dwell-time signals which are both more frequent-enough-yet-targeted and already cover the same engagement funnel.",
    },
    "video_start": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "video_start alone is too weak to anchor a dedicated Custom Audience: pressing play signals only momentary curiosity, not purchase intent, and provides no information about whether anyone actually watched anything. At best it could be folded into a broader low-priority \"site engagers\" Custom Audience (7-14 day lookback) alongside other on-page interaction signals, used as a wide top-of-funnel awareness pool — never as a standalone retargeting or optimization event, since it would dilute audience quality with one-second bounces.",
        "why_this_event": "The trigger fires on the first frame of playback with zero watch-time required, so it can't separate someone who immediately clicked away from someone who watched the whole thing — video_progress (50%/75%) or video_complete are the trigger points that actually indicate engagement depth and intent, making video_start mostly noise rather than a distinct, audience-worthy signal.",
    },
    "video_progress": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Custom Audience seeded from users firing video_progress at the 50% or 75% milestone, built as a mid-funnel engagement retargeting pool with a 14-30 day lookback for a Conversions-objective or engagement campaign promoting the featured product/collection. Layer it as a Lookalike seed (alongside purchasers) to find new shoppers who behave like deep-engagement viewers, and exclude recent purchasers/AddToCart users so spend isn't wasted on people already further down-funnel. Because it's a custom (non-standard) event capped under Aggregated Event Measurement, prioritize using it for audience-building/exclusion rather than as a primary optimization event.",
        "why_this_event": "The 10/25/50/75% milestone trigger lets you filter out accidental autoplay/scroll-by impressions (which video_start alone can't distinguish) and isolate users who deliberately watched a meaningful chunk of product/lookbook video -- a stronger, more distinct intent signal than a generic page view, without being as rare/late-funnel as AddToCart.",
    },
    "video_stop": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once routed to Meta (post-GTM/CAPI wiring), video_stop could only seed a weak custom-event Custom Audience (e.g., 1-3 day lookback of \"paused/stopped a product video\") for retargeting with reminder creative. But pausing/stopping doesn't reliably signal positive or negative intent -- someone could pause to finish later, get distracted, or simply lose interest -- so it's not solid enough to anchor a dedicated retargeting segment or a Conversions-objective optimization event.",
        "why_this_event": "video_stop fires on manual pause OR early termination, conflating two opposite intents (intentional re-watch later vs. disengagement), unlike video_complete (clear positive completion) or video_progress milestones (graduated, directional engagement depth) -- making it inherently noisier and largely redundant with those cleaner video signals.",
    },
    "video_complete": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once wired into Meta (via GTM Pixel migration or CAPI), feed video_complete as a custom event seeding a 30-day Website Custom Audience of \"fully engaged content viewers\" -- this becomes a strong Lookalike seed for top-of-funnel prospecting, since full completion filters for users who actually absorbed brand/product storytelling rather than just bouncing past an autoplay clip. Pair it with a custom conversion optimization event in a Conversions-objective campaign retargeting these viewers with the specific products/collections featured in the video they finished, while excluding recent purchasers.",
        "why_this_event": "Reaching 100% completion (not just video_start or a mid-progress milestone) is the cleanest proxy for genuine attention -- it screens out scroll-past/autoplay-skip noise that inflates lower-bar video events, making it a higher-quality, lower-volume signal worth a separate audience tier rather than folding into generic engagement events.",
    },
    "video_seek": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too noisy to anchor an audience on. Scrubbing the timeline is ambiguous intent — could mean skipping past boring/sales-y parts just as easily as jumping ahead to a product reveal — so a Custom Audience built from it would mix high- and low-intent users indiscriminately. If video engagement is going to seed a retargeting audience or Lookalike, video_progress milestones (25/50/75/90%) or video_complete are the cleaner choice since \"watched X% of the video\" is monotonic and unambiguous, unlike \"moved the scrubber.\" Not worth wiring as its own audience or optimization event once Meta Pixel is moved into GTM/CAPI.",
        "why_this_event": "video_seek fires on any scrub in either direction, so it conflates engaged viewers fast-forwarding to the part they care about with disengaged viewers skipping ahead to escape the video — that directional ambiguity is exactly what makes it unsuitable for targeting, versus video_progress/video_complete which track only forward, cumulative watch depth.",
    },
    "review_image_clicked": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too thin to anchor its own audience. Review-image clicks happen for a small slice of an already-small slice (visitors who scroll to reviews, then click a photo) — volume will struggle to clear the ~100-person minimum for ad delivery at SKU or even category level within a useful lookback window. If it ever does accumulate volume, fold it as one input into a broader \"high-intent engaged shopper\" Custom Audience alongside ViewContent/AddToCart (7-30 day window) rather than building a standalone audience or optimization event from it.",
        "why_this_event": "It does mark a real intent bump (wanting real-customer photo proof before buying), but the trigger is a niche micro-interaction nested two levels deep (reach PDP → scroll to reviews → click a photo) — too rare and too redundant with the underlying ViewContent/PDP engagement signal to justify dedicated audience-building effort over more frequent, equally informative events.",
    },
    "new_customer_product_review": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once wired to Meta (via GTM-hosted Pixel or CAPI), use submitted reviews as a Lookalike Audience seed: reviewers are post-purchase, satisfied, brand-advocate customers, a higher-quality (if lower-volume) seed than raw Purchase events for finding similar high-LTV/high-engagement shoppers. Build a long-lookback (90-180 day, accumulate-to-100+) Custom Audience of reviewers to also use as: (1) an exclusion segment keeping happy customers out of discount/win-back retargeting, and (2) a targeting segment for UGC, referral, or loyalty-program campaigns where social proof affinity matters.",
        "why_this_event": "Submitting a review requires both a completed purchase and voluntary post-purchase advocacy effort, a distinctly higher-intent/loyalty signal than Purchase alone, and one that doesn't overlap with transactional or browsing events already captured elsewhere — making reviewers a cleaner lookalike seed for finding more brand-loyal buyers rather than just any purchaser.",
    },
    "google_review_user_intent": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Seed a custom-event Website Custom Audience (7-30 day lookback) of visitors who clicked/interacted with the Google reviews widget but haven't purchased, and use it as a warm-retargeting pool in a Conversions-objective campaign featuring testimonial/social-proof creative or top-reviewed product ads — these are people actively trust-checking the brand, one nudge from converting. It also works as a secondary signal layered into a Lookalike seed alongside Purchase, and as an exclusion segment to avoid showing generic cold-prospecting creative to people already deep in consideration. Note: this is forward-looking — the event needs to be wired into Meta Pixel/CAPI before any of this is usable.",
        "why_this_event": "The trigger is an explicit click/interaction with review content, not a passive page load — that's a deliberate trust-verification action that places the user meaningfully closer to purchase than a generic ViewContent fire, making it a sharper consideration-stage signal than page-view-based audiences.",
    },
    "wishlist_add": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "AddToWishlist",
        "audience_use_case": "Build a 14-30 day \"Wishlist Adders – Not Purchased\" Custom Audience for dynamic product retargeting ads (carousel/catalog showing the saved item plus complementary SKUs), excluding anyone who fired Purchase since the wishlist add. This is a strong warm-intent layer between ViewContent and AddToCart — pair with a price-drop or restock message to convert. Wishlist adders with repeat saves (3+) also make a high-quality Lookalike seed for prospecting, since the behavior filters for users with real purchase consideration rather than casual browsers.",
        "why_this_event": "Saving an item to a wishlist is a deliberate, named declaration of interest in one specific product — stronger and more durable than a passive ViewContent, and it maps directly onto Meta's AddToWishlist standard event, giving it native optimization and audience tooling other custom events lack.",
    },
    "wishlist_remove": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "If wired to Meta this could only feed a narrow suppression rule: drop a user from the wishlist-retargeting Custom Audience once they remove an item, on the theory interest has cooled. That's marginal value, not worth a dedicated audience or optimization event — better suppression already comes from Purchase events or natural decay of the wishlist_add-based audience's lookback window. Not a candidate for a Custom Audience seed or Lookalike source on its own.",
        "why_this_event": "The trigger is directionally ambiguous — removal can mean \"purchased elsewhere,\" \"changed mind,\" or simple list cleanup — so unlike wishlist_add (clear positive intent) it can't reliably signal disinterest worth suppressing or excluding on, making it noise rather than a distinct targeting signal.",
    },
    "wishlist_product_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a custom-event-seeded retargeting Custom Audience (7-14 day lookback) of shoppers who clicked back into a saved wishlist item — this is a \"warm re-engagement\" tier distinct from cold browsers, ideal for dynamic product ads or a discount-nudge campaign on the exact item they revisited. Pair with an exclusion of recent purchasers so spend isn't wasted on converted users. Once volume is sufficient (~100+/month), it can also feed a value-weighted Lookalike seed alongside Purchase/AddToCart, since clicking back into a saved item correlates with closer-to-purchase intent than a first-time product view.",
        "why_this_event": "Unlike a generic product-page view, this click is gated by prior deliberate action (the user already saved the item to their wishlist), so it isolates a higher-intent \"reconsideration\" moment rather than first-touch browsing noise — exactly the kind of signal worth a distinct audience tier instead of folding into a generic ViewContent bucket.",
    },
    "wishlist_page_view": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Build a Website Custom Audience of users who fired wishlist_page_view in the last 7-14 days, excluded against recent purchasers, as a warm retargeting pool fed with Dynamic Product Ads showing the saved items (once Meta Pixel is wired into GTM or sent via CAPI). This is a higher-intent slice than generic ViewContent — these are shoppers actively returning to check on items they've already shortlisted, so a \"complete your purchase\" or price-drop/back-in-stock creative on this audience should outperform broad retargeting. Secondary use: seed a Lookalike from this group to find prospects who behave like serial wishlist-curators (typically higher LTV).",
        "why_this_event": "Visiting the wishlist page is an active, repeat-visit behavior distinct from AddToWishlist (a one-time save action) or ViewContent (passive product browsing) — it signals a shopper deliberately returning to weigh items they already flagged as wanted, which is a stronger pre-purchase consideration signal than generic site traffic or single product views.",
    },
    "cart_upsell_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once wired into Meta (via CAPI or GTM-routed Pixel), use as a custom event to seed a short-window (14-30 day) Custom Audience of \"cart cross-sell engagers\" -- shoppers already in checkout-adjacent intent who actively browsed upsell suggestions -- excluding anyone who already hit Purchase. Retarget this audience with Dynamic Product Ads featuring the clicked upsell item plus similar add-ons, optimized toward AOV lift rather than first-touch acquisition. It can also serve as a secondary custom-conversion signal layered into a Conversions-objective campaign (alongside Purchase/InitiateCheckout) to help Advantage+ catalog ads learn which users respond to bundle/cross-sell creative.",
        "why_this_event": "This click only fires once a shopper is already in the cart actively evaluating add-ons, which is a materially hotter and more specific intent signal than a generic product-page click or wishlist save happening earlier in the browse funnel. That cart-stage context is exactly what makes it useful for AOV-focused cross-sell retargeting rather than broad prospecting.",
    },
    "product_recommendation_click": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Once wired to Meta, seed a 14-30 day Website Custom Audience of \"recommendation-engaged, non-purchasers\" — users who clicked a recommended product but didn't complete a purchase — to retarget with dynamic cross-sell/upsell ads featuring the exact items they showed algorithmic affinity for. This audience also makes a strong 1-2% Lookalike seed, since recommendation-widget clickers are mid-funnel browsers actively exploring beyond their initial product, a higher-intent signal than a homepage visit. As a custom conversion event it's better suited to engagement/traffic optimization than a Conversions-objective primary event, given its lower individual purchase-correlation versus AddToCart.",
        "why_this_event": "The trigger is specifically a click on an algorithmically-surfaced recommendation widget (not a direct product navigation), so it isolates users responsive to cross-sell/upsell merchandising logic rather than generic product-page traffic — a distinct intent signal ViewContent alone would blur together with organic browsing.",
    },
    "product_recommendation_view": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too weak to seed a dedicated audience. A viewport-enter trigger fires for nearly every visitor who scrolls past a recs carousel on home/PDP/cart pages — it's volume-heavy but intent-flat, essentially redundant with PageView/ViewContent already covering those same pages. Building a Custom Audience or optimization event on \"widget was visible\" would just re-bucket general site traffic, diluting Lookalike seed quality rather than sharpening it. If recs interaction matters for targeting, a click/add-to-cart on a recommended product (not mere visibility) is the signal worth wiring up instead.",
        "why_this_event": "Trigger condition is passive scroll-into-view, not a deliberate user action, so it can't distinguish someone who glanced past a carousel from someone who actually considered a recommended product — that ambiguity makes it noise rather than a usable intent signal for ad targeting.",
    },
    "login_attempt": {
        "eligible": True, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Best used as a suppression/exclusion audience: a 7-30 day Website Custom Audience built from login_attempt, excluded from prospecting/Advantage+ acquisition campaigns so ad spend isn't wasted re-targeting people who already have a Tharaa account (mostly repeat customers, not new-customer prospects). Secondary use: combine with purchase data as a Lookalike seed for \"engaged returning shopper\" profiles, since account holders skew toward higher lifetime engagement than anonymous browsers. Not suited as a primary optimization/conversion event — it's an identity/engagement signal, not a purchase-funnel step.",
        "why_this_event": "A login form submission is a deliberate, account-bound action that cleanly marks someone as an existing registered customer, which is exactly the segment you want to exclude from cold-prospecting spend — generic browsing or session events can't make that existing-vs-new distinction.",
    },
    "sign_up": {
        "eligible": True, "meta_event_type": "standard", "mapped_standard_event": "CompleteRegistration",
        "audience_use_case": "Once wired into Meta (via GTM-routed Pixel or CAPI), fire sign_up as CompleteRegistration to seed a 30-90 day Website Custom Audience of new account holders who haven't yet purchased — retarget with a first-order incentive or welcome offer in a Conversions-objective campaign. It's also a strong Lookalike seed once paired with later purchase data (registered-then-purchased users), and works as a secondary optimization event for account-growth campaigns when Purchase volume alone is too thin to hit Meta's reliable optimization threshold.",
        "why_this_event": "Account creation is a deliberate, identity-bound commitment — distinct from a one-off email opt-in — that maps directly onto Meta's CompleteRegistration standard event, giving it native Ads Manager support and a cleaner intent signal than any anonymous browsing event.",
    },
    "order_note_added": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Too rare and operationally idiosyncratic to anchor a Custom Audience. Order notes (gift messages, delivery instructions) fire in the same checkout session as InitiateCheckout/Purchase and add no distinct intent signal beyond what those events already capture — wiring it into Meta would burn one of the limited custom-event slots for a population nearly identical to existing checkout-stage audiences.",
        "why_this_event": "Typing an order note is a fulfillment-logistics action, not a purchase-funnel-progression signal — it doesn't indicate higher or lower buying intent than the InitiateCheckout/Purchase event it rides alongside, so it's redundant rather than incremental.",
    },
    "cookie_consent_accepted": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not an audience-building event — it's a consent-state flag, not a behavioral or purchase signal. Its real value to Meta Ads is indirect: only sessions where this fires can have their other events (ViewContent, AddToCart, Purchase) reliably sent to Meta with full attribution, so accept-rate should be tracked as a data-quality/reach metric rather than wired in as its own Custom Audience or optimization event.",
        "why_this_event": "Accepting cookies is a precondition for measurement, not an expression of product interest — using it as an audience seed would just approximate \"everyone Meta can see,\" which is already implicit in every other event that successfully reaches Meta.",
    },
    "cookie_consent_declined": {
        "eligible": False, "meta_event_type": "custom", "mapped_standard_event": "",
        "audience_use_case": "Not usable as a Meta audience or optimization event — by definition, a user who declines consent blocks the very pixel/CAPI signal needed to add them to a Custom Audience or retarget them at all. The only actionable use of this event is internal: track decline rate over time as a measurement-coverage health metric, since a rising decline rate silently shrinks every other audience and degrades Conversions-objective optimization quality across the board.",
        "why_this_event": "The trigger (declining tracking consent) is definitionally unreachable by Meta's ad systems — there's no scenario where building an audience from \"people who opted out of being tracked\" is technically coherent, making this the one event in the registry that's structurally ineligible rather than just low-signal.",
    },
}


def _baseline_conversion_rate(after: tuple) -> float:
    df, _ = run_report(dimensions=(), metrics=("sessionConversionRate",), single=after)
    return float(df["sessionConversionRate"].sum()) * 100 if not df.empty else 0.0


def _get_lift(event_name: str, after: tuple) -> dict | None:
    """Pure data fetch — no rendering. Returns None on failure or zero data."""
    try:
        funnel_df = run_funnel_report((event_name, "purchase"), after, is_open=True)
        if funnel_df.empty:
            return None
        # GA4 drops the step-1 row entirely when the event never fired in this period —
        # match by label instead of position, or a dead event silently reads purchase's row.
        step1 = funnel_df[funnel_df["step"].str.startswith("1.")]
        if step1.empty:
            return {"doers": 0, "doer_rate": 0.0, "baseline_rate": _baseline_conversion_rate(after)}
        row = step1.iloc[0]
        doers = int(row["activeUsers"])
        if doers == 0:
            return {"doers": 0, "doer_rate": 0.0, "baseline_rate": _baseline_conversion_rate(after)}
        return {
            "doers": doers,
            "doer_rate": float(row["completionRate"]) * 100,
            "baseline_rate": _baseline_conversion_rate(after),
        }
    except Exception:
        return None


def _get_secondary_data(event_name: str, spec: dict, after: tuple) -> dict:
    """Pure data fetch for the secondary chart — no rendering. Returns a dict tagged by kind."""
    kind = spec["secondary"]
    try:
        if kind == "page_type":
            df, _ = run_report(
                dimensions=("customEvent:content_group",), metrics=("eventCount",),
                single=after, dim_filter=string_filter("eventName", event_name),
                order_by_metric="eventCount",
            )
            df = df[df["customEvent:content_group"] != "(not set)"]
            return {"kind": "bar", "df": df, "label_col": "customEvent:content_group",
                    "value_col": "eventCount", "noun": "firings", "axis_label": "Page Type"}

        elif kind == "item":
            df, _ = run_report(
                dimensions=("pagePath",), metrics=("eventCount",),
                single=after, dim_filter=string_filter("eventName", event_name),
                order_by_metric="eventCount", limit=15,
            )
            return {"kind": "bar_table", "df": df, "label_col": "pagePath",
                    "value_col": "eventCount", "noun": "firings", "axis_label": "Page"}

        elif kind == "value" and spec.get("secondary_param"):
            dim = spec["secondary_param"]
            df, _ = run_report(
                dimensions=(dim,), metrics=("eventCount",),
                single=after, dim_filter=string_filter("eventName", event_name),
                order_by_metric="eventCount", limit=20,
            )
            df = df[df[dim] != "(not set)"]
            return {"kind": "bar", "df": df, "label_col": dim, "value_col": "eventCount",
                    "noun": "firings", "axis_label": dim.split(":")[-1]}

        elif kind == "metric_avg" and spec.get("secondary_param"):
            metric = spec["secondary_param"]
            df, _ = run_report(
                dimensions=(), metrics=("eventCount", metric),
                single=after, dim_filter=string_filter("eventName", event_name),
            )
            return {"kind": "metric_avg", "df": df, "metric": metric, "label": metric.split(":")[-1]}

        else:  # trend
            df, _ = run_report(
                dimensions=("date",), metrics=("eventCount",),
                single=after, dim_filter=string_filter("eventName", event_name),
            )
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
                df = df.sort_values("date")
            return {"kind": "trend", "df": df}
    except Exception as e:
        return {"kind": "error", "error": str(e)}


def _build_findings(event_name: str, lift: dict | None, sec: dict) -> list[str]:
    """Turn fetched numbers into concrete, computed bullet-point findings."""
    findings = []

    if lift and lift["doers"] > 0:
        doer_rate, base_rate, doers = lift["doer_rate"], lift["baseline_rate"], lift["doers"]
        if base_rate > 0:
            mult = doer_rate / base_rate
            if doer_rate > base_rate * 1.05:
                findings.append(
                    f"**{num(doers)} users** triggered this event in the after period, and "
                    f"**{doer_rate:.1f}%** of them went on to purchase — **{mult:.1f}x** the "
                    f"**{base_rate:.1f}%** site-wide baseline."
                )
            elif doer_rate < base_rate * 0.95:
                findings.append(
                    f"**{num(doers)} users** triggered this event, but only **{doer_rate:.1f}%** "
                    f"purchased — below the **{base_rate:.1f}%** baseline, a friction signal "
                    f"worth investigating."
                )
            else:
                findings.append(
                    f"**{num(doers)} users** triggered this event; their **{doer_rate:.1f}%** "
                    f"purchase rate tracks close to the **{base_rate:.1f}%** baseline."
                )
    elif lift is not None:
        findings.append("No users triggered this event in the after period yet — no lift to measure.")

    kind = sec.get("kind")
    if kind in ("bar", "bar_table"):
        df, label_col, value_col, noun = sec["df"], sec["label_col"], sec["value_col"], sec["noun"]
        if not df.empty:
            total = df[value_col].sum()
            ranked = df.sort_values(value_col, ascending=False)
            top = ranked.iloc[0]
            top_pct = top[value_col] / total * 100 if total else 0
            findings.append(
                f"**{top[label_col]}** alone accounts for **{top_pct:.0f}%** of all {noun} "
                f"(**{num(int(top[value_col]))}** of **{num(int(total))}**)."
            )
            if len(ranked) >= 2:
                top2_pct = (ranked.iloc[0][value_col] + ranked.iloc[1][value_col]) / total * 100 if total else 0
                if top2_pct < 95:
                    findings.append(
                        f"The top 2 — **{ranked.iloc[0][label_col]}** and **{ranked.iloc[1][label_col]}** "
                        f"— together cover **{top2_pct:.0f}%**, the rest is long tail."
                    )
        else:
            findings.append("No breakdown data available yet for this event.")

    elif kind == "metric_avg":
        df, metric, label = sec["df"], sec["metric"], sec["label"]
        if not df.empty and float(df["eventCount"].sum()) > 0:
            total = float(df[metric].sum())
            count = float(df["eventCount"].sum())
            findings.append(
                f"Average **{label}** across **{num(int(count))}** firings is **{total / count:,.1f}**."
            )
            findings.append(
                f"`{metric}` is registered in GA4 as a metric, not a dimension — a per-bucket "
                "breakdown needs it registered as a custom dimension too."
            )
        else:
            findings.append("No data available yet for this metric.")

    elif kind == "trend":
        df = sec["df"]
        if not df.empty and len(df) >= 2:
            mid = len(df) // 2
            first_half = df.iloc[:mid]["eventCount"].sum()
            second_half = df.iloc[mid:]["eventCount"].sum()
            if first_half > 0:
                change = (second_half - first_half) / first_half * 100
                if change > 15:
                    findings.append(f"Volume is **rising** — up **{change:.0f}%** in the second half of the period vs the first.")
                elif change < -15:
                    findings.append(f"Volume is **falling** — down **{abs(change):.0f}%** in the second half of the period vs the first.")
                else:
                    findings.append("Volume has stayed roughly flat across the period.")
            peak = df.loc[df["eventCount"].idxmax()]
            findings.append(f"Peak day: **{peak['date'].strftime('%b %d')}** with **{num(int(peak['eventCount']))}** events.")
        else:
            findings.append("No trend data available yet for this event.")

    elif kind == "error":
        findings.append(f"GA4 query failed while computing this insight: {sec['error']}")

    return findings


def _render_secondary_chart(event_name: str, spec: dict, sec: dict):
    kind = sec.get("kind")
    if kind == "error":
        st.error(f"GA4 query failed: {sec['error']}")
        return

    if kind == "bar":
        df = sec["df"]
        if not df.empty:
            fig = px.bar(
                df.sort_values(sec["value_col"], ascending=False),
                x=sec["label_col"], y=sec["value_col"],
                title=f"{event_name} by {sec['axis_label']}",
                labels={sec["label_col"]: sec["axis_label"], sec["value_col"]: "Events"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No breakdown available yet.")

    elif kind == "bar_table":
        df = sec["df"]
        if not df.empty:
            fig = px.bar(
                df, x=sec["label_col"], y=sec["value_col"],
                title=f"{event_name} by {sec['axis_label']}",
                labels={sec["label_col"]: sec["axis_label"], sec["value_col"]: "Events"},
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df.rename(columns={sec["label_col"]: sec["axis_label"], sec["value_col"]: "Events"}),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No page breakdown available yet.")

    elif kind == "metric_avg":
        df, metric, label = sec["df"], sec["metric"], sec["label"]
        if not df.empty and float(df["eventCount"].sum()) > 0:
            total = float(df[metric].sum())
            count = float(df["eventCount"].sum())
            st.metric(f"Average {label} on this event", f"{total / count:,.1f}")
        else:
            st.info("No data available yet for this metric.")

    elif kind == "trend":
        df = sec["df"]
        if not df.empty:
            fig = px.line(
                df, x="date", y="eventCount",
                title=f"{event_name} — Daily Trend",
                labels={"date": "Date", "eventCount": "Events"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available yet.")


def _render_use_case(event_name: str, after: tuple):
    spec = EVENT_USE_CASES[event_name]
    badge = "💰 Revenue" if spec["tag"] == "revenue" else "💵 Cost"

    st.markdown(f"### {spec['title']}  ·  {badge}")
    st.caption(f"`{event_name}` — {spec['category']}")

    lift = _get_lift(event_name, after)
    sec = _get_secondary_data(event_name, spec, after)
    findings = _build_findings(event_name, lift, sec)

    st.markdown("#### 📊 Key Findings")
    if findings:
        for f in findings:
            st.markdown(f"- {f}")
    else:
        st.info("Not enough data yet to compute findings for this event.")

    st.markdown("#### 🎯 Recommended Action")
    callout(spec["narrative"], kind="info")

    st.divider()

    if lift and lift["doers"] > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Users Who Triggered This Event", num(lift["doers"]))
        c2.metric("Of Them, % Who Purchased", f"{lift['doer_rate']:.1f}%")
        c3.metric("Baseline Session Conversion Rate", f"{lift['baseline_rate']:.1f}%")
    elif lift is not None:
        st.info("No users triggered this event in the after period yet.")
    else:
        st.error("GA4 funnel query failed for conversion lift.")

    st.divider()
    _render_secondary_chart(event_name, spec, sec)

    st.divider()
    _render_meta_audience_use_case(event_name)


def _render_meta_audience_use_case(event_name: str):
    meta = META_AUDIENCE_USE_CASES.get(event_name)
    if not meta:
        return

    st.markdown("#### 📣 Meta Ads Audience Use Case")

    badge = "✅ Eligible" if meta["eligible"] else "⛔ Not Recommended"
    type_label = (
        f"Standard Event → `{meta['mapped_standard_event']}`"
        if meta["meta_event_type"] == "standard"
        else "Custom Event"
    )
    st.markdown(f"**{badge}**  ·  {type_label}")

    st.markdown("**Audience strategy**")
    st.markdown(meta["audience_use_case"])

    st.markdown("**Why this event specifically**")
    st.markdown(meta["why_this_event"])


def render(before: tuple, after: tuple):
    st.subheader("Behavioral Use Case Insights")
    callout(
        "All behavioral events are listed below — each one is a specific GA4 signal mapped to a "
        "concrete revenue-gain or cost-cut action, not just a raw count. Search or filter to narrow the list.",
        kind="info",
    )

    all_events = sorted(EVENT_USE_CASES.keys())

    search = st.text_input(
        f"Search events ({len(all_events)} available) — leave blank to see all",
        "",
    )
    eligibility_filter = st.radio(
        "Meta Export Eligibility",
        ["All", "✅ Eligible for Meta Export", "⛔ Not Eligible for Meta Export"],
        horizontal=True,
    )

    events = all_events
    if search:
        q = search.lower()
        events = [
            e for e in events
            if q in e.lower() or q in EVENT_USE_CASES[e]["title"].lower()
        ]
    if eligibility_filter != "All":
        want_eligible = eligibility_filter.startswith("✅")
        events = [
            e for e in events
            if META_AUDIENCE_USE_CASES.get(e, {}).get("eligible") == want_eligible
        ]

    if not events:
        st.info("No events match this search/filter.")
        return

    st.caption(f"Showing {len(events)} of {len(all_events)} behavioral events.")

    for event_name in events:
        _render_use_case(event_name, after)
        st.divider()
