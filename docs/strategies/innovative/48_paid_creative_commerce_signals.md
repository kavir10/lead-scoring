# Lead Engine 48 — Meta and TikTok Creative Signal List

**Motion:** Curation (with a Trigger overlay — an active paid push is a "spending money to sell this *now*" signal)
**Vertical fit:** All (strongest on shippable retail — butcher, wine, cheese, bakery, specialty; weakest on dine-in-only restaurants)
**Suggested list name(s):** `paid_creative_commerce_signals`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $12/run (TikTok Creative Center scrape is the only meaningful spend; Meta Ad Library is manual/targeted, not bulk-automated)

## Premise

A merchant running **paid ads for a preorder, gift, club, event, or holiday
product** is doing the single most expensive version of demand capture: paying
per impression to move a finite, time-boxed SKU through a storefront that
mostly wasn't built to pre-sell. That's a louder Trigger than organic scarcity
language (Engine 03) or a missing gift SKU (Engine 21) — they're not just
*announcing* gift/holiday demand, they're **funding it**. The ask writes
itself: "you're paying Meta to sell holiday gift boxes one at a time — a
Table22 prepaid bundle or club turns that spend into recurring revenue."

This maps cleanly to the two-score model. The **Trigger** is the live paid
creative promoting recurring-commerce-shaped product (preorder / gift / club /
event / seasonal drop). The **ICP Fit** gate decides whether the spender is the
right kind of business — and ad surfaces leak anti-ICP hard (liquor stores,
chains, and ghost kitchens all advertise aggressively), so the gate does heavy
lifting. Best rows are high on both: a butcher ($75.9k), wine ($68.2k), or
cheese ($63.8k) shop running creative for a "holiday meat share" or "wine club"
is exactly the demand-over-capacity, high-AGMV profile we invest in.

**Hard caveat baked into the design.** This is **targeted monitoring, not a
complete automated source.** The **Meta Ad Library has no broad commercial
ad-intelligence API** for this use case — its public API is built around
political/issue ads, and the Ad Library *UI* is the only reliable surface for
commercial-ad search. So Meta is a **manual / semi-automated targeted lane**
(check named candidates, not crawl the universe). **TikTok Creative Center** is
the more automatable surface (public trends + Top Ads examples by industry/
region), but it's a *discovery sampler*, not a per-merchant census. Treat this
engine as a **high-precision, low-recall trigger overlay**, not a primary
volume source.

## Recipe

The novelty here is that the *signal source is an ad surface*, but everything
downstream (ICP gate, enrichment, scoring) reuses existing primitives. There is
**no general "scrape all Meta ads" API** — don't pretend there is. The engine
has two lanes feeding one ICP gate.

### Lane A — TikTok Creative Center (automatable discovery sampler)

1. **Pull Top Ads + Trends by food vertical and US region.** TikTok Creative
   Center exposes public **Top Ads** and **Keyword/Hashtag Insights** filtered
   by industry (Food & Beverage), region (US), and time window. Scrape it with
   the `best_wine_shops/` pattern — **httpx + selectolax happy path, Playwright
   fallback** when the JS-rendered grid blocks (it usually will; the Creative
   Center is a React app, so budget for the Playwright path). Capture: brand /
   advertiser name, ad caption/CTA text, landing URL, region, like/share/
   comment proxies where shown.

2. **Filter creative to recurring-commerce intent (regex over caption + CTA).**
   Keep only ads whose copy reads as preorder / gift / club / event / holiday
   commerce:

   ```
   COMMERCE_INTENT_PATTERNS = (
     r"pre[\s-]?order", r"reserve\s+your", r"limited\s+(drop|release|batch)",
     r"holiday\s+(box|share|order|menu)", r"gift\s+(box|set|basket|card)",
     r"thanksgiving|christmas|hanukkah|valentine|mother'?s\s*day",
     r"(wine|cheese|meat|charcuterie|beer|coffee)\s+club",
     r"subscri(be|ption)", r"members?\s*only", r"monthly\s+(box|share)",
     r"(ticket|rsvp|seats?)\s+for", r"dinner\s+series", r"tasting\s+(event|dinner)",
     r"whole[\s-]?animal\s+share", r"cow\s*share|herd\s*share", r"allocation",
   )
   ```

   Drop pure brand-awareness / menu-photo ads with no commerce verb.

3. **Resolve advertiser → business identity.** TikTok gives a brand/handle and a
   landing URL but not a clean business record. Resolve to a real merchant: if a
   landing domain is present, that's the join key; otherwise resolve the TikTok/
   IG handle via the **Apify instagram-profile-scraper** (reuse the step-2 hook,
   batches of 30) to recover website + location, then geocode to city/state.

### Lane B — Meta Ad Library (manual / targeted monitoring, NOT bulk)

4. **Run as a targeted watchlist, not a crawl.** For a *named candidate set* —
   the existing enriched corpus, niche-lane rows (`butcher/`,
   `best_wine_shops/`, `directories/`, awards master), and Lane-A hits — query
   the Ad Library **UI** per advertiser (Playwright, low volume, human-in-loop
   for ambiguous matches) to confirm an active ad and pull its creative text +
   first-seen date. This answers "is *this specific* high-ICP merchant
   currently running paid commerce creative?" — a corroboration step, not a
   discovery firehose. Do **not** build this as an unattended bulk scraper; the
   Ad Library will rate-limit and there is no commercial API to lean on.

### Shared — enrich, classify, gate, score

5. **Classify creative + write the outbound hook (Claude, cheap pass).** Send
   the ad caption/CTA + landing-page snippet to Claude (`claude-haiku-4-5`, the
   model `scrape_beli` uses) to (a) label `creative_intent ∈
   {preorder, gift, club, event, holiday_drop, awareness_only}`, (b) confirm the
   ad promotes *recurring-commerce-shaped* product (reject awareness-only), and
   (c) emit a one-line `trigger_summary` a BDR can quote. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

6. **Enrich the resolved merchant.** Once a website/handle is resolved, run the
   row through the standard pipeline — `enrich.py` **step 1 (websites)** for
   ecommerce flag + reservation platform, **step 2 (instagram)** for
   follower/engagement context. Join `detect_clubs.py` (`has_club` — an existing
   club is a *positive* platform-switch signal, not a DQ).

7. **Apply the ICP gate (the curation half).** Run `reclassify.py`
   (`partner_type` / `business_type_v2`, wine-bar claw-back). Reject anti-ICP
   *before* scoring — ad surfaces leak this hard:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  OR wine commodity-SKU leak in landing catalog
         (Tito's, Smirnoff, Veuve, BuzzBallz, Budweiser, Josh, Cupcake, Barefoot,
          Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic,
          Andre, Cloud Break)  OR ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)  # heavy ad spenders
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar  -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
     creative_intent == awareness_only   # no commerce trigger

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery
     static-social-only / thin metrics in small market (never DQ — understates brand)

   creative_strength:
     +3 active paid creative for club/subscription product (recurring shape)
     +3 active paid creative for whole-animal share / allocation / preorder on premium catalog
     +2 active gift/holiday-drop creative + commerce_capable landing page
     +2 confirmed on BOTH surfaces (TikTok + Meta) — corroborated spend
     +1 single event/RSVP ad, or single-surface low-engagement creative
     +1 if has_club == True (proven recurring demand)

   QUALIFY (engine output) if: passes ICP gate AND creative_strength >= 2
   ```

8. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   creative columns ride as evidence; `creative_strength` orders the outbound
   queue inside a tier.

## Output schema

```
output/paid_creative/paid_creative_commerce_signals_<YYYYMMDD>.csv
source = "paid_creative_commerce_signals"
tier = <1|2|3>     # 1 = butcher/wine/cheese + active club/preorder creative; 2 = gift/holiday or bakery/specialty; 3 = ICP-soft / single event ad
business_type = butcher | wine_store | cheese | bakery | specialty | restaurant
distinction = "Running paid {creative_intent} creative ({platform}) — convert ad spend into a Table22 {club|bundle}"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    platform               # tiktok | meta | both
    advertiser_name        # brand/handle as it appears on the ad surface
    creative_intent        # preorder | gift | club | event | holiday_drop
    creative_text          # verbatim caption/CTA (the outbound-quotable line)
    creative_cta           # the call-to-action button text where present
    landing_url            # ad destination (join key + commerce evidence)
    matched_terms          # pipe-delim verbatim commerce phrases hit
    first_seen             # earliest date the ad was observed live
    engagement_proxy       # like/share/comment proxy from Creative Center (where shown)
    commerce_capable       # has_ecommerce from enrich.py step 1
    creative_strength      # int, intra-tier outbound ordering
    trigger_summary        # one-line Claude-written outbound hook
    has_club               # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
    resolved_via           # landing_domain | ig_handle | manual_match
```

## Volume & cost

- **Lane A (TikTok Creative Center):** the Top Ads grid surfaces, realistically,
  **~200–500 distinct food-vertical US advertisers per pull** across windows/
  filters. After the commerce-intent regex (~25–35% match) and ICP gate, expect
  **~40–90 qualified net-new rows per run**. This is a *sampler* — it will not
  return thousands.
- **Lane B (Meta Ad Library, targeted):** corroboration/enrichment over a named
  candidate set, not net-new discovery — adds confidence (`platform = both`) and
  a handful of high-ICP merchants the corpus already knows, **not** raw volume.
- **Costs:** TikTok scrape is free-ish (httpx/Playwright, bandwidth + time;
  Playwright fallback is the bottleneck, not a dollar cost). Apify
  profile-scraper resolution for Lane-A hits without a clean landing domain
  (~150 profiles, batches of 30) ≈ **$1–3**. Claude Haiku classify pass on
  matched creatives (~150–250 short prompts) ≈ **$1–3**. **Per-run total: ~$3–8**
  — well under target. Cost stays low *because* this is precision, not census.
- **Net-new qualified leads per run: ~40–90.** Low-recall by nature — the value
  is the *strongest possible Trigger* (live paid spend), not breadth.

## Refresh cadence

**Biweekly, with heavy runs the first weeks of October and January.** Paid
commerce creative is sharply seasonal — holiday preorder/gift pushes ramp Oct–
Dec, Valentine's/Mother's-Day in Jan–Apr — and the whole point is to catch the
ad **while spend is live and the product hasn't shipped yet**, so the outbound
lands ("you're paying for this gift push right now — let's make it recurring").
Off-season, club/subscription creative turns over slowly, so biweekly suffices
without re-burning the Playwright path.

## Risks

- **No commercial Meta Ad Library API — the core constraint.** Anyone scoping
  this as a bulk automated Meta source is wrong; the public API is political/
  issue-ad oriented and the commercial Ad Library is UI-only. Lane B must stay
  **targeted + human-in-loop**; don't promise unattended Meta volume.
- **Discovery sampler, not a census.** TikTok Creative Center surfaces *Top/
  trending* ads, biased toward bigger spenders and viral creative — it
  systematically under-samples small indie merchants (exactly our ICP) running
  modest budgets. Treat absence as no-signal, never as a negative.
- **Anti-ICP leakage is severe on ad surfaces.** Liquor stores, 10+-location
  chains, ghost kitchens, and meal-kit DTC brands out-spend indie food
  businesses on paid creative. Run `config.CHAIN_KEYWORDS`, the commodity-SKU
  catalog scan, and ESP-red-flag (City Hive, Spot Hopper) checks *upstream* of
  `creative_strength`, or the list fills with disqualifiers.
- **Wine-bar / liquor-store false positives.** A bottle shop pushing "Veuve gift
  sets" is commodity liquor, not a curated wine partner. Enforce wine-bar
  exclusion (except geographic-monopoly) and the `reclassify.py` claw-back.
- **Identity-resolution failure.** Ad surfaces give a brand/handle, not a
  business record; a generic name ("The Butcher Shop") can resolve to the wrong
  merchant. Require a confirmed landing-domain or IG-handle match; flag
  `resolved_via = manual_match` rows for QA before sales.
- **Awareness-only creative masquerading as a trigger.** A pretty product video
  with no commerce verb is not a buy signal. Gate on the commerce-intent regex
  *and* the Claude `creative_intent != awareness_only` check.
- **Sweets-only demotion.** A bakery running "Valentine's gift box" ads is a real
  trigger but single-product — cap Tier 2.
- **Small-market metrics run low / static-social understates brand.** A rural
  butcher running a tiny local Meta push won't trend on TikTok and will have thin
  social volume — weight relative local dominance + the paid trigger; never DQ on
  static-only social.
- **Platform/scrape fragility.** The Creative Center is a JS React app that
  changes layout and rate-limits; the Ad Library UI likewise. Expect the
  Playwright fallback to carry most pulls; throttle, jitter, cache, and degrade
  gracefully (a failed pull is a skipped run, not corrupt data).

## Repo placement

Standalone package mirroring the `best_wine_shops/` shape (httpx happy path +
Playwright fallback + Claude extract), reusing `enrich.py` step-1/step-2 and the
shared ICP-gate helpers as libraries.

```
paid_creative/
  __init__.py                  # engine constants; registers pattern banks + surface configs
  signals.py                   # COMMERCE_INTENT_PATTERNS, commodity-SKU/ESP leak lists, tier thresholds
  tiktok_creative.py           # Lane A: httpx+selectolax happy path, Playwright fallback over Creative Center
  meta_ad_library.py           # Lane B: targeted per-advertiser Ad Library UI probe (Playwright, human-in-loop)
  resolve_identity.py          # advertiser -> merchant (landing domain | Apify ig-profile-scraper, batches of 30)
  classify.py                  # Claude haiku-4-5: creative_intent + trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), creative_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_paid_creative.py      # orchestrator: tiktok-pull -> intent-filter -> resolve -> meta-corroborate -> classify -> gate -> finalize
```

Refactor target: extract `enrich.py` **step-1** website parsing (ecommerce flag,
reservation/social detection) and the **step-2** Apify profile-scraper batching
into shared libs (`enrich_websites_lib`, `enrich_instagram_lib`) so this engine
reuses them without duplicating — the same shared-lib argument Engines 19 and 21
raise. Also extract the recurring **ICP-gate block** (commodity-SKU/ESP leak
lists, chain filter, wine-bar claw-back, BANNED_STATES) into a shared
`icp_gate.py` — it's now copy-pasted across several engines. `config.py` knobs to
add: `COMMERCE_INTENT_REGEX`, TikTok Creative Center filter params (industry/
region/window), and the `creative_strength` thresholds. The Meta Ad Library
human-in-loop lane is the genuinely-new bit — there is no existing
unattended-scrape primitive that fits a UI-only, no-API source, and we should
**not** build one that pretends otherwise.

## Open questions

1. **Is Lane A worth the Playwright cost given the recall ceiling?** TikTok
   Creative Center under-samples small indie spenders. Does a ~40–90-row precision
   sampler justify a fragile React-scrape, or is this better as a *corroboration*
   signal merged onto other engines' rows (e.g. add `paid_creative_active` as an
   evidence column to Engines 03/19/21) rather than a standalone list?
2. **Meta Ad Library automation boundary.** How far can Lane B be automated
   before it trips rate-limits or ToS? Is the right shape a small,
   human-reviewed weekly batch over a *curated* high-ICP watchlist, fully manual,
   or skip Meta entirely and lean on TikTok only?
3. **Identity-resolution accuracy on generic names.** What's the false-match rate
   resolving advertiser handles to merchants without a landing domain? Worth a
   labeled probe on 50 known advertisers before trusting `resolved_via = ig_handle`.
4. **Merge vs standalone.** Many qualified rows will already sit in our corpus
   (they advertise *because* they're established). Do we phone-first dedupe via
   `dedupe_existing.py` and merge the paid-creative trigger onto the existing
   partner row, or emit a distinct list with its own outbound timing?
```