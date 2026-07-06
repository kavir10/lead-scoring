# AGENTS.md

Guidance for Codex and other coding agents when working in this repo. This
file is a mirror of `CLAUDE.md` — the two are kept identical apart from this
header; update both when changing developer-facing instructions.

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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # pinned versions (see top of the file)
playwright install chromium          # for Playwright-backed sources
cp .env.example .env                 # then fill in keys
python tests/smoke_test.py           # validate env/config/imports — no API calls
```

`make setup` does the venv + install + Chromium + `.env` seed in one step, and
`make test` runs the smoke test. `make help` lists the shortcuts.

`.env` keys: `SERPER_API_KEY`, `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY` (each
optional depending on the pipeline — see `.env.example` for who needs what).

If your shell sets an empty `ANTHROPIC_API_KEY` (Claude Desktop side-effect),
prefix scripts with `unset ANTHROPIC_API_KEY &&` — `load_dotenv()` will not
override an existing empty var. Same applies to any script importing the
`anthropic` SDK.

> **Before trusting output or refactoring, read [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md)** —
> it catalogs confirmed bugs (e.g. reservation scoring never fires), fragile
> scrapers, and run-specific scripts. Referenced inline below where relevant.

## Pipelines

### Generic Serper pipeline — `main.py`

Three phases, orchestrated end-to-end or piecewise:

```bash
python main.py                                              # full pipeline
python main.py --discover                                   # phase 1 only
python main.py --discover --types butcher,wine              # valid: neighbourhood_restaurant,butcher,wine,bakery,cheese,fish,deli,specialty_grocer
python main.py --discover --max-searches 50
python main.py --discover --max-cities 5                    # limit to first N cities
python main.py --discover --merge output/1_discovered.csv   # union with existing
python main.py --enrich output/1_discovered.csv             # phase 2 only
python main.py --enrich-from reviews output/2_enriched_*.csv  # resume mid-phase-2
python main.py --enrich-remaining output/2_enriched_reviews.csv  # reels+posts+availability
python main.py --score output/2_enriched_availability.csv   # phase 3 only
```

**Phase 1 — Discovery (`discover.py`).** Serper Maps across ~385 US cities
(`config.CITIES`), 190 keyword queries across 12 categories. Dedupes by phone,
filters chains via `CHAIN_KEYWORDS` in `config.py`, applies quality floors
(restaurants: ≥50 reviews / ≥4.2 rating; niche: ≥20 / ≥4.0), requires a
website. ⚠️ The restaurant floor and the liquor-store filter key on
`business_type` values (`"restaurant"`, `"wine_store"`) that `BUSINESS_TYPE_MAP`
never produces, so in practice every lead gets the niche floor — see
`docs/KNOWN_ISSUES.md`.

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
plus a `_top.csv` filtered to A+B tier. ⚠️ Two tier tables exist
(restaurant A55+/B35+ vs. niche A45+/B25+/C15+), but because no lead ever has a
`business_type` in `RESERVATION_TYPES`, the niche table is always used and the
15-pt reservation weight never contributes — see `docs/KNOWN_ISSUES.md`.

### Awards — `awards/` + `discover_awards.py`

~43 editorial / award sources across restaurants, wine, bakery, cheese,
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

In practice **most sources use mode 3** (Serper to find URLs + Claude to
extract), so they cost money. `docs/AWARDS.md`'s per-source "Strategy" column
is partly stale; `ALL_SOURCES` in code is authoritative. Only
`discover_michelin_direct.py` and `--master-only` are free.

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
`candidates_*.json`, `images/`). ⚠️ Run `merge_and_finalize.py` **before**
`add_post_context.py`; `filter_new_posts.py` is a hard-coded one-off — see
`docs/KNOWN_ISSUES.md`.

### Wave 2 curation channels (experimental) — `jobs/`, `social_graph/`, `scarcity/`

Eight alternative discovery channels documented in `docs/strategies/01…08`.
Channels 03/04/06/07/08 are implemented as `directories/` sub-sources (`somm_*`,
`d2c_*`, `substack_*`, `cookbook_authors`, `distributor_*`). The other three are
standalone packages with the same schema/orchestrator shape as awards:

```bash
python discover_jobs.py --list          # jobs/: restaurants hiring wine/bev staff (Serper + HTML). --source/--all/--master-only
python discover_ig_graph.py --aggregate # social_graph/: venues tagged by ~51 seed chef/somm IG accounts (Apify). --fetch [--limit N|--handle H]
python -m scarcity.reservation_impossible --input output/2_enriched_availability.csv --limit 100  # scarcity/: unbookable venues (Apify+Resy)
```

Outputs land in `output/jobs/`, `output/social_graph/`, `output/scarcity/`.
These are **first-pass scaffolds** (guessed selectors, reverse-engineered APIs,
some doc drift, Tock unimplemented) — see `docs/KNOWN_ISSUES.md` before relying
on them.

### `scripts/` — run-specific & bulk helpers

~28 helpers built for specific past runs: `fresh_*_discovery.py` (Serper Maps
discovery per vertical), website/IG/FB augmentation (`crawl_*`, `augment_*`,
`apify_*_instagram_counts.py`), bulk crawls (`scrape_newsletter.py`,
`scrape_resy_tock.py` + their `recover_*`/`finalize_*`/`merge_*` siblings), and
"Wave 2" assembly (`build_wave2_master.py`, `clean_wave2_master.py`). Many
**hard-code dated input filenames** from one run — adapt, don't assume turnkey.
They reuse top-level modules (`score`, `enrich`, `config`, `backfill_type`).
Cost/orphan caveats are catalogued in `docs/KNOWN_ISSUES.md`.

### Analysis & reference (not lead generators)

- **`tam_calc.py`** — TAM calculator, prints tables to stdout. ⚠️ Hard-codes an
  absolute local input path and has no CLI/`__main__` guard — not portable
  as-is (see `docs/KNOWN_ISSUES.md`).
- **`research/trendy_neighborhoods/`** — finished research + reusable
  neighborhood CSVs to feed discovery searches. No runnable code.
- **`docs/lead-discovery-plan.html`** — browser-viewable strategy briefing.
  `docs/README.md` indexes all strategy/reference docs.

## Postprocessing helpers

Each is a standalone script that takes a CSV in and produces a CSV out —
none modify the input.

- **`detect_clubs.py` / `detect_clubs_v2.py`** — concurrent website scraping (default 50 threads) to flag businesses with an existing club/subscription program. Adds `has_club`, `club_type`, `club_url`, `club_signals`. Supports `--resume` to continue from a partial output.
- **`reclassify.py`** — re-buckets leads using Google Maps `type` (`output/type_lookup.csv`) + name/page_title heuristics into `partner_type` (fine: destination_restaurant, neighbourhood_restaurant, butcher, wine, cheese, bakery, fish, deli, specialty_grocer, books, farm) and `business_type_v2` (coarse: restaurants | wine | retail | other). Includes a "wine bar claw-back" pass.
- **`reclassify_clubs.py`** — same idea, scoped to flagged club rows.
- **`backfill_type.py` / `backfill_type_clubs.py`** — fill `business_type` on older CSVs that predate the canonical schema.
- **`clean_directories.py` / `clean_awards.py` / `clean_clubs_sales_ready.py`** — schema normalization, dedupe, and last-mile cleanup before handoff.
- **`dedupe_existing.py`** — phone-first, then name+address dedupe on any CSV.
- **`sample_clubs_for_qa.py` / `sample_clubs_for_sales.py`** — sample N rows for review or sales handoff.
- **`apply_edge_case_verdicts.py`** — fold manual QA verdicts back into a CSV.

## `config.py`

Single central config (~1200 lines):

- API keys via `python-dotenv`
- Apify actor IDs
- Search queries by business type (190 queries, 12 categories)
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
- **Testing is intentionally light.** `tests/smoke_test.py` is a
  dependency-free env/config/import check (no API calls) — run it after setup
  and after touching `config.py` or the registries. There is no unit-test
  suite.
- **Known bugs are flagged, not fixed.** `docs/KNOWN_ISSUES.md` documents the
  scoring/discovery `business_type` mismatch and other sharp edges. If you fix
  one, update that doc.
- **`CLAUDE.md`** is the canonical copy; this file mirrors it. Update both
  when changing developer-facing instructions.
