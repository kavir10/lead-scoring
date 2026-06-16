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

### Waves 3–4 — 2026-06-16 (swarm expansion)

After spend-limit cleared, the restaurant / butcher / cheese / wine wave agents each
spawned 5–9 regional sub-agents (national award lanes, full state sweeps, affluent
suburbs, destination towns, club/share/CSA bullseyes). All recovered via the transcript
harvest (`harvest_subagent_rows.py`). Restaurants cleared 1,000 and were stood down;
remaining capacity focused on the four laggards.

**Composition note (read with the counts).** To approach 1,000 on butcher and cheese —
verticals whose premium-independent universe ICP.md pegs at only ~1,000–1,200 (butcher)
and similar (cheese) — the lists deliberately include Tier-2 independents, **farm-retail /
meat-CSA hybrids** (flagged "farm retail/share" in evidence), regional sausage makers,
farmstead creameries with retail, and Italian-deli mozzarella counters. These are real
ICP-adjacent leads but skew below the Beast-and-Cleaver / cut-to-order-monger bullseye.
A tiering/QA pass is recommended before sales hand-off (see next steps).

### Blocker — session limit (2026-06-16 ~15:30 UTC)

Hit "session limit · resets 7:40pm UTC" mid-run. This caps agent spawning, so the
remaining wine (national club lane), bakery (wave-3 deep), and cheese (Texas+club lane)
sub-agents were killed before writing. Harvest/merge/commit (local) still work, so all
completed batches are captured and pushed. The loop is scheduled to resume after the
reset.

## Status (2026-06-16, at session-limit checkpoint)

| Vertical | Deduped leads | w/ website | Target | % to target |
|---|---:|---:|---:|---:|
| restaurants | 1113 | 110 (9%) | 1000 | **✓ 111%** |
| wine | 792 | 325 (41%) | 1000 | 79% |
| bakeries | 757 | 285 (37%) | 1000 | 76% |
| butchers | 717 | 348 (48%) | 1000 | 72% |
| cheese | 660 | 299 (45%) | 1000 | 66% |
| **total** | **4039** | **1367** | **5000** | **81%** |

### Next steps (on session-limit reset)

1. Resume discovery for the 4 laggards (~1,030 net-new still needed): re-run the killed
   lanes (wine national clubs, bakery deep state sweep, cheese TX+club) plus new lanes
   (do-you-ship comment mining, hidden-club detection, press-without-infrastructure,
   gift-ready, link-in-bio chaos) and finer state/suburb sweeps.
2. Domain-backfill sweep across **all** final masters (restaurants only 9% — the listicle
   agents left websites blank; the per-business search lookup proven in
   `apply_domain_backfill.py` fills these).
3. Tiering/QA pass on butcher + cheese to separate bullseye from farm-share/Tier-2.

Note: ICP.md says the premium independent butcher universe is ~1,000–1,200 shops total;
hitting 1,000 *qualified* butchers may require including Tier-2 premium independents and
farm-retail hybrids. Flagged here so the count is read with that context.
