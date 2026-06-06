# Lead Engine 07 — Wine Shop Street-Cred List

**Motion:** Hybrid (Curation overlay on top of the existing wine-shop universe)
**Vertical fit:** Wine shops (curated indie / natural-wine bottle shops; explicitly NOT liquor stores)
**Suggested list name(s):** `wine_existing_club_transition`, `wine_street_cred_new_club`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run

## Premise

Generic "wine store near me" scraping returns mostly liquor-store noise — the
anti-ICP. Wine qualifies on a different axis than volume verticals: the
predictive signal isn't review count, it's **street cred** — owner/sommelier
prominence, natural-wine positioning, and stocking respected importers. Wine is
the #2 partner type by Peak AGMV ($68.2k), so a clean wine list is high-value,
but only if we filter hard on curation and exclude liquor/commodity SKUs.

Wine has two distinct buying motions, and this engine emits **two lists** to
match the two-score model. The **transition** list is High-ICP + High-Trigger:
shops that already run a club / newsletter / delivery program — proven recurring
demand, so Table22 is a platform-switch sale, not a cold start. The **new-club**
list is High-ICP + nurture-trigger: credible curators (owner-somm, natural-wine
identity, respected-importer shelf, engaged audience, email-list presence) who
*should* run a club but don't yet — the demand-over-capacity thesis says their
brand can carry one.

Both lists ride on top of infrastructure that already finds the right kind of
business (`best_wine_shops/`, `directories/wine/raisin_app`, importer stockist
mining). This engine's job is to **classify and route** that universe into the
two motions, preserving the evidence sales needs to open the conversation.

## Recipe

1. **Assemble the candidate universe (reuse, don't re-scrape).** Union the
   latest outputs of:
   - `best_wine_shops/` (`output/best_wine_shops/best_wine_shops_<YYYYMMDD>.csv`)
     — editorial "best wine shops" articles; carries `is_large_indie` /
     `is_online_only` tags.
   - `directories/wine/raisin_app` — Raisin natural-wine map (US `wine_shop`).
   - Importer stockist modules under `directories/wine/`
     (`stockist_zev_rovine`, `stockist_jenny_francois`, …) via `_stockists.py`.
   - Optional top-up: `discover.py` Serper Maps with a curated query set
     (below) over `config.CITIES`, niche quality floors (≥20 reviews / ≥4.0),
     website required, `config.CHAIN_KEYWORDS` applied.
   Dedupe with `dedupe_existing.py` (phone-first, then name+address).

2. **Hard-filter liquor / commodity leakage** before anything else. Run
   `reclassify.py` and keep `partner_type == wine`; honor its **wine-bar
   claw-back** (wine bars excluded except geographic-monopoly). Then drop any
   candidate whose website or Google name trips the liquor/commodity filter:

   ```
   LIQUOR_DQ_NAME   = ["liquor", "wine & spirits", "discount", "warehouse",
                       "package store", "bevmo", "total wine", "abc"]
   COMMODITY_SKUS   = ["tito's","smirnoff","veuve","buzzballz","michelob",
                       "budweiser","josh","cupcake","barefoot","kendall jackson",
                       "meiomi","duckhorn","bogle","j. lohr","yellowtail",
                       "apothic","andre","cloud break"]
   LIQUOR_ESP_FLAGS = ["cityhive","spothopper"]   # site footer / cart platform
   # DQ if name hits LIQUOR_DQ_NAME, OR site lists ≥3 COMMODITY_SKUS and
   # ZERO street-cred signals, OR ESP == City Hive / Spot Hopper.
   ```

3. **Crawl each candidate site for street-cred + club signals** (reuse the
   `enrich.py` step-1 `websites` concurrent crawler, 10 threads — extend its
   keyword set rather than fork it). Capture raw matched snippets for evidence:

   ```
   STREETCRED = ["natural wine","low intervention","low-intervention",
                 "biodynamic","organic","small grower","grower champagne",
                 "pét-nat","skin contact","orange wine","minimal intervention"]
   IMPORTERS  = ["skurnik","louis/dressner","dressner","jenny & francois",
                 "selection massale","zev rovine","rosenthal","polaner",
                 "vom boden","t. edward","jose pastor"]
   OWNER_SOMM = ["sommelier","master sommelier","wset","court of master",
                 "former wine director","our buyer","owner & somm"]
   ```

4. **Detect existing club / recurring program** — run `detect_clubs.py`
   (50-thread site scrape; `has_club`, `club_type`, `club_url`,
   `club_signals`). Wine-specific club lexicon to add: `wine club`,
   `bottle club`, `monthly allocation`, `wine subscription`, `case club`,
   `membership`, `allocation list`. Email-signup presence already comes from
   the `websites` step (`email_signup` flag) — keep it as the new-club proxy.

5. **Audience-engagement pass (light).** For candidates passing ICP, run the
   `instagram` enrich step (Apify `instagram-profile-scraper`, batches of 30)
   and the `reels` step (`instagram-reel-scraper`) to capture `avg_video_views`
   / `avg_shares` — the decisive engagement signals (video views > shares >
   comments > likes; follower *count* is weaker). Static-only social
   **understates** brand for indie wine — do not DQ on low IG; weight relative
   local prominence and importer-shelf depth instead.

6. **Route into two lists.**

   ```
   icp_ok = passes step-2 liquor/commodity filter AND
            (streetcred_hits ≥ 1 OR importer_hits ≥ 1 OR owner_somm_hit)
   if not icp_ok:                         -> drop (or park as low-ICP)
   if has_club:                           -> wine_existing_club_transition  (Trigger=hot)
   elif email_signup OR avg_video_views high OR importer_hits ≥ 2:
                                          -> wine_street_cred_new_club      (Trigger=nurture)
   else:                                  -> wine_street_cred_new_club      (Tier 2, weak trigger)
   ```

7. **Score** with `score.py` / `config.SCORING_WEIGHTS` (SHAP-aligned — do not
   retune). Partner Type = wine dominates; reservation difficulty is N/A for
   retail, so the wine signal stack (importer depth, engagement, prominence)
   carries Trigger. Emit standard `_all` + `_top` (A+B tier) CSVs.

## Output schema

```
output/directories/wine_street_cred_<YYYYMMDD>.csv      # union of both lists, list_name col splits them
source = "wine_existing_club_transition" | "wine_street_cred_new_club"
tier = 1 (importer-shelf or club-confirmed) | 2 (single-signal / weak-trigger)
business_type = "wine_store"
distinction = "<e.g. 'Stocks Skurnik + Zev Rovine; runs monthly wine club'>"
year = <discovery_year>
+ evidence cols:
    list_name              (transition | new_club)
    streetcred_signals     ["natural wine","biodynamic",...]
    importer_signals       ["skurnik","dressner",...]    # respected-importer shelf
    owner_somm_signal      bool / matched snippet
    has_club, club_type, club_url, club_signals   (from detect_clubs.py)
    email_signup           bool   (new-club readiness proxy)
    avg_video_views, avg_shares, ig_handle, follower_count
    is_large_indie, is_online_only   (carried from best_wine_shops/)
    liquor_dq_reason       (empty if kept; populated rows excluded but logged)
    candidate_sources      ["best_wine_shops","raisin_app","stockist_zev_rovine"]
```

Final scored handoff follows the standard convention:
`custom-serper-scoring_<owner>_<YYYYMMDD>_wine_<count>_<all|top>.csv`.

## Volume & cost

- Candidate universe (union, post-dedupe): ~1,500-2,500 curated US wine shops
  (best_wine_shops ~600 + Raisin US ~700 + importer stockists ~600, heavy
  overlap → ~2K unique).
- After liquor/commodity hard filter (step 2): ~70-80% survive → ~1.5K ICP-clean.
- Split estimate: ~15-20% have a detectable club → **~250 transition leads**;
  remainder → **~1,200 new-club leads**.
- Cost: site crawl (steps 3-4) free (httpx threads). Apify IG profile ~$0.01/profile
  × ~1.5K ≈ $15; reels scrape on the ICP-clean subset (~1K) ≈ $8. Serper Maps
  top-up + geocode ≈ $2. LLM not required (regex/keyword classification).
  **Per-run total: ~$25-30.**
- **Net-new per run (first run): ~1,450 unique;** subsequent quarterly runs
  ~5-10% incremental.

## Refresh cadence

Quarterly for the full re-crawl (the curated wine universe is small and slow-
moving). Run the `detect_clubs.py` + email-signup pass **monthly** on the
existing ICP-clean set — club launches are the trigger event that flips a
new-club lead into a transition lead, and that's the moment to contact.

## Risks

- **Liquor-store leakage is the dominant failure mode.** Step-2 filter must run
  before scoring; a single-keyword name match isn't enough — gate on
  commodity-SKU density + absence of street-cred. Audit a 30-row QA sample
  (`sample_clubs_for_qa.py`) each run.
- **Wine-bar contamination.** Raisin and importer lists include bars. Lean on
  `reclassify.py` wine-bar claw-back; keep only geographic-monopoly bars.
- **Static social understates indie wine brand.** Low IG ≠ low ICP. Never DQ on
  follower/engagement alone; importer-shelf depth and local prominence outrank it.
- **Small-market metrics run low.** A great shop in a small metro will look thin
  on raw counts — weight relative local dominance / regional best-of mentions.
- **Importer-shelf signal is site-text-dependent.** Shops that stock Dressner but
  don't name it online get under-scored. Stockist backlink mining
  (`directories/wine/` modules) is the more reliable path — prioritize matches
  that come from the importer's own "find our wines" page over site-keyword hits.
- **Existing club is a POSITIVE signal**, not a disqualifier — route to
  transition, never drop.
- **Apify IG fragility / rate limits** — batch IG in 30s as the existing steps do;
  IG enrichment is optional and should not block list emission if it fails.

## Repo placement

Mostly orchestration over existing lanes; one new orchestrator + one shared
classifier. No new top-level package needed.

```
directories/
  wine/
    street_cred_router.py        # NEW: unions candidate sources, runs step-2
                                 #      liquor filter + step-3/4 classification,
                                 #      splits into the two list_names
scripts/
  discover_wine_street_cred.py   # NEW orchestrator: pulls latest best_wine_shops
                                 #   + raisin + stockist CSVs, calls router,
                                 #   runs detect_clubs + optional IG enrich,
                                 #   writes output/directories/wine_street_cred_<date>.csv
enrich.py                        # REFACTOR: expose the step-1 `websites`
                                 #   keyword-crawl as an importable fn so the
                                 #   router can reuse it with the wine keyword set
                                 #   (today it's wired into the sequential pipeline)
config.py                        # ADD: WINE_STREETCRED_KEYWORDS, WINE_IMPORTER_LIST,
                                 #   WINE_COMMODITY_SKUS, WINE_CLUB_LEXICON knobs
```

`detect_clubs.py`, `reclassify.py`, `dedupe_existing.py`, `sample_clubs_for_qa.py`
are reused unchanged (CSV-in/CSV-out).

## Open questions

1. Is the importer-shelf signal better sourced from **shop websites** (broad but
   noisy) or strictly from **importer stockist pages** (clean but only covers the
   ~10 importers we mine)? Pick the authoritative path before scoring weights it.
2. Should `is_online_only` curated wine shops (no physical retail) flow into this
   list or a separate B2C lane? Scoring assumes physical presence.
3. What's the minimum reliable signal for "owner is a known somm" without an LLP
   pass — site bio keywords, or do we need a Serper Web press check
   (`enrich.py` step 4) against wine media (PUNCH, SevenFifty Daily, Wine
   Enthusiast)?
4. For the transition list, can we observe the *current* club platform (Commerce7,
   WineDirect, Shopify) from site footprint? That would make the switch-pitch
   sharper and is worth a dedicated detector if observable.
