# Channel 01 — Sommelier / Chef IG Graph Traversal

**Motion:** Curation
**Vertical fit:** Wine shops, destination restaurants, wine bars (primary); bakeries, cheese, butcher (secondary, via chef seeds)
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $40/run (Apify IG actor) + Sonnet judging on aggregated venues

## Premise

Existing IG hashtag discovery surfaces venues that *use* hashtags well. It
misses operators who are well-known *inside the industry* but don't surface
for `#naturalwine` or `#sommlife`. Those operators do show up in the
**tagged-location** and **following** graphs of ~150 named industry seeds.

This channel rides the **person graph** rather than the keyword surface.

## Seed list (~150 named industry people)

| Source | Count | Cadence | How |
|---|---:|---|---|
| James Beard Foundation semifinalists (Outstanding Wine Program, Beverage Program, Chef, Best New Restaurant) | ~80 | Annual, every March | JBF site has structured lists |
| GuildSomm directory (Advanced + Master Sommeliers, opt-in profile) | ~60 | Quarterly refresh | guildsomm.com member directory (public profile-photos page) |
| Eater 38 — named chefs across top-20 metros | ~120 (dedupe to ~60) | Quarterly | Editorial pages, chef name in body copy |
| Food & Wine Best New Chef alumni (last 10 years) | ~50 | Annual | foodandwine.com archive |
| Wine & Spirits Best New Sommeliers (last 5 years) | ~50 | Annual | wineandspiritsmagazine.com |
| Wine Spectator Restaurant Awards (Grand Award winners — beverage director named) | ~40 | Annual | winespectator.com |

After dedupe across sources, target = **150 unique IG handles**. Manual
verification on the seed list is one-time and cheap. Seeds live in
`social_graph/industry_seeds.csv` (name, role, source, ig_handle).

## Traversal recipe

For each seed handle:

1. **Profile pull** (Apify `apify/instagram-profile-scraper` — already used by
   `enrich.py` step 2). Confirms account is real + public.
2. **Tagged-locations pull** — Apify IG `apify/instagram-tagged-posts-scraper`
   or post-by-user scraper, grab last 100 posts, extract location.id +
   location.name from each post.
3. **Following list** — gated behind login; skip unless we have a session
   token. Cheaper alternative: pull the seed's last 30 reels, extract
   collab/tagged accounts, and *those* become candidate venues.
4. **Tagged-by list** — `apify/instagram-tagged-posts-scraper` returns
   accounts the seed has been tagged by. These are often *the venues* tagging
   the seed in an after-service post.

## Aggregation & scoring

For each candidate venue surfaced:

- `seed_frequency` — how many distinct seeds reference this venue
- `seed_quality` — sum of seed weights (Master Somm > JBF semifinalist > Eater 38)
- `mention_recency` — most recent mention timestamp

A venue mentioned by ≥3 distinct seeds at quality-weight ≥ 6 is **promoted to
A-list**. Single-seed mentions go to B-list and require corroboration before
BDR handoff.

## Output

`output/social_graph/somm_chef_ig_graph_<YYYYMMDD>.csv` with canonical
schema:

```
source = "ig_graph_somm_chef"
distinction = comma-joined seed names + roles
year = max(mention_year)
business_type = best-guess from location.category + venue name heuristics
+ extra cols: seed_frequency, seed_quality, last_mention_at, seed_names
```

## Volume & cost estimate

- 150 seeds × 100 posts each = 15K post pulls @ Apify IG ≈ $5-10
- 150 tagged-by pulls × 50 mentions = ~7.5K records @ ~$5
- LLM rollup + venue type inference: Sonnet 4.5, ~$10
- **Per-run total: ~$25-40**
- **Net-new venues per run (estimate): 600-1,200 unique, of which ~150-250 promoted to A-list**

## Refresh cadence

Quarterly. Seed list refreshed annually after each JBF/F&W/W&S cycle.

## Risks

- IG aggressively rate-limits and rotates anti-bot. Apify actor handles
  rotation but expect partial coverage. Mitigation: run in two passes a week
  apart; merge.
- Tagged-locations data is messy — same venue can have 3 Foursquare
  location.ids. Mitigation: dedupe by name + zip during aggregation, then
  re-geocode against Google Places API for canonical address.
- Some seeds will have private accounts. Drop them, replace with next-eligible
  candidate from the same source list.

## Repo placement

```
social_graph/
  __init__.py
  industry_seeds.csv          # the 150 named seeds
  build_seeds.py              # one-time aggregator that builds seeds CSV
  fetch_seed_posts.py         # Apify IG profile + tagged-posts pull
  aggregate_venues.py         # rollup by venue with seed_frequency scoring
  finalize.py                 # emits canonical CSV
discover_ig_graph.py          # orchestrator, mirrors discover_awards.py shape
```

## Open questions

1. Do we have IG session cookies for the GuildSomm members whose accounts are
   private? Without them ~25% of the seed surface is dark.
2. Should we filter to US-only at the IG-location stage or post-hoc? Apify
   returns global, but `location.country` is usually populated.
3. Worth pairing with `lookalike_v3` as a second judge input — "did v3 also
   surface this venue?" If yes, that's a triple-corroboration signal.
