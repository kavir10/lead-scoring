# Trendy Neighborhoods — proof that neighborhood-level search is an effective lead signal

**Question:** Are Table22's active partners concentrated in "trendy" neighborhoods? If so,
searching for trendy neighborhoods is a viable way to find lookalike prospects.

**Answer:** Yes. **56.5% of active partners (737 / 1,304)** sit in a trendy neighborhood
once the neighborhood list covers their city. Hit-rate within covered cities is consistent
at **~62–64%**, independent of whether the city was in the original curated list or
discovered later by automated search — which is the core proof: *automated trendy-neighborhood
search reproduces curated quality.*

## Files

### Reference data (committed — use these in discovery searches)
- `trendy_neighborhoods_top100_us_20260531.csv` — curated top-100-city list (484 neighborhoods).
- `trendy_neighborhoods_top100_us_tiered_20260531.csv` — expanded tiered list (624 neighborhoods).
- `trendy_neighborhoods_uncovered_cities_20260601.csv` — **482 neighborhoods across 270 cities**
  discovered via an automated research workflow for cities that had active partners but were
  missing from the curated lists. Schema: `city, state, partner_count, neighborhood, notes`.
- `uncovered_cities_no_trendy_area_20260601.csv` — 90 cities (mostly small-town/suburban,
  94 partners) with no genuine trendy district; recorded so they aren't re-researched.

### Partner-level analysis (gitignored — contains names + addresses)
- `active_partners_20260601.csv` / `active_partners_addresses_20260601.csv` — 1,304 active
  partners pulled from BigQuery (`loftsmart-data.disaggregated_views.partners_all`).
- `partners_trendy_neighborhood_20260601.csv` — v1 classification (original curated lists only).
- `partners_trendy_neighborhood_v2_20260601.csv` — **final** classification after adding the
  discovered neighborhoods. Columns: `classification` (trendy / not_trendy_neighborhood /
  not_trendy_city / unknown_no_address), `partner_neighborhood`, `matched_trendy_neighborhood`,
  `confidence`, `reasoning`.

## Final tallies (v2, 1,304 active partners)

| Classification | Count | % |
|---|---|---|
| In a trendy neighborhood | 737 | 56.5% |
| In a trendy-list city, not a trendy neighborhood | 429 | 32.9% |
| City with no trendy district | 94 | 7.2% |
| No street address on file | 44 | 3.4% |

## Method
1. Pull active partners + addresses from BigQuery.
2. Map each partner address → neighborhood (LLM, geography knowledge).
3. Match neighborhood against the per-city trendy list (curated + discovered).
4. For cities absent from the list, an automated research workflow discovered their trendy
   neighborhoods (web-search backed), then partners there were re-classified.

## Known undercount
Brooklyn/Queens partners were classified against only the 4 newly-discovered Brooklyn
neighborhoods, not unioned with the Brooklyn entries already filed under "New York" in the
curated list (Fort Greene, Carroll Gardens/Cobble Hill). Folding boroughs into NYC and
unioning the lists would push the trendy total slightly above 737.
