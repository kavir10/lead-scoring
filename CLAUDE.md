# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## What this is

Lead discovery, enrichment, and scoring for Table22. Independent food
businesses (restaurants, butchers, wine shops, bakeries, cheesemongers,
specialty grocers) are evaluated as subscription-program prospects.

The repo is **not one pipeline**. It's a collection of source-specific
discovery pipelines that share a canonical row schema, plus a generic
Serper-based discover → enrich → score loop. Each pipeline can run
independently; outputs all land in `output/`.

For the user-facing tour see `README.md`. This file documents the parts
that matter when modifying code.

## Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # for Playwright-backed sources
```

`.env` keys: `SERPER_API_KEY`, `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`.

If your shell sets an empty `ANTHROPIC_API_KEY` (Claude Desktop side-effect),
prefix scripts with `unset ANTHROPIC_API_KEY &&` — `load_dotenv()` will not
override an existing empty var. Same applies to any script importing the
`anthropic` SDK.

## Web UI — `webui/`

`python -m webui` serves a localhost-only browser UI (default
`http://127.0.0.1:8722`) for the generic Serper pipeline. It is a thin
wrapper: runs are spawned as `python main.py ...` subprocesses, so UI runs
and CLI runs behave identically. FastAPI backend in `webui/server.py`,
no-build vanilla JS frontend in `webui/static/`. Run state + logs persist
under `output/webui_runs/<run_id>/`. The server binds `127.0.0.1` on
purpose — never make it externally reachable.

## Pipelines

### Generic Serper pipeline — `main.py`

Three phases, orchestrated end-to-end or piecewise:

```bash
python main.py                                              # full pipeline
python main.py --discover                                   # phase 1 only
python main.py --discover --types butcher,wine     # canonical types = values of BUSINESS_TYPE_MAP
python main.py --discover --max-searches 50
python main.py --discover --merge output/1_discovered.csv   # union with existing
python main.py --enrich output/1_discovered.csv             # phase 2 only
python main.py --enrich-from reviews output/2_enriched_*.csv  # resume mid-phase-2
python main.py --enrich-remaining output/2_enriched_reviews.csv  # reels+posts+availability
python main.py --score output/2_enriched_availability.csv   # phase 3 only
```

**Phase 1 — Discovery (`discover.py`).** Serper Maps across ~385 US cities,
keyword queries per business type. Dedupes by phone, filters chains via
`CHAIN_KEYWORDS` in `config.py`, applies quality floors (restaurants: ≥50
reviews / ≥4.2 rating; niche: ≥20 / ≥4.0), requires a website.

**Phase 2 — Enrichment (`enrich.py`).** Sequential, each step saving a
checkpoint CSV to `output/`. The step list lives in `main.py:ENRICHMENT_STEPS`:

1. `websites` → 2_enriched_websites.csv  — concurrent crawl (10 threads): ecommerce, email signup, social links, reservation platforms
2. `instagram` → 2_enriched_instagram.csv  — Apify profile scraper, batches of 30
3. `facebook` → 2_enriched_social.csv  — HTML scraping for FB likes; computes combined `follower_count` (IG + FB)
4. `press` → 2_enriched_full.csv  — Serper Web against food media domains + award keywords
5. `reviews` → 2_enriched_reviews.csv  — Apify Google Maps Reviews; mines review text for reservation-difficulty signals
6. `reels` → 2_enriched_reels.csv  — Apify IG Reel scraper
7. `posts` → 2_enriched_posts.csv  — Apify IG Post scraper
8. `availability` → 2_enriched_availability.csv  — OpenTable (Apify) + Resy API for reservation scarcity

**Phase 3 — Scoring (`score.py`).** Weighted /100 using `config.py:SCORING_WEIGHTS`.
Outputs `custom-serper-scoring_<owner>_<YYYYMMDD>_<verticals>_<count>_all.csv`
plus a `_top.csv` filtered to A+B tier. Tiers: A 55+, B 35+, C 20+, D <20.

### Awards — `awards/` + `discover_awards.py`

~40 editorial / award sources across restaurants, wine, bakery, cheese,
butcher, and specialty. **One module per source** under
`awards/<category>/<slug>.py`, registered in `awards/__init__.py:ALL_SOURCES`
as `(slug, category, tier, module_path, business_type, requires_auth)`.

Each module exposes `def scrape(**kwargs) -> pandas.DataFrame` returning rows
in the canonical schema from `awards/_lib.SCHEMA`:

```
source, tier, business_type, name, city, state, country,
distinction, year, source_url, blurb
```

```bash
python discover_awards.py --source james_beard
python discover_awards.py --category bakery
python discover_awards.py --tier 1
python discover_awards.py --all                  # skips 🔒 sources w/o --cookies-from
python discover_awards.py --source nyt --cookies-from cookies/nyt.json
python discover_awards.py --master-only          # rebuild master from existing per-source CSVs
```

Outputs: `output/awards/<slug>_<YYYYMMDD>.csv` per source,
`output/awards_all_<YYYYMMDD>.csv` for the union.

**Michelin is special.** `discover_michelin_direct.py` runs the Michelin
pipeline standalone. `awards/restaurants/michelin.py` is a thin wrapper that
loads the latest `output/michelin_direct_us_*.csv` so Michelin rows show up
in the master union without re-scraping.

**Extraction modes** used by source modules (see `docs/AWARDS.md`):
1. Structured Playwright pagination (Michelin-style)
2. httpx + selectolax + regex over a clean machine-readable list
3. LLM extraction (`awards/llm_extract.py`) over editorial articles when no
   structured list exists. LLM mode is best-effort — flag in `docs/AWARDS.md`.

**Adding a source.** Drop a module under `awards/<category>/<slug>.py`
implementing `scrape()`, register it in `ALL_SOURCES`, add a row to
`docs/AWARDS.md`. The orchestrator handles backfilling `source`, `tier`,
`business_type` if the module doesn't set them.

### Directories & stockists — `directories/` + `discover_directories.py`

Parallel to awards but for non-award sources: curated directories (Raisin)
and importer "where to buy" backlink mining. Same module contract, same
schema, same orchestrator shape.

```bash
python discover_directories.py --list
python discover_directories.py --source raisin_app
python discover_directories.py --category wine
python discover_directories.py --all
python discover_directories.py --master-only
```

Outputs: `output/directories/<slug>_<YYYYMMDD>.csv`,
`output/directories_all_<YYYYMMDD>.csv`. The package docstring in
`directories/__init__.py` lists sources investigated but **intentionally
skipped** (RAW WINE, several natty fairs, traditional importers with no
public stockist pages) — re-probe periodically before re-adding.

### Best wine shops — `best_wine_shops/`

Self-contained scraper for editorial "best wine shops in America" articles.
Seed list of 7 curated sources plus Serper-discovered articles on the same
theme. httpx + selectolax for the happy path, Playwright fallback when
blocked, Claude for extraction.

```bash
python -m best_wine_shops.discover                   # full
python -m best_wine_shops.discover --no-seeds
python -m best_wine_shops.discover --no-search
python -m best_wine_shops.discover --max-per-query 3
python -m best_wine_shops.discover --dry-run
```

Outputs `output/best_wine_shops/best_wine_shops_<YYYYMMDD>.csv`.
Tags rows with `is_large_indie` and `is_online_only`.

### Butcher source-scrape — `butcher.py` + `butcher_sources.py` + `discover_butchers.py`

Standalone butcher vertical. **Skips Serper/Google and all enrichment** —
scrapes alternative source lanes only: Good Meat Finder, EatWild, Good Food
Awards, AGA, stockist pages.

```bash
python discover_butchers.py
```

Outputs: `output/butcher/1_discovered_butchers.csv` (deduped), a timestamped
snapshot, raw rows pre-dedupe, and a per-source status CSV.

`BANNED_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}` is enforced in
this lane only — these are states the butcher vertical can't ship to.

### Beli — `scrape_beli/`

Multi-phase mining of `@beli_eats` Instagram posts for restaurant mentions.
Run modules in order (each writes a JSON or CSV the next consumes):

```bash
python scrape_beli/fetch_posts.py --username beli_eats --limit 100
python scrape_beli/extract_captions.py
python scrape_beli/ocr_images.py
python scrape_beli/filter_new_posts.py        # optional incremental filter
python scrape_beli/add_post_context.py
python scrape_beli/merge_and_finalize.py      # phase 4-6: merge + US filter
python scrape_beli/dedupe_by_handle.py
python scrape_beli/dedupe_final.py
python scrape_beli/clean_data.py
```

Uses Apify for IG fetching and Claude (`claude-haiku-4-5-20251001`) for
caption/OCR extraction. Outputs are gitignored (`raw_posts_*.json`,
`candidates_*.json`, `images/`).

## Postprocessing helpers — `postprocess/`

Each is a standalone script that takes a CSV in and produces a CSV out —
none modify the input. Run from the repo root as
`python postprocess/<script>.py ...` (each script puts the repo root on
`sys.path` so `config`/`discover` imports resolve).

- **`postprocess/detect_clubs.py` / `detect_clubs_v2.py`** — concurrent website scraping (default 50 threads) to flag businesses with an existing club/subscription program. Adds `has_club`, `club_type`, `club_url`, `club_signals`. Supports `--resume` to continue from a partial output.
- **`postprocess/reclassify.py`** — re-buckets leads using Google Maps `type` (`output/type_lookup.csv`) + name/page_title heuristics into `partner_type` (fine: destination_restaurant, neighbourhood_restaurant, butcher, wine, cheese, bakery, fish, deli, specialty_grocer, books, farm) and `business_type_v2` (coarse: restaurants | wine | retail | other). Includes a "wine bar claw-back" pass.
- **`postprocess/reclassify_clubs.py`** — same idea, scoped to flagged club rows.
- **`postprocess/backfill_type.py` / `backfill_type_clubs.py`** — fill `business_type` on older CSVs that predate the canonical schema.
- **`postprocess/clean_directories.py` / `clean_awards.py` / `clean_clubs_sales_ready.py`** — schema normalization, dedupe, and last-mile cleanup before handoff.
- **`postprocess/dedupe_existing.py`** — phone-first, then name+address dedupe on any CSV.
- **`postprocess/sample_clubs_for_qa.py` / `sample_clubs_for_sales.py`** — sample N rows for review or sales handoff.
- **`postprocess/apply_edge_case_verdicts.py`** — fold manual QA verdicts back into a CSV.

`scripts/` holds one-off run scripts from past lead-gen waves (fresh
discovery sweeps, recovery jobs, wave merges). They follow the same
`ROOT`-on-`sys.path` pattern and are kept for reference/re-runs, not as
maintained pipelines.

## `config.py`

Single central config (~1200 lines):

- API keys via `python-dotenv`
- Apify actor IDs
- Search queries by business type
- City list (~385 cities)
- `SCORING_WEIGHTS` (SHAP-aligned — see design notes)
- `CHAIN_KEYWORDS` + liquor-license filter keywords (aggressive on purpose)
- Press domains, reservation platform rankings
- `BUSINESS_TYPE_MAP` — maps search categories (`butcher_premium`, `butcher_local`) to canonical types (`butcher`)
- `TYPE_TO_PARTNER_TYPE`, `PARTNER_TO_BUSINESS_TYPE`, `NAME_HEURISTIC_RULES` — used by `reclassify.py`

## Output conventions

- All CSVs land in `output/` (gitignored).
- Per-source: `<slug>_<YYYYMMDD>.csv`.
- Per-pipeline master: `<pipeline>_all_<YYYYMMDD>.csv`.
- Generic-pipeline intermediates: phase-numbered (`1_discovered.csv`, `2_enriched_*.csv`).
- Final scored output: `custom-serper-scoring_<owner>_<YYYYMMDD>_<verticals>_<count>_<all|top>.csv`.

**Always date-stamp new output files** (`YYYYMMDD` in the filename). Never
overwrite source CSVs in-place — write a new file. If a script needs to
clear/rewrite rows on an existing CSV, back up first.

## Design notes

- **SHAP-aligned weights.** Scoring weights come from a prior model run.
  Don't change weights without understanding the SHAP context.
- **`reservation_difficulty`** is a composite: 40% platform signal, 35%
  review-text sentiment, 25% real-time availability — not a simple lookup.
- **`follower_count`** is IG followers + FB likes, computed in
  `enrich_facebook()`.
- **Chain filtering is aggressive** by design. `CHAIN_KEYWORDS` includes
  non-food chains that show up in Maps results.
- **`--enrich-remaining`** exists so pipeline interruptions don't re-burn
  expensive Apify jobs.
- **Existing club programs are a positive signal**, not a disqualifier —
  proven demand makes Table22 a switch-the-platform sale rather than a
  cold-start. `detect_clubs.py` exists to surface these, not filter them
  out.
- **`AGENTS.md`** mirrors this file for Codex. Update both when changing
  developer-facing instructions.
