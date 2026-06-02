# Lead Engine 22 — Seasonal Preorder Calendar

**Motion:** Curation (a scheduling/orchestration overlay on top of existing Curation + Hybrid engines)
**Vertical fit:** Bakeries (Thanksgiving pies, holiday cookies, king cakes, panettone), butchers (holiday roasts, turkeys, grilling boxes), wine (holiday cases, Thanksgiving pairings, summer rosé), cheese (holiday boards, gifting bundles)
**Suggested list name(s):** `seasonal_preorder_calendar`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (per scheduled wave; the calendar itself is free — cost is the scoped re-runs it triggers)

## Premise

Independent food businesses make a disproportionate share of their margin in a
handful of **predictable, calendar-locked commerce windows**: bakeries at
Thanksgiving (pies), December (cookie boxes, panettone) and Mardi Gras (king
cakes); butchers at Thanksgiving (turkeys), Christmas/Easter (roasts, hams) and
summer (grilling boxes); wine shops at the holidays (cases, gifting) and early
summer (rosé club); cheese shops at the holidays (boards, party boxes, gifting).
Every one of these is a recurring spike the operator already plans for — which
makes it the single most legible **Trigger** in the two-score model. The outbound
line writes itself and is *time-true*: "your holiday preorder window is about to
open — Table22 runs it for you."

The catch is timing. The seasonal trigger only converts if outbound lands
**60–90 days before the seasonal pain**, while the operator is planning the
window and before they've committed to last year's manual Google Form. A list
that surfaces "great Thanksgiving butcher" on November 20th is worthless; the
same list on September 15th is the highest-intent outbound we can send. So this
engine is not a new discovery primitive — it is a **calendar that schedules the
existing trigger engines** (02 manual preorder, 12 events/programming, 03
sold-out, and the niche lanes) to fire on a per-vertical, per-season cron so the
right vertical surfaces at the right lead time.

In the two-score model the calendar contributes **Trigger timing**, not ICP fit —
ICP is still decided downstream by `reclassify.py` and the per-engine gates. It
biases toward the high-AGMV verticals where seasonal commerce is largest and
margin-dense: butcher ($75.9k Peak AGMV), wine ($68.2k), cheese ($63.8k), with
bakery ($34.7k) included because its seasonal windows are unusually sharp even if
its base AGMV is lower.

## Recipe

The calendar is a thin orchestrator + a seasonal-signal vocabulary. It does **not**
re-implement crawling, IG mining, or scoring — it parameterizes the engines that
already do those things, scopes them to one vertical + one season, and tightens
the trigger regex to the seasonal SKU set.

1. **Define the season table (`config.py` knob).** Add a `SEASONAL_WINDOWS`
   structure: each row is `(season_key, vertical, sale_window_start,
   sale_window_end, outreach_lead_days, seasonal_phrases, seasonal_skus)`. The
   calendar computes `fire_date = sale_window_start − outreach_lead_days` and emits
   a wave whenever `today` is within ±7 days of a `fire_date`.

   ```
   SEASONAL_WINDOWS = [
     # season_key            vertical   sale_window     lead_days
     ("thanksgiving_pie",    "bakery",  (11,15,11,26),  75),
     ("holiday_cookies",     "bakery",  (12,1,12,24),   75),
     ("panettone",           "bakery",  (12,1,12,24),   75),
     ("king_cake",           "bakery",  (1,6,2,17),     60),   # Epiphany→Mardi Gras
     ("thanksgiving_turkey", "butcher", (11,10,11,26),  90),
     ("holiday_roast",       "butcher", (12,15,12,31),  90),
     ("easter_ham",          "butcher", (3,20,4,20),    75),
     ("grilling_box",        "butcher", (5,15,7,4),     60),
     ("holiday_case",        "wine",    (11,25,12,31),  75),
     ("thanksgiving_pairing","wine",    (11,10,11,26),  75),
     ("summer_rose_club",    "wine",    (5,1,6,21),     75),
     ("holiday_board",       "cheese",  (11,25,12,31),  75),
     ("cheese_gift_box",     "cheese",  (12,1,12,24),   75),
   ]
   ```

   Seasonal phrase/SKU banks per `season_key` (these tighten the downstream
   trigger regex — they do not loosen it):

   ```
   SEASONAL_PHRASES = {
     "thanksgiving_pie":    ["thanksgiving pie", "pie preorder", "pre-order your pie",
                              "holiday pie order", "pumpkin pie order"],
     "holiday_cookies":     ["holiday cookie box", "cookie tin", "christmas cookies",
                              "cookie preorder", "holiday gift box"],
     "panettone":           ["panettone", "pre-order panettone", "limited panettone"],
     "king_cake":           ["king cake", "king cake preorder", "mardi gras"],
     "thanksgiving_turkey": ["heritage turkey", "thanksgiving turkey", "reserve your turkey",
                              "turkey preorder", "fresh turkey order"],
     "holiday_roast":       ["holiday roast", "prime rib", "standing rib roast",
                              "crown roast", "reserve your roast", "beef tenderloin"],
     "easter_ham":          ["easter ham", "bone-in ham", "spiral ham preorder", "lamb leg"],
     "grilling_box":        ["grilling box", "bbq box", "memorial day box",
                              "july 4th box", "cookout box"],
     "holiday_case":        ["holiday case", "gift case", "mixed case", "case discount",
                              "holiday wine gift"],
     "thanksgiving_pairing":["thanksgiving pairing", "thanksgiving wine", "turkey pairing"],
     "summer_rose_club":    ["rosé club", "rose club", "summer rosé", "rosé all day"],
     "holiday_board":       ["holiday cheese board", "party box", "cheese platter order",
                              "holiday board preorder"],
     "cheese_gift_box":     ["cheese gift box", "cheese gift bundle", "holiday cheese gift"],
   }
   ```

2. **Determine the active wave(s).** The orchestrator (`discover_seasonal.py`)
   reads `SEASONAL_WINDOWS`, computes each `fire_date`, and selects every season
   whose fire window overlaps `today` (override with `--season <key>` /
   `--vertical <v>` for manual runs and backfill). Each active season produces one
   scoped wave.

3. **Seed the wave universe (no fresh cold sweep by default).** For the wave's
   vertical, feed the existing enriched corpus (`output/2_enriched_*.csv`) plus the
   relevant niche lane (`butcher/`, `best_wine_shops/`, `directories/`, awards
   master) filtered to that `business_type`. For net-new seasonal geography, the
   wave may seed a *scoped* Serper Maps pass (`discover.py` /
   `scripts/fresh_icp_search.py`) for that one vertical, biased to
   `research/trendy_neighborhoods/` (~56.5% of partners sit in trendy
   neighborhoods). One vertical per wave keeps Serper + Apify spend bounded.

4. **Run the downstream trigger engines, parameterized to the season.** The
   calendar does not detect anything itself — it invokes the existing engines with
   the season's phrase/SKU banks injected into their regex:
   - **Engine 02 (`manual_preorder`)** — the primary detector. Its step-1 crawl
     parse layer scans homepage + `/preorder`, `/holiday`, `/order`, `/shop` paths;
     the calendar overrides its `ORDER_PHRASE_REGEX` with this season's
     `SEASONAL_PHRASES` (turkey/pie/roast/case/board) so a hit is unambiguously the
     *seasonal* SKU, not a year-round form.
   - **Engine 12 (`events_programming`)** — catches "holiday preorder window open"
     and seasonal pairing dinners / boards as live programming.
   - **Engine 03 (`sold_out_demand`)** where it exists — last-season sell-out is
     strong corroboration ("sold out of turkeys by Nov 1 last year").
   - IG corroboration reuses the **Apify instagram-post-scraper** (enrich step 7)
     over recent captions and the **profile-scraper** (step 2, batches of 30) for
     link-in-bio resolution — exactly the hooks Engines 02/12 already wrap. No new
     Apify actor.

5. **Classify + write the seasonal trigger (Claude, cheap pass).** For matched
   snippets, reuse the Engine 02/12 `classify.py` (Claude `claude-haiku-4-5`, the
   model `scrape_beli` uses) to confirm `season_key`, extract `window_status ∈
   {announced, open, sold_out, closed, prior_year_only}`, parse a
   `preorder_open_date` where listed, and emit a one-line `trigger_summary`. Prefix
   the script with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

6. **ICP gate + seasonal timing score.** Run `reclassify.py` (`partner_type` /
   `business_type_v2`) and `detect_clubs.py` (existing seasonal club = positive
   switch-the-platform signal, carry `has_club` through). Reject anti-ICP, then
   score on seasonal timing:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  or  wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, Josh, Meiomi, ...) or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}      # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery (a holiday-cookie-only shop is a real seasonal hit but caps Tier 2)
     static-social-only / thin metrics in a small market (understates brand — never DQ)

   season_strength:
     +3 seasonal preorder window OPEN now (live, citable trigger)
     +2 window ANNOUNCED / scheduled but not yet open  (perfect 60-90d lead)
     +2 prior-year sold-out evidence for this season    (proven scarcity)
     +1 prior_year_only listing (capability proof, weaker now-trigger)
     +1 if has_club == True (already monetizing the seasonal spike)
     +1 if today within [fire_date, sale_window_start]  (in the outreach sweet spot)

   QUALIFY if: passes ICP gate AND season_strength >= 2 AND business_type == wave vertical
   ```

7. **Hand off to scoring.** Emit the per-season canonical CSV (below) and run
   `score.py` unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned).
   `season_strength` orders the outbound queue inside a tier so sales works the
   open/announced windows first.

## Output schema

```
output/seasonal/seasonal_preorder_calendar_<season_key>_<YYYYMMDD>.csv
source = "seasonal_preorder_calendar"
tier = <1|2|3>   # 1 = butcher/wine/cheese + open-or-announced window; 2 = bakery or prior-year-only; 3 = ICP-soft
business_type = bakery | butcher | wine_store | cheese
distinction = "Seasonal preorder: {season_key} — reach out {lead_days}d before the window"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    season_key             # thanksgiving_turkey | holiday_case | king_cake | summer_rose_club | ...
    window_status          # announced | open | sold_out | closed | prior_year_only
    preorder_open_date     # parsed date the window opens, if listed
    sale_window_start      # from SEASONAL_WINDOWS (this season's calendar anchor)
    fire_date              # computed outreach date (sale_window_start - lead_days)
    season_strength        # int, intra-tier outbound ordering
    seasonal_evidence_url  # site /preorder page or IG/link-in-bio destination
    seasonal_evidence_snippet  # verbatim text that matched the seasonal phrase
    found_on               # website | link_in_bio | instagram | both
    trigger_summary        # one-line Claude-written, season-true outbound hook
    has_club, club_type    # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

## Volume & cost

- The calendar fires **per wave** (one vertical + one season), not against the
  whole corpus at once — this is the cost-control mechanism.
- Per-vertical slice of the enriched corpus + niche lane, deduped: butcher ≈1–1.2K
  (small universe), bakery ≈2.5K, wine ≈3K, cheese ≈1.5K.
- Step-1 crawl extension: free (rides the existing 10-thread crawl; the calendar
  only narrows the regex — no new fetch budget).
- IG corroboration via Apify post-scraper, only for rows with a handle and no
  website-side seasonal match (~35%): on a ~3K wave ≈1K profiles at
  $0.002–0.003/profile in batches of 30 ≈ **$6–10**.
- Link-in-bio resolution (profile scraper) on the high-priority subset (~600):
  **≈ $2–3**.
- Optional scoped Serper Maps top-up for net-new seasonal geography (one vertical,
  trendy-neighborhood biased): **≈ $3–5**.
- Claude Haiku classify pass on matched snippets (~1.5K short prompts): **≈ $2–4**.
- **Per-wave total: ~$13–22.**
- **Net-new qualified leads per wave:** of a ~3K vertical slice, a *seasonal*
  trigger hits **~10–15%** (≈300–450); after the ICP gate + `season_strength >= 2`,
  expect **~120–250 qualified rows per wave**. Across the ~13 seasonal waves/year
  this is ~1.5–3K timed-trigger rows — most already in our corpus, the value being
  the *timing*, which re-prioritizes them for outbound in the conversion window.

## Refresh cadence

**Event-driven, not periodic — the engine is the cadence.** Each `season_key`
fires once when `today` enters `[fire_date − 7, fire_date + 7]`, i.e. 60–90 days
before its `sale_window_start`. In practice that clusters into a heavy late-summer
/ early-fall block (turkey, pie, holiday case, holiday board, cookies, panettone,
roast all fire Aug–Oct), a late-winter block (king cake, then easter ham), and a
spring block (grilling box, summer rosé). Run the orchestrator weekly on cron so it
catches each window the moment it opens; most weeks no wave fires and it no-ops.
Re-fire a season only if a new geography seed is added — seasonal commerce is
sticky year-over-year, so a butcher that ran turkey preorders last year is a
near-certain target this year (that's the `prior_year` corroboration).

## Risks

- **Wrong lead time burns the trigger.** Fire too late and the operator has
  already stood up last year's manual flow; too early and "your holiday window"
  reads as noise. `lead_days` is the load-bearing parameter per season — validate
  against real partner-onboarding lead times, don't guess uniformly.
- **Prior-year-only staleness reads as live.** A 2024 `/thanksgiving` page proves
  the *pattern* but not that *this* year's window is open. Record `window_status`
  and fetch-time; `prior_year_only` is `season_strength +1`, not a live trigger.
  Don't quote "your preorder is open" off a stale page.
- **Liquor-store / commodity-wine leakage on "holiday case."** "Holiday case" and
  "gift case" match liquor stores moving Veuve and Tito's. Keep the commodity-SKU
  and ESP-red-flag (City Hive, Spot Hopper) checks plus the `reclassify.py`
  wine-bar claw-back *upstream* of `season_strength`.
- **Sweets-only demotion.** A holiday-cookie-box-only or king-cake-only bakery is a
  sharp seasonal hit but single-product — cap at Tier 2, never promote on the
  seasonal trigger alone.
- **Caterer leakage on seasonal boxes.** A business whose only seasonal product is a
  catered "holiday party box" with no retail core is a caterer (anti-ICP). Require a
  resolved retail `partner_type` from `reclassify.py`.
- **Small-market metrics run low.** A dominant rural butcher selling out of turkeys
  every November will have thin social/review volume. Weight relative local
  dominance + prior-year scarcity over raw follower/review floors; **never DQ on
  static-only social** — it understates seasonal brand.
- **Chain leakage.** Multi-location bakeries/butchers run the loudest holiday
  preorders. Keep `config.CHAIN_KEYWORDS` + the `reclassify.py` coarse pass upstream
  so high-AGMV partner-type weight doesn't inflate chain scores.
- **Apify / page fragility under burst.** Waves cluster in fall, concentrating Apify
  load. Batch at 30, back off, fall back to website-only matches when IG resolution
  fails (don't block the row), and stagger the fall waves across separate cron days.

## Repo placement

A thin orchestrator package that **schedules and parameterizes** the existing
trigger engines rather than re-implementing detection. It depends on Engines 02
and 12 landing first (or their shared `enrich_websites_lib` crawler refactor).

```
seasonal/
  __init__.py                  # engine constants; registers SEASONAL_WINDOWS view
  calendar.py                  # season table logic: fire_date calc, active-wave selection, --season/--vertical overrides
  signals.py                   # SEASONAL_PHRASES, SEASONAL_SKUS per season_key (tightens downstream regex)
  run_wave.py                  # invokes Engine 02/12 detectors with season phrase banks injected; scoped to one vertical
  classify.py                  # reuses haiku-4-5 classify: season_key + window_status + preorder_open_date + trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), season_strength, dedupe
  finalize.py                  # per-season canonical schema writer, date-stamped output
discover_seasonal.py           # orchestrator: read calendar -> pick wave(s) -> seed -> run detectors -> classify -> gate -> finalize
```

Config: add `SEASONAL_WINDOWS` + `SEASONAL_PHRASES`/`SEASONAL_SKUS` to `config.py`
alongside the existing search-query/SKU banks. Refactor target: Engines 02 and 12
both want `enrich.py` step-1 parsing extracted into a shared `enrich_websites_lib`;
this engine consumes that lib through them rather than touching the crawl directly.
Engine 02's `ORDER_PHRASE_REGEX` and Engine 12's `PROGRAMMING_PHRASES` should accept
an injectable phrase bank so the calendar can override them per season without
forking the detectors.

## Open questions

1. **Build vs. schedule boundary.** Should `seasonal/` ship as a pure scheduler that
   shells out to Engines 02/12 (requires they expose a callable, parameterized API),
   or should it carry a minimal self-contained seasonal detector so it isn't blocked
   on those engines landing first?
2. **`lead_days` calibration.** Are the 60/75/90-day leads right per vertical?
   Butchers may need 90 (planning livestock), wine 45–60 (faster to stand up a case).
   Validate against actual partner onboarding-to-first-sale time before locking the
   table.
3. **Prior-year scarcity source.** Where does "sold out of turkeys last year" come
   from — Engine 03 (`sold_out_demand`), review-text mining (enrich step 5), or a
   stored prior-wave snapshot? If the latter, the calendar needs a per-season history
   store to compare against.
4. **One list per wave vs. a rolling seasonal master.** Do we hand sales a fresh
   `seasonal_preorder_calendar_<season_key>_<date>.csv` per wave (cleanest outbound
   timing), or also maintain a rolling `seasonal_all_<date>.csv` for partners that
   hit multiple windows (a cheese shop with both a holiday board and a summer event)?
```