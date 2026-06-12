# Innovative 5×1000 Lead Run Log

Date started: 2026-06-12
Branch: `claude/lead-generation-verticals-zoq0ot`
Goal: 1,000 ICP-qualified leads per vertical — restaurants, butchers, cheese shops,
bakeries, wine shops — using the trigger-based lanes from
`docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md`, qualified against `docs/ICP.md`.

## Environment constraint (why not the Serper pipeline)

This run executes in a remote container with **no `.env`** (no `SERPER_API_KEY` /
`APIFY_API_TOKEN`) and a **limited network policy** (package managers + GitHub only;
all other outbound HTTP from the container 403s). The repo's Serper/Apify pipelines
therefore cannot run. Discovery instead uses the harness WebSearch/WebFetch tools
(which run outside the container) via parallel research subagents.

Implication: leads carry name/city/state/source/evidence, **not** the full enrichment
schema (no phone, review counts, IG metrics). When keys are available, these lists can
be fed through `main.py --enrich` for full enrichment + scoring.

## Method

- Agent brief: `docs/leadgen_agent_brief_20260612.md` (output contract + per-vertical
  qualification rules distilled from ICP.md).
- Per-agent CSVs land in `output/innovative_leads/<vertical>/` (force-added to git so
  progress survives the ephemeral container).
- Merge/dedupe: `scripts/merge_innovative_leads.py` (stdlib-only; dedupes by
  normalized name+city and website host; enforces butcher banned states) →
  `output/innovative_leads/master_<vertical>_<YYYYMMDD>.csv`.
- Loop: dynamic `/loop` — each iteration spawns a wave of parallel research agents on
  lanes/cities not yet covered, merges, counts, repeats until every vertical ≥ 1,000.

## Lanes used (from the innovative-ideas doc)

- press_awards_recent_momentum (James Beard, Michelin/Bib, Good Food Awards, CMI)
- existing_club_transition / hidden_club_detection (wine club, meat share/CSA, cheese
  club, bread club/CSB)
- best_of_city_list (Eater 38, Infatuation, local press) across major metros
- sold_out_demand_signals, seasonal_preorder_calendar (bakery)
- events_programming_repeat_commerce (butchery/cheese classes, supper clubs)
- natural_wine_map_expansion + supplier_importer_graph (respected importers)
- reservation_refresh_pain (hard-to-book restaurant lists)
- small_market_local_dominance (smaller affluent towns, later waves)

## Wave log

### Wave 1 — 2026-06-12

5 parallel agents (one per vertical): national award/press lanes + top-25/30 metros +
club-language searches. Targets: 250–300 rows each. Results: see counts below as
iterations complete.

## Status

| Vertical | Deduped leads | Target |
|---|---:|---:|
| restaurants | wave 1 in flight | 1000 |
| butchers | wave 1 in flight | 1000 |
| cheese | wave 1 in flight | 1000 |
| bakeries | wave 1 in flight | 1000 |
| wine | wave 1 in flight | 1000 |

Note: ICP.md says the premium independent butcher universe is ~1,000–1,200 shops total;
hitting 1,000 *qualified* butchers may require including Tier-2 premium independents and
farm-retail hybrids. Flagged here so the count is read with that context.
