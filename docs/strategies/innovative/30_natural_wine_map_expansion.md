# Lead Engine 30 — Natural Wine Map Expansion

**Motion:** Curation (community-signal harvest with a hard retail filter)
**Vertical fit:** Wine shops (curated indie / natural-wine bottle shops; explicitly NOT liquor stores or wine bars)
**Suggested list name(s):** `natural_wine_map_expansion`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run

## Premise

Natural-wine communities are a high-purity ICP filter. A shop that lives on the
Raisin map, gets reviewed by natural-wine accounts, or hosts low-intervention
tastings has already been curated *for* us by a community whose taste maps
almost exactly onto Table22's wine ICP. That community membership is itself the
ICP-Fit signal — natural wine self-selects against the commodity/liquor anti-ICP
that pollutes generic "wine store" Serper scraping. Wine is the #2 partner type
by Peak AGMV ($68.2k), so a clean, curated wine list is high value per row.

Engine 07 already classifies the *known* wine universe (best_wine_shops + Raisin
wine_shop + importer stockists) into transition vs new-club. This engine is
different: it goes **wider into the Raisin surface itself** — venues tagged
bar/restaurant/event, community likes, and event listings — to surface curated
retailers that Engine 07's `wine_shop`-only filter (`raisin_app._is_wine_shop_lead`)
discards today. The catch: that wider net drags in wine bars and restaurants,
which are mostly anti-ICP. So the engine's core job is a **hard retail-behavior
filter**: keep an entity only if it sells bottles to-go (a bottle shop, a
shop+bar hybrid with a real retail counter, or a geographic-monopoly bar where
no dedicated bottle shop exists). Community signal supplies ICP-Fit; the retail
gate supplies the disqualification; the trigger comes from club/email/event
cadence on the survivors.

## Recipe

1. **Pull the full Raisin venue set (reuse + extend `raisin_app`).** The
   `directories/wine/raisin_app.py` module already POSTs the no-auth
   `proxy-map-venues/` endpoint and returns ~12k global venues with `is:[...]`
   type tags. Extend it (or add a sibling fetcher) to keep **all** US venues
   whose types include any of `wine_shop`, `bar`, `restaurant` — not just
   `wine_shop` — preserving the raw `is[]` tags, `likevote_number`, and `id`
   for the downstream gate. Keep the existing US bbox logic (`US_BBOXES`) and
   `_is_us` unchanged. Also pull Raisin **event** listings for the same venues
   where exposed (tasting cadence = a trigger signal).

2. **Resolve address + Google identity.** Raisin's map API returns no address
   (only lat/lng in `blurb`). Resolve each kept venue to a Google Maps record
   via a Serper Maps lookup (name + lat/lng → `discover.py` helper), backfilling
   `city`, `state`, website, phone, Google `type`, review count/rating. Drop
   anything Serper can't resolve to a US business with a website.

3. **Hard retail-behavior gate (the load-bearing step).** This is where the
   wider net pays for itself or leaks. Keep a venue only if it passes:

   ```
   is_retail = (
       "wine_shop" in raisin_types                      # Raisin says shop
       OR google_type in {"wine_store","liquor_store"}  # Maps says retailer
       OR site_signals_retail                           # see RETAIL_SITE below
   )
   RETAIL_SITE = ["shop","bottle","buy wine","add to cart","online store",
                  "/collections/","/products/","case","6-pack","mixed case",
                  "to-go","bottles to go","retail"]
   # Bar/restaurant-only with NO retail site signal -> drop (anti-ICP),
   # UNLESS geographic-monopoly exception (step 4).
   ```

   Then run `reclassify.py` and require `partner_type == wine`; honor its
   **wine-bar claw-back** so pure wine bars fall out. A shop+bar hybrid with a
   real retail counter survives; a bar that merely sells the occasional bottle
   does not.

4. **Geographic-monopoly exception for bars.** A natural-wine bar in a metro
   with *no* dedicated curated bottle shop is a legitimate lead (it's the only
   curated wine commerce in town). Flag `is_geo_monopoly = True` when a
   bar/restaurant survivor sits in a city where step-1/3 produced zero pure
   bottle shops. Cross-check against `research/trendy_neighborhoods/` — a
   monopoly in a trendy nbhd is the strongest version of this. Cap geo-monopoly
   bars at Tier 2.

5. **Liquor / commodity leakage filter** (same gate as Engine 07 — reuse, don't
   re-derive). The retail gate in step 3 deliberately admits Google
   `liquor_store` types, so this pass is mandatory:

   ```
   LIQUOR_DQ_NAME  = ["liquor","wine & spirits","discount","warehouse",
                      "package store","bevmo","total wine","abc"]
   COMMODITY_SKUS  = ["tito's","smirnoff","veuve","buzzballz","michelob",
                      "budweiser","josh","cupcake","barefoot","kendall jackson",
                      "meiomi","duckhorn","bogle","j. lohr","yellowtail",
                      "apothic","andre","cloud break"]
   LIQUOR_ESP      = ["cityhive","spothopper"]   # liquor-store cart/site platforms
   # DQ if name hits LIQUOR_DQ_NAME, OR site lists >=3 COMMODITY_SKUS and
   # ZERO natural-wine signals, OR ESP == City Hive / Spot Hopper.
   ```

   Raisin membership is a strong counter-signal: a venue that is on the Raisin
   map AND trips a single commodity SKU is almost certainly a real natural shop
   that also stocks one mainstream bottle — don't DQ on Raisin-listed venues for
   SKU density alone; require name-match or ESP-match for those.

6. **Street-cred + club + email enrich (reuse `enrich.py` step 1).** Run the
   step-1 `websites` concurrent crawler (10 threads) over survivors for the
   natural-wine / importer lexicon and the `email_signup` + ecommerce flags:

   ```
   NATWINE   = ["natural wine","low intervention","low-intervention","biodynamic",
                "organic","pét-nat","skin contact","orange wine","glou","zero-zero",
                "no added sulfites","small grower","grower champagne"]
   IMPORTERS = ["skurnik","louis/dressner","dressner","jenny & francois",
                "selection massale","zev rovine","rosenthal","polaner","vom boden",
                "t. edward","jose pastor"]
   ```

   Then `detect_clubs.py` (50-thread scrape; `has_club`, `club_type`,
   `club_url`, `club_signals`) with the wine club lexicon (`wine club`,
   `bottle club`, `monthly allocation`, `wine subscription`, `case club`,
   `allocation list`).

7. **Light engagement pass (optional, don't block).** For ICP-clean survivors,
   run `instagram` (Apify `instagram-profile-scraper`, batches of 30) + `reels`
   (`instagram-reel-scraper`) for `avg_video_views` / `avg_shares` — the decisive
   engagement signals. Static social **understates** indie-wine brand; never DQ
   on low IG.

8. **Trigger routing & score.**

   ```
   if has_club:                      trigger = "hot"    # platform-switch sale
   elif raisin_event_cadence OR email_signup OR importer_hits >= 2:
                                     trigger = "warm"   # demand, no club yet
   else:                             trigger = "nurture"
   tier = 1 if (importer_hits >= 1 OR has_club) and not is_geo_monopoly else 2
   ```

   Score with `score.py` / `config.SCORING_WEIGHTS` (SHAP-aligned — do not
   retune). Reservation difficulty is N/A for retail; the wine signal stack
   (Raisin membership, importer depth, engagement, event cadence) carries
   Trigger. Emit `_all` + `_top` (A+B tier).

## Output schema

```
output/directories/natural_wine_map_expansion_<YYYYMMDD>.csv
source = "natural_wine_map_expansion"
tier = 1 (curated bottle shop, importer-shelf or club-confirmed) | 2 (geo-monopoly bar / single-signal)
business_type = "wine_store"
distinction = "<e.g. 'Raisin natural wine shop; stocks Zev Rovine + Dressner; runs case club'>"
year = <discovery_year>
+ evidence cols:
    raisin_id, raisin_types        ["wine_shop","bar"]   # raw is[] tags
    raisin_likes                   (likevote_number)
    raisin_event_cadence           # # of natural-wine events listed, if exposed
    retail_gate_reason             # which RETAIL_SITE / type rule passed
    is_geo_monopoly                bool
    natwine_signals                ["natural wine","pét-nat",...]
    importer_signals               ["skurnik","dressner",...]
    has_club, club_type, club_url, club_signals   (detect_clubs.py)
    email_signup, has_ecommerce    bool
    avg_video_views, avg_shares, ig_handle, follower_count
    trigger                        hot | warm | nurture
    liquor_dq_reason               # empty if kept; excluded rows logged separately
    google_type, review_count, rating
```

Final scored handoff:
`custom-serper-scoring_<owner>_<YYYYMMDD>_wine_<count>_<all|top>.csv`.

## Volume & cost

- Raisin US venues across all kept types (`wine_shop` + `bar` + `restaurant`):
  ~2,000-2,800 (vs ~700 for `wine_shop`-only today).
- Step-3 retail gate keeps an estimated ~40-50% → ~1,000-1,300 retail-behavior
  candidates.
- Step-5 liquor/commodity filter drops ~5-10% (Raisin membership keeps leakage
  low) → ~950-1,200 ICP-clean.
- **Net-new vs Engine 07**: dedupe against the existing wine universe
  (`dedupe_existing.py`, phone-first then name+address); the incremental win is
  the bar/restaurant survivors + shop+bar hybrids Engine 07 never saw —
  estimated **~250-400 net-new curated retail leads** on first run.
- Cost: Raisin fetch free; Serper Maps resolution (step 2) ~1,200 lookups ≈ $3;
  site crawl + detect_clubs free (httpx threads); Apify IG profile ~$0.01 ×
  ~1,000 ≈ $10; reels on the clean subset ≈ $8. No LLM required.
  **Per-run total: ~$20-25.**

## Refresh cadence

Quarterly for the full Raisin re-fetch + retail gate — the natural-wine map
grows steadily but slowly, and new venues take time to build a retail footprint.
Run the `detect_clubs.py` + email-signup + Raisin-event pass **monthly** on the
ICP-clean set: a club launch or a newly recurring tasting series is the trigger
event that flips a nurture lead to warm/hot, and that's the moment to contact.

## Risks

- **Wine-bar leakage is the dominant failure mode.** Widening to `bar`/`restaurant`
  types is the whole point, but most are anti-ICP. The step-3 retail gate +
  `reclassify.py` wine-bar claw-back must both fire; QA a 30-row sample
  (`sample_clubs_for_qa.py`) every run, focused on bar-tagged survivors.
- **Geo-monopoly is a judgement call that over-fires.** "No bottle shop in town"
  is sensitive to how completely step 1 enumerated the metro. A missed shop
  promotes a bar that shouldn't qualify — cap geo-monopoly at Tier 2 and review
  manually.
- **Liquor/commodity leakage via the `liquor_store` Google type** admitted in
  step 3. Step-5 filter is mandatory and runs before scoring; but don't let it
  over-DQ Raisin-listed shops that stock one mainstream SKU.
- **Raisin API fragility.** Single no-auth POST endpoint, no SLA — if
  `proxy-map-venues/` changes shape or rate-limits, the whole engine stalls.
  Cache the raw payload per run; degrade to the existing `wine_shop`-only path.
- **Address resolution noise.** Raisin gives only lat/lng; Serper Maps
  name+coordinate matching can grab the wrong nearby business. Verify the
  resolved name fuzzy-matches the Raisin name before keeping.
- **Static social understates indie-wine brand** and **small-market metrics run
  low** — weight relative local dominance and importer-shelf depth over raw
  social/review counts; never DQ a clean shop on thin IG.
- **Existing club is a POSITIVE signal** — route to `trigger=hot`, never drop.

## Repo placement

Mostly orchestration over existing lanes; extend one module, add one
orchestrator, share one keyword block. No new top-level package.

```
directories/
  wine/
    raisin_app.py                  # EXTEND: optional all_types=True path that
                                   #   keeps wine_shop+bar+restaurant and preserves
                                   #   raw is[] tags + likevote_number + id; keep
                                   #   the wine_shop-only default for Engine 07
    natural_wine_retail_gate.py    # NEW: step-3 retail-behavior gate + step-4
                                   #   geo-monopoly flag; CSV-in/CSV-out
scripts/
  discover_natural_wine_map.py     # NEW orchestrator: raisin(all_types) -> Serper
                                   #   Maps resolve -> retail gate -> reclassify ->
                                   #   liquor filter -> websites/clubs enrich ->
                                   #   optional IG -> trigger route -> write
                                   #   output/directories/natural_wine_map_expansion_<date>.csv
enrich.py                          # REFACTOR (shared w/ Engine 07): expose the
                                   #   step-1 `websites` keyword-crawl as an
                                   #   importable fn so the orchestrator can run it
                                   #   with the NATWINE/IMPORTERS keyword set
config.py                          # ADD: WINE_NATWINE_KEYWORDS, WINE_IMPORTER_LIST
                                   #   (share with Engine 07), RAISIN_RETAIL_SITE_SIGNALS
```

`reclassify.py`, `detect_clubs.py`, `dedupe_existing.py`, `sample_clubs_for_qa.py`
are reused unchanged (CSV-in/CSV-out).

## Open questions

1. Does the Raisin map API expose **event listings / tasting cadence** per
   venue, or only venue records? Event cadence is a strong trigger signal — if
   it needs a separate endpoint or scrape, scope that before depending on it.
2. What's the cleanest definition of "retail counter" for a shop+bar hybrid —
   site ecommerce presence, a Google `type` of `wine_store`, or both? This
   single rule decides most of the net-new volume.
3. Should geo-monopoly bars flow into this list at all, or into a separate
   review queue? They're real but rare and high-judgement — a dedicated
   low-volume lane might keep this list cleaner.
4. How much does this overlap Engine 07 after dedupe? If net-new is <250, fold
   the all-types Raisin path into Engine 07 instead of standing up a separate
   orchestrator.
```
