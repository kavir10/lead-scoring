# lead-scoring

Lead discovery, enrichment, and scoring pipelines for Table22. The repo finds
independent food businesses — restaurants, butchers, wine shops, bakeries,
cheesemongers, specialty grocers — and ranks them as subscription-program
prospects.

There is **no single pipeline**. The repo is a collection of source-specific
discovery pipelines that all emit rows into a shared schema, plus a generic
Serper-based discover → enrich → score loop for restaurants.

```
discovery sources ──► canonical lead CSV ──► (optional) enrich ──► (optional) score
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # only needed for Playwright-backed sources
cp .env.example .env            # if it exists; otherwise create one
```

`.env` keys used across the repo:

| Key                  | Used by                                                |
|----------------------|--------------------------------------------------------|
| `SERPER_API_KEY`     | Generic Serper Maps + Web discovery, press/awards      |
| `APIFY_API_TOKEN`    | Instagram, Google Reviews, OpenTable, Beli scraping    |
| `ANTHROPIC_API_KEY`  | LLM extraction in `awards/`, `best_wine_shops/`, Beli |

Note: if your shell sets `ANTHROPIC_API_KEY=` (empty) from Claude Desktop,
prefix Python invocations with `unset ANTHROPIC_API_KEY &&` — `load_dotenv()`
does not override an existing empty var.

## Pipelines

### 1. Generic Serper discovery → enrich → score (`main.py`)

The original pipeline. Searches Serper Maps across ~130 US cities, enriches
through 8 sequential steps, and scores with SHAP-aligned weights.

```bash
python main.py                                          # full pipeline
python main.py --discover --types butcher,wine_store    # discovery only
python main.py --enrich  output/1_discovered.csv        # enrich existing
python main.py --score   output/2_enriched_availability.csv
```

Tiered output: A (55+), B (35+), C (20+), D (<20). See `CLAUDE.md` for the
full step list and design notes.

### 2. Awards & editorial sources (`awards/` + `discover_awards.py`)

~40 award sources across restaurants, wine, bakery, cheese, butcher, and
specialty. One module per source under `awards/<category>/<slug>.py`, each
exposing `scrape() -> DataFrame`. Orchestrator iterates the registry in
`awards/__init__.py:ALL_SOURCES`.

```bash
python discover_awards.py --source james_beard
python discover_awards.py --category bakery
python discover_awards.py --tier 1
python discover_awards.py --all
python discover_awards.py --source nyt --cookies-from cookies/nyt.json
```

Outputs `output/awards/<slug>_<YYYYMMDD>.csv` per source plus a master union
at `output/awards_all_<YYYYMMDD>.csv`. Full catalog in `docs/AWARDS.md`.

### 3. Directories & stockists (`directories/` + `discover_directories.py`)

Non-award lead sources: curated directories (Raisin natural-wine app) and
"where to buy" backlink mining on premium importer sites.

```bash
python discover_directories.py --list
python discover_directories.py --source raisin_app
python discover_directories.py --all
```

Same shape as the awards orchestrator. Output: `output/directories/` +
`output/directories_all_<YYYYMMDD>.csv`.

### 4. Best wine shops (`best_wine_shops/`)

Self-contained scraper for editorial "best wine shops in America" articles
plus ~70 Serper-discovered articles on the same theme. httpx + selectolax
with a Playwright fallback when blocked, Claude for extraction.

```bash
python -m best_wine_shops.discover                       # full
python -m best_wine_shops.discover --no-search           # seed URLs only
python -m best_wine_shops.discover --max-per-query 3
python -m best_wine_shops.discover --dry-run
```

### 5. Butcher source-scrape (`butcher.py` + `discover_butchers.py`)

Standalone butcher vertical. Skips Serper/Google discovery and all
enrichment — scrapes alternative source lanes (Good Meat Finder, EatWild,
Good Food Awards, AGA, stockist pages) and applies banned-state filters.

```bash
python discover_butchers.py
```

Outputs into `output/butcher/`.

### 6. Beli posts (`scrape_beli/`)

Phased pipeline that mines `@beli_eats` Instagram posts for restaurant
mentions: fetch posts → extract captions → OCR images → merge → US-filter.
Run modules in order:

```bash
python scrape_beli/fetch_posts.py --limit 100
python scrape_beli/extract_captions.py
python scrape_beli/ocr_images.py
python scrape_beli/merge_and_finalize.py
```

## Postprocessing helpers

- `detect_clubs.py` / `detect_clubs_v2.py` — concurrent website scraping to flag businesses with an existing club/subscription program (adds `has_club`, `club_type`, `club_url`, `club_signals`)
- `reclassify.py` / `reclassify_clubs.py` — re-bucket leads with `partner_type` and `business_type_v2` using Google Maps `type` + name heuristics
- `backfill_type.py` / `backfill_type_clubs.py` — fill `business_type` on older CSVs
- `clean_directories.py` / `clean_awards.py` / `clean_clubs_sales_ready.py` — schema normalization and dedupe
- `dedupe_existing.py` — phone/name+address dedupe pass on any CSV
- `sample_clubs_for_qa.py` / `sample_clubs_for_sales.py` — sampling for review
- `apply_edge_case_verdicts.py` — apply manual QA verdicts back into a CSV

## Repo layout

```
main.py                    # generic 3-phase pipeline
discover.py / enrich.py / score.py
config.py                  # API keys, cities, scoring weights, blocklists

awards/                    # award-source modules + registry
discover_awards.py
docs/AWARDS.md             # catalog & status legend

directories/               # non-award sources (Raisin, stockists)
discover_directories.py

best_wine_shops/           # editorial mention scraper
butcher.py / butcher_sources.py / discover_butchers.py
scrape_beli/               # Beli IG post mining

detect_clubs*.py
reclassify*.py
backfill_type*.py
clean_*.py / sample_clubs_*.py / apply_edge_case_verdicts.py / dedupe_existing.py

output/                    # all CSVs land here (gitignored)
```

## Output conventions

All CSVs go to `output/`. Per-source CSVs are date-stamped `_<YYYYMMDD>`.
The generic pipeline's intermediate files are phase-numbered (`1_`, `2_`,
`3_`). Master union files are named `<source>_all_<YYYYMMDD>.csv`.
