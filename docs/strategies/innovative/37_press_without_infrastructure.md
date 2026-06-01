# Lead Engine 37 — Press Without Infrastructure List

**Motion:** Hybrid (a Trigger overlay — fresh press — intersected with a structural ICP gap: no demand-capture infrastructure)
**Vertical fit:** Destination + neighborhood restaurants, bakeries, wine shops, cheesemongers, butchers — any operator editorial food media covers but who runs a transactional storefront and nothing else
**Suggested list name(s):** `press_without_infrastructure`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$8–16/run (folds onto Engine 08's press output + a `detect_clubs.py` + websites crawl over the matched set; no new Apify discovery spend)

## Premise

The single sharpest Table22 pitch is "you have demand you can't capture." This engine finds the operators where that gap is provable from public data: **fresh, credible press exists, but there is no mechanism on the property to convert the resulting wave into recurring revenue.** An Eater "best new," a James Beard semifinalist nod, an Infatuation review, a Bon Appétit / Food & Wine feature, a Good Food Award — each pulls a demand spike against a fixed counter, case, or kitchen. If that operator has no newsletter, no preorder, no online shop, and no club/subscription, the spike dissipates the moment the article ages out. That is demand-over-capacity stated as a structural absence, and it is the cleanest possible reason to call now.

In the two-score model this engine deliberately combines a high **Trigger** (recent press — a calendar event a BDR can cite verbatim) with a **negative ICP-infrastructure read** that *raises* the value of the conversation rather than lowering ICP Fit. The absence of capture infrastructure is not a disqualifier — it is the whole sale. Table22 *is* the missing layer. Contrast with Engine 01 (existing-club transition, platform-switch) and Engine 20 (owns a list, no monetization): this engine sits one rung earlier — the operator has neither the list nor the monetization, but has just been handed validated demand by the press. "You just got named to the Eater 16 and there's nowhere on your site to capture that interest" is the line.

This is explicitly the **intersection of Engine 08 (Press Momentum Watchlist) and an infrastructure-absence scan**. It consumes 08's fresh-press rows and keeps only those that fail every demand-capture check. High-ICP partner type (butcher / wine / cheese / destination restaurant) + fresh press + zero infrastructure = top of the call list. Weak-ICP press (pizza-first roundup spot, cocktail bar in a nightlife list) is filtered hard before sales — press never overrides a disqualifier, and "no infrastructure" on an anti-ICP business is just an anti-ICP business.

## Recipe

A **Hybrid overlay** that reuses two existing motions end-to-end: Engine 08's fresh-press lane (or a direct `awards/` + `enrich.py` step-4 press pull) for the Trigger, and the `detect_clubs.py` + websites-crawl primitives for the infrastructure-absence read. No fresh Serper Maps discovery is added here.

1. **Input — the fresh-press set.** Take Engine 08's emitted CSV (`output/press_signals/press_awards_recent_momentum_<YYYYMMDD>.csv`), which already carries `name, city, state, partner_type, press_source, press_date, age_days, source_url, matched_phone, matched_website` and has been recency-gated (≤120d) and Serper-Maps-resolved. If Engine 08 hasn't run, fall back to the `awards/` recurring lane + `enrich.py` step-4 press primitive directly (Serper Web vs `config.py` food-media domains + award keywords), then resolve names via the `discover.py` Serper Maps primitive. **Do not re-discover** — this engine is a filter over already-pressed, already-resolved operators.

2. **Crawl the matched website for capture infrastructure (reuse `enrich.py` step 1 `websites`).** Run the concurrent websites crawl (10 threads) over each row's `matched_website`. Step 1 already detects: ecommerce flag, email-signup form, social links, reservation-platform detection. Capture all four; this engine reads three of them as the infrastructure check (ecommerce, email signup, reservation/commerce surface). One fetch, no extra request.

3. **Negative club/subscription check (reuse `detect_clubs.py`).** Run `detect_clubs.py` (50-thread site scrape, `--resume`) over the matched set to populate `has_club`, `club_type`, `club_url`, `club_signals`. Its keyword/path patterns already cover wine club, meat/fish share, CSA, monthly box, bread/cheese club, allocation, subscription, membership, autoship. Keep only `has_club == False` rows. Club-positive rows are **not discarded** (existing club is a positive signal) — tag them `route=nurture_transition` and hand to Engine 01.

4. **Belt-and-suspenders infrastructure-absence scan.** Over the crawled homepage plus a link probe to `/shop`, `/store`, `/order`, `/subscribe`, `/club`, `/newsletter`, `/preorder`, `/gift`, catch capture wording the structured flags miss. A row qualifies only if **zero** matches across all four buckets:

   ```
   MUST_BE_ABSENT (zero matches across all buckets to qualify as "no infrastructure"):
     newsletter / list:  newsletter, join our list, mailing list, subscribe (email),
                         signup form, klaviyo|mailchimp|flodesk|omnisend|beehiiv
                         |constant contact|convertkit fingerprint, footer/popup capture
     ecommerce:          add to cart, shop now, online store, /shop /store /products,
                         shopify|squarespace-commerce|woocommerce|bigcommerce cart,
                         "buy online", "ship nationwide"
     preorder/ordering:  preorder, pre-order, order online, order ahead, toast|square
                         online ordering, "order for pickup"
     club/subscription:  (covered by detect_clubs.py step 3) subscription, membership,
                         wine|meat|bread|cheese club, monthly box, CSA, standing order,
                         allocation, autoship, gift subscription
   ```

   `has_ecommerce`, `has_email_capture`, `has_online_ordering`, `has_club` must all be `False`.

5. **Grade the gap (infrastructure-absence completeness).** A property with *nothing* is the purest lead; a property with only a passive reservation widget is still wide open:

   ```
   infra_gap:
     total    = no ecommerce AND no email capture AND no online ordering AND no club
                AND no preorder                                  # nothing to monetize demand
     partial  = exactly one weak capture surface present
                (e.g. a bare mailto: or a reservation link only) but no commerce/club
     has_infra = any real commerce/club/list surface present     # drop — not this engine
   keep infra_gap in {total, partial}
   ```

6. **Trigger × ICP tiering.** Combine 08's press source weight, recency, and ICP partner type with the gap grade. This is a *contact-now* overlay — it does **not** touch `config.SCORING_WEIGHTS`:

   ```
   src_tier   = 1  JBF semis/finalists, Eater "best new", Good Food Awards,
                   Cheesemonger Invitational, marquee BA/F&W feature   (from Engine 08)
              = 2  Infatuation review, established city-mag best-of
              = 3  local paper mention, listicle inclusion
   icp_ok     = partner_type in {butcher, wine, cheese, destination_restaurant,
                   neighbourhood_restaurant, bakery, deli, specialty_grocer}
   recency_hot = age_days <= 45

   if   src_tier == 1 and icp_ok and infra_gap == "total" and recency_hot:  tier = 1
   elif src_tier <= 2 and icp_ok and infra_gap in {total, partial}:         tier = 2
   elif icp_ok:                                                             tier = 3
   else: drop                          # weak-ICP press + no infra = still anti-ICP
   ```

7. **Vertical adjudication before handoff.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, wine-bar claw-back) then `dedupe_existing.py` (phone-first against the scored universe to mark net-new vs re-surfaced). For `business_type == wine`, the same liquor-store tells from `config.py` apply: a "no infrastructure" liquor store is still a liquor store (anti-ICP), and a City Hive / Spot Hopper site vendor is a liquor-store red flag, not a curated-wine gap. Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter only to `partner_type == butcher` rows.

8. **Optional demand confirmation (restaurants).** For Tier-1/2 restaurant rows, run `enrich.py` step 8 (availability — OpenTable/Apify + Resy) to confirm the press is translating into reservation scarcity. Fresh feature + no-availability + no online capture is the strongest outbound line in the deck. Skip for retail verticals where reservations don't apply.

## Output schema

```
output/press_signals/press_without_infrastructure_<YYYYMMDD>.csv
source = "press_without_infrastructure"
tier = <1|2|3>
business_type = restaurant | bakery | wine | cheese | butcher | deli | specialty_grocer
distinction = "Fresh press ({press_source}, {press_date}, {age_days}d ago) — no {missing_infra} on site"
year = <YYYY of press_date>
+ canonical: name, city, state, country, source_url (= press article URL), blurb
+ evidence cols (preserve verbatim so sales can cite both the trigger and the gap):
    press_source, press_source_tier, headline, press_url,   # the press citation
    press_date, age_days, recency_hot,
    matched_website, matched_phone,                          # resolved operator
    has_ecommerce, has_email_capture, has_online_ordering,   # the gap, itemized
    has_club, club_signals,                                  # should be empty
    infra_absence_scan,         # MUST_BE_ABSENT matches found (should be empty)
    missing_infra,              # human list, e.g. "newsletter, shop, club"
    infra_gap,                  # total | partial
    partner_type, src_tier,
    is_net_new,                 # vs current scored universe
    reservation_difficulty, availability_checked,  # optional, restaurants only
    route,                      # sales | nurture_transition (club-present spillover)
    scan_date
```

Master union: `output/press_signals/press_without_infrastructure_all_<YYYYMMDD>.csv`. The `press_url` + `missing_infra` pairing is the deliverable: a BDR opens with the dated press cite and names the exact missing layer ("congrats on the JBF semi — noticed there's no way to preorder or join a list on your site").

## Volume & cost

Bounded by Engine 08's fresh-press output, not a 130-city crawl. Per weekly run, off ~150–350 recency-gated press rows from Engine 08:

- **Infrastructure-absence rate is the key multiplier.** Among independent, press-covered food operators, a meaningful share still run a brochure site only — empirically **~30–45%** lack ecommerce, list capture, ordering, *and* a club. So ~50–155 rows survive the all-absent filter.
- Of those, after `reclassify.py` + chain/liquor-store/wine-bar adjudication drops weak-ICP press leakage (~25–35%), expect **~35–110 net-new + re-surfaced leads per run**, of which **~15–40 hit Tier 1** (marquee fresh recognition × strong ICP × `infra_gap == total`).
- Cost arithmetic: the press lane is Engine 08's spend (don't double-count). Marginal cost here = the websites crawl + `detect_clubs.py` over ~150–350 rows (near-free compute, bandwidth only) + optional availability check on ~30–60 Tier-1/2 restaurant rows (Apify OpenTable + Resy) ≈ **$3–7**. If this engine runs standalone (no Engine 08), add the press lane's Serper Web + Maps + LLM resolution (~$8–14). **Standalone per-run total: ~$8–16; overlay-only marginal: ~$3–7.**

## Refresh cadence

**Weekly**, ride-along to Engine 08. Press recency (the 45-day `recency_hot` window) is half the mechanism and decays fast; infrastructure absence at a small operator changes slowly. The high-value diff is a previously-qualified row that *adds* a shop/list/club between runs — that intersection (this run's `has_infra==True` ∩ a prior run's `press_without_infrastructure` set) is itself a signal the operator is investing in capture and is now a warmer, more sophisticated conversation. Burst around known announcement seasons (JBF semis ~late January, Good Food Awards ~January, "best of year" lists ~December) when 08 floods.

## Risks

- **Infrastructure false negatives kill good leads.** JS-injected newsletter pop-ups, CDN-cached footers, headless Shopify storefronts, and "order on a third-party domain" links can hide a real capture surface, wrongly admitting an operator who *does* have infrastructure. Keep `infra_absence_scan` raw in the output and QA tier-1 rows before outreach — false "no infrastructure" claims burn credibility on the first call. Prefer precision on the absence filter.
- **Weak-ICP press leakage.** Listicles mix in pizza-first spots, cocktail bars, caterers, ghost kitchens, chains. Run `reclassify.py` (wine-bar claw-back) and `config.CHAIN_KEYWORDS` *before* tiering; high-trigger / weak-ICP is filtered, never sold. "No infrastructure" never rescues an anti-ICP business.
- **Liquor-store / wine-bar confusion.** A wine roundup can name a wine *bar* (mostly excluded except geographic monopoly) or a liquor store (DQ vs curated shop). A liquor store with no ecommerce is still anti-ICP; the City Hive / Spot Hopper vendor tell and commodity-SKU exclusion list (Tito's, Smirnoff, Veuve, Yellowtail, Josh, Barefoot, etc.) must run. Don't admit on the gap alone.
- **Sweets-only demotion.** A bakery named for one viral pastry with no online presence is still capped at Tier 2 (single-product heavy demotion). Carry `partner_type` and apply the cap regardless of how clean the press × gap intersection looks.
- **Small-market metrics run low, and thin web footprint is the norm, not the exception.** A dominant rural butcher just named regional best-of will genuinely have a sparse site — that's the lead, not a disqualifier. Weight relative local dominance + reservation difficulty over raw social/review volume. Static-only social understates small-market brand; don't DQ on a thin IG. Butcher/deli/specialty-grocer audiences skew Facebook — `follower_count` (IG + FB) already accounts for this.
- **Closed/relocated venues.** Press lags reality; the websites crawl + 08's Serper Maps resolution double as a liveness check — a dead site or permanently-closed Maps listing is a drop, and a missing site here means "can't verify the gap," not "no infrastructure." Don't admit unresolvable rows.
- **Source fragility.** Inherits all of Engine 08's editorial-source breakage (Eater/Infatuation re-templating, JBF format drift) plus `detect_clubs.py` keyword rot. Isolate per-source failures; one source down ≠ run down, mirroring `discover_awards.py`.
- **Double-counting cost.** If both engines run, the press-lane spend belongs to Engine 08 — only the crawl + detect_clubs + optional availability are this engine's marginal cost.

## Repo placement

An overlay package plus a thin orchestrator, reusing Engine 08's output and the existing crawl/club primitives. No new external tool.

```
press_signals/                          # EXTEND existing package (shared with Engine 08)
  __init__.py                           # + INFRA_ABSENCE keyword/path table, infra_gap thresholds
  fetch_infra.py                        # NEW: run enrich.py step-1 websites crawl + detect_clubs.detect()
                                        #      over Engine 08's fresh-press rows (or a direct press pull)
  aggregate_infra.py                    # NEW: MUST_BE_ABSENT scan, infra_gap grading, src_tier x ICP tiering
  finalize_infra.py                     # NEW: reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical CSV

discover_press_without_infra.py         # NEW orchestrator (mirrors discover_butchers.py / discover_press_momentum.py)
  python discover_press_without_infra.py --input output/press_signals/press_awards_recent_momentum_<YYYYMMDD>.csv
  python discover_press_without_infra.py --standalone --window 120   # runs the 08 press lane first
  python discover_press_without_infra.py --master-only

enrich.py
  + expose the step-1 websites crawl as a callable (e.g. crawl_website(url) -> dict)   # REFACTOR
      so fetch_infra.py and detect_clubs.py share one fetch instead of importing enrich wholesale
  + expose step-8 availability funcs as _availability_lib.py                            # REFACTOR
      (same lift proposed for Engines 04/05/08) for the optional reservation-scarcity confirm

config.py
  + reuse existing City Hive / Spot Hopper liquor-ESP red flags + commodity-SKU exclusion list
  + INFRA_ABSENCE patterns may live here or in press_signals/__init__.py (keep with the engine if engine-specific)
```

The only genuinely new code is the infrastructure-absence scan + tiering (`fetch_infra.py` / `aggregate_infra.py` / `finalize_infra.py`) and the orchestrator. Everything else — fresh press (Engine 08), the websites crawl, `detect_clubs.py`, `reclassify.py`, `dedupe_existing.py` — already exists. The `crawl_website()` refactor is shared with Engine 20's `detect_list_capture` lift; build the shared step-1 fetch lib once.

## Open questions

1. Is the "no infrastructure" read better as a **hard all-four-absent gate** (high precision, low volume) or the graded `infra_gap in {total, partial}` (more volume, requires the partial bucket be tightly defined)? A reservation widget alone is arguably still "no capture infrastructure" for a restaurant — does a Resy link count as infra, or is reservations orthogonal to demand-capture and exempt from the gate?
2. Should this engine consume Engine 08's output as a hard dependency (cleaner, but couples release cadence) or carry its own optional `--standalone` press pull (duplicates the press lane logic)? Determines whether the two engines share `fetch_recent_press.py`.
3. Headless/third-party ordering (a Toast or Square ordering domain linked off-site, a separate Shopify subdomain) is easy to miss in a homepage-only crawl. Do we follow off-domain order/shop links to confirm true absence, or accept some false "no infrastructure" and lean on tier-1 QA?
4. For the club-present spillover (`route=nurture_transition`), do we physically hand those rows to Engine 01's transition pipeline, or tag-and-keep here? Same coupling question Engine 20 raised — resolve once across the infrastructure-overlay engines.
