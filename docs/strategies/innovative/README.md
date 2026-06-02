# Innovative Lead Engines — Pipeline Specs

**Created:** 2026-06-01
**Source:** One doc per lead engine in [`../../INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md`](../../INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md), grounded in [`../../ICP.md`](../../ICP.md) and the real repo infrastructure (`discover.py`, `enrich.py`, `score.py`, `awards/`, `directories/`, `detect_clubs.py`, `config.py`, `scrape_beli/`, `best_wine_shops/`, `butcher.py`).

Each file is a self-contained, engineer-ready spec for one lead engine — a pipeline that can be built and run independently to emit a named, date-stamped CSV under `output/`. Every doc follows the house style of the sibling `../0X_*.md` channel docs: **Premise · Recipe · Output schema · Volume & cost · Refresh cadence · Risks · Repo placement · Open questions.**

These are **specs, not yet code.** Status on every doc is `Not yet built`.

## Core principle (from the source doc)

Do not build lists by category alone. Build **trigger-based lists** where every business has both **ICP Fit** ("right kind of business?") and **Trigger Fit** ("reason to contact now?"). The best outbound lists sit at the intersection. Each engine emits both kinds of evidence so sales can cite the trigger in outbound — every output schema preserves the source evidence columns.

## The 52 engines

| # | Engine | Motion | Suggested list name(s) | Spec |
|--:|---|---|---|---|
| 01 | Existing Club Transition | Curation | `wine_existing_club_transition`, `butcher_meat_share_transition`, `cheese_club_transition` | [01](01_existing_club_transition.md) |
| 02 | Manual Workflow Pain | Hybrid | `premium_retail_manual_preorder` | [02](02_premium_retail_manual_preorder.md) |
| 03 | Sold-Out Demand | Curation | `sold_out_demand_signals` | [03](03_sold_out_demand_signals.md) |
| 04 | Video Engagement Spike | Curation | `video_engagement_spike` | [04](04_video_engagement_spike.md) |
| 05 | Capacity Expansion Trigger | Curation | `capacity_expansion_trigger` | [05](05_capacity_expansion_trigger.md) |
| 06 | Premium Butcher Universe | Curation | `butcher_meat_share_whole_animal` | [06](06_butcher_meat_share_whole_animal.md) |
| 07 | Wine Shop Street-Cred | Hybrid | `wine_existing_club_transition`, `wine_street_cred_new_club` | [07](07_wine_street_cred_new_club.md) |
| 08 | Press Momentum Watchlist | Curation | `press_awards_recent_momentum` | [08](08_press_awards_recent_momentum.md) |
| 09 | Tech-Ready, No Subscription | Hybrid | `tech_ready_no_subscription` | [09](09_tech_ready_no_subscription.md) |
| 10 | Small-Market Local Dominance | Curation | `small_market_local_dominance` | [10](10_small_market_local_dominance.md) |
| 11 | Partner-Adjacency Graph | Curation | `partner_adjacency_graph` | [11](11_partner_adjacency_graph.md) |
| 12 | Events and Programming | Curation | `events_programming_repeat_commerce` | [12](12_events_programming_repeat_commerce.md) |
| 13 | "Do You Ship?" Comment Mining | Curation | `do_you_ship_comment_mining` | [13](13_do_you_ship_comment_mining.md) |
| 14 | Out-of-Town Demand | Curation | `out_of_town_demand` | [14](14_out_of_town_demand.md) |
| 15 | Cult Product | Hybrid | `cult_product_demand` | [15](15_cult_product_demand.md) |
| 16 | "Angry Demand" Review Mining | Curation | `angry_demand_reviews` | [16](16_angry_demand_reviews.md) |
| 17 | Reservation Refresh Pain | Curation | `reservation_refresh_pain` | [17](17_reservation_refresh_pain.md) |
| 18 | Hidden Club Detection | Curation | `hidden_club_detection` | [18](18_hidden_club_detection.md) |
| 19 | Shopify Out-of-Stock Patterns | Hybrid | `shopify_out_of_stock_patterns` | [19](19_shopify_out_of_stock_patterns.md) |
| 20 | Email List, No Monetization | Hybrid | `email_list_no_monetization` | [20](20_email_list_no_monetization.md) |
| 21 | Gift-Ready, No Gift Product | Curation | `gift_ready_no_gift_product` | [21](21_gift_ready_no_gift_product.md) |
| 22 | Seasonal Preorder Calendar | Curation (scheduler) | `seasonal_preorder_calendar` | [22](22_seasonal_preorder_calendar.md) |
| 23 | Permit and Buildout Watchlist | Curation | `permit_buildout_watchlist` | [23](23_permit_buildout_watchlist.md) |
| 24 | Equipment Expansion Signals | Curation | `equipment_expansion_signals` | [24](24_equipment_expansion_signals.md) |
| 25 | Hiring Intent | Curation | `hiring_intent_growth_roles` | [25](25_hiring_intent_growth_roles.md) |
| 26 | Events-to-Subscriptions | Curation | `events_to_subscriptions` | [26](26_events_to_subscriptions.md) |
| 27 | Local Influencer Repetition | Curation | `local_influencer_repetition` | [27](27_local_influencer_repetition.md) |
| 28 | Industry Comment Graph | Curation | `industry_comment_graph` | [28](28_industry_comment_graph.md) |
| 29 | Supplier and Importer Graph | Curation | `supplier_importer_graph` | [29](29_supplier_importer_graph.md) |
| 30 | Natural Wine Map Expansion | Curation | `natural_wine_map_expansion` | [30](30_natural_wine_map_expansion.md) |
| 31 | Wine Inventory Distinctiveness | Curation | `wine_inventory_distinctiveness` | [31](31_wine_inventory_distinctiveness.md) |
| 32 | No Ecomm, Many Product Pages | Hybrid | `product_story_no_ecomm` | [32](32_product_story_no_ecomm.md) |
| 33 | Broken Commerce | Hybrid | `broken_commerce_intent` | [33](33_broken_commerce_intent.md) |
| 34 | Link-in-Bio Commerce Chaos | Curation | `link_in_bio_commerce_chaos` | [34](34_link_in_bio_commerce_chaos.md) |
| 35 | Marketplace Avoidance | Curation | `marketplace_avoidance_direct_order` | [35](35_marketplace_avoidance_direct_order.md) |
| 36 | Founder Story Density | Curation | `founder_story_density` | [36](36_founder_story_density.md) |
| 37 | Press Without Infrastructure | Hybrid | `press_without_infrastructure` | [37](37_press_without_infrastructure.md) |
| 38 | Award Finalist Drift | Hybrid | `award_finalist_no_recurring_commerce` | [38](38_award_finalist_no_recurring_commerce.md) |
| 39 | Almost-Partner Lookalikes | Curation | `almost_partner_lookalikes` | [39](39_almost_partner_lookalikes.md) |
| 40 | Chef & Sommelier Alumni Graph | Curation | `chef_sommelier_alumni_graph` | [40](40_chef_sommelier_alumni_graph.md) |
| 41 | Hospitality Group Incubation | Curation | `hospitality_group_incubation` | [41](41_hospitality_group_incubation.md) |
| 42 | Retail Arm of Restaurant | Curation | `restaurant_retail_arm` | [42](42_restaurant_retail_arm.md) |
| 43 | Customer Language Mining | Curation | `customer_language_mining` | [43](43_customer_language_mining.md) |
| 44 | Worth-the-Drive | Curation | `worth_the_drive` | [44](44_worth_the_drive.md) |
| 45 | Affluent Convenience Gap | Curation | `affluent_convenience_gap` | [45](45_affluent_convenience_gap.md) |
| 46 | Office & Corporate Gift Potential | Hybrid | `corporate_gift_potential` | [46](46_corporate_gift_potential.md) |
| 47 | Private Event Spillover | Curation | `private_event_spillover` | [47](47_private_event_spillover.md) |
| 48 | Meta & TikTok Creative Signal | Curation | `paid_creative_commerce_signals` | [48](48_paid_creative_commerce_signals.md) |
| 49 | Static Social, Offline Demand Rescue | Hybrid | `static_social_offline_demand` | [49](49_static_social_offline_demand.md) |
| 50 | Facebook-Heavy Butcher & Deli | Curation | `facebook_heavy_butcher_deli` | [50](50_facebook_heavy_butcher_deli.md) |
| 51 | Subscription Objection Reversal | Curation | `subscription_objection_reversal` | [51](51_subscription_objection_reversal.md) |
| 52 | Churned / Former Club Recovery | Curation | `former_club_recovery` | [52](52_former_club_recovery.md) |

## Four-layer model (which engines feed which layer)

Per the source doc, the most defensible lists combine four layers. Engines map to a primary layer:

- **Demand signals** — 03 sold-out · 04 video spike · 13 do-you-ship · 14 out-of-town · 15 cult product · 16 angry-demand · 17 reservation refresh · 27 influencer repetition · 43 customer language · 44 worth-the-drive · 50 FB-heavy.
- **Operational pain** — 02 manual preorder · 19 Shopify OOS · 20 email-no-monetization · 32 product-story-no-ecomm · 33 broken commerce · 34 link-in-bio chaos · 35 marketplace avoidance · 51 objection reversal.
- **Curation authority** — 06 premium butcher · 07 wine street-cred · 08 press momentum · 10 small-market dominance · 11 partner adjacency · 28 industry comments · 29 supplier/importer · 30 natural wine · 31 wine inventory · 36 founder story · 39 almost-partner lookalikes · 48 paid creative.
- **Timing triggers** — 05 capacity expansion · 09 tech-ready-no-sub · 12 events/programming · 18 hidden club · 21 gift-ready · 22 seasonal calendar · 23 permits · 24 equipment · 25 hiring · 26 events-to-subs · 37 press-without-infra · 38 award-finalist drift · 40 alumni graph · 41 hospitality incubation · 42 restaurant retail arm · 45 affluent convenience · 46 corporate gift · 47 private-event spillover · 49 static-social rescue · 52 former-club recovery.

The strongest lists intersect layers (e.g. premium butcher **+** whole-animal sourcing **+** holiday-preorder chaos **+** new dry-aging room **+** customers asking for meat boxes). Engine 01 (existing club) and 18/52 (hidden/former club) treat an existing program as a **positive** switch-the-platform signal, never a disqualifier.

## Cross-cutting build dependencies

Several engines independently converge on the same refactors. Do these once and many engines get cheaper:

- **`enrich_websites_lib`** — lift `enrich.py` step-1 crawl (ecommerce/email-capture/social/reservation/platform detection, About-page text) into an importable function. Wanted by **02, 03, 05, 07, 09, 12, 20, 21, 31, 32, 33, 36, 37, 41, 47** and the `detect_tech_stack()` / `detect_list_capture()` fingerprinters (09, 20).
- **`enrich_ig_lib`** — share the Apify IG profile/reel/post/tagged actors across enrich + the graph engines. Wanted by **04, 11, 13, 27, 28, 39**. Note: `config.py` Apify actor IDs currently cover reels/posts/reviews/opentable; **IG profile-scraper and instagram-tagged-posts-scraper IDs are not yet in config** (11, 24, 28).
- **`enrich_reviews_lib`** — one step-5 review-text pass shared by the reservation-difficulty miner and the sold-out / angry / cult / worth-the-drive lexicons (**15, 16, 44**).
- **`enrich_availability_lib`** — expose the Resy/Tock/OpenTable scarcity hooks from step-8 (**03, 16, 17, 37, 39**).
- **`maps_lib` / `serper_resolve_lib`** — lift the Serper-Maps name+city→place_id resolver out of `discover.py` / `scripts/fresh_icp_search.py` for mention resolution and a `suspend_quality_floors` flag for pre-open/small-market venues (**08, 10, 38, 40, 43**).
- **`icp_gate.py`** — the ICP-Fit gate block (partner-type, engagement hierarchy, liquor/chain/sweets exclusions) is copy-pasted across nearly every overlay engine; factor it out.

## Genuinely-new infrastructure (beyond refactors)

A handful of engines need net-new ingestion the repo doesn't have today — scope these as standalone builds:

- **Public-records ingestion** (`permits/` package: Socrata/ArcGIS/CKAN/Accela) — **23**.
- **Wayback / Internet Archive CDX client** (keyless) for live→broken / once-had-a-club diffs — **33, 52**.
- **Cross-run snapshot store** (parquet history) for restock cadence / live→dark transitions — **19** (and lighter for 33).
- **Wine-Searcher merchant scraper** — **31**. **Experience-platform scrapers** (Tock/OpenTable Experiences) — **26**. **TikTok Creative Center sampler + manual Meta Ad Library probe** — **48**.
- **Hand-seeded registries** (one-time, checked in): partner seeds from HubSpot/roster (**11, 39**), industry handles (**28**), supplier/importer registry (**29**), equipment-vendor registry (**24**), local-creator registry (**27**), hospitality-group seeds (**41**), `config.SMALL_MARKETS` / `config.OFFICE_CORRIDORS` geo frames (**10, 46**).
- **`scripts/discover_jobs.py`** is referenced in `CLAUDE.md` but does not yet exist — Engine **25** specs it from scratch.

## Scoring

Every lead should carry two scores (per the source doc): an **ICP Fit Score** and a **Trigger Score**, kept distinct. High-ICP/no-trigger → nurture; high-trigger/weak-ICP → filter hard before sales; both-high → priority outbound. Engine docs that touch ranking introduce a local momentum/trigger score and **do not** mutate `config.SCORING_WEIGHTS` (SHAP-aligned — see CLAUDE.md design notes).
