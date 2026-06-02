# Lead Engine 33 — Broken Commerce List

**Motion:** Hybrid (a Trigger overlay over discovered/enriched leads; the abandoned-commerce signal is pure Trigger, the ICP gate does the qualifying)
**Vertical fit:** All retail — butcher, wine, cheese, bakery, specialty grocer, deli/market; secondarily restaurants with a retail/preorder arm
**Suggested list name(s):** `broken_commerce_intent`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$5–10 per run (rides the websites crawl; net-new cost is a polite path-probe pass + a small Claude classify call)

## Premise

A dead `/club`, `/preorder`, or `/subscribe` page is a louder buying signal than no page at all. To build it, the operator already decided recurring/preorder commerce was worth doing, scoped it, named it, and put it on the site — then it 404'd, stalled at "coming soon", went stale, or now shows an empty product grid. That is **proven prior intent plus a documented operational failure**: they wanted the exact thing Table22 sells and couldn't make it stick on their own stack. The outbound hook writes itself — "you launched a meat share and the page is down; we run that for you."

This is demand-over-capacity inverted into intent-over-execution. The two-score model reads it cleanly: the broken-commerce signal is a sharp, citable **Trigger** ("you tried this, it broke, now is the moment"), while the partner-type/vertical filter supplies **ICP Fit**. Best rows are both — a butcher or wine shop (the $75.9k / $68.2k AGMV verticals) with a dead preorder page is the platonic lead. It sits beside Engine 09 (tech-ready, no subscription) and Engine 20 (list, no monetization): Engine 09 keys on *never built one*, Engine 20 on *built a list but no program*, and this engine on *built the program surface and it's now broken*. A broken page outranks a missing one — execution intent is already proven.

It is explicitly **Hybrid**. A broken `/club` URL on a liquor store, a chain, or a defunct ghost kitchen is noise; the staleness is the Trigger, the ICP gate filters. High-trigger / weak-ICP rows drop before sales, not nurture.

## Recipe

A **postprocessing overlay** that consumes an already-discovered + `websites`-enriched CSV and emits a filtered, evidence-tagged CSV. No fresh Serper discovery; it reuses the step-1 websites crawler and probes a fixed set of commerce URL paths per row.

1. **Input.** Take a scored or at-least-`websites`-enriched CSV (`output/2_enriched_websites.csv`, a vertical lane master, or a `custom-serper-scoring_*_all.csv`). Every row already has `website`, cleared discovery floors, and survived `config.CHAIN_KEYWORDS`. Do not re-discover. For net-new geography, seed Serper Maps off `research/trendy_neighborhoods/` for `butcher | wine_store | cheese | bakery | specialty grocer` first, run step-1 `websites`, then feed here.

2. **Build the candidate URL set per row.** Start from the homepage + any commerce/nav links the step-1 crawl already harvested, then append a fixed probe list of canonical commerce paths:

   ```
   COMMERCE_PATHS = [
     /shop, /store, /order, /order-online, /online-store,
     /club, /clubs, /membership, /members, /subscribe, /subscription,
     /subscriptions, /preorder, /pre-order, /box, /boxes, /monthly-box,
     /meat-share, /share, /csa, /wine-club, /cheese-club, /bread-club,
     /gift, /gifts, /gift-box, /gift-boxes, /gift-subscription, /products,
     /collections/all
   ]
   ```

   Also scan harvested nav/footer anchor text for the same words so we probe the operator's *actual* slug, not just guesses (e.g. a link labeled "Bacon of the Month" → follow its real href). Record which paths exist as links vs which are blind probes.

3. **Fetch + classify each candidate (rides/extends step-1, httpx).** This is a thin per-URL HEAD-then-GET pass folded into the step-1 `websites` crawl (10-thread, polite, jittered). For each candidate capture HTTP status, final URL after redirects, `Last-Modified`/sitemap `lastmod`, and rendered body, then classify into a `commerce_state`:

   ```
   BROKEN signals (any -> candidate is "broken commerce"):
     http_status in {404, 410, 403, 5xx}
     soft-404: 200 but body matches /(page|store) not found|no longer available|
               nothing here|coming soon|launching soon|opening soon|under construction|
               check back soon|we'?ll be back|temporarily (closed|unavailable)/i
     empty grid: a /shop|/store|/products|/collections page that renders 0 product
                 cards / "no products found|currently empty|sold out of everything"
     stranded redirect: a /club|/preorder link that 301s back to homepage (page removed)
     stale: published commerce page whose Last-Modified / sitemap lastmod is
            > 12 months old AND has no in-stock product
   LIVE (disqualifies the path as a trigger, keep as context):
     200 with >=1 in-stock purchasable product / a working signup/checkout form
   ```

   Distinguish **was-there-now-broken** from **never-existed**: a probe path that simply 404s with no inbound link and no Wayback history is a missing page (Engine 09 territory), not broken commerce. A 404/soft-404/stale on a path that the site *links to* (or that the Wayback Machine shows was once live — see step 4) is the real trigger.

4. **Confirm prior intent (Wayback corroborator).** For broken candidates, query the Internet Archive CDX API (`web.archive.org/cdx/search/cdx?url=<path>&output=json&limit=...`) to confirm the page once returned a live commerce surface. A path that has archived snapshots with product/club content but is now broken is the strongest variant (`prior_intent_confirmed = True`). No-history paths stay lower-confidence. *(New external dependency — see Repo placement; it's a free public API, httpx, no key.)*

5. **Classify the broken surface (Claude, cheap pass).** Send the broken page's title/slug + a body snippet to Claude (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to label `broken_program_type` (club | subscription | preorder | membership | gift_box | online_store | meat_share/CSA | unknown) and emit a one-line `trigger_summary` sales can quote verbatim. Prefix the invocation with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha). Skip the call for unambiguous hard-404s on a clearly-named slug — derive the type from the slug to save tokens.

6. **Negative live-commerce guard (reuse `detect_clubs.py`).** Run `detect_clubs.py` (50-thread site scrape: `has_club`, `club_type`, `club_url`, `club_signals`) over the same input. A row where the program page is **broken but `detect_clubs` finds a working club elsewhere** (they relaunched on a different URL/platform) is not a broken-commerce lead — it's an existing-club row; tag `route=nurture_transition` and hand to Engine 01. Existing *working* club stays a positive signal, never a DQ. Only rows whose commerce surface is genuinely down qualify here.

7. **Apply the ICP gate (curation half).** Run `reclassify.py` (`partner_type` / `business_type_v2`, wine-bar claw-back) and reject anti-ICP before scoring:

   ```
   DISQUALIFY if:
     partner_type == liquor_store, or wine commodity-SKU leak on the live pages
        (Tito's, Smirnoff, Veuve, BuzzBallz, Budweiser, Josh, Cupcake, Barefoot,
         Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic,
         Andre, Cloud Break) or ESP/site red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
     whole site dead (homepage 404/parked) -> business closed, drop (not a lead)

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery
     static-social-only / thin metrics in small market   # never DQ — understates brand
     missing-not-broken (no inbound link, no Wayback history)  # Engine 09, lower tier

   broken_strength:
     +3 broken club/subscription/meat-share page AND prior_intent_confirmed (Wayback)
     +3 partner_type in {butcher, wine, cheese} with any broken recurring-commerce page
     +2 broken preorder / gift-box page, prior_intent_confirmed
     +2 empty / abandoned online store on a premium retail row
     +1 single broken commerce path, no Wayback confirmation
     +1 stale (>12mo) but technically-200 commerce page

   QUALIFY (engine output) if: passes ICP gate AND broken_strength >= 2
   ```

8. **Dedupe + hand off to scoring.** Run `dedupe_existing.py` (phone-first, then name+address), emit the canonical CSV (below), and pass qualifying rows through the remaining `enrich.py` steps + `score.py` **unmodified** — do not touch `config.SCORING_WEIGHTS` (SHAP-aligned). Broken-commerce columns ride as evidence; `broken_strength` orders the outbound queue inside a tier.

## Output schema

```
output/broken_commerce/broken_commerce_intent_<YYYYMMDD>.csv
source = "broken_commerce_intent"
tier = <1|2|3>     # 1 = butcher/wine/cheese + Wayback-confirmed broken club/preorder; 2 = bakery/specialty or single broken path; 3 = stale-only / missing-not-broken
business_type = butcher | wine | cheese | bakery | specialty_grocer | deli | restaurant
distinction = "Launched a <broken_program_type> page — now broken; we run that for you"
year = <discovery_year>
+ canonical: name, city, state, country, source_url (= website), blurb
+ evidence cols (preserve verbatim so sales can cite the trigger in outbound):
    broken_url               # the dead commerce page (the literal thing to cite)
    commerce_state           # broken_404 | soft_404 | empty_grid | stranded_redirect | stale
    http_status              # 404 | 410 | 200(soft) | 301 | 5xx ...
    broken_program_type      # club | subscription | preorder | membership | gift_box | online_store | meat_share | unknown
    was_linked               # bool — site still links to the dead page (intent on display)
    prior_intent_confirmed   # bool — Wayback shows it once carried commerce content
    wayback_last_live        # YYYYMMDD of last archived live snapshot (if any)
    last_modified            # Last-Modified / sitemap lastmod of the broken page
    broken_snippet           # the "coming soon" / "not found" body text captured
    has_club                 # from detect_clubs.py — True => route to Engine 01, not here
    broken_strength          # int, intra-tier outbound ordering
    trigger_summary          # one-line Claude-written outbound hook
    route                    # sales | nurture_transition (relaunched-elsewhere spillover)
    partner_type             # from reclassify.py
```

Master union: `output/broken_commerce/broken_commerce_all_<YYYYMMDD>.csv`.

## Volume & cost

Bounded by input list size, not fresh discovery. Over a typical ~2,500-row vertical-mix enriched batch:

- Probing ~30 paths/row is cheap but most rows have **no** commerce surface at all to break. Empirically expect **~20–30%** of indie food sites to have *some* commerce/club/preorder page present (live or dead) → ~500–750 rows with a real surface to evaluate.
- Of those, a meaningful fraction are broken/stale rather than cleanly live — abandoned launches, season-over preorder pages, dead online stores: **~25–35%** → ~150–260 broken-commerce candidates.
- After the `detect_clubs` relaunch guard, ICP gate, and `broken_strength >= 2`: expect **~80–150 qualified net-new leads per 2,500-row batch**, ~30–50 of them tier-1 (butcher/wine/cheese + Wayback-confirmed). These are unusually high-intent — a smaller, hotter list than volume engines.

Cost arithmetic: path-probe + status classify folds into the step-1 `websites` crawl (HEAD-then-GET, ~30 lightweight requests/row at 10 threads, bandwidth only). Wayback CDX is a free public API (one call per broken candidate, ~150–260 calls). `detect_clubs.py` is a second site fetch (free compute). Claude Haiku classify runs only on confirmed-broken rows with ambiguous slugs (~150 short prompts) ≈ **$1–3**. No Apify, no Serper Web, no Resy. **Overlay-only marginal cost: ~$5–10**; if fresh discovery is needed first, that Serper Maps cost (~$5–10) belongs to the discovery run, not this overlay.

## Refresh cadence

**Quarterly per vertical, with a pre-holiday pass.** Commerce pages break and stall slowly; a monthly re-run mostly re-surfaces the same dead URLs. The high-value diff is two-directional: (a) a page that was **live last quarter and is broken now** — a fresh, dated trigger ("your preorder page went down since the holidays"); and (b) a previously-broken lead whose page **comes back live** — drop it from the next list. A pre-holiday pass (Oct/Nov) catches turkey/charcuterie/pie/allocation preorder pages that get stood up, fail under load, or never finish — peak broken-commerce season. Keep prior-run snapshots so the live→broken transition can be computed (lighter version of Engine 19's history store).

## Risks

- **Soft-404 / SPA false positives.** Many indie sites return HTTP 200 for everything (SPA shells, Squarespace/Wix catch-all routes), so status alone lies. The body-text soft-404 regex and the empty-grid check are mandatory, and JS-rendered storefronts may need a Playwright fallback for a handful of rows (mirror `best_wine_shops/`'s httpx-happy-path → Playwright-fallback pattern) before declaring a page "empty".
- **Missing ≠ broken.** A blind probe path that 404s with no inbound link and no Wayback history is a page that never existed — that's Engine 09, not this engine. Gate the high `broken_strength` tiers on `was_linked` OR `prior_intent_confirmed`; never assign a hard trigger to a pure blind-probe 404.
- **Whole-business-dead leakage.** A dead `/club` because the *entire shop closed* is not a lead. If the homepage is 404/parked or Maps shows permanently-closed, drop the row entirely — don't pitch a defunct business.
- **Relaunched-elsewhere false positives.** They may have moved the club to a new URL or to Shopify/Squarespace commerce; the old `/club` 404s but a working program exists. The `detect_clubs.py` guard (step 6) catches this — route those to Engine 01 (nurture/transition), don't pitch them a "broken" page they've already fixed.
- **Seasonal-by-design pages.** A preorder page that's intentionally dark out of season (turkey preorder in March) is "broken" but not a failure. `last_modified` + Wayback cadence help distinguish a seasonally-parked page (regular on/off) from a genuinely abandoned one; lean on the pre-holiday pass for these and don't over-trigger off-season.
- **ICP leakage through the trigger.** Liquor stores, chains, ghost kitchens all have broken commerce pages too. Keep `config.CHAIN_KEYWORDS`, the commodity-SKU scan, and ESP red-flags (City Hive, Spot Hopper) upstream of `broken_strength`; enforce wine-bar exclusion (except geographic-monopoly) via the `reclassify.py` claw-back.
- **Small-market metrics run low.** A dominant rural butcher with a dead meat-share page will under-index on social/reviews and may have a thin, brittle site. Weight relative local dominance + the broken-intent trigger; **never DQ on static-only social** — it understates brand. Butcher/deli/specialty audiences skew Facebook over IG; `follower_count` (IG + FB) already absorbs that.
- **Sweets-only demotion.** A cookie shop with a dead "Cookie Club" page is a real trigger but a single-product bakery — cap Tier 2; `broken_strength` must not override the sweets-only demotion.
- **Rate-limit / politeness.** Probing ~30 paths per domain can look like a scan. Throttle per-host, jitter, respect `robots.txt`, cap concurrent requests per domain, and back off on 429/403; HEAD-first to avoid downloading full bodies on obvious 404s.

## Repo placement

Standalone overlay package mirroring the niche-lane shape, reusing the step-1 crawler as a library plus `detect_clubs.py` and `reclassify.py`. One small genuinely-new dependency: the Wayback CDX corroborator.

```
enrich.py
  + probe_commerce_paths(base_url, harvested_links) -> list[dict]   # NEW, called inside step-1 websites crawl
  +   (export so the overlay imports it; status + soft-404 + empty-grid classify, no second crawl)

broken_commerce/                         # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                           # COMMERCE_PATHS, BROKEN/LIVE regex sets, broken_strength thresholds
  probe.py                              # reuses enrich.probe_commerce_paths over input CSV; commerce_state
  wayback.py                            # Internet Archive CDX lookups (prior_intent_confirmed, wayback_last_live)  [NEW external API]
  classify.py                           # Claude haiku-4-5: broken_program_type, trigger_summary
  aggregate.py                          # detect_clubs relaunch guard + ICP gate (reclassify) + broken_strength + dedupe
  finalize.py                           # canonical schema writer, date-stamped output + master union

discover_broken_commerce.py             # NEW orchestrator (mirrors discover_email_list.py / discover_butchers.py)
  python discover_broken_commerce.py --input output/2_enriched_websites.csv
  python discover_broken_commerce.py --input output/custom-serper-scoring_*_all.csv --verticals butcher,wine,cheese
  python discover_broken_commerce.py --master-only

output/broken_commerce/_history/        # OPTIONAL lightweight snapshot store: per-run broken-state for live<->broken diff
```

Refactor target: extract the `enrich.py` step-1 fetch/parse into a shared `enrich_websites_lib` so the probe pass reuses one crawl instead of duplicating it — the same shared-lib argument Engines 02, 05, 19, and 20 raise; build it once. The **Wayback CDX client** (`wayback.py`) is the only net-new external dependency this engine needs — free, keyless public API, but new to the repo; keep it isolated and rate-limited. The optional `_history/` snapshot store mirrors Engine 19's persisted store but is lighter (just commerce_state per URL) — only needed if we want the live→broken transition trigger.

## Open questions

1. **Confirmation bar for "prior intent".** Is `was_linked` (site still links to the dead page) sufficient to call it broken commerce, or do we require a Wayback hit for tier-1? Wayback adds cost/latency and has coverage gaps on small sites — leaning toward `was_linked OR prior_intent_confirmed` for tier-2 and *requiring* Wayback for tier-1.
2. **Seasonal vs abandoned.** How many quarters of "parked" must a preorder page show before we treat it as truly abandoned rather than seasonally dark? This decides whether the `_history/` store is optional or load-bearing, and whether the pre-holiday pass needs special-case handling.
3. **SPA / soft-404 coverage.** What share of the input needs the Playwright fallback to correctly read an empty-grid or JS-rendered "coming soon", and is that worth the latency, or do we accept undercounting JS-heavy storefronts and lean on body-text + status?
4. **Overlap with Engines 09 and 20.** A broken `/club` row may also be Engine 09 (tech-ready, no working subscription) or Engine 20 (list, no monetization). Do we dedupe across the three at the master level and let `broken_strength` win the outbound timing, or keep this as a distinct higher-intent list with its own queue?
