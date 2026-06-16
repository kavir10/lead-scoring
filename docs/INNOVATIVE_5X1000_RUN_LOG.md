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

### Wave 3 — 2026-06-16 (after spend-limit lifted)

Spend limit (which killed wave 2 mid-run on 06-12) cleared. Re-ran 5 discovery
agents on fresh lanes: complete state sweeps, affluent suburbs, destination small
towns, cuisine-fit roundups, club/share/CSA bullseyes, butcher Tier-2 + farm-retail.

**Sub-agent swarm + harvest.** The restaurant wave-3 agent spawned ~9 regional
sub-agents that returned qualified rows **as text** instead of writing the CSV, and
SendMessage isn't available in this harness to resume them. Built
`scripts/harvest_subagent_rows.py` to recover well-formed schema rows directly from
sub-agent JSONL transcripts (HTML-unescaped, schema-validated, deduped) → per-vertical
`harvested_subagents_<stamp>.csv`, folded in by the normal merge. This recovered
~400 restaurant rows that would otherwise have been lost.

**Domain backfill.** Leads from listicles lacked websites. `apply_domain_backfill.py`
fills the `website` field from a per-business search-resolved mapping
(`output/innovative_leads/domains/<vertical>_*.csv`); mappings are re-applied after every
merge (merge rebuilds masters from wave files, so backfill must be re-run). First batch:
110 restaurant domains.

## Status (2026-06-16)

| Vertical | Deduped leads | Target | % |
|---|---:|---:|---:|
| restaurants | 854 | 1000 | 85% |
| wine | 422 | 1000 | 42% |
| bakeries | 391 | 1000 | 39% |
| cheese | 359 | 1000 | 36% |
| butchers | 349 | 1000 | 35% |
| **total** | **2375** | **5000** | **48%** |

Domain coverage backfill is a separate pass run against the final masters once
discovery hits target (restaurants partially done: 110+).

Note: ICP.md says the premium independent butcher universe is ~1,000–1,200 shops total;
hitting 1,000 *qualified* butchers may require including Tier-2 premium independents and
farm-retail hybrids. Flagged here so the count is read with that context.
