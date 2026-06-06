# Restaurant 5K Lead Run Log

Date: 2026-06-06
Branch: `restaurant-trendy-neighborhood-discovery`

## Goal

Find the top 5,000 ICP-fit restaurant leads via Serper Maps, seeding each search
with a **trendy neighborhood name + city** (not just city). Rationale:
`research/trendy_neighborhoods/README.md` shows ~56–64% of active partners sit in
a trendy neighborhood, so neighborhood-level search reproduces curated quality.

## ICP Read

Read `docs/ICP.md` first. Restaurant-specific rules applied (Serper-observable subset):

- **Partner type (SHAP #1):** keep `destination_restaurant` + `neighbourhood_restaurant`
  only. Destination scored ~2× (≈ AGMV $60k vs $32k). `fast_casual` / QSR excluded.
- **Cuisine fit (Appendix B):** core (Italian, French, Mediterranean, Middle Eastern,
  steakhouse, New American, Thai, European/bistro…) > emerging (Korean, Japanese, Chinese,
  Mexican, BBQ, Spanish…) > lower (pizza-first, breakfast/brunch, burgers, most Latin
  American/African) — scored, not gated.
- **Destination promotion:** name/query acclaim signals (michelin, james beard, tasting
  menu, omakase, prix fixe, chef-driven, fine dining) lift score toward destination tier.
- **Gate:** 50+ reviews, rating ≥ 4.2, has website, not a chain, no anti-ICP text.
  (Reservation difficulty / IG / tenure are not Serper-observable — left to enrichment.)

## Scripts Added

- `scripts/fresh_restaurant_discovery.py` — neighborhood-seeded Serper Maps crawl +
  ICP qualify + SHAP-aligned score + dedupe → ranked top-N. Re-filter a saved raw with
  `--raw-input` (no new API calls).
- `scripts/dedupe_restaurants_by_cid.py` — split a top CSV into net-new vs already-seen
  by Google CID, against the prior `output/` corpus (excludes the run's own dir).

## Crawl

- Locations: `trendy_neighborhoods_top100_us_tiered_20260531.csv` — **624 neighborhoods, 100 cities**.
- 16 weighted restaurant queries × 624 neighborhoods = **9,984 Serper Maps calls**.
- Neighborhood entered the **location field** (`q="best restaurant"`,
  `location="Bushwick, New York, NY, United States"`), matching `fresh_wine_discovery.py`.
- Result: 192,152 raw → 21,889 accepted/deduped → **top 5,000**.

## QA (multi-agent adversarial audit)

Ran a 10-auditor + synthesis workflow over a 340-row risk-stratified sample (bottom
score band, `neutral`-cuisine, destination claims). First pass verdict: **needs_rework,
25.6% sample leakage** — surfaced three *systematic* leaks (chains rank HIGH because
review volume drives score):

1. **Restaurant chains** — `config.CHAIN_KEYWORDS` had no upscale-restaurant brands.
2. **Not-a-restaurant** — hotel/resort outlets, wineries, banquet/event venues, breweries.
3. **Per-location franchise URLs** (`/locations/<city>/`) — never inspected.

## Fixes applied (scoped to the discovery script; `config.py` untouched)

- `FRANCHISE_URL_RE` → reject `/locations/<slug>` and hyphenated `/location/<brand-city>`.
- `VENUE_REJECT_TYPES` → reject when Google `types` include Banquet hall / Event venue /
  Wedding venue / Winery / Hotel / Casino / Brewery / Night club, etc.
- `HOSPITALITY_DOMAINS` + `.edu` → reject in-house outlets by website host.
- `RESTAURANT_CHAINS` (apostrophe-normalized) → catch Fleming's, J. Alexander's, Culinary
  Dropout, North Italia, Landry's, Pappadeaux, Sam Snead's, etc. (Kincaid Grill, a genuine
  Anchorage independent, is correctly retained.)
- **Chain-domain collapse** → drop any domain appearing ≥4× (chains share one root domain
  across locations but have distinct per-location phones, which survives phone-keyed dedupe).
  Dropped 3,382 rows across 145 domains.
- Re-filtered the saved raw (`--raw-input`, zero new API calls). Post-fix top 5,000:
  **0 franchise URLs, 0 hotel domains, 0 venue secondary types.**

## Deliverable: 5,000 NET-NEW, lower-fit excluded (`output/fresh_restaurant_leads/`)

Requirement was **5,000 net-new** (CID absent from prior `output/`), **excluding lower-fit
cuisine** (pizza/breakfast/burger). Lower-fit is now a hard reject in
`fresh_restaurant_discovery.py` by default (`--keep-lower-fit` to score-demote instead),
which dropped the qualified pool 21,889 → 20,526. Method: rank the full qualified set (20,489
after intra-file CID collapse) by ICP score, drop CIDs already in the prior corpus, take the
top 5,000 of the remainder. 11,187 net-new available → cut is score-quality-bound.

- `fresh_restaurant_top_20526_20260606_150421_netnew_top5000_20260606_150435.csv` —
  **the 5,000 net-new leads.** 5,000 distinct CIDs, 0 overlap with prior `output/`, 0 lower-fit.
  392 destination / 4,608 neighbourhood; 3,280 core / 767 emerging / 953 neutral; score 59.5–85.8.
  (Destination skews low because acclaimed high-review spots are mostly already discovered — they
  land in the seen bucket.)
- `…_netnew_11187_*.csv` — all 11,187 net-new, ranked (headroom beyond 5,000).
- `…_seen_9302_*.csv` — qualified leads already in prior discovery.
- `fresh_restaurant_top_20526_20260606_150421.csv` — full qualified set, ranked (source).
- `fresh_restaurant_raw_20260606_143538.csv` — full 192k raw (re-filterable via `--raw-input`).
- `fresh_restaurant_report_20260606_150421.txt`.

## Open follow-ups

- Mid-list (rank ~50–3000) was thinly sampled in QA; chain density across the full list may
  exceed the audited rate. Consider a fuller audit before enrichment spend.
- No `permanently_closed` check yet (Serper can surface closed places) — add before handoff.
- Enrichment (IG/reviews/reservations) + scoring not run — separate, Apify-cost pass.
