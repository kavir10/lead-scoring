# Scraping & lead-run learnings

Read this before any discovery, scraping, enrichment, or list-building run.
When a run surfaces a new failure, add it here before closing the run
(format: what happened → evidence → rule). Keep entries short and concrete.

Sources: `docs/RESTAURANT_5K_RUN_LOG.md`, `docs/WINE_5K_RUN_LOG.md`, and the
whole-animal butcher run (2026-09-25, PR #21).

## Pre-flight checklist

1. `.env` exists in the repo root (or worktree root) with the keys the run
   needs. Check names only: `awk -F= '{print $1}' .env`. Don't copy keys from
   other projects' `.env` files; ask the user to add them.
2. Smoke-test on known exemplars first (the ICP anchors in `docs/ICP.md`).
   If an anchor fails your filter, decide whether that's correct *before* the
   full run, not after.
3. Smoke-test one Serper call and read the raw JSON for the fields you need.
4. Estimate API cost up front (calls × credits) and state it.
5. Save raw outputs so filters can be re-run with zero new API calls.

## Input lists

- **Hand/LLM-built lists have bad URLs.** The vault butcher ICP list
  (`Obsidian/table22/ICP - Premium Independent Butcher Shops.csv`) had
  238/1,059 (22%) website domains that don't resolve in DNS, plus internal
  duplicates (same shop listed twice, rebranded shops pointing at another
  shop's site). → Resolve every row to its Google Maps listing
  (`scripts/discover_whole_animal.py lookup`) and prefer the Maps website
  before crawling. Separate `dead_domain` (DNS fails) from `unreachable`
  (resolves but blocks) so they get different fixes.
- **A Maps "no match" often means closed.** 177/1,059 vault rows had no
  Maps match; spot checks (e.g. American Butcher, Birmingham) were closed.
  → Keep these out of sales lists unless the site shows current hours, and
  flag them.
- **Research tier labels ≠ evidence.** 780 vault rows were "Tier 1:
  whole-animal", but only 146 sites said so. → Re-verify claims from the
  business's own site; don't trust inherited labels.

## Serper Maps

- 3 credits per `/maps` call; max 20 results; **`page` is ignored** (page 2
  returns 0 rows). → Get coverage from query variety and finer locations
  (neighborhood files in `research/trendy_neighborhoods/`), not pagination.
  Big metros saturate at 20 results per query.
- Neighborhoods work either in the location field
  (`location="Bushwick, New York, NY, United States"`, restaurant/wine runs)
  or in the query (`q="butcher shop in Bushwick, New York NY"`).
- `discover.search_serper_maps` drops `openingHours`. Maps hours plus a
  street address are the best physical-storefront signal we have; use a
  call that keeps them (`scripts/discover_whole_animal.py:_search`).
- Serper can return permanently closed places; there's no closed check yet.
- Narrow craft queries under-yield. For butchers, "whole animal butcher" +
  "nose to tail butcher" (770 calls) gave 3,911 meat listings but only 27
  net-new final leads. Google doesn't filter by the claim, so a broad
  "butcher shop" sweep plus site verification finds more.
- In the sandbox, Serper can silently return zero rows (wine run). If a
  smoke test returns nothing, check the network before changing code.

## Crawling websites

- ~10% of live sites block plain `httpx` (403, Cloudflare, JS-only
  Squarespace/Wix). → Retry failures in headless Chromium
  (`verify_whole_animal.py` does this automatically). It recovered 46/103
  blocked vault sites.
- The homepage alone misses claims. Crawl linked about/story/farms/visit/
  hours pages (5 per site now).
- **One malformed href crashed the whole batch.** `urljoin` raised
  `ValueError: Invalid IPv6 URL` inside `asyncio.gather` and killed a
  4,324-row run. → Wrap per-link parsing in try/except and isolate
  exceptions per row; fill default columns for errored rows.
- **A dead headless browser hangs the run forever, and results written only
  at the end are lost.** An 8.6k-site verify stalled at 800/819 in the
  Chromium retry pass (browser process gone, Python at 0% CPU awaiting
  pages) and 30 minutes of crawling had to be redone. → Put a hard per-site
  timeout around every fetch (`asyncio.wait_for`), append each site's result
  to a JSONL checkpoint as it finishes, and make reruns resume from it
  (`verify_whole_animal.py --cache`, on by default). If a log line hasn't
  moved in 5+ minutes, check `ps` for the browser before waiting longer.
- **A network drop mid-run gets recorded as thousands of dead sites.** On
  2026-09-25 the laptop lost DNS during an 8.6k-site verify: 5,450 sites
  were cached as `unreachable`, only 1,230 came back `ok` (vs 3,271/4,324 on
  the earlier run), and the Apify step died on `impit.ConnectError: dns
  error`. → Never cache failures as final (retry `unreachable`/`error` on
  rerun); when a site fails, check a canary host and wait for the network
  instead of recording a verdict; checkpoint paid API batches (Apify)
  per item; run long jobs under `caffeinate -i` on macOS. Sanity-check the
  `ok` rate against the previous run before trusting results.
- Posted hours come in many formats: "Open now • Closes at 7PM",
  "Wednesday through Friday 4:00-10:00", "Tue - Sat 10-6", "Location & Hours".
  Regexes that require am/pm miss half of them. Prefer Maps hours.
- A site linking to `table22.com` is almost always an existing partner
  (McCall's, Publican Quality Meats, Beast and Cleaver...). Flag it
  (`links_table22`) so sales doesn't prospect current partners.

## Keyword claims (classification)

- **A keyword hit isn't a claim.** "whole animal" showed up in bulk sales
  ("buy a half or whole animal"), custom processing ("we process your whole
  animal"), merch ("Nose to Tail Hoodie"), dry-aging explainers ("hanging
  the whole animal"), SEO FAQ text, and chef bios on restaurant sites.
  "whole carcass" meant a wholesale box product. → Keep *all* matched
  snippets, grade them (strong / bulk / processing / weak), and only
  count "strong". Put the rest in a review file and don't drop them
  silently.
- Test grading regexes against real snippets from the run before trusting
  them. Two real shops were missed on phrasing: "products from the same
  whole animals" and "Whole Animal & Seafood Butchery".
- Famous ICP anchors don't always advertise the ICP trait. McCall's, Publican
  Quality Meats, and Dai Due don't say "whole animal" on their sites.
  Confirm with the user whether "advertises X" is the rule or "is X".
- Restaurant-type Maps listings match on chef bios. → Count a restaurant
  listing only if its name says butcher/meat/salumeria/charcuterie.
- Farms and meat shares crowd directory sources (EatWild is ~90% farms).
  Exclude by Maps type (farm, ranch, livestock) and name (Farm(s), Ranch,
  Acres, Cattle Co), not by "Homestead" (Homestead Meats is a real shop).

## Chains, venues, franchises (restaurant run)

- Chains rank high because review volume drives score. `CHAIN_KEYWORDS` had no
  upscale restaurant brands. → Extend chain lists per vertical and collapse
  any domain that appears ≥4× (chains share a root domain across locations).
- Reject `/locations/<slug>` franchise URLs, hotel/resort outlets, `.edu`,
  and Google types like Banquet hall / Event venue / Winery / Hotel / Brewery.

## Dedupe

- **`pandas.drop_duplicates(subset=[col])` treats NaN as one value.** All
  rows with a blank CID collapsed into one, silently dropping real shops.
  → Dedupe only non-null keys:
  `df[df.cid.isna() | ~df.cid.duplicated()]`.
- Dedupe on CID first, then website domain, then domain+address. A row
  without a Maps address duplicates any row sharing its domain. Keep
  distinct addresses for real multi-location shops.
- New sweeps overlap heavily with existing lists (646/3,911 were already in
  the vault). Always dedupe new against existing before verifying, to save
  crawl time.

## Environment

- **macOS deletes old files under `/private/tmp`.** A worktree, venv, and
  `.env` in the Claude scratchpad (`/private/tmp/claude-*/…/scratchpad`) lost
  `pyvenv.cfg`, the worktree `.git` link, `.env`, and two uncommitted script
  edits between 2026-09-25 and 09-30. → For any run that may span days, put
  the worktree outside `/tmp` (e.g. `~/Downloads/lead-scoring-wt/<thing>`),
  commit and push after each working change, and copy outputs out of the
  scratchpad as soon as they're produced.

- `apify_client` 2.x `actor().call()` returns a `Run` object, not a dict:
  `run["defaultDatasetId"]` raises `TypeError`. Use `run.default_dataset_id`
  (or handle both). Pass `logger=None` to stop the actor log flooding output.

- macOS has no `timeout` command. Use the tool's timeout or background jobs.
- `load_dotenv()` with no path fails from `python - <<EOF` stdin scripts
  (`find_dotenv` assertion). Pass an explicit path: `load_dotenv(".env")`.
- An empty `ANTHROPIC_API_KEY` in the shell beats `.env` (see CLAUDE.md).
- Full crawl of ~4.3k sites at concurrency 32 plus a Chromium retry took
  about 30–40 minutes. Run it in the background and check the log.

## Yield benchmarks (for scoping asks)

| Run | Screened | Final | Rate |
|---|---|---|---|
| Butcher, whole-animal claim + storefront, no farms/shares (2026-09-25) | 3,271 reachable sites | 108 | 3.3% |
| Wine, strict ICP (2026-06) | ~10.5k accepted candidates | 3,209 strict | — |
| Restaurant net-new (2026-06) | 192k raw Maps rows | 5,000 | — |

For a target N under a strict claim-based rule, plan to screen ~30×N
reachable sites.
