# Lead Engine 23 — Permit and Buildout Watchlist

**Motion:** Curation
**Vertical fit:** Bakeries, butchers, wine shops, cheesemongers, specialty grocers, destination + neighborhood restaurants — any operator whose growth touches a regulated facility (production kitchen, retail food establishment, alcohol license)
**Suggested list name(s):** `permit_buildout_watchlist`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run (ingestion is mostly free open-data; cost is Serper Maps resolution + bounded Claude classification)

## Premise

Government records are the *earliest* public proof that capacity is changing.
A health-department food-establishment application, a state liquor/wine
license filing, a building-permit "tenant improvement — restaurant" record,
or a new LLC registered to a known operator all appear **weeks to months
before** the business shows up on Google Maps, posts an opening announcement,
or earns press. This engine ingests county/state open-data portals to catch
the buildout while the operator is still pre-revenue and pre-platform — the
moment a club program is cheapest to design in from day one.

In the two-score model this is a pure **Trigger** engine, and an unusually
early one. ICP Fit must be inferred from thin pre-opening data (concept name,
the type of permit, the operator's prior businesses), so the engine is most
valuable when the *operator already has an ICP-fit track record* — a
respected butcher opening a second counter, an owner-somm filing a retail
wine license, an acclaimed bakery permitting a commissary. A wine *retail*
license filing is a structurally strong signal: it telegraphs a future
wine-shop ICP-fit business before a single bottle is on a shelf.

The thesis is demand-over-capacity expressed at its source: nobody files for
a new production kitchen or a second location without demand justifying the
capital. The permit *is* the capacity-expansion event, captured at filing
time rather than at announcement time. That earliness is the moat — and the
liability (see Risks: a filing is intent, not a live business).

## Recipe

This engine adds genuinely new infrastructure: a **public-records ingestion
lane**. There is no existing primitive that pulls county/state permit feeds,
so this is the one place we build new code rather than reuse a scraper. Once a
permit row exists, everything downstream — resolution, classification,
tiering, evidence — reuses existing primitives.

1. **Build a portal registry.** Most US open-data lives on a small set of
   platforms with public APIs: **Socrata** (data.cityofnewyork.us,
   data.sfgov.org, etc. — SoQL/JSON endpoints, no key needed for read),
   **ArcGIS Open Data / Hub** (REST FeatureServer queries), **CKAN**
   (state portals), and **Accela Citizen Access** (HTML, many county building
   departments). Seed the registry from the top metros in `config.CITIES`,
   biased toward the **trendy-neighborhood** geography in
   `research/trendy_neighborhoods/` (~56.5% of partners sit there — prioritize
   those county/city portals first). Each registry entry: `{jurisdiction,
   platform, dataset_url, dataset_type, field_map}`.

2. **Ingest four record classes** (one fetcher per class, all writing the same
   raw schema):
   - **Health / food-establishment permits** — new-establishment applications
     and plan-review records (Socrata/ArcGIS).
   - **Alcohol licenses** — state ABC/liquor-authority feeds; many states
     publish pending + issued. *Filter to off-premise wine/retail license
     classes* — these are the wine-shop precursors; route on-premise-only and
     full-liquor classes to the anti-ICP gate.
   - **Building / construction permits** — "tenant improvement," "commercial
     kitchen," "restaurant," "bakery," "food prep" use-types.
   - **Business filings** — new LLC / DBA registrations (Secretary-of-State
     bulk data where free) used only to *attribute* a permit to a known
     operator, not as a standalone trigger (too noisy alone).

3. **Keyword/use-type filtering at ingest.** Permit feeds are mostly noise
   (nail salons, offices, residential). Filter use-type and description fields
   on a seed list before anything leaves the fetcher:

   ```
   food/establishment: "food establishment", "retail food", "commercial kitchen",
       "commissary", "food prep", "plan review", "mobile food", "bakery", "deli",
       "meat market", "butcher", "grocery", "specialty food", "cheese"
   construction/TI:     "tenant improvement", "restaurant", "cafe", "kitchen hood",
       "type i hood", "walk-in cooler", "food service", "bakery", "wine"
   alcohol (KEEP):      "off-premise", "package", "retail wine", "wine shop",
       "wine and beer off", "class * wine retail"
   ```

4. **Anti-ICP and chain pre-filter at ingest.** Drop before resolution:
   on-premise-only and full-liquor alcohol classes (cocktail bar / liquor-store
   precursors), names matching `config.CHAIN_KEYWORDS`, and the
   liquor-store-ESP / commodity red flags from the cheat-sheet
   (City Hive / Spot Hopper if a site is already up; Tito's/Smirnoff/Veuve
   class names in the filing). Enforce the butcher-lane
   `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` for butcher-typed rows.

5. **Resolve to a real (or future) business — Serper Maps.** Reuse the
   `discover.py` Serper Maps primitive to look up the applicant/concept name +
   address. Three outcomes, all kept with a `liveness` flag:
   - **Open & enrichable** → it's an *expansion* of an existing operator. Hand
     to the standard universe; run `detect_clubs.py` to flag whether they
     already run a club (existing club = positive platform-switch signal).
   - **Permitted, not yet on Maps** → the pre-opening prize. Hold in a
     `pre_opening` cohort; cannot be ICP-scored on social/reviews yet.
   - **No resolution / closed** → park in raw, do not emit.

6. **Attribute to an operator (Claude).** For pre-opening rows, run the permit
   text + applicant name + any linked LLC through `awards/llm_extract.py`-style
   Claude extraction (prefix `unset ANTHROPIC_API_KEY &&`) to (a) guess the
   concept's `partner_type`, and (b) match the applicant to a *known existing
   operator* by name/principal (e.g. "filed by the owner of <known butcher>").
   Operator-attributed filings are far stronger than anonymous new LLCs.

7. **Score the trigger.** Permit class × operator track record × recency.
   Pre-opening rows get a trigger score but **no `score.py` /100 ICP score**
   (insufficient data) — flag `icp_inferred`. Expansion rows of known
   operators flow through normal `score.py` weighting (do **not** re-tune
   `config.SCORING_WEIGHTS`).

   ```
   PERMIT_WEIGHTS = {
       "retail_wine_license":     1.0,  # telegraphs a future wine-shop ICP
       "new_production_kitchen":  0.95, # commissary / commercial kitchen
       "second_location_food":    0.9,  # known operator, new food establishment
       "new_food_establishment":  0.8,  # new applicant, food retail/prep
       "restaurant_TI":           0.7,  # tenant improvement, restaurant use
       "bakery_permit":           0.7,
       "new_llc_food_only":       0.4,  # filing-only, no permit corroboration
   }
   recency = max(0, 1 - months_since_filing / 12)   # permits perish fast
   trigger_score = PERMIT_WEIGHTS[permit_class] * recency
   operator_bonus = 0.15 if attributed_to_known_icp_operator else 0

   tier = 1 if (trigger_score + operator_bonus >= 0.85 and icp_ok) else \
          2 if (trigger_score + operator_bonus >= 0.55) else 3
   # pre_opening rows cap at Tier 2 until a real business exists to verify
   ```

8. **Emit + diff.** Archive each run's raw permits to `output/permits/raw/` and
   diff against the prior run so the master only flags **newly filed** records
   (a standing 8-month-old permit shouldn't re-fire every run).

## Output schema

```
output/permits/permit_buildout_watchlist_<YYYYMMDD>.csv
source = "permit_buildout_watchlist"
tier = <1|2|3>
business_type = <butcher | wine | cheese | bakery | specialty_grocer | restaurant>
distinction = "<human-readable trigger, e.g. 'Retail wine license filed (Mar 2026), Brooklyn'>"
year = <YYYY of filing>
+ evidence cols:
    permit_class            # normalized enum from PERMIT_WEIGHTS
    permit_class_raw         # original use-type / license-class string from the feed
    jurisdiction             # county/city portal the record came from
    portal_platform          # socrata | arcgis | ckan | accela
    filing_date              # date the record was filed/issued
    permit_id                # record number for verification (sales can cite/lookup)
    permit_url               # link to the public record (cite-the-trigger)
    applicant_name           # name on the filing
    attributed_operator      # known operator matched by Claude, or null
    liveness                 # open_on_maps | pre_opening | unresolved
    matched_phone, matched_website   # from Serper Maps resolution (if open)
    has_club, club_url       # from detect_clubs.py (open operators only)
    icp_inferred             # true for pre-opening rows (no /100 score yet)
    icp_score                # /100 from score.py (open/enrichable rows only)
    trigger_score, recency
    is_net_new               # vs current scored universe (phone-first)
    scan_date
```

Preserve `permit_id` + `permit_url` on every row — a permit filing is a
verifiable public record, and the strongest possible outbound line cites it
("saw the retail-wine license you filed in March — want to launch the club
the day you open?").

## Volume & cost

Bounded by how many jurisdictions are wired up, not a Maps crawl. Assume an
initial registry of ~25 metros covering the trendy-neighborhood geography.

- Open-data ingestion (Socrata/ArcGIS/CKAN APIs): **free** (public read; only
  request volume). Accela HTML scrapes add a little Playwright time, no $.
- Keyword/use-type + anti-ICP filtering: free, runs in-process.
- Serper Maps resolution: after filtering, expect ~300–700 food-relevant
  filings/run across 25 metros → ~$0.003 each ≈ **$1–2**.
- Claude attribution/classification on the filtered set (~500 rows, Haiku):
  ≈ **$3–5**.
- `detect_clubs.py` on the open-operator subset (~150 sites, 50 threads):
  negligible API $, just compute.
- **Per-run total: ~$5–10** (well under target; new code is the real cost).

Expected yield from ~25 metros: of the ~300–700 food-relevant filings,
perhaps **60–120 carry a real expansion/pre-opening trigger**, of which
**~20–40 reach Tier 1** (retail-wine filing, known-operator second location,
or new production kitchen). Most pre-opening rows are net-new to the universe
— that's the point: this engine front-runs every other discovery lane.

## Refresh cadence

**Weekly.** Permits perish fast as triggers — the 12-month recency decay is
aggressive, and the diff-vs-prior-run logic means cadence determines how
quickly a freshly filed permit reaches sales. Weekly catches filings while the
operator is mid-buildout (the ideal contact window for a pre-opening club
design). Re-resolve `pre_opening` rows each run; a row flips to
`open_on_maps` the week the business goes live, at which point it gets the
full enrichment + `score.py` treatment.

## Risks

- **Filing ≠ live business.** A permit is *intent*; concepts die in buildout,
  applicants are landlords or contractors not operators, and timelines slip
  6–18 months. `pre_opening` rows are explicitly capped at Tier 2 and carry
  `icp_inferred=true` — never sell them as established operators. The weekly
  re-resolution is the liveness check.
- **Anti-ICP / liquor leakage.** Alcohol feeds are dominated by liquor stores,
  cocktail bars, and on-premise venues — all disqualifiers. Keeping *only*
  off-premise wine/retail classes is load-bearing; an over-broad alcohol
  filter floods the list with liquor stores (vs. curated wine shops). Apply
  the wine commodity/liquor-store-ESP exclusions and never admit a full-liquor
  or on-premise class as a wine row.
- **Chain / franchise leakage.** New-location and TI permits fire heavily for
  chains and franchises. Run `config.CHAIN_KEYWORDS` at ingest *and* after
  Maps resolution; specialty-grocer and restaurant are the leakiest buckets.
- **Sweets-only / single-product demotion.** A bakery permit for a
  cupcakes-only / single-pastry concept still caps at Tier 2 per the
  cheat-sheet even with a strong fresh permit; carry the single-product flag
  forward from Claude classification.
- **Small-market + thin pre-opening data.** Rural/small-metro filings have no
  social or reviews to score on, and static social understates brand anyway —
  do **not** down-rank for absence of signal. Weight relative local dominance
  and the operator track record over raw metrics; this engine only *adds*
  leads on a positive filing.
- **Portal fragility & coverage gaps.** Open-data portals re-template,
  rate-limit, change dataset IDs, and many counties publish nothing usable
  (Accela behind logins, PDFs only). Coverage will be uneven and US-patchwork;
  isolate per-jurisdiction failures (one portal down ≠ run down, mirroring
  `discover_awards.py`) and log per-jurisdiction coverage so a silent feed
  outage doesn't read as "no filings."
- **Schema drift across jurisdictions.** Every portal names use-types and
  license classes differently. The `field_map` per registry entry plus the
  `permit_class_raw` passthrough exist so normalization mistakes are auditable;
  validate the keyword map per new jurisdiction before trusting its Tier 1.
- **Banned states.** Enforce butcher-lane `BANNED_STATES` for butcher-typed
  rows before output.

## Repo placement

```
permits/
  __init__.py                 # registers fetchers + jurisdiction registry
  _lib.py                     # raw SCHEMA, PERMIT_WEIGHTS, keyword + anti-ICP seeds
  registry.py                 # {jurisdiction, platform, dataset_url, field_map} table
  fetch_socrata.py            # SoQL/JSON read for Socrata portals
  fetch_arcgis.py             # FeatureServer query for ArcGIS Hub portals
  fetch_ckan.py               # CKAN datastore read (state portals)
  fetch_accela.py             # Playwright HTML scrape for Accela Citizen Access
  classify.py                 # use-type filter + Claude attribution/partner_type guess
  resolve_and_match.py        # Serper Maps resolution + dedupe_existing.py + detect_clubs.py
  finalize.py                 # PERMIT_WEIGHTS scoring, diff-vs-raw, tiering, canonical CSV
discover_permits.py           # orchestrator (mirrors discover_awards.py shape):
                              #   --jurisdiction <slug>  --platform socrata
                              #   --all  --since 90d  --master-only  --resume
output/permits/raw/           # per-run raw archive for the newly-filed diff
```

Shared-code refactors this engine wants:
- Reuse the `discover.py` Serper Maps lookup as an importable resolver (the
  same lift several trigger engines want) rather than re-implementing Maps auth
  in `resolve_and_match.py`.
- Add `PERMIT_WEIGHTS`, the use-type keyword map, the off-premise alcohol-class
  allowlist, and the jurisdiction registry to `config.py` alongside the
  existing keyword/chain blocks so non-engineers can extend coverage.
- `detect_clubs.py` is reused as-is on the open-operator subset (no change).

## Open questions

1. How many county/state portals expose **food-establishment + alcohol +
   building permits** with a usable free API vs. PDFs/login-walls? Coverage,
   not code, decides this engine's ceiling — run a probe across the top
   trendy-neighborhood metros before committing to a registry size.
2. Is a **retail-wine-license filing alone** (no resolvable operator yet)
   enough for Tier 1, given it so cleanly telegraphs a future wine-shop ICP, or
   should Tier 1 require operator attribution to a known principal?
3. What's the right re-contact policy for a `pre_opening` row that takes 14
   months to open — keep re-surfacing weekly, age it out, or move to a
   long-horizon nurture cohort and only re-flag on the `open_on_maps` flip?
4. Do Secretary-of-State LLC/DBA feeds add enough operator-attribution lift to
   justify ingesting them, or is the new-LLC signal too noisy to be worth the
   bulk-data handling?
