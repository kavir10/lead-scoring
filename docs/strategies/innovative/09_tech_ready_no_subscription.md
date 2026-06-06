# Lead Engine 09 — Tech-Ready But No Subscription List

**Motion:** Hybrid (a Trigger overlay applied to discovered/enriched leads, not a standalone discovery source)
**Vertical fit:** Restaurants (destination + neighborhood), wine, butchers, bakeries, specialty grocers
**Suggested list name(s):** `tech_ready_no_subscription`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$8–15 per run (no new Apify spend; reuses the websites crawl + detect_clubs site fetch)

## Premise

The single biggest predictor of platform-switch friction is whether a business already operates digital infrastructure. A shop running Toast/Square for POS, Shopify/Squarespace for ecommerce, Klaviyo/Mailchimp for email, and Resy/Tock/OpenTable for reservations has already cleared the "can they handle digital ops + audience building" bar that kills most cold-start subscription sales. They have a list, they have repeat-buyer behavior, they have a website that takes money online. What they *lack* is the monetization layer for repeat demand: no club, subscription, membership, preorder, or monthly box.

That gap is the trigger. In the two-score model this engine produces leads that are **high ICP Fit by construction** (we run it only over already-qualified, in-vertical rows) and gives them a **sharp, citable Trigger**: "You already run [Klaviyo + Shopify + Resy] — you've built the audience and the storefront but haven't turned recurring demand into recurring revenue." This is a tooling-maturity signal, not a brand signal, so it complements the demand-over-capacity thesis rather than restating it. Tech-ready businesses are the cheapest to onboard (data migration is trivial, owner already understands SaaS), which compresses time-to-Peak-AGMV — most valuable in the high-headroom partner types (butcher $75.9k, wine $68.2k, cheese $63.8k, destination restaurant $60.5k).

It is explicitly **Hybrid**: ICP Fit comes from the underlying discovery/scoring pipeline; this engine only adds the Trigger column and a tech-maturity tier. High-tech / has-club rows route to nurture (they already monetize repeat demand — different pitch); high-tech / no-club rows are the sales-ready slice.

## Recipe

This engine is a **postprocessing overlay** — it consumes an already-discovered + websites-enriched CSV and emits a filtered, tech-tagged CSV. It does not run Serper discovery itself; it borrows discovery from `main.py --discover` (or any vertical lane) and reuses two existing crawlers.

1. **Input.** Take a scored or at-least-`websites`-enriched CSV (`output/2_enriched_websites.csv` or a `custom-serper-scoring_*_all.csv`). Every row already has a `website` and passed quality floors + `CHAIN_KEYWORDS`. Do not re-discover.

2. **Detect the tech stack (extend `enrich.py` step 1 `websites`).** The websites crawl already fetches each homepage with the 10-thread concurrent crawler and detects ecommerce / email-signup / social / reservation platform. Add a `detect_tech_stack(html, headers, scripts)` pass to that same fetch (no extra request) that fingerprints platform signatures from HTML, script `src`, `<meta name="generator">`, and headers:

   ```
   POS / ordering:   toasttab.com, order.online (Toast), squareup.com/square,
                     spoton.com, bentobox (getbento.com / bentobox.io)
   site builder:     squarespace.com / static1.squarespace, wix.com / wixstatic,
                     wp-content / wp-json (WordPress), shopify (cdn.shopify, /cart.js,
                     Shopify.theme)
   email / ESP:      klaviyo.com (klaviyo.js, _learnq), mailchimp (list-manage.com,
                     mc.us*.list-manage), mailchimp embedded form
   reservations:     resy.com (widget), exploretock.com / tock, opentable.com,
                     tripleseat (events/private-dining)
   ```

   Emit a structured `tech_stack` column (pipe-joined detected vendors) plus booleans: `has_pos`, `has_ecom`, `has_esp`, `has_reservation_tech`, `has_modern_cms`. Compute `tech_score` = count of distinct *categories* present (0–5). Refactor: expose `detect_tech_stack()` as a function in `enrich.py` so `detect_clubs.py` and this overlay can both import it rather than re-crawling.

3. **Negative club check (reuse `detect_clubs.py`).** Run `detect_clubs.py` (50-thread site scrape) over the same input to populate `has_club`, `club_type`, `club_url`, `club_signals`. This engine keeps **only `has_club == False`** rows. Note the standing repo principle: existing-club is normally a *positive* signal — but for *this* engine the whole thesis is the absence of monetized recurring demand, so club presence is the disqualifier here. (Club-present + tech-ready rows are not discarded; they fall through to Engine-style "transition" lists and should be tagged `route=nurture_transition`.)

4. **Belt-and-suspenders subscription-absence scan.** `detect_clubs.py` already mines club/subscription/membership signals, but add a lightweight regex pass over the crawled homepage + a `/subscribe`, `/membership`, `/club`, `/box`, `/preorder` link probe to catch preorder/monthly-box wording it may miss:

   ```
   ABSENT_OK   (we want NONE of these present):
     subscription, subscribe & save, membership, member(s) club, wine club,
     meat share, CSA, monthly box, bottle club, mystery box, preorder,
     pre-order, standing order, recurring (order|delivery)
   ```

   A row qualifies only if zero club/subscription signals from step 3 AND zero matches here.

5. **Tech-readiness tiering.** Score and tier on stack maturity, weighted toward the ESP + ecommerce signals that prove audience + transaction capability:

   ```
   readiness = (has_esp * 2) + (has_ecom * 2) + has_pos + has_reservation_tech + has_modern_cms
   tier 1  if has_esp and has_ecom and readiness >= 5     # list + storefront, ready to switch on a club
   tier 2  if (has_esp or has_ecom) and readiness >= 3    # one pillar present
   tier 3  if readiness >= 2                              # tech-aware but thin
   drop    if readiness < 2                               # not actually tech-ready
   ```

6. **Vertical-aware ESP nuance (wine + liquor-store leakage).** For `business_type == wine`, reuse the liquor-store-ESP red flags from `config.py` — `City Hive` and `Spot Hopper` as the ESP/site vendor are a strong liquor-store (anti-ICP) tell, not curated-wine maturity. Demote any wine row whose only detected ESP/site is City Hive or Spot Hopper to tier 3 and flag `liquor_store_esp_suspect=True` for the reclassify pass to adjudicate.

7. **Reclassify + dedupe before handoff.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, with the wine-bar claw-back) then `dedupe_existing.py` (phone-first). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter only to `partner_type == butcher` rows.

8. **(Optional) Score for ranking.** If the input was only websites-enriched, hand qualifying rows back to the full `enrich.py` remaining steps + `score.py` so the tech trigger rides on top of the SHAP-aligned score. Do not alter `SCORING_WEIGHTS`; `tech_score` is an overlay attribute, not a scoring feature.

## Output schema

```
output/tech_ready/tech_ready_no_subscription_<YYYYMMDD>.csv
source = "tech_ready_no_subscription"
tier = <1|2|3>                       # tech-readiness tier from recipe step 5
business_type = restaurant | wine | butcher | bakery | specialty_grocer
distinction = "Tech-ready, no subscription: runs <tech_stack>, no club/box detected"
year = 2026
+ canonical: name, city, state, country, source_url (= website), blurb
+ evidence cols (preserve so sales can cite the trigger in outbound):
    tech_stack            # e.g. "Toast|Shopify|Klaviyo|Resy"
    tech_score            # 0-5 distinct categories
    has_pos, has_ecom, has_esp, has_reservation_tech, has_modern_cms
    readiness             # weighted int from step 5
    has_club              # must be False
    club_signals          # raw detect_clubs output (should be empty)
    subscription_scan     # ABSENT_OK matches found (should be empty)
    liquor_store_esp_suspect   # wine-only flag
    route                 # sales | nurture_transition (club-present spillover)
```

## Volume & cost

Per run is bounded by the input list size, not by fresh discovery. Over a typical ~2,500-row vertical-mix discovery batch:

- ~60–75% have *some* detectable modern tech (food businesses skew toward Toast/Square/Squarespace) → ~1,600 tech-touched rows.
- Of those, club/subscription penetration in the independent-food long tail is low — empirically ~15–25% run any recurring program → ~75–85% survive the negative-club filter.
- After tier-1/2 maturity gate (`has_esp` or `has_ecom` present): roughly **350–550 net-new tier-1+2 leads per 2,500-row batch**, ~150–200 of them tier-1 (list + storefront).

Cost arithmetic: tech detection is folded into the existing `websites` crawl (zero marginal request). `detect_clubs.py` is a second site fetch over ~2,500 rows at 50 threads ≈ free compute, only bandwidth. No Apify, no Serper Web, no Resy calls are added by the overlay. If the input needs fresh discovery first, that Serper Maps cost (~$5–10) belongs to the discovery run, not this engine. **Overlay-only marginal cost: ~$8–15** (mostly the detect_clubs crawl on a fresh list; near-zero if `has_club` is already populated upstream).

## Refresh cadence

**Quarterly per vertical.** Tech-stack adoption and club launches move slowly at independent shops — a butcher who added Klaviyo last month won't launch a meat share for several quarters. Re-running monthly mostly re-surfaces the same rows. The high-value transition is a previously-tier-1 lead *acquiring* a club: a quarterly diff (this run's `has_club==True` ∩ last run's `tech_ready` set) is itself a useful "they finally launched recurring revenue — switch them to Table22" trigger. Run opportunistically off the back of any large discovery batch rather than on a fixed independent schedule.

## Risks

- **Static-site false negatives.** Server-rendered or heavily CDN-cached sites can hide ESP/POS fingerprints; absence of a signal ≠ absence of tooling. Treat `tech_score` as a floor, not a measurement. Static-only social already understates brand — same caution applies to tech detection; do not DQ on low `tech_score` alone, demote to tier 3.
- **Club-detection false positives kill good leads.** `detect_clubs.py` flags "wine club" in a blog post or a "membership" loyalty punch-card as a club, which would wrongly disqualify a genuine no-subscription lead. Keep `club_signals` in the output and sample via `sample_clubs_for_qa.py` before sales handoff; prefer precision on the negative filter.
- **Liquor-store leakage (wine).** Many liquor stores run Square + a Squarespace site + City Hive — high `tech_score`, zero curated-wine ICP. The City Hive / Spot Hopper demote (step 6) plus `reclassify.py` wine-bar/liquor adjudication is mandatory; without it this engine over-produces anti-ICP wine rows.
- **Chain / franchise leakage.** Toast/Square are *more* common at small local chains. `CHAIN_KEYWORDS` runs at discovery, but a 3–9-location group can slip through; reconfirm independence on tier-1 rows before outreach.
- **Wine-bar exclusion.** Resy/Tock + BentoBox is a wine-bar tell; wine bars are mostly out (avg AGMV $36.2k) except geographic monopolies. The reclassify claw-back must run before scoring.
- **Sweets-only / single-product demotion.** A bakery running Shopify selling only cookies is tech-ready but caps at Tier 2 on ICP grounds — `tech_score` must not override the sweets-only demotion baked into scoring.
- **Small-market metrics.** Rural shops may have a real list (Mailchimp) but thin web fingerprints; weight relative local dominance + reservation difficulty over raw `tech_score` for non-metro rows.
- **Fingerprint rot.** Vendor signatures (Squarespace `static1`, Klaviyo `_learnq`, Toast `order.online`) change. The signature table needs periodic re-validation against known-stack reference sites or it silently degrades.

## Repo placement

This is an overlay package plus a thin orchestrator, with one shared-lib refactor in `enrich.py`.

```
enrich.py
  + detect_tech_stack(html, headers, scripts) -> dict   # NEW, called inside step-1 websites crawl
  +   (export so detect_clubs.py and the overlay import it; no second crawl)

tech_ready/                              # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                           # TECH_SIGNATURES table, ABSENT_OK regex, tiering thresholds
  fetch.py                              # reuses detect_tech_stack + detect_clubs.detect() over input CSV
  aggregate.py                          # negative-club filter, subscription scan, readiness scoring, tiering
  finalize.py                           # reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical schema

discover_tech_ready.py                  # NEW orchestrator (mirrors discover_butchers.py)
  python discover_tech_ready.py --input output/2_enriched_websites.csv
  python discover_tech_ready.py --input output/custom-serper-scoring_*_all.csv --verticals wine,butcher
  python discover_tech_ready.py --master-only

config.py
  + TECH_SIGNATURES dict (or keep in tech_ready/__init__.py if vendor-specific)
  + reuse existing City Hive / Spot Hopper liquor-ESP red-flag list
```

No new external tool is required — every primitive (websites crawl, detect_clubs, reclassify, dedupe) already exists. The only genuinely new code is the `detect_tech_stack` fingerprinter (small, lives in `enrich.py` so the cost folds into an existing fetch) and the overlay package that joins + tiers.

## Open questions

1. Where should tech detection physically live — inline in `enrich.py` step 1 (zero marginal request, but couples to the generic pipeline) or as a standalone re-crawl in `tech_ready/fetch.py` (works on any input CSV, costs a second fetch)? Leaning inline-with-export.
2. What `tech_score` floor actually correlates with onboarding ease — does `has_esp` alone predict it, or is the ESP+ecom pair the real gate? Needs a backtest against onboarded-partner stacks if that data exists.
3. Should `has_pos` (Toast/Square) carry more weight? POS implies real transaction volume but not audience-building maturity (the thing the subscription pitch actually needs). Current weighting favors ESP/ecom — confirm against won deals.
4. For the club-present spillover (`route=nurture_transition`), do we hand those to a separate transition-list engine, or keep them in this CSV with a route flag? Affects whether finalize.py emits one file or two.
