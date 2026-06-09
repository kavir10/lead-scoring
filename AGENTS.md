# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What This Is

Lead scoring pipeline for Table22 that finds, enriches, and scores independent food businesses (restaurants, butchers, wine stores, bakeries) as potential subscription program leads. Three-phase pipeline: Discover -> Enrich -> Score.

## Running the Pipeline

```bash
# Activate venv first
source .venv/bin/activate

# Full pipeline
python main.py

# Individual phases
python main.py --discover                          # Phase 1 only
python main.py --discover --types butcher,wine     # Specific business types (values of BUSINESS_TYPE_MAP)
python main.py --discover --max-searches 50        # Cap API calls
python main.py --discover --merge output/1_discovered.csv  # Merge with existing
python main.py --enrich output/1_discovered.csv    # Phase 2 from existing CSV
python main.py --enrich-remaining output/2_enriched_reviews.csv  # Resume enrichment (reels, posts, availability)
python main.py --score output/2_enriched_availability.csv  # Phase 3 only
```

Install dependencies: `pip install -r requirements.txt`

## Web UI (`webui/`)

`python -m webui` serves a localhost-only browser UI (default
`http://127.0.0.1:8722`) that wraps the same `main.py` CLI as subprocesses:
discover / full pipeline / enrich / score, with live logs and CSV downloads.
FastAPI backend in `webui/server.py`, static frontend in `webui/static/`.
Run state and logs persist in `output/webui_runs/`. It binds `127.0.0.1` on
purpose — never expose it externally.

## Architecture

### Three-Phase Pipeline (`main.py` orchestrates)

**Phase 1 - Discovery (`discover.py`):** Searches Serper Maps API across ~385 US cities with keyword queries per business type. Deduplicates by phone number, filters chains (extensive blocklist in `config.py`), applies quality floors (restaurants: 50+ reviews/4.2+ rating; niche: 20+ reviews/4.0+), requires website.

**Phase 2 - Enrichment (`enrich.py`):** Sequential enrichment steps, each saving an intermediate CSV to `output/`:
1. **Websites** (2a) - Concurrent crawl (10 threads) for ecommerce, email signup, social links, reservation platforms
2. **Instagram** (2b) - Apify profile scraper in batches of 30
3. **Facebook** (2c) - HTML scraping for follower counts; computes combined `follower_count` (IG + FB)
4. **Press & Awards** (2d) - Serper web search against food media domains + award keywords
5. **Google Reviews** (2e) - Apify Google Maps Reviews scraper; analyzes review text for reservation difficulty keywords
6. **Instagram Reels** (2f) - Apify IG Reel scraper for video view counts
7. **Instagram Posts** (2g) - Apify IG Post scraper for engagement metrics
8. **Booking Availability** (2h) - OpenTable (Apify) and Resy API for reservation scarcity

**Phase 3 - Scoring (`score.py`):** Weighted scoring (100 points total) using SHAP-aligned weights defined in `config.py:SCORING_WEIGHTS`. Outputs tiered leads: A (55+), B (35+), C (20+), D (<20).

### Configuration (`config.py`)

Central config for everything: API keys (from `.env`), Apify actor IDs, search queries by business type, city list, scoring weights, chain/liquor filter keywords, press domains, reservation platform rankings. The `BUSINESS_TYPE_MAP` maps search categories (e.g., `butcher_premium`, `butcher_local`) to canonical types (`butcher`).

### Output Files

All outputs go to `output/` directory. Intermediate CSVs are numbered by phase (`1_`, `2_`, `3_`). Scored files include timestamps. The `--enrich-remaining` flag exists to resume enrichment mid-pipeline without re-running expensive earlier steps.

### Repo Layout

Beyond the generic pipeline, discovery lanes live in their own packages
(`awards/`, `directories/`, `best_wine_shops/`, `scrape_beli/`, butcher
files) with `discover_*.py` orchestrators at the root. CSV-in → CSV-out
cleanup helpers live in `postprocess/` (run as
`python postprocess/<script>.py` from the repo root); one-off historical run
scripts live in `scripts/`. See `CLAUDE.md` for the full per-pipeline detail
— that file is the source of truth and this one mirrors it.

## External APIs & Costs

- **Serper** (Maps + Web search) - discovery + press/awards. Rate limited with exponential backoff.
- **Apify** - Instagram profiles, Instagram reels, Instagram posts, Google Reviews, OpenTable. Batched to avoid timeouts.
- **Resy** - Reverse-engineered API for reservation availability (may break).

API keys loaded from `.env` via python-dotenv.

## Key Design Decisions

- Scoring weights are SHAP-aligned from a prior analysis model. Don't change weights without understanding the SHAP context.
- `reservation_difficulty` is a composite score (40% platform signal, 35% review sentiment, 25% availability) — not a simple lookup.
- `follower_count` is a combined metric (IG followers + FB likes), computed in `enrich_facebook()`.
- Chain filtering is aggressive by design. The `CHAIN_KEYWORDS` list in config.py is extensive and includes non-food chains that appear in Maps results.
- `--enrich-remaining` was added to handle pipeline interruptions without re-running costly Apify jobs.
