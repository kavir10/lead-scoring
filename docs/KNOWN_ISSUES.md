# Known issues, fragile code & run-specific scripts

A honest inventory of things that are broken, silently no-op, approximate, or
hard-wired to a specific past run. **Nothing here has been "fixed"** — this
document exists so operators don't trust a number that the code can't actually
produce, and so a future engineer knows where the sharp edges are.

Legend: 🔴 **bug** (produces wrong/no output silently) · 🟠 **fragile**
(works today, breaks easily) · 🟡 **run-specific** (hard-coded to a past run) ·
⚪ **stale docs** (comment/doc disagrees with code).

_Last reviewed: 2026-07-06._

---

## Generic pipeline (`main.py` / `discover.py` / `enrich.py` / `score.py`)

- 🔴 **Reservation scoring never fires for any lead.** `score.py` gates the
  15-point reservation weight on `business_type in {"restaurant", "wine_bar"}`
  (`score.py:188`), but discovery only ever tags leads with
  `BUSINESS_TYPE_MAP` values (`neighbourhood_restaurant`, `wine`, `butcher`, …
  — `config.py`). Those two literals are **never produced**, so:
  - `reservation_difficulty` and `booking_availability_score` contribute
    **0 points to every score**, even though the OpenTable/Resy enrichment
    still *costs money* to collect.
  - Tiering always uses the looser "niche" thresholds (A≥45/B≥25/C≥15); the
    restaurant thresholds (A≥55/B≥35 quoted in older docs) are unreachable.
  - The stricter restaurant discovery quality floor (≥50 reviews / ≥4.2
    rating) also never applies — every lead uses the niche floor (≥20 / ≥4.0).
  - The liquor-store filter keys on `business_type == "wine_store"` (also never
    produced), so it never fires.
- 🔴 **Invalid `--types` example in help text.** `main.py:164` suggests
  `--types butcher,wine_store`; `wine_store` matches nothing. Correct value is
  `wine`. (This README and CLAUDE.md now use the correct values.)
- ⚪ **Wine award keywords are dead.** `enrich.py` adds wine-specific award
  search terms only when `business_type == "wine_store"` — never true — so
  wine shops get only generic award keywords.
- ⚪ **Unused Google-Reviews config.** `APIFY_ACTOR_GOOGLE_REVIEWS` and
  `GOOGLE_REVIEWS_MAX_PER_PLACE = 30` are imported but unused; reviews are
  actually fetched via Serper with a hard-coded `num: 10`.
- ⚪ **Wrong "next step" message.** `main.py:229` tells you to open
  `3_top_leads_*.csv`, which is never written — the real file is
  `custom-serper-scoring_..._top.csv`.
- 🟠 **Resy availability is reverse-engineered** and self-flagged fragile
  (`config.py`); it silently no-ops without `RESY_API_KEY`.

## Awards (`discover_awards.py` / `awards/`)

- 🟡 **`nyt` and `decanter` always produce 0 rows** unless you pass
  `--cookies-from`; no `cookies/` directory ships with the repo.
- 🔴 **`michelin` awards source is empty until you run Michelin first.** It
  reads the latest `output/michelin_direct_us_*.csv`; run
  `python discover_michelin_direct.py --us` first. Note it looks for the `_us_`
  scope specifically — a `--smoke` output file won't be picked up.
- ⚪ **`docs/AWARDS.md` "Strategy" column is stale.** Many sources listed as
  free "Playwright" scrapers are actually implemented as Serper+Claude (so they
  cost money). The doc also references module filenames that don't exist
  (`jbf_wine.py`, `fabi.py`, `sofi.py`, `regional_best_of.py`, …); the real
  registry is `awards/__init__.py:ALL_SOURCES`, which is authoritative.
- ⚪ **Stubs that always return empty:** `michelin_grape`, `american_cmi`.
- 🟠 **Double-scrape in `--all`:** `jbf_bakery` re-invokes `james_beard`, and
  `wine_enthusiast_retailer` re-invokes `wine_enthusiast_star`, so those
  upstream Serper+Claude scrapes run twice.
- ⚪ **Dead Playwright code** in `awards/restaurants/james_beard.py`
  (`_scrape_search_page`, ~90 lines) is never called.

## Directories (`discover_directories.py` / `directories/`)

- 🔴 **Broken example in the file's own docstring:** it shows
  `--source stockist_louis_dressner`, but that source is intentionally *not*
  registered (Louis/Dressner has no public stockist page). Use
  `--source stockist_zev_rovine` instead.
- 🟠 **A "0 rows" source usually means breakage, not "no leads."** The
  orchestrator swallows import/scrape errors and writes an empty CSV, so
  selector/URL drift looks like an empty result. Check the console log.

## Beli (`scrape_beli/`)

- 🟡🔴 **`filter_new_posts.py` is a hard-coded one-off.** It reads
  `raw_posts_200.json` / `raw_posts_800.json` (which don't exist) and has no
  CLI args — it will crash for general use. It's optional; skip it.
- ⚪ **Dead LLM dependency in `merge_and_finalize.py`** — imports and builds an
  Anthropic client + `MODEL` it never uses, so it needs the `anthropic` package
  installed even though it makes no LLM calls.
- ⚪ **Doc order is wrong in older docs:** `add_post_context.py` must run
  *after* `merge_and_finalize.py` (it appends to that CSV). The README ordering
  is correct.

## Butcher (`butcher.py`)

- ⚪ **`butcher.py` is unused by the run path.** `discover_butchers.py` imports
  only `butcher_sources.py`. `butcher.py`'s city-loader and rationale builder
  are never called, and `BANNED_STATES` is duplicated across both files (edit
  both if you change it).

## Experimental scaffolds (`jobs/`, `social_graph/`, `scarcity/`)

These arrived together in the "Scaffold scrapers for Wave 2" commit — they run
and are defensively coded, but are first-pass.

- 🟠 **`jobs/` HTML scrapers use guessed CSS selectors** (`culinary_agents`,
  `poached`) that likely won't match live markup → expect 0 rows until tuned.
  ⚪ docstrings say "30-metro panel" but `DEFAULT_METROS` has 25.
- 🟠 **`scarcity/reservation_impossible.py`:** OpenTable date handling is an
  explicit approximation; **Tock is documented but not implemented** (only
  Resy + OpenTable URLs are scored); default input
  `output/2_enriched_availability.csv` won't exist on a clean checkout.
- ⚪ **`social_graph/` doc drift:** raw JSON actually lands in a `raw/`
  subdirectory (docstring says otherwise); the "≥3 frequency / ≥18 quality"
  rule in the docstring is the *tier-1* bar, not the inclusion cutoff.

## Analysis scripts

- 🔴 **`tam_calc.py` is not portable.** It hard-codes an absolute input path
  under `/Users/kavir/Downloads/...`, has no CLI args, and no `__main__`
  guard (runs on import). It will `FileNotFoundError` for anyone else until the
  path becomes a repo-relative file or CLI argument.

## `scripts/` — run-specific helpers (🟡)

Most are pinned to a specific past run and won't work turnkey; adapt them:

- `build_wave2_master.py` / `clean_wave2_master.py` — scoped to the 2026-05-25
  "Wave 2" run, with hand-curated keep/drop whitelists.
- `augment_butcher_facebook.py` / `augment_butcher_instagram.py` — hard-code
  `fresh_butcher_leads_20260531` / `_20260601` filenames (two-step chain).
- `apify_all_instagram_counts.py` / `apify_missing_instagram_counts.py` —
  hard-code `fresh_bakery_leads_20260525` + specific dated files; "missing"
  looks superseded by "all".
- `backfill_type_esp.py` — thin ESP-scoped shim over `backfill_type.py`;
  hard-codes `newsletter_signal_clean_20260531.csv`.
- `recover_lost_resy_tock.py` / `scrape_resy_tock.py` — read seed files
  (`lost_to_recover.csv`, `seed_52k.csv`) that no committed script builds;
  those universes were assembled manually/externally.
- `build_bakery_leads.py` / `build_wine_leads.py` / `build_newsletter_seed.py`
  — default to a 2026-04 corpus CSV (under gitignored `output/`, so absent on a
  clean checkout — supply your own).
