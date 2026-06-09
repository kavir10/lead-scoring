# lead-scoring

Lead discovery, enrichment, and scoring for **Table22**. The repo finds
independent food businesses — restaurants, butchers, wine shops, bakeries,
cheesemongers, specialty grocers — and ranks them as subscription-program
prospects.

```
discovery sources ──► canonical lead CSV ──► (optional) enrich ──► (optional) score
```

There is **no single pipeline**. The repo is a collection of source-specific
discovery pipelines that all emit rows into a shared schema, plus a generic
Serper-based discover → enrich → score loop. Every pipeline writes its CSVs
into `output/` (gitignored).

**New here? Two paths:**

1. **Point-and-click** — set up once (below), then run `python -m webui` and
   build a lead list from your browser. No CLI knowledge needed.
2. **CLI** — run the pipelines directly. Each one is documented below.

---

## Setup (one time)

```bash
git clone <this repo> && cd lead-scoring
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # only needed for Playwright-backed scrapers
```

Create a `.env` file in the repo root with your API keys:

```
SERPER_API_KEY=...        # required for discovery (serper.dev)
APIFY_API_TOKEN=...       # required for enrichment (apify.com)
ANTHROPIC_API_KEY=...     # required for LLM-extraction scrapers
```

| Key                 | Used by                                               |
|---------------------|-------------------------------------------------------|
| `SERPER_API_KEY`    | Google Maps/Web discovery, press & awards search      |
| `APIFY_API_TOKEN`   | Instagram, Google Reviews, OpenTable, Beli scraping   |
| `ANTHROPIC_API_KEY` | LLM extraction in `awards/`, `best_wine_shops/`, Beli |

> Gotcha: if your shell already exports an **empty** `ANTHROPIC_API_KEY`
> (a Claude Desktop side-effect), `.env` won't override it. Prefix commands
> with `unset ANTHROPIC_API_KEY &&`.

---

## The web UI — create a lead list from your browser

```bash
source .venv/bin/activate
python -m webui            # then open http://127.0.0.1:8722
```

The UI lets anyone create a new lead list without touching the CLI:

- **Discover only** — pick business types (butcher, wine, bakery, …), cap the
  number of cities/searches for a cheap test run, and get
  `output/1_discovered.csv`. Uses only the Serper key.
- **Full pipeline** — discover → 8 enrichment steps → scored A/B/C/D list.
  Slow and uses paid Apify credits; best run overnight.
- **Enrich / Score an existing CSV** — resume from any CSV already in
  `output/`.
- Watch live logs for each run, stop runs, and download any output CSV.

The server binds to `127.0.0.1` only — it works exclusively on the machine
where the repo is installed and is **not** meant to be deployed anywhere.
Run state and logs live in `output/webui_runs/`.

---

## Repo map

```
main.py                     # generic 3-phase pipeline (the one the web UI wraps)
discover.py / enrich.py / score.py
config.py                   # API keys, search queries, ~385 cities, scoring weights, blocklists

webui/                      # localhost browser UI for building lead lists

awards/                     # ~40 award/editorial sources, one module each
discover_awards.py          #   orchestrator        → docs/AWARDS.md is the catalog
directories/                # non-award sources (Raisin, importer stockists, Substacks)
discover_directories.py     #   orchestrator
best_wine_shops/            # "best wine shops in America" editorial scraper
butcher.py / butcher_sources.py / discover_butchers.py   # standalone butcher vertical
discover_michelin_direct.py # standalone Michelin pipeline
scrape_beli/                # Beli IG post mining (run modules in order)
jobs/ / scarcity/ / social_graph/   # experimental lead-signal lanes

postprocess/                # CSV-in → CSV-out cleanup helpers (see below)
scripts/                    # one-off run scripts from past lead-gen waves

docs/                       # AWARDS catalog, ICP definition, strategy notes
output/                     # ALL pipeline outputs land here (gitignored)
```

---

## Pipelines

### 1. Generic Serper discover → enrich → score (`main.py`)

The flagship pipeline (and what the web UI drives). Searches Serper Maps
across ~385 US cities, enriches through 8 sequential steps, scores with
SHAP-aligned weights.

```bash
python main.py                                          # full pipeline
python main.py --discover --types butcher,wine          # discovery only
python main.py --discover --max-searches 50             # cheap smoke test
python main.py --enrich  output/1_discovered.csv        # enrich an existing CSV
python main.py --enrich-from reviews output/2_enriched_full.csv   # resume mid-enrichment
python main.py --score   output/2_enriched_availability.csv
```

Discovery dedupes by phone, filters chains, and applies quality floors.
Enrichment checkpoints a CSV after every step so interruptions are cheap.
Scoring outputs an `_all.csv` plus a `_top.csv` filtered to A+B tiers
(A 55+, B 35+, C 20+, D <20). Full step list in `CLAUDE.md`.

### 2. Awards & editorial sources (`awards/` + `discover_awards.py`)

~40 award sources (James Beard, Michelin, Eater, Wine Spectator, Good Food
Awards, …) across six categories. One module per source under
`awards/<category>/<slug>.py`, each exposing `scrape() -> DataFrame` in the
shared schema.

```bash
python discover_awards.py --source james_beard
python discover_awards.py --category bakery
python discover_awards.py --tier 1
python discover_awards.py --all
```

Catalog and per-source status: `docs/AWARDS.md`. Michelin runs standalone via
`discover_michelin_direct.py`.

### 3. Directories & stockists (`directories/` + `discover_directories.py`)

Non-award sources: curated directories (Raisin), importer "where to buy"
stockist mining, restaurant Substacks. Same orchestrator shape as awards.

```bash
python discover_directories.py --list
python discover_directories.py --source raisin_app
python discover_directories.py --all
```

### 4. Best wine shops (`best_wine_shops/`)

Scrapes editorial "best wine shops in America" articles (7 curated seeds +
Serper-discovered articles), extracting shops with Claude.

```bash
python -m best_wine_shops.discover
python -m best_wine_shops.discover --dry-run
```

### 5. Butcher source-scrape (`discover_butchers.py`)

Standalone butcher vertical that skips Google/Serper entirely — scrapes Good
Meat Finder, EatWild, Good Food Awards, AGA, and stockist pages, with
banned-state filtering.

```bash
python discover_butchers.py
```

### 6. Beli posts (`scrape_beli/`)

Mines `@beli_eats` Instagram posts for restaurant mentions. Run the modules
in the order listed in `CLAUDE.md` (fetch → captions → OCR → merge → dedupe).

---

## Postprocessing helpers (`postprocess/`)

Standalone CSV-in → CSV-out scripts. None of them modify their input file.
Run from the repo root, e.g. `python postprocess/detect_clubs.py input.csv`.

| Script | What it does |
|---|---|
| `detect_clubs.py` / `detect_clubs_v2.py` | Crawl websites to flag existing club/subscription programs (`has_club`, `club_type`, `club_url`) — a *positive* signal for Table22 |
| `reclassify.py` / `reclassify_clubs.py` | Re-bucket leads into `partner_type` + `business_type_v2` using Google Maps types + name heuristics |
| `backfill_type.py` / `backfill_type_clubs.py` | Backfill the Google Maps `type` field on older CSVs |
| `clean_awards.py` / `clean_directories.py` / `clean_clubs_sales_ready.py` | Schema normalization, dedupe, last-mile cleanup before handoff |
| `dedupe_existing.py` | Phone-first, then name+address dedupe on any CSV |
| `sample_clubs_for_qa.py` / `sample_clubs_for_sales.py` | Sample N rows for QA or sales handoff |
| `apply_edge_case_verdicts.py` | Fold manual QA verdicts back into a CSV |

---

## Output conventions

- Everything lands in `output/` (gitignored).
- Per-source files: `<slug>_<YYYYMMDD>.csv`. Master unions: `<pipeline>_all_<YYYYMMDD>.csv`.
- Generic-pipeline intermediates are phase-numbered (`1_discovered.csv`, `2_enriched_*.csv`).
- Final scored lists: `custom-serper-scoring_<owner>_<YYYYMMDD>_<verticals>_<count>_<all|top>.csv`.
- **Always date-stamp new outputs; never overwrite a source CSV in place.**

## More docs

- `CLAUDE.md` — developer-level detail on every pipeline (also the AI-assistant guide)
- `docs/AWARDS.md` — award source catalog and status
- `docs/ICP.md` — who counts as a Table22 prospect
- `docs/LEAD_LIST_STRATEGY.md` — strategy notes behind the lanes
