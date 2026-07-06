# lead-scoring

Tools that build **ranked lists of independent food & drink businesses**
(restaurants, butchers, wine shops, bakeries, cheesemongers, specialty
grocers) as Table22 subscription-program prospects. You run a command, it
writes a spreadsheet (CSV) into the `output/` folder, and you work it
top-down.

This README is written for the **person running the tools to get lead
lists** — you do not need to be able to read the code. If you *are* modifying
the code, read [`CLAUDE.md`](CLAUDE.md) as well.

> **There is no single "run everything" button.** The repo is a collection of
> independent discovery pipelines, each pulling leads from a different source.
> You pick the one that matches the leads you want. They all write CSVs with
> the same core columns, so their outputs can be combined later.

---

## ⚠️ Read this before running anything

1. **Most pipelines cost money per run** (Serper search credits, Apify
   scraping credits, Claude API usage). Cost is marked on every pipeline
   below with these icons:

   | Icon | Meaning |
   |------|---------|
   | 🟢 **Free** | Only downloads public web pages. No metered API. |
   | 🟡 **Serper** | Spends Google-search credits (cheap, ~$0.001/search — but discovery does *tens of thousands* of them). |
   | 🔴 **Apify** | Spends scraping credits, billed **per result**. The biggest cost driver in the repo. |
   | 🔵 **Claude** | Spends Anthropic API tokens (LLM reads articles / images). |

2. **Always run the "smoke test" command first.** Every pipeline below lists
   a tiny, cheap (or free) command that proves your setup works — API keys,
   internet, dependencies — *before* you launch a full run that could cost
   real money. If the smoke test fails, fix that first.

3. **Nothing is overwritten.** Output files are date-stamped and land in
   `output/` (which is not committed to git). Re-running on the same day
   overwrites *that day's* file only.

4. **Some code is known-fragile or run-specific.** See
   [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) before relying on a number.

---

## One-time setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies (pinned versions, for reproducibility)
pip install -r requirements.txt

# 3. Install the headless browser (needed by some scrapers)
playwright install chromium

# 4. Add your API keys
cp .env.example .env
#    ...then open .env and paste in your keys.

# 5. Check everything works (no API keys or spend required)
python tests/smoke_test.py
```

You must `source .venv/bin/activate` in **every new terminal** before running
a pipeline.

### Which keys does each pipeline need?

Fill in only the keys for the pipelines you plan to run (see `.env.example`).
A pipeline that is missing a key it needs will either skip that step or fail
fast — it will not silently make things up.

| Key | Needed by |
|-----|-----------|
| `SERPER_API_KEY`  | Generic pipeline discovery/press, awards, directories, best-wine-shops, job-boards |
| `APIFY_API_TOKEN` | Generic pipeline enrichment (Instagram/reviews/reels/availability), Beli, IG-graph, some `scripts/` |
| `ANTHROPIC_API_KEY` | Awards (LLM sources), best-wine-shops, Beli |

> **Claude Desktop gotcha:** if your shell already exports an *empty*
> `ANTHROPIC_API_KEY`, the tools can't read the real one from `.env`. Prefix
> the command with `unset ANTHROPIC_API_KEY &&` in that case.

---

## Which pipeline should I run?

| I want leads from… | Run this | Cost |
|--------------------|----------|------|
| Google Maps, scored & ranked (restaurants + niche food retail) | [Generic pipeline](#1-generic-pipeline-google-maps--enrich--score-mainpy) | 🟡🔴 |
| "Best of" / award lists (Michelin, James Beard, VinePair…) | [Awards](#2-awards--editorial-lists-discover_awardspy) | 🔵🟡 (Michelin: 🟢) |
| Curated directories & importer "where to buy" pages | [Directories](#3-directories--stockists-discover_directoriespy) | 🔵🟡 (Raisin: 🟢) |
| "Best wine shops in America" editorial articles | [Best wine shops](#4-best-wine-shops-best_wine_shops) | 🔵🟡 |
| Butchers (specialty meat directories, no Google) | [Butcher lane](#5-butcher-lane-discover_butcherspy) | 🟢 |
| Restaurants mentioned by the @beli_eats account | [Beli](#6-beli-instagram-mining-scrape_beli) | 🔴🔵 |
| Restaurants actively hiring wine/beverage staff | [Job boards](#7-job-boards-experimental-discover_jobspy) | 🟡 |
| Venues tagged by famous chefs/sommeliers on Instagram | [IG social graph](#8-instagram-social-graph-experimental-discover_ig_graphpy) | 🔴 |
| Hard-to-book "reservation impossible" restaurants | [Reservation scarcity](#9-reservation-scarcity-experimental-scarcityreservation_impossiblepy) | 🔴 |

Everything below assumes you have run `source .venv/bin/activate` first.

---

## Pipelines

### 1. Generic pipeline: Google Maps → enrich → score (`main.py`)

**What it does.** Searches Google Maps (via Serper) for food businesses
across 385 US cities, throws away chains / duplicates / low-quality places,
then *enriches* each survivor with website, Instagram, Facebook, press,
reviews, and reservation signals, and finally *scores* each lead 0–100 and
sorts them into A/B/C/D tiers. This is the original, most complete pipeline.

It runs in three phases you can run together or separately:

```bash
# Full pipeline (discover → enrich → score). EXPENSIVE — see smoke test first.
python main.py

# Phase 1 only — discovery. Writes output/1_discovered.csv
python main.py --discover
python main.py --discover --types butcher,wine        # limit to certain types
python main.py --discover --max-cities 5              # limit to first 5 cities
python main.py --discover --max-searches 100          # cap total searches

# Phase 2 only — enrich an existing discovery CSV, then score
python main.py --enrich output/1_discovered.csv
python main.py --enrich output/2_enriched_full.csv --enrich-from reviews  # resume mid-way
python main.py --enrich-remaining output/2_enriched_reviews.csv           # just the tail steps

# Phase 3 only — score an already-enriched CSV (FREE, no API calls)
python main.py --score output/2_enriched_availability.csv
```

Valid `--types` values: `neighbourhood_restaurant`, `butcher`, `wine`,
`bakery`, `cheese`, `fish`, `deli`, `specialty_grocer`.

**🧪 Smoke test first (≈1 Serper search):**
```bash
python main.py --discover --types butcher --max-searches 5
```
Then validate scoring is free and works on the result:
```bash
python main.py --score output/1_discovered.csv    # or any 2_enriched_*.csv
```

**Cost.** 🟡 Discovery = one Serper Maps search per (query × city). A full,
unfiltered discovery is ~190 queries × 385 cities ≈ **73,000 searches** — so
*always* narrow it with `--types` / `--max-cities`. 🔴 Enrichment is the
expensive phase: roughly **3 Serper searches per lead** plus **up to 3 Apify
scrapes per lead that has an Instagram**. Scoring is free.

**Output.** `output/1_discovered.csv`, then a checkpoint CSV per enrichment
step (`output/2_enriched_*.csv`), then the scored files:
`custom-serper-scoring_<owner>_<YYYYMMDD>_<verticals>_<count>_all.csv` (every
lead) and `…_top.csv` (A + B tier only — this is the one you hand to sales).

**Reading the output** — the columns you'll care about most:

| Column | Meaning |
|--------|---------|
| `lead_score` | 0–100 overall fit score |
| `tier` | `A - Hot Lead` / `B - Warm Lead` / `C - Worth a Look` / `D - Low Priority` |
| `name`, `address`, `city`, `state`, `phone`, `website` | contact basics |
| `follower_count` | Instagram followers + Facebook likes combined |
| `press_mentions`, `awards_count` | earned-media signals |
| `has_email_signup`, `has_ecommerce` | marketing sophistication signals |

> ⚠️ There is a known scoring quirk affecting restaurants — see
> [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

---

### 2. Awards & editorial lists (`discover_awards.py`)

**What it does.** Turns published "best of" / award lists (Michelin, James
Beard, Eater, VinePair, etc.) into lead rows — one per recognized business.
~43 sources across restaurants, wine, bakery, cheese, butcher, and specialty.

```bash
python discover_awards.py --source james_beard
python discover_awards.py --category bakery        # restaurants|wine|bakery|cheese|butcher|specialty
python discover_awards.py --tier 1                 # 1 = most prestigious
python discover_awards.py --all                    # every source (EXPENSIVE)
python discover_awards.py --source nyt --cookies-from cookies/nyt.json   # paywalled sources
python discover_awards.py --master-only            # rebuild the union CSV, no scraping

# Michelin is a separate, self-contained scraper (no API keys needed):
python discover_michelin_direct.py --us
```

**🧪 Smoke test first (free, no keys):**
```bash
python discover_michelin_direct.py --smoke
```
This scrapes one Michelin page with the browser only — it proves your
environment (venv + Chromium) works with zero spend.

**Cost.** 🔵🟡 Almost every award source uses Serper (to find the article
URLs) **and** Claude (to read each article) — so `--all` fires hundreds of
searches and hundreds of LLM calls. 🟢 Exceptions: `discover_michelin_direct.py`
and `--master-only` are free.

**Output.** `output/awards/<slug>_<YYYYMMDD>.csv` per source +
`output/awards_all_<YYYYMMDD>.csv` (union). Full source catalog:
[`docs/AWARDS.md`](docs/AWARDS.md).

---

### 3. Directories & stockists (`discover_directories.py`)

**What it does.** Finds leads from public "lists of businesses" rather than
awards: curated directories (the Raisin natural-wine map), importer/distributor
"where to buy" pages, sommelier rosters, cookbook-author bios, and food-writer
Substacks.

```bash
python discover_directories.py --list              # show all sources (free)
python discover_directories.py --source raisin_app
python discover_directories.py --category wine     # wine|restaurants|meat|cheese|seafood|specialty
python discover_directories.py --all               # EXPENSIVE
python discover_directories.py --master-only       # rebuild union, no scraping
```

**🧪 Smoke test first (free — Raisin is a public data feed):**
```bash
python discover_directories.py --list
python discover_directories.py --source raisin_app
```

**Cost.** 🟢 `raisin_app`, `somm_*`, `--list`, `--master-only` are free.
🔵🟡 Most other sources (distributors, cookbook authors, all `substack_*`)
use Serper and/or Claude; `--all` runs hundreds of LLM calls.

**Output.** `output/directories/<slug>_<YYYYMMDD>.csv` +
`output/directories_all_<YYYYMMDD>.csv`.

---

### 4. Best wine shops (`best_wine_shops/`)

**What it does.** Harvests "Best Wine Shops in America" editorial articles (7
hand-picked seeds + ~110 Serper-discovered articles), reads each with Claude,
and extracts the independent wine shops named. Tags big/online-only players.

```bash
python -m best_wine_shops.discover                 # full run
python -m best_wine_shops.discover --no-search     # 7 seed articles only
python -m best_wine_shops.discover --max-per-query 3
python -m best_wine_shops.discover --dry-run       # print the plan, spend nothing
```

**🧪 Smoke test first (free):**
```bash
python -m best_wine_shops.discover --dry-run
```

**Cost.** 🔵🟡 Every article fetched → 1 Claude call; every search → Serper.
A full run reads ~100+ articles.

**Output.** `output/best_wine_shops/best_wine_shops_<YYYYMMDD>.csv`, with extra
`is_large_indie` and `is_online_only` flag columns.

---

### 5. Butcher lane (`discover_butchers.py`)

**What it does.** A standalone butcher-lead finder that **skips Google/Serper
and all enrichment**. It scrapes curated meat directories (Good Meat Finder,
EatWild, Good Food Awards, AGA) and ~26 heritage-meat brand "where to buy"
pages, then filters out states Table22 can't ship to.

```bash
python discover_butchers.py        # no flags; always runs the full curated list
```

**🧪 Smoke test.** There is no smaller-run flag, but this pipeline is
**🟢 free** (public web pages only), so the full command *is* the safe test.
Watch the per-source status table it prints — some source pages break over
time and will show `error` or 0 rows.

**Cost.** 🟢 Free. No paid APIs.

**Output.** `output/butcher/1_discovered_butchers.csv` (the deduped list),
plus timestamped raw/snapshot/status CSVs.

---

### 6. Beli Instagram mining (`scrape_beli/`)

**What it does.** Mines the `@beli_eats` Instagram account for restaurant
mentions — reading both captions and the carousel images (which often show
ranked lists as on-image text) — and turns them into a clean, US-only,
deduped lead CSV.

Run the modules **in this order** (each writes a file the next one reads; keep
the `--limit` number consistent across steps):

```bash
python scrape_beli/fetch_posts.py --username beli_eats --limit 100
python scrape_beli/extract_captions.py --input scrape_beli/raw_posts_100.json
python scrape_beli/ocr_images.py --raw scrape_beli/raw_posts_100.json --captions scrape_beli/candidates_captions_100.json
python scrape_beli/merge_and_finalize.py --captions scrape_beli/candidates_captions_100.json --ocr scrape_beli/candidates_ocr_100.json --out scrape_beli/beli_leads.csv
python scrape_beli/add_post_context.py --raw scrape_beli/raw_posts_100.json --csv scrape_beli/beli_leads.csv
python scrape_beli/dedupe_by_handle.py --input scrape_beli/beli_leads.csv --output scrape_beli/beli_leads_dedup.csv
python scrape_beli/dedupe_final.py --input scrape_beli/beli_leads_dedup.csv --output scrape_beli/beli_leads_final.csv
python scrape_beli/clean_data.py --input scrape_beli/beli_leads_final.csv --output scrape_beli/beli_leads_clean.csv
```

> Order note: run `merge_and_finalize.py` **before** `add_post_context.py`
> (the latter appends columns to the CSV the former creates).

**🧪 Smoke test first (smallest paid pull):**
```bash
python scrape_beli/fetch_posts.py --username beli_eats --limit 1
python scrape_beli/extract_captions.py --input scrape_beli/raw_posts_1.json
python scrape_beli/ocr_images.py --raw scrape_beli/raw_posts_1.json --captions scrape_beli/candidates_captions_1.json
python scrape_beli/merge_and_finalize.py --captions scrape_beli/candidates_captions_1.json --ocr scrape_beli/candidates_ocr_1.json --out scrape_beli/smoke.csv --skip-websites
```

**Cost.** 🔴 `fetch_posts.py` (Apify, scales with `--limit`) and
`merge_and_finalize.py` (Apify profile scraper — skip with `--skip-websites`).
🔵 `extract_captions.py` (1 Claude call/post) and `ocr_images.py` (1 Claude
*vision* call **per carousel slide** — usually the biggest LLM cost). The
dedupe/clean steps are free.

**Output.** Intermediate `raw_posts_*.json` / `candidates_*.json` are
gitignored; the final CSVs are written where you point `--output`.

---

### 7. Job boards (experimental) (`discover_jobs.py`)

**What it does.** Finds restaurants **actively hiring** wine/beverage staff
(sommelier, wine director, beverage director) as a buying-intent signal, by
scraping five hospitality job boards.

```bash
python discover_jobs.py --list            # list the 5 sources (free)
python discover_jobs.py --source job_indeed_serper
python discover_jobs.py --all
python discover_jobs.py --master-only
```

**🧪 Smoke test first (free):** `python discover_jobs.py --list`

**Cost.** 🟡 Three of the five sources use Serper; two crawl HTML for free.

**Output.** `output/jobs/<slug>_<YYYYMMDD>.csv` + `output/jobs_all_<YYYYMMDD>.csv`.

> **Experimental:** these scrapers use guessed page selectors and may return 0
> rows until tuned. See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

---

### 8. Instagram social graph (experimental) (`discover_ig_graph.py`)

**What it does.** Starts from ~51 famous chefs/sommeliers on Instagram, pulls
their recent posts, and rolls up the venues they tag — surfacing restaurants
the industry repeatedly references.

```bash
python discover_ig_graph.py --aggregate            # roll up already-fetched posts (free)
python discover_ig_graph.py --fetch --limit 1      # cheap paid test: 1 seed
python discover_ig_graph.py --fetch --aggregate    # full run (COSTS $ per seed)
```

**🧪 Smoke test first (free):** `python discover_ig_graph.py --aggregate`
(prints a friendly "run fetch first" message if nothing is cached).

**Cost.** 🔴 `--fetch` uses Apify at ~$0.02/seed. Aggregation is free.

**Output.** `output/social_graph/somm_chef_ig_graph_<YYYYMMDD>.csv` (+ cached
raw JSON under `output/social_graph/raw/`).

> **Experimental** — see [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

---

### 9. Reservation scarcity (experimental) (`scarcity/reservation_impossible.py`)

**What it does.** Takes an already-enriched restaurant list and probes their
Resy/OpenTable pages over 30 days; flags venues that are essentially
unbookable as high-demand prospects.

```bash
python -m scarcity.reservation_impossible --input output/2_enriched_availability.csv --limit 100
```

**Cost.** 🔴 Apify (OpenTable) + reverse-engineered Resy API.

**Output.** `output/scarcity/reservation_impossible_<YYYYMMDD>.csv`.

> **Experimental** (OpenTable date handling is approximate; Tock not
> implemented) — see [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).

---

## Postprocessing helpers

Run *after* discovery to clean, classify, dedupe, or sample a lead CSV. Each
takes a CSV in and writes a **new** CSV out (never edits the input in place).

- **`detect_clubs.py` / `detect_clubs_v2.py`** — crawl websites to flag
  businesses that already run a club/subscription program (a *positive*
  signal — proven demand). Adds `has_club`, `club_type`, `club_url`,
  `club_signals`. Supports `--resume`.
- **`reclassify.py` / `reclassify_clubs.py`** — re-bucket leads into
  `partner_type` (fine-grained) and `business_type_v2` (coarse) using Google
  Maps type + name heuristics.
- **`backfill_type.py` / `backfill_type_clubs.py`** — fill `business_type` on
  older CSVs that predate the current schema.
- **`clean_directories.py` / `clean_awards.py` / `clean_clubs_sales_ready.py`**
  — schema normalization, dedupe, and last-mile cleanup before handoff.
- **`dedupe_existing.py`** — phone-first, then name+address dedupe.
- **`sample_clubs_for_qa.py` / `sample_clubs_for_sales.py`** — sample N rows.
- **`apply_edge_case_verdicts.py`** — fold manual QA verdicts back into a CSV.

## `scripts/` — run-specific & bulk helpers

The `scripts/` folder holds ~28 helpers built for specific past lead runs
(fresh discovery by vertical, website/Instagram/Facebook augmentation, bulk
newsletter & reservation-link crawls, "Wave 2" channel assembly). Many hard-code
dated input filenames from a particular run, so treat them as **references you
adapt**, not turnkey commands. See [`CLAUDE.md`](CLAUDE.md) and
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) for the catalog and caveats.

## Analysis & reference (not lead generators)

- **`tam_calc.py`** — total-addressable-market calculator (prints tables).
  ⚠️ Currently hard-codes a local input-file path — see
  [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md).
- **`research/trendy_neighborhoods/`** — finished research + neighborhood
  lists you can feed into discovery searches.
- **`docs/`** — strategy write-ups. Start at [`docs/README.md`](docs/README.md).

---

## Output conventions

- All CSVs land in `output/` (gitignored — not committed).
- Per-source files are date-stamped: `<slug>_<YYYYMMDD>.csv`.
- Per-pipeline union files: `<pipeline>_all_<YYYYMMDD>.csv`.
- Generic-pipeline intermediates are phase-numbered: `1_discovered.csv`,
  `2_enriched_*.csv`.
- Final scored file:
  `custom-serper-scoring_<owner>_<YYYYMMDD>_<verticals>_<count>_<all|top>.csv`.

## More documentation

- [`docs/README.md`](docs/README.md) — index of all strategy & reference docs.
- [`docs/AWARDS.md`](docs/AWARDS.md) — the awards source catalog.
- [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) — known-fragile / broken /
  run-specific code, and the scoring quirks. **Read before trusting a number.**
- [`CLAUDE.md`](CLAUDE.md) — developer/agent reference (architecture, every
  module). Mirrored for Codex in [`AGENTS.md`](AGENTS.md).
