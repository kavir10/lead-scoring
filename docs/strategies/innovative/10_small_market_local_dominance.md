# Lead Engine 10 — Small-Market Local Dominance List

**Motion:** Curation
**Vertical fit:** Wine, butchers, bakeries, cheese, destination-town restaurants
**Suggested list name(s):** `small_market_local_dominance`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $35/run

## Premise

Our standard discovery floors (restaurants ≥50 reviews / ≥4.2; niche ≥20 /
≥4.0, in `discover.py`) and our SHAP weights both lean on *absolute* metrics —
review count, follower count, monthly traffic. In a small affluent town those
metrics run structurally low and the strongest operators in the market get
DQ'd or buried, even when they are obviously the only premium option for 40
miles. The ICP cheat-sheet is explicit about this: in small markets, weight
**relative local dominance**, regional best-of, and reservation difficulty
over raw social/review volume, and never let thin static-social numbers
disqualify a brand that quietly owns its town.

This engine reframes the question from "how big is this business?" to "how
dominant is it *relative to its market*?" A wine shop with 220 reviews and a
4.8 in a town whose next-best wine option is a gas-station beer cave is a
near-monopoly on curated wine demand. That is a clean **ICP Fit** signal: the
captive, affluent local base has nowhere else to spend, and a Table22 program
captures that recurring demand without the operator needing to add a single
square foot. Partner-type economics still favor the same verticals — butcher
$75.9k > wine $68.2k > cheese $63.8k > destination restaurant $60.5k Peak
AGMV — so we bias the dominance scan to those.

The **Trigger** half is supplied by relative scarcity: limited hours, a
sold-out / waitlist posture, hard-to-book bookings in a town with no
substitute. High dominance *and* a scarcity posture is the call-now cohort;
high dominance with no scarcity is a strong nurture lead, not a hard pass.

## Recipe

This is a **geography-first curation** engine. Instead of querying ~130 big
metros, it enumerates small affluent markets, then computes each candidate's
rank *within its own market* before any absolute floor is applied.

1. **Build the small-affluent-market frame.** Assemble a target list of small
   markets (towns / micropolitan areas, roughly pop. 5k–75k, above-median
   household income) distinct from `config.CITIES`, which is big-metro-biased.
   Seed from `research/trendy_neighborhoods/` where those rows are
   small-town/resort-town (Hudson NY, Healdsburg, Aspen, Sausalito, etc.) and
   extend with a curated affluent-small-town list. Store as a new
   `config.SMALL_MARKETS` list (name, state, lat/lng, optional pop/income).
   This is genuinely new infra — the existing city list won't surface these.

2. **Discover per market, NO absolute floor yet.** Reuse the Serper Maps path
   in `discover.py` / `scripts/fresh_icp_search.py`, one sweep per small
   market across the fit-vertical keyword sets (wine, butcher, bakery, cheese,
   restaurant). Dedupe by phone, run `config.CHAIN_KEYWORDS` + liquor-license
   filters, require a website — but **bypass the review/rating quality floor at
   this stage**; relative rank is computed next and the floor would discard the
   small-market winners we're hunting.

3. **Compute relative local dominance per (market × vertical).** Group all
   candidates by market and canonical vertical, then rank within the group:

   ```
   # within each (market, vertical) bucket:
   rank_reviews   = percentile of this biz's review_count vs market peers
   rank_rating    = this.rating - median(market peer ratings)
   n_competitors  = count of same-vertical peers in market (after chain filter)
   is_only_premium = 1 if n_competitors <= 1 (sole curated option in market)
   review_gap     = this.review_count / max(2nd_place_review_count, 1)

   dominance = (40 * rank_reviews)                 # leader-in-market share
             + (20 if rank_rating >= 0.2 else 0)   # also the best-rated
             + (25 if is_only_premium else 0)       # monopoly bonus
             + (15 * clamp(log2(review_gap), 0, 1)) # blowout vs 2nd place
   # 0–100; high = owns the market regardless of absolute volume
   ```

   `is_only_premium` and `review_gap` are the load-bearing small-market
   features — they reward monopoly position, which absolute counts hide.

4. **Layer a relative scarcity trigger.** Reuse Engine 03's text-signal bank
   over website + IG/FB captions (limited hours, `sold out`, `next drop`,
   `waitlist`, `by appointment`, seasonal closures), and — for the restaurant
   sub-cohort — the `enrich.py` step 8 availability probe (OpenTable via Apify,
   Resy API). In a small market, **interpret scarcity relative to market
   size**: "booked two weeks out" in a 10k-pop town is a stronger demand signal
   than the same in Manhattan. Emit `scarcity_signal` (0/1) + the matched
   snippet.

5. **Enrich the survivors, lightly.** Run the candidates that clear a dominance
   floor through `main.py --enrich` steps 1–3 (websites, instagram, facebook)
   only. Butcher / deli / specialty-grocer skew to Facebook engagement, so
   `follower_count` (IG + FB, computed in `enrich_facebook`) matters more than
   IG alone here. Skip the expensive Apify reels/posts/reviews steps on the
   first pass — dominance, not engagement depth, is the qualifier in this lane.

6. **Qualify against ICP, with the small-market overrides.** Run
   `reclassify.py` (partner_type + business_type_v2 + wine-bar claw-back) and
   `detect_clubs.py` (existing club = positive platform-switch signal, not a
   DQ). Hard-filter liquor-store / chain / delivery-only leakage and the wine
   commodity-SKU exclusion list. Then:

   ```
   final = dominance >= 55                          # owns its market
           AND partner_type in FIT_VERTICALS        # butcher/wine/cheese/bakery/dest-restaurant
           AND not anti_icp                          # post chain/liquor/ghost filters
   tier  = 1 if (dominance >= 70 AND scarcity_signal) else \
           2 if dominance >= 55 else 3
   ```

   Critically, do **not** route survivors through `score.py`'s absolute-metric
   floors as a gate — `score.py` can still compute an ICP-fit score for
   reference, but the dominance score is the qualifier in this lane (the whole
   point is that absolute scoring under-rates these). Matched scarcity snippets
   are preserved verbatim for outbound.

## Output schema

```
output/local_dominance/small_market_local_dominance_<YYYYMMDD>.csv
source = "small_market_local_dominance"
tier = <1|2|3>                       # 1 = dominant + scarcity; 2 = dominant; 3 = leaning
business_type = wine_store | butcher | bakery | cheese | restaurant
distinction = "Local market leader in {market}, {state} ({rank}/{n_competitors} {vertical}, only premium option={is_only_premium})"
year = <YYYY>
source_url = <google maps / website url — sales cites the market context>
blurb = <one-line: e.g. "Sole curated wine shop in Healdsburg; 3x the reviews of 2nd place">
+ evidence cols:
    market, market_state, market_pop_band,
    dominance_score, rank_reviews_pct, rank_rating_delta,
    n_competitors, is_only_premium, review_gap,
    review_count, rating,                 # absolute, for context only — NOT a gate
    scarcity_signal, scarcity_snippet,    # verbatim quote for outbound
    follower_count, has_club, partner_type,
    icp_fit_score,                        # from score.py, reference only
    scan_date
```

Per-run master union: `output/local_dominance/small_market_local_dominance_all_<YYYYMMDD>.csv`.

## Volume & cost

The small-affluent-town universe is the limiter, not the search budget.

- Markets in the frame: ~300–500 small affluent towns.
- Serper Maps: ~5 vertical sweeps × ~500 markets ≈ 2,500 searches ×
  ~$0.001 = **~$2.50** (Serper Maps is cheap; geography breadth, not depth).
- Light enrichment (websites crawl is free; IG/FB via Apify ~$0.015/profile)
  on survivors. After chain/liquor filtering and the dominance floor, expect
  ~1,500–2,500 candidates to enrich → ~2,000 × $0.015 ≈ **~$30**.
- Availability probe (OpenTable/Resy) only on the restaurant sub-cohort
  (~few hundred rows) ≈ **$1–2**.
- **Per-run total: ~$30–35.**
- **Net-new qualified leads per run:** most of these will be *genuinely
  net-new* — they're below our standard discovery floors and big-metro city
  list, so the existing pipeline never saw them. Expect **~250–450 leads**
  clearing `dominance >= 55` + ICP fit, of which ~80–150 carry a scarcity
  trigger (tier 1). This is the engine's whole value: it manufactures supply
  the absolute-metric pipeline structurally misses.

## Refresh cadence

**Quarterly.** Local dominance is a slow-moving structural fact — a town's
sole premium butcher doesn't lose that position month to month. A quarterly
re-scan catches new entrants, a competitor opening (which can flip
`is_only_premium`), and seasonal-market towns coming into season. The scarcity
trigger sub-layer (step 4) decays faster and can be re-run monthly on the
already-qualified dominant set to refresh tier-1 promotion without re-doing the
full geographic sweep.

## Risks

- **Small-market metrics run low — by design.** This is the core thesis: do
  *not* re-apply the ≥50/≥20 absolute review floors as a gate, or the engine
  collapses to standard discovery. The floors are bypassed at step 2 on
  purpose; flag any code path that reintroduces them.
- **Static-social understates brand.** A dominant small-town operator may
  barely post. Low `follower_count` must never demote here — it's a context
  column, not a gate. Dominance + scarcity carry the qualification.
- **Thin-market false positives.** "Only premium option" can mean "only
  *anything* option" in a near-empty market with no real demand base. Gate on
  the market's affluence band (income filter in `config.SMALL_MARKETS`) and a
  minimum absolute rating/review floor *only as a sanity check* (e.g. ≥4.3 and
  ≥40 reviews) so a 12-review nothing-shop doesn't win by default.
- **Liquor-store / chain leakage.** In small towns the "wine shop" is often a
  liquor store pushing Tito's/Veuve/Yellowtail-grade SKUs. Enforce
  `config.CHAIN_KEYWORDS` + liquor-license filter + the wine commodity-SKU
  exclusion list; City Hive / Spot Hopper ESP footprints are a liquor-store red
  flag. Respected-importer signals (Skurnik, Louis/Dressner, Jenny & Francois,
  Zev Rovine, etc.) on the website are a positive curated-wine tell.
- **Wine-bar exclusion.** Wine bars are mostly excluded — but a small-town
  geographic-monopoly wine bar is exactly the claw-back case. Let
  `reclassify.py`'s wine-bar claw-back gate it; don't blanket-drop.
- **Sweets-only demotion.** A town's only bakery that is cupcake/single-product
  is still demoted to a tier-2 cap per the sweets-only rule, even with perfect
  dominance.
- **BANNED_STATES for butchers.** The butcher lane can't ship to
  HI/IN/IA/KS/NV/ND/SD. Apply the same `BANNED_STATES` filter from `butcher.py`
  to butcher rows in this lane before handoff.
- **Market-definition fragility.** Mis-drawn market boundaries (a "small town"
  that's actually a suburb of a big metro) inflate dominance. Cross-check
  against `config.CITIES` proximity and drop candidates whose market centroid
  is within commuting distance of a major metro the main pipeline already
  covers.

## Repo placement

A new top-level package mirroring the `best_wine_shops/` / awards orchestrator
shape, since the geographic frame and relative-rank logic are engine-specific:

```
local_dominance/
  __init__.py            # FIT_VERTICALS, dominance thresholds
  markets.py             # loads/validates config.SMALL_MARKETS frame
  fetch.py               # per-market Serper Maps sweep (reuses discover.py helpers, floor bypassed)
  rank.py                # relative-dominance scoring per (market, vertical)
  scarcity.py            # reuses triggers/_text_signals bank + enrich.py step-8 availability lib
  finalize.py            # reclassify + detect_clubs + DQ filter + master union
discover_local_dominance.py   # orchestrator (mirrors discover_awards.py / discover_butchers.py CLI shape)
```

Refactor targets to share, not fork:

- Lift the Serper Maps query + dedupe + chain-filter helpers out of
  `discover.py` into an importable function that accepts a **`apply_quality_floor=False`**
  flag, so `fetch.py` can reuse it without copy-pasting and `discover.py` keeps
  its default floor.
- Reuse the Engine 03 `triggers/_text_signals.py` regex bank for scarcity
  (don't duplicate the regex).
- Expose `enrich.py` step-8 availability functions (OpenTable/Resy) as an
  importable lib so the restaurant scarcity check doesn't shell out to the full
  enrich pipeline.
- New `config.SMALL_MARKETS` list (+ optional income/pop columns) is the one
  genuinely new piece of infra this engine requires.

## Open questions

1. What's the authoritative source for the small-affluent-market frame — a
   manually curated list, Census micropolitan + median-income joins, or
   harvesting resort/wine-region town names from existing partner geography?
   Frame quality directly determines false-positive rate.
2. How do we define a "market" boundary for dominance grouping — Serper Maps
   radius around the town centroid, ZIP cluster, or drive-time isochrone? A
   too-wide radius pulls in a neighboring metro and dilutes the monopoly
   signal.
3. Should `is_only_premium` require an *active* check that the named
   competitors are genuinely non-premium (liquor store vs curated wine), and is
   that worth a per-competitor `reclassify.py` pass, or is the chain/liquor
   filter on peers sufficient?
4. Do we let `dominance_score` feed the SHAP model as a relative-rank Trigger
   feature, or keep it a qualification-and-ranking overlay that never touches
   `config.SCORING_WEIGHTS` (consistent with Engines 03/08)?
