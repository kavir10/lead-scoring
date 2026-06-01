# Lead Engine 38 — Award Finalist Drift List

**Motion:** Hybrid (a Curation intersection — durable award credential × a "no recurring commerce" gap — that emits a small, hand-citable list while attention is still high)
**Vertical fit:** All high-fit — butcher, wine, cheese, destination + neighbourhood restaurants, bakery, specialty grocer; anywhere a craft-award body recognizes independent operators
**Suggested list name(s):** `award_finalist_no_recurring_commerce`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$8–16 per run (one `detect_clubs`-style site crawl + a small Serper Maps resolution pass over award rows; no fresh 130-city discovery, minimal LLM)

## Premise

An award — James Beard semifinalist/finalist/winner, Good Food Award, Good Food
Mercantile placement — does two things at once. It is a **durable ICP-Fit
credential** (the `awards/` package already captures it, and *Awards* is a SHAP
feature) and it is a **demand event**: recognition pulls a wave of new
attention against a fixed counter, case, or kitchen. The sharpest possible
two-score lead is an operator that scores high on ICP Fit *and* has a fresh
reason to be contacted — and the most under-exploited version of that is the
award winner who **has no way to capture the repeat demand the award just
created**. They got the attention; they have no club, no subscription, no
standing-order book, no recurring product to convert that attention into
retained revenue. That gap *is* the pitch.

This is the demand-over-capacity thesis stated as a missed-monetization event:
the award manufactures a demand spike, and the absence of recurring commerce
means it dissipates. Table22 is the mechanism that turns "everyone heard about
us this month" into a subscription program. So this engine is deliberately an
**intersection**: the `awards/` master (high ICP-Fit, credentialed, often
top-AGMV verticals — butcher $75.9k, wine $68.2k, cheese $63.8k) **minus** every
operator `detect_clubs.py` shows already runs recurring commerce. The "drift"
is the recency overlay: an award won this cycle, with no recurring product, is a
*now* trigger; an award won three years ago with no club is a nurture row.

Note one inversion of the usual rule: existing club is normally a positive
(platform-switch) signal. Here we explicitly route those rows **out** — a
credentialed operator that already runs a club belongs to the labeled-club
transition lists (Engine 01). This engine owns the complement: credentialed,
high-attention, and *no recurring commerce yet to switch*.

## Recipe

A **postprocessing intersection** over two things we already produce — the
`awards/` master union and a `detect_clubs` scan — plus a light resolution step
to attach contactable Maps data. It runs no fresh Serper discovery.

1. **Input A — the award universe.** Take the latest awards master
   (`output/awards_all_<YYYYMMDD>.csv`) produced by `discover_awards.py`, or
   rebuild it with `python discover_awards.py --master-only`. Each row is already
   canonical (`source, tier, business_type, name, city, state, country,
   distinction, year, source_url, blurb`). Optionally widen with the directories
   master (`output/directories_all_*.csv`) for stockist/curated-directory
   credentials, but keep `awards/` as the spine — it carries `year`, which the
   drift gate needs. Focus seed sources match the idea: James Beard
   (`jbf_semifinalists` + finalists/winners), Good Food Awards
   (`good_food_awards`), Good Food Mercantile, plus the existing craft-award
   modules already registered in `awards/__init__.py:ALL_SOURCES`.

2. **Resolve each award row to a real, contactable operator.** Award rows carry
   name + city/state but rarely phone/website. Run a Serper Maps lookup (the
   `discover.py` primitive) per row to attach `phone`, `website`, `address`, the
   Google Business `type`, and a liveness check (skip permanently-closed
   listings — award lists lag reality). This is the join key for the next steps;
   without a `website` we cannot test for recurring commerce.

3. **Test for recurring commerce (the intersection — `detect_clubs.py`).** Run
   `detect_clubs.py` / `detect_clubs_v2.py` (50-thread crawl, `--resume`) over the
   resolved `website` column to populate `has_club`, `club_type`, `club_url`,
   `club_signals`. This catches *labeled* programs (club / subscription /
   membership). To avoid undercounting recurring commerce — and to keep this list
   from cold-pitching shops that already monetize repeat demand — also fold in the
   `websites` enrichment ecommerce/email-signup flags and (if the `hidden_club`
   overlay from Engine 18 exists) its `is_recurring_program` verdict. Define:

   ```
   has_recurring_commerce =
        has_club                                   # labeled club/subscription/membership
     OR is_recurring_program (Engine 18 hidden)    # allocation / standing order / share / box
     OR (has_ecommerce AND has_subscribe_product)  # an actual recurring SKU on their store
   ```

4. **Take the complement — award AND no recurring commerce.** Keep only rows
   where `has_recurring_commerce == False`. This is the engine's whole point:
   credentialed operators with attention and no machinery to retain it.

   ```
   candidate = (in awards/directories master)
               AND resolved_live_website
               AND not has_recurring_commerce
   ```

5. **Drift gate (the trigger half of the two-score model).** Use the award `year`
   (and announcement date where the module exposes it) to stamp recency. The
   credential is durable, but the *contact-now* strength decays:

   ```
   age_years = current_year - year
   fresh   = age_years <= 1     # this cycle / last cycle — hot trigger
   recent  = age_years <= 2     # still a credible "congrats on the ..." opener
   stale   = age_years >  2     # durable ICP credential, weak trigger -> nurture
   ```

6. **Tier by award weight × ICP partner type × drift freshness.** This is a
   contact-priority overlay — it does **not** touch `config.SCORING_WEIGHTS`.

   ```
   award_tier = 1  JBF finalist/winner, Good Food Award winner, marquee craft award
              = 2  JBF semifinalist, Good Food Mercantile / finalist
              = 3  regional / lower-tier craft recognition
   icp_top    = partner_type in {butcher, wine, cheese, destination_restaurant}
   icp_ok     = partner_type in {neighbourhood_restaurant, bakery, deli,
                                 specialty_grocer, market}

   if   award_tier == 1 and (icp_top or icp_ok) and fresh:        tier = 1
   elif award_tier <= 2 and (icp_top or icp_ok) and recent:       tier = 2
   elif (icp_top or icp_ok):                                      tier = 3   # stale credential -> nurture
   else: drop                                                     # weak-ICP award = filter, not sell
   ```

7. **Clean, reclassify, dedupe, state-filter before handoff.** Run
   `reclassify.py` (Maps `type` + name heuristics → `partner_type` /
   `business_type_v2`, wine-bar claw-back) so wine bars (mostly excluded) and
   liquor stores don't ride in on a wine award. Run `clean_awards.py` for schema
   normalization, then `dedupe_existing.py` (phone-first, then name+address)
   against the current scored universe to mark net-new vs. re-surfaced. Apply the
   butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter to
   `partner_type == butcher` rows only.

8. **(Optional) full score for ranking.** If a row is net-new and tier-1/2, hand
   it through the remaining `enrich.py` steps + `score.py` so the drift trigger
   rides on top of the SHAP-aligned ICP score. The award/drift fields are overlay
   evidence; preserve the citation, don't bury it.

## Output schema

```
output/award_drift/award_finalist_no_recurring_commerce_<YYYYMMDD>.csv
source = "award_finalist_no_recurring_commerce"
tier = <1|2|3>                       # contact-priority tier from recipe step 6
business_type = restaurant | bakery | wine | cheese | butcher | deli | specialty_grocer | market
distinction = "{award_source} {award_distinction} ({year}, {age_years}y ago) — no recurring commerce yet"
year = <YYYY of the award>
+ canonical: name, city, state, country, source_url (= award page), blurb
+ evidence cols (preserve so sales can cite both the credential and the gap):
    award_source            # jbf / good_food_awards / good_food_mercantile / ...
    award_distinction       # "2026 Semifinalist, Best Chef: Northeast", "GFA Winner — Charcuterie"
    award_tier              # 1|2|3 award weight
    age_years, drift_state  # fresh | recent | stale
    partner_type            # from reclassify.py
    matched_phone, matched_website   # from Serper Maps resolution
    has_club, club_type, club_signals        # must indicate NO recurring commerce
    has_recurring_commerce  # must be False (step 3 composite)
    has_ecommerce, has_esp  # store / email-list presence (capture-readiness)
    is_net_new              # vs current scored universe
    scan_date
```

`source_url` (award page) + `award_distinction` give the BDR the verbatim
credential, and `has_recurring_commerce=False` + `has_esp` frame the gap:
"congrats on the James Beard semifinal — you've got the audience and an email
list, but no way to turn it into recurring revenue yet." That paired cite is the
whole reason this is Curation, not Volume.

## Volume & cost

Bounded by the size of the award master, not a fresh crawl. A full
`awards_all` union is on the order of **~2,000–4,000 rows** across all
categories and years.

- Resolve to Maps (~2,000–4,000 lookups, deduped first to one per operator →
  ~1,200–2,500 unique) ≈ **$4–8** in Serper Maps calls.
- `detect_clubs` crawl over the resolved websites folds into the existing
  50-thread crawler — bandwidth only, near-free compute.
- Optional Engine-18 hidden-club LLM pass on the no-labeled-club subset: a few
  hundred Haiku calls ≈ **$2–5** (skip if Engine 18 hasn't shipped).
- No fresh Serper discovery, no Apify IG/reviews, no Resy.
- **Per-run total: ~$8–16.**

Net-new math: of ~1,200–2,500 unique resolved award operators, a large share
already run recurring commerce or are already in the scored universe. Empirically
expect **~40–60%** to lack any recurring product (`has_recurring_commerce==False`)
→ ~500–1,500 candidates; after the drift gate (fresh/recent only) and ICP tiering,
**~80–200 tier-1/2 leads per run**, skewed toward the high-AGMV verticals (Good
Food Awards charcuterie/cheese, JBF butcher/restaurant). Most of the value is a
*dated credential-plus-gap stamp* that vaults a high-ICP row to the top of the
queue while the award is fresh.

## Refresh cadence

**Tied to award announcement seasons, with a quarterly base run.** The two big
seeds are calendar events: James Beard semifinalists drop ~late January with
finalists/winners following in spring; Good Food Awards announce ~January. Burst
the run right after each announcement so this-cycle winners enter the list while
`drift_state == fresh`. Between seasons, a quarterly base run re-tests the
`has_recurring_commerce` flag — the high-value diff is a previously-listed award
row that *still* hasn't added recurring commerce (a hardened "they had a year and
still no club" nurture-to-active signal) or, conversely, one that just did (drop
it — it now belongs to Engine 01's transition list).

## Risks

- **Stale-credential / re-mint noise.** The same JBF or Good Food name recurs
  year over year. Gate hard on `age_years` and dedupe phone-first; don't mint a
  fresh tier-1 every January for an unchanged 2019 award. Keep the highest
  `award_tier` × freshest `year` as the canonical row.
- **The "no recurring commerce" call is the whole engine — and it's failure-prone.**
  Many real recurring programs are invisible to a homepage crawl: a wine
  allocation list, a butcher standing order run over text/DM, a CSA on a Google
  Form. A clean `detect_clubs` scan is **not** proof of no program. Bias toward
  precision: prefer the Engine-18 hidden-club composite in step 3, and treat
  thin-web operators as lower-confidence rather than confident "no club." Sample
  via `sample_clubs_for_qa.py` before sales handoff — a false "you have no club"
  cite is embarrassing in outbound.
- **Weak-ICP award leakage.** Award lists include pizza-first spots, cocktail
  bars (JBF has a bar program), caterers, and the occasional chain. Run
  `reclassify.py` + `config.CHAIN_KEYWORDS` filtering and the wine-bar claw-back
  *before* tiering; high-trigger / weak-ICP must be filtered, never sold. An
  award never overrides a disqualifier.
- **Wine-bar / liquor-store confusion.** A wine award can name a wine *bar*
  (mostly excluded except geographic monopoly) or be mis-resolved to a liquor
  store. Respect reclassification; don't admit on award strength alone. Watch
  commodity-SKU / City Hive / Spot Hopper red flags if the wine slice over-produces.
- **Sweets-only demotion.** A bakery recognized for one viral pastry is still
  capped at Tier 2 (single-product demotion); carry `partner_type` and apply the cap.
- **Small-market metrics run low.** A regional Good Food Award winner in a
  non-top-30 metro is a *stronger* relative signal than its national footprint
  implies, and its static social will understate its brand — weight the credential
  and local dominance, don't down-rank on thin traffic/follower volume.
- **Resolution false-matches.** Serper Maps may attach the wrong location for a
  common name or a multi-location operator. Confirm city/state agreement between
  the award row and the Maps hit before binding `website`; mismatches go to manual
  review, not the list.
- **Source fragility.** JBF and Good Food publish in inconsistent formats year to
  year; the upstream `awards/` modules already absorb this, but expect per-source
  drift in `year` extraction — the drift gate depends on a reliable `year`.

## Repo placement

An overlay package plus a thin orchestrator — every primitive already exists; the
genuinely new code is the intersection/drift logic.

```
award_drift/                              # NEW top-level package, mirrors hidden_club/ + best_wine_shops/ shape
  __init__.py                             # drift thresholds (fresh/recent/stale), award_tier + ICP tiering weights
  resolve.py                              # Serper Maps resolution of award rows -> phone/website/type/liveness
                                          #   (wraps the discover.py Maps primitive)
  intersect.py                            # detect_clubs scan + has_recurring_commerce composite (step 3)
  aggregate.py                            # complement filter, drift gate, award_tier x ICP tiering
  finalize.py                             # reclassify -> clean_awards -> dedupe_existing -> BANNED_STATES (butcher)
                                          #   -> canonical CSV

discover_award_drift.py                   # NEW orchestrator (mirrors discover_awards.py / discover_butchers.py)
  python discover_award_drift.py --awards output/awards_all_<YYYYMMDD>.csv
  python discover_award_drift.py --awards-master-only          # rebuild awards master first, then run
  python discover_award_drift.py --window 1 --fresh-only       # this-cycle drift gate
  python discover_award_drift.py --verticals butcher,wine,cheese
  python discover_award_drift.py --resume

config.py
  + reuse existing CHAIN_KEYWORDS, wine commodity/liquor exclusion SKUs + City Hive/Spot Hopper
    red flags, importer trust list, BANNED_STATES (all already present)
```

Refactor targets: (1) lift the `discover.py` Serper-Maps lookup body into a small
`maps_lib.py` so `award_drift/resolve.py` reuses one resolver instead of importing
`discover.py` wholesale (the same lift Engine 08 wants for name resolution);
(2) expose a `detect_clubs.scan_site(website) -> {has_club, club_type, club_url,
club_signals}` callable so `intersect.py` can run the scan per-row without
shelling the standalone script. No new external tool is required.

## Open questions

1. What is the authoritative definition of "no recurring commerce"? Labeled-club
   absence alone is too loose (misses hidden allocation/standing-order programs and
   over-pitches). Should this engine *require* the Engine-18 hidden-club composite
   in step 3, making Engine 18 a hard dependency, or ship a labeled-only v1 and
   accept lower precision until 18 lands?
2. Do JBF **semifinalists** (broad pool, ~20/category/city) and **winners**
   (narrow) belong in the same list, or split — semis as a high-volume Tier-2 net,
   winners as the durable Tier-1 credential? Semis are the timelier trigger.
3. How far back should the durable-credential window reach for nurture rows? A
   2019 Good Food Award with still no recurring commerce is a real ICP row, but at
   what `age_years` does the trigger stop being citable in outbound?
4. Should multi-location and recently-expanded award winners be flagged (and
   possibly routed to a capacity-expansion engine) rather than treated as single
   shops, given resolution attaches only one Maps location per name?
