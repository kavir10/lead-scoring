# Lead Engine 31 — Wine Inventory Distinctiveness

**Motion:** Curation (an inventory-based ICP classifier for the wine universe; pairs with a Trigger engine for outbound timing)
**Vertical fit:** Wine shops (curated indie / natural / fine-wine bottle shops; explicitly NOT liquor or grocery-wine)
**Suggested list name(s):** `wine_inventory_distinctiveness`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run

## Premise

For wine, the dominant ICP question is "curated bottle shop vs commodity liquor
store?" — and the cleanest evidence isn't the website copy or the IG feed (both
thin and gameable for indie shops), it's **what's actually on the shelf**.
Wine-Searcher indexes per-merchant offers across tens of thousands of retailers:
which producers a shop lists, at what price, and in what depth. A shop's offer
catalog is a near-unfakeable curation fingerprint — you cannot list Selection
Massale growers and Zev Rovine imports by accident, and you cannot hide a wall of
Josh / Cupcake / Barefoot if that's what you sell.

This maps directly to the two-score model's **ICP Fit** half. Wine is the #2
partner type by Peak AGMV ($68.2k), so a clean, correctly-classified wine list is
high value — but only if liquor/commodity leakage is filtered hard *before* sales
ever sees it (high-trigger / weak-ICP is the exact failure we filter, not
nurture). Inventory distinctiveness is the strongest available ICP proxy when
social and site signals are thin, which for indie wine is most of the time. It is
deliberately **not** a Trigger — it says "this is the right kind of business," and
should be unioned with a trigger engine (07 club-transition, 19 OOS, 15 cult
product) to produce a both-high list.

A secondary payoff: the same offer data exposes **online ordering / e-commerce
depth** (offer count, in-stock breadth), which corroborates that the shop can
actually transact recurring orders — a precondition for a Table22 club.

## Recipe

Wine-Searcher has no public bulk API in this repo's stack; treat it like the
`best_wine_shops/` lane — httpx + selectolax happy path, Playwright fallback when
blocked, polite throttling, and Claude only for ambiguous extraction. The engine
is a **classifier over the existing wine universe**, not a fresh discovery scrape.

1. **Assemble the candidate universe (reuse, don't re-scrape).** Union the latest:
   - `best_wine_shops/` (`output/best_wine_shops/best_wine_shops_<YYYYMMDD>.csv`)
   - `directories/wine/raisin_app` and importer-stockist modules under
     `directories/wine/` (`stockist_zev_rovine`, `stockist_jenny_francois`, …)
   - any `partner_type == wine` rows from the enriched corpus (`output/2_enriched_*.csv`)
   - optional top-up: `discover.py` Serper Maps `wine_store` over `config.CITIES`,
     niche floors (≥20 reviews / ≥4.0), website required, `config.CHAIN_KEYWORDS`.
   Dedupe with `dedupe_existing.py` (phone-first, then name+address).

2. **Resolve each shop to its Wine-Searcher merchant page.** Wine-Searcher hosts a
   per-merchant store page listing that retailer's offers. Resolve via a Serper Web
   query (`google.serper.dev/search`, the same client the press step uses):
   `site:wine-searcher.com/merchant "<shop name>" <city> <state>`. Cache the
   resolved merchant URL on the row; unresolved shops fall through to a website-only
   fallback (step 5).

3. **Pull the offer catalog.** For each resolved merchant page, fetch the offer
   list (httpx+selectolax; Playwright fallback on block). Capture per offer:
   producer/wine name, region/grape if shown, price. Compute per shop:

```
offer_count        = number of distinct listed offers
producer_set       = set of producers/labels parsed
median_price       = median(offer price)         # price-tier proxy
distinct_regions   = count of distinct wine regions among offers
```

4. **Score inventory distinctiveness.** Match `producer_set` against curated lists
   (config knobs, below). The respected-importer / natural-wine list is the
   positive signal; the commodity-SKU list is the negative signal.

```
IMPORTER_TRUST = ["skurnik","louis/dressner","dressner","jenny & francois",
                  "selection massale","zev rovine","rosenthal","polaner",
                  "vom boden","t. edward","jose pastor"]
NATURAL_GROWER = ["grower champagne","pét-nat","skin contact","pet nat",
                  "low intervention","biodynamic","small grower"]   # label/region cues
COMMODITY_SKUS = ["josh","cupcake","barefoot","kendall jackson","meiomi",
                  "duckhorn","bogle","j. lohr","yellowtail","apothic","andre",
                  "cloud break","veuve","tito's","smirnoff","buzzballz",
                  "michelob","budweiser"]

importer_hits    = |producer_set ∩ IMPORTER_TRUST|        # via name match on offers
commodity_count  = count of offers whose label ∈ COMMODITY_SKUS
commodity_ratio  = commodity_count / max(offer_count, 1)
curated_depth    = distinct_regions + (offers from small/grower producers)

distinctiveness_score:
  +3 importer_hits >= 2
  +2 importer_hits == 1
  +2 commodity_ratio < 0.05 AND curated_depth high (broad-region, low-commodity)
  +1 distinct_regions >= 8 (real depth, not a one-shelf grocery set)
  -3 commodity_ratio >= 0.25      # commodity-dominant catalog
  -5 hard liquor SKUs present (Tito's/Smirnoff/etc) AND importer_hits == 0
```

5. **Website fallback for unresolved / thin merchants.** Shops not on Wine-Searcher
   (or with sparse offers) fall back to the `enrich.py` **step-1 (websites)** crawl
   (10-thread) over an extended keyword set — same importer / natural-wine /
   commodity lexicon applied to the shop's own catalog pages and the `has_ecommerce`
   / `email_signup` flags. Lower confidence than offer data; flagged `signal_source`.

6. **Hard ICP gate (curation filter).** Run `reclassify.py` (keep
   `partner_type == wine`, honor the **wine-bar claw-back** — wine bars excluded
   except geographic-monopoly). Then drop liquor/commodity leakage:

```
DISQUALIFY if:
  name trips LIQUOR_DQ_NAME = ["liquor","wine & spirits","discount","warehouse",
      "package store","bevmo","total wine","abc"]
  OR ESP red flag (City Hive, Spot Hopper) on site footer/cart
  OR distinctiveness_score < 0 (commodity-dominant, no curation signal)
  OR chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
DEMOTE (cap Tier 2, do not DQ):
  no Wine-Searcher page AND website-only signal (understates curated brand)
  small-market shop with thin offer_count (weight relative local dominance)
QUALIFY (engine output) if: passes gate AND distinctiveness_score >= 2
```

7. **Join e-commerce / club corroborators.** Carry `has_ecommerce` / `email_signup`
   from step-1, and join `detect_clubs.py` (`has_club` — existing club is a POSITIVE
   switch signal, not a DQ). These don't change the ICP verdict; they sharpen tier
   and feed downstream trigger engines.

8. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). Partner
   Type = wine dominates; `distinctiveness_score` orders the outbound queue inside a
   tier. Emit standard `_all` + `_top` (A+B) handoff CSVs.

## Output schema

```
output/directories/wine_inventory_distinctiveness_<YYYYMMDD>.csv
source = "wine_inventory_distinctiveness"
tier = 1 (importer_hits>=2 or deep curated catalog) | 2 (single-signal / website-only) | 3 (ICP-soft)
business_type = "wine_store"
distinction = "Wine-Searcher catalog lists {importer_hits} trust importers, {commodity_ratio} commodity — curated bottle shop"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the curation proof in outbound):
    signal_source          # wine_searcher | website_fallback
    merchant_url           # resolved Wine-Searcher merchant page
    offer_count            # distinct offers listed
    importer_hits          # count of IMPORTER_TRUST producers matched
    importer_signals       # ["skurnik","zev rovine",...]
    natural_signals        # ["biodynamic","grower champagne",...]
    commodity_count        # commodity SKUs listed
    commodity_ratio        # commodity_count / offer_count
    distinct_regions       # catalog breadth proxy
    median_price           # price-tier proxy
    distinctiveness_score  # int, intra-tier outbound ordering
    has_ecommerce          # from enrich.py step-1
    email_signup           # from enrich.py step-1
    has_club, club_type, club_url, club_signals   # from detect_clubs.py (positive signal)
    liquor_dq_reason       # empty if kept; populated rows logged + excluded
    candidate_sources      # ["best_wine_shops","raisin_app","stockist_zev_rovine"]
```

Final scored handoff: `custom-serper-scoring_<owner>_<YYYYMMDD>_wine_<count>_<all|top>.csv`.

## Volume & cost

- Candidate universe (union, post-dedupe): ~1,500–2,500 curated US wine shops
  (heavy overlap across best_wine_shops + Raisin + stockists → ~2K unique).
- Wine-Searcher resolution: 1 Serper Web query per shop ≈ 2,000 queries ≈ **$6**
  (Serper ~ $0.003/query). Expect ~55–65% to resolve to a merchant page → ~1.2K.
- Offer-catalog pulls: free (httpx/selectolax, public pages, throttled); Playwright
  fallback on the ~10–15% blocked.
- Website fallback crawl (step 5) on unresolved ~800: free (step-1 thread crawl).
- Claude only on ambiguous label parsing (~few hundred rows, short prompts): **≈ $2–4**.
- detect_clubs join: free (rides existing 50-thread scrape).
- **Per-run total: ~$10–14** (under target; Serper resolution is the only metered cost).
- **Net-new qualified leads (first run):** of ~2K candidates, after liquor/commodity
  hard gate (~25–30% leak out) and `distinctiveness_score >= 2`, expect
  **~1,000–1,300 ICP-clean wine rows** with cited inventory evidence. Subsequent
  quarterly runs ~5–10% incremental (universe is small and slow-moving).

## Refresh cadence

**Quarterly.** Inventory distinctiveness is a structural ICP property, not a
time-sensitive trigger — a shop's importer book and curation posture change over
seasons, not days. Re-resolve merchant pages quarterly to catch new shops entering
the curated lists and to refresh offer breadth. Run the cheap `detect_clubs.py` +
`email_signup` join **monthly** on the ICP-clean set, since a club launch is the
event that flips one of these high-ICP rows into a both-high outbound target.

## Risks

- **Liquor-store leakage is the dominant failure mode.** The whole engine exists to
  prevent it; the commodity-SKU + ESP (City Hive, Spot Hopper) + name gate must run
  before scoring. Audit a 30-row QA sample (`sample_clubs_for_qa.py`) each run.
- **Wine-Searcher coverage gaps under-count curated shops.** Many great indie shops
  don't list on Wine-Searcher at all — a missing merchant page is **no-signal, not a
  negative**. Route to the website fallback and demote (cap Tier 2), never DQ.
- **Offer staleness.** Wine-Searcher offers can lag a shop's real shelf; a one-time
  commodity listing shouldn't tank an otherwise curated catalog. Gate the −5 hard
  penalty on `importer_hits == 0` so a single stray SKU doesn't DQ a real shop.
- **Producer-name matching is fuzzy.** Importer ≠ producer — Wine-Searcher lists the
  *wine*, not always the importer. `IMPORTER_TRUST` matching via offer labels is
  imperfect; the importer-stockist backlink lane (`directories/wine/`) remains the
  authoritative importer-shelf source — prefer it where it overlaps.
- **Wine-bar contamination.** Raisin and best-of lists include bars; enforce the
  `reclassify.py` claw-back, keep only geographic-monopoly bars.
- **Small-market metrics run low.** A great rural shop will show a thin
  `offer_count`; weight relative local dominance and importer depth, not raw breadth.
- **Static social understates indie wine brand** — this engine deliberately avoids
  social as an ICP gate; never DQ a curated catalog on low IG.
- **Platform fragility / rate limits.** Wine-Searcher will block aggressive httpx;
  throttle, jitter, fall back to Playwright, and treat blocks as no-signal rather
  than failing the row.

## Repo placement

Lives under `directories/wine/` (it's a curation classifier over the wine
universe, sibling to the stockist lanes), with a thin orchestrator mirroring the
existing `discover_*` shape. Reuses the `best_wine_shops/` fetch pattern and the
step-1 crawler as a library.

```
directories/
  wine/
    winesearcher_inventory.py     # NEW: resolve merchant page (Serper Web),
                                  #   pull offer catalog (httpx+selectolax,
                                  #   Playwright fallback), parse producer_set,
                                  #   compute distinctiveness_score
    inventory_signals.py          # NEW: IMPORTER_TRUST, NATURAL_GROWER,
                                  #   COMMODITY_SKUS, LIQUOR_DQ_NAME, ESP flags
scripts/
  discover_wine_inventory.py      # NEW orchestrator: union candidate sources,
                                  #   call winesearcher_inventory, website fallback,
                                  #   ICP gate (reclassify), detect_clubs join,
                                  #   write output/directories/wine_inventory_distinctiveness_<date>.csv
enrich.py                         # REFACTOR: expose step-1 `websites` keyword
                                  #   crawl as an importable fn so the website
                                  #   fallback reuses it with the wine lexicon
                                  #   (today it's wired into the sequential pipeline)
config.py                         # ADD: WINE_IMPORTER_LIST, WINE_NATURAL_CUES,
                                  #   WINE_COMMODITY_SKUS, WINE_LIQUOR_DQ_NAME knobs
                                  #   (shared with Engine 07 — define once)
```

`reclassify.py`, `detect_clubs.py`, `dedupe_existing.py`, `sample_clubs_for_qa.py`
are reused unchanged (CSV-in/CSV-out). The config knobs overlap with Engine 07's
proposed `WINE_*` lists — define them once and import in both.

## Open questions

1. **Wine-Searcher's anti-bot posture.** How aggressively does it block offer-page
   scraping at ~1–1.5K merchant pulls/run, and is Playwright fallback enough — or do
   we need cookie/session handling (like the `--cookies-from` award sources)?
2. **Merchant-page resolution accuracy.** How reliably does the
   `site:wine-searcher.com/merchant "<name>" <city>` Serper query land the right
   store vs a same-name collision? Do we need a name+address confirmation pass?
3. **Importer vs producer matching.** Wine-Searcher lists wines, not importers — is
   matching offer labels to `IMPORTER_TRUST` good enough, or should this engine lean
   primarily on the existing importer-stockist backlink lane and use Wine-Searcher
   only for commodity-leak detection + depth?
4. **Overlap with Engine 07.** Both classify the same wine universe for curation.
   Should this be a standalone list, or should its `distinctiveness_score` and
   `importer_hits` be merged onto Engine 07's rows as a stronger inventory-backed
   ICP signal feeding its transition/new-club routing?
