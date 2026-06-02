# Wine 5K Lead Run Log

Date: 2026-06-02
Branch: `codex/wine-5k-leads`

## ICP Read

Read `docs/ICP.md` before running. Wine-specific constraints applied:

- Prioritize wine-focused retail shops, not wine bars.
- Suppress wineries/vineyards, pure online retailers, chains, big-box stores, liquor-store-like rows, and commodity-brand signals.
- Treat existing club, email signup, ecommerce, Instagram, press/awards, and wine-directory/best-of source membership as positive signals.
- Keep rating/review floors for non-prestige rows; prestige-directory rows can survive sparse public data.

## Branch / Commit Checkpoint

Committed existing butcher/ICP work on `codex/butcher-5k-run`:

- Commit: `d1ae635` (`Add ICP docs and fresh butcher discovery tools`)

Created new wine branch:

- Branch: `codex/wine-5k-leads`

## Scripts Added

- `scripts/build_wine_leads.py`
  - Builds a wine-store lead list from existing corpora and fresh wine discovery files.
  - Applies ICP-aligned rejection reasons and dedupes by phone, website host, then name/city/state.
  - Writes ranked candidates, rejected candidates, QA sample, summary, and top lead CSVs under `output/fresh_wine_leads_20260602/`.

- `scripts/fresh_wine_discovery.py`
  - Runs wine-only Serper Maps discovery.
  - Uses narrower retail queries: `wine store`, `wine shop`, `independent wine shop`, `natural wine shop`, `wine merchant`, etc.
  - Writes fresh raw and candidate CSVs for the builder to consume.

## Runs

### Existing Sources Only

Command:

```bash
.venv/bin/python scripts/build_wine_leads.py --limit 5000
```

Result:

- Loose first pass reached 5000, but QA showed false positives near the top (venues, bookstores, bakeries, restaurants).
- After tightening wine-retail evidence, existing default sources produced `2,429` strict accepted rows.

### Expanded Legacy Sources

Command included:

- `output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all_clubs_v2.reclassified_20260422.csv`
- `output/fresh_icp_search_tiered_abcd_7761_20260601_033726.csv`
- `output/wine_directories_cleaned_20260515_dedup.csv`
- `output/best_wine_shops/best_wine_shops_20260525_dedup.csv`
- `output/1_wine_new_to_enrich.csv`
- `output/clubs_sales_ready_combined_20260422_cleaned.csv`
- `output/clubs_working_sales_list_20260422.csv`
- `output/3_scored_all_combined_final.csv`

Result:

- `2,691` strict accepted deduped rows.

### Fresh Serper Smoke Test

Sandboxed network returned zero rows. Escalated network run succeeded.

Command:

```bash
.venv/bin/python scripts/fresh_wine_discovery.py --max-searches 20 --workers 8 --rps 5
```

Result:

- Raw rows: `395`
- Candidate rows: `21`
- Candidate Google types: mostly `Wine store`

### Fresh Serper 3,000-Search Pass

Command:

```bash
.venv/bin/python scripts/fresh_wine_discovery.py --max-searches 3000 --workers 30 --rps 20
```

Result:

- Raw rows: `49,556`
- Candidate rows before final builder: `1,726`
- Candidate file: `output/fresh_wine_leads_20260602/fresh_wine_serper_candidates_1726_20260602_113512.csv`
- Most candidate Google types:
  - `Wine store`: `1,315`
  - `Wine wholesaler and importer`: `112`
  - `Wine storage facility`: `49`
  - Long tail included beer/bar/convenience/noisy rows for final filtering.

### Strict Merge With Fresh Candidates

Command:

```bash
.venv/bin/python scripts/build_wine_leads.py --limit 5000 --sources \
  output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all_clubs_v2.reclassified_20260422.csv \
  output/fresh_icp_search_tiered_abcd_7761_20260601_033726.csv \
  output/wine_directories_cleaned_20260515_dedup.csv \
  output/best_wine_shops/best_wine_shops_20260525_dedup.csv \
  output/1_wine_new_to_enrich.csv \
  output/clubs_sales_ready_combined_20260422_cleaned.csv \
  output/clubs_working_sales_list_20260422.csv \
  output/3_scored_all_combined_final.csv \
  output/fresh_wine_leads_20260602/fresh_wine_serper_candidates_1726_20260602_113512.csv
```

Result:

- Final rows: `2,917`
- Accepted deduped rows: `2,917`
- Rejected rows: `18,811`
- Final with website: `2,427`
- Final with email signup: `1,266`
- Final with club signal: `242`
- Final with Instagram: `861`
- Median rating: `4.7`
- Median review count: `83`

Output files:

- `output/fresh_wine_leads_20260602/wine_leads_top_2917.csv`
- `output/fresh_wine_leads_20260602/wine_candidates_ranked.csv`
- `output/fresh_wine_leads_20260602/wine_candidates_rejected.csv`
- `output/fresh_wine_leads_20260602/wine_leads_qa_sample.csv`
- `output/fresh_wine_leads_20260602/summary.json`

## Current Read

Under strict ICP filters, the current workspace evidence supports `2,917` accepted deduped wine-store leads, not 5000. A looser 5000-row file can be produced, but QA showed that loosened filtering admits obvious non-wine-store false positives.

To continue toward 5000, choose one:

- Keep strict ICP and accept that the available US wine-store universe may be closer to 3k than 5k without including liquor stores, wineries, wine bars, or low/no-footprint rows.
- Expand to lower-confidence wine retail candidates: allow missing websites, 10-19 review rows, some wine-and-beer hybrids, and rows needing human QA.
- Spend more API calls on long-tail locations/directories, knowing the 3,000-search pass added only `226` net strict accepted rows after dedupe.

## Continuation: Remaining Wine Searches

Added `--skip-searches` to `scripts/fresh_wine_discovery.py` and ran the remaining query/location combinations after the first 3,000 tasks.

Command:

```bash
.venv/bin/python scripts/fresh_wine_discovery.py --skip-searches 3000 --workers 30 --rps 20
```

Result:

- Raw rows: `56,043`
- Candidate rows before final builder: `1,882`
- Candidate file: `output/fresh_wine_leads_20260602/fresh_wine_serper_candidates_1882_20260602_114513.csv`

Strict merge with both fresh candidate files:

- Final strict rows: `3,003`
- This confirms the strict, deduped, wine-store-evidenced corpus is roughly 3k with the current sources/searches.

## Expanded 5,000-Row Working List

Added `--expanded` to `scripts/build_wine_leads.py`.

Expanded mode ranks rows in three confidence bands:

- `strict`: ICP-filtered wine-store evidence.
- `expanded`: wine-retail evidence with a controlled caveat, such as low review count, missing website, hybrid wine shop/bar, or rating exception.
- `prospecting_tail`: wine-query provenance but not verified enough to call ICP-clean; these rows are marked `qa_required=True`.

Command:

```bash
.venv/bin/python scripts/build_wine_leads.py --expanded --limit 5000 --sources \
  output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all_clubs_v2.reclassified_20260422.csv \
  output/fresh_icp_search_tiered_abcd_7761_20260601_033726.csv \
  output/wine_directories_cleaned_20260515_dedup.csv \
  output/best_wine_shops/best_wine_shops_20260525_dedup.csv \
  output/1_wine_new_to_enrich.csv \
  output/clubs_sales_ready_combined_20260422_cleaned.csv \
  output/clubs_working_sales_list_20260422.csv \
  output/3_scored_all_combined_final.csv \
  output/fresh_wine_leads_20260602/fresh_wine_serper_candidates_1726_20260602_113512.csv \
  output/fresh_wine_leads_20260602/fresh_wine_serper_candidates_1882_20260602_114513.csv
```

Result:

- Final rows: `5,000`
- Output: `output/fresh_wine_leads_20260602/wine_leads_top_5000.csv`
- Accepted deduped rows available behind the top file: `10,010`
- Final by mode:
  - `strict`: `3,003`
  - `expanded`: `611`
  - `prospecting_tail`: `1,386`
- Final with website: `4,342`
- Final with email signup: `2,672`
- Final with club signal: `648`
- Final with Instagram: `2,134`
- Median rating: `4.7`
- Median review count: `99`

QA note:

- The 5,000-row file is a working prospecting list, not 5,000 ICP-clean wine shops.
- `prospecting_tail` rows must be QA'd before sales use. Spot checks show some high-rated restaurants, wineries, and other wine-query false positives still appear in this tail.
- For a sales-ready wine-store list, use `wine_list_mode in {"strict", "expanded"}` first; that yields `3,614` rows.
