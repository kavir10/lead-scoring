# Lead Engine 19 — Shopify Out-of-Stock Pattern List

**Motion:** Hybrid (Curation-grade ICP gate + a quantified operational Trigger from structured stock data)
**Vertical fit:** Bakeries, butchers, wine, cheese, specialty grocers
**Suggested list name(s):** `shopify_out_of_stock_patterns`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $15/run (rides existing crawl; net-new cost is `/products.json` pulls + a small Claude classify pass)

## Premise

Engine 03 reads *human* scarcity language ("sold out by 9am"). This engine
reads the **machine-readable truth underneath it**: the Shopify
`/products.json` and per-product `/products/<handle>.js` endpoints expose every
variant's `available` flag, `inventory` state, price, and product type — no
login, no marketing copy, just the operator's live catalog state. A shop whose
JSON shows a high and *recurring* sold-out ratio on premium SKUs is publicly
broadcasting demand-over-capacity in structured data we can quantify and
re-measure over time.

This is the cleanest possible Trigger because it's first-party, current, and
*measurable as a rate* rather than a single mention. Repeated OOS = demand we
can capture on a recurring basis (the recurring-revenue ceiling is set by
capacity, not interest) **and** operational pressure (they're rationing finite
stock through a storefront that doesn't pre-sell or waitlist well). It maps
straight to the two-score model: a strong Trigger that also correlates with
**ICP Fit**, because the partner types that sell out finite premium product —
butcher $75.9k, wine $68.2k, cheese $63.8k, specialty/market $48.7k — are
exactly the high-AGMV verticals this engine targets.

It's a **Hybrid**: Shopify-on-a-food-domain is a decent ICP prior, but a liquor
store, a chain, or a hype-merch drop can all run Shopify with sold-out variants
too. The OOS rate is the Trigger; the ICP gate does the filtering. High-trigger
/ weak-ICP rows get dropped before sales, not nurtured.

## Recipe

Shopify detection already rides the `enrich.py` **step-1 (websites)** crawl
(10-thread, pulls ecommerce flag + social links). We add a Shopify-platform
detector to that parse layer, then a thin JSON-pull stage. The real innovation
is the **two-snapshot restock cadence** — one run can't prove recurrence, so we
persist a per-shop OOS history.

1. **Seed the universe.** Run over the existing enriched corpus
   (`output/2_enriched_*.csv`) plus niche lanes (`butcher/`,
   `best_wine_shops/`, `directories/`, awards master) — rows that already
   cleared discovery floors and carry `website`. The step-1 `has_ecommerce`
   flag pre-filters to commerce-capable sites. For net-new geography, seed
   Serper Maps off `research/trendy_neighborhoods/` for `bakery | butcher |
   cheese | wine_store | specialty grocer`.

2. **Detect Shopify (rides step-1 crawl, no new fetch).** In the step-1 parse
   layer, flag a site as Shopify on any of: `cdn.shopify.com` asset refs,
   `Shopify.theme` / `window.Shopify` JS globals, `x-shopid` / `x-sorting-hat`
   response headers, `/cdn/shop/` paths, or a meta generator tag. Record
   `is_shopify` + the resolved storefront base URL.

3. **Pull structured catalog state.** For each Shopify shop, fetch the public
   JSON (httpx, polite rate, paginate):

   - `https://<domain>/products.json?limit=250&page=N` — full catalog: each
     product's `product_type`, `tags`, `published_at`, and `variants[]` with
     `price` and `available`.
   - `https://<domain>/products/<handle>.js` only when a product's
     availability is ambiguous (gives per-variant `inventory_quantity` /
     `inventory_management` where exposed).

   Compute per shop:

```
product_count       = len(products)
oos_variants        = sum(1 for p in products for v in p.variants if not v.available)
total_variants      = sum(len(p.variants) for p in products)
oos_ratio           = oos_variants / total_variants
oos_products        = count(products where ALL variants unavailable)
aov_proxy           = median(variant.price over available variants)   # price tier proxy
top_oos_types       = top product_types among sold-out products
back_in_stock_alert = bool  # see step 4
```

4. **Detect back-in-stock alert infrastructure.** A shop that installed a
   restock-notify app is *actively managing* OOS demand — a strong corroborator.
   In the step-1 crawl scan product-page HTML / script srcs for the common
   apps: `back_in_stock`, `restock(rocket| alerts?)`, `klaviyo` back-in-stock
   form, `swym` wishlist/alerts, `notify me when available`, `back-in-stock.js`,
   `restocked.io`. Record `back_in_stock_alert` + `back_in_stock_vendor`.

5. **Persist a snapshot for restock cadence.** Write each run's per-shop OOS
   metrics to a date-stamped history file (`output/shopify_oos/_history/`). On
   subsequent runs, diff against the prior snapshot to derive:

```
restock_cadence_days = median gap between a variant flipping
                       unavailable -> available across snapshots
recurrence_flag      = True if a SKU has gone OOS in >= 2 distinct snapshots
oos_persistence_days = days a still-OOS variant has been unavailable
```

   Single-snapshot rows ship with `recurrence_flag = False` and cadence
   `null` — the engine's value compounds across runs (this is why cadence
   needs its own persisted store, see Repo placement).

6. **Classify product type + AOV tier (Claude, cheap pass).** Send the
   `top_oos_types` + a sample of sold-out product titles to Claude
   (`claude-haiku-4-5`, the model `scrape_beli` uses) to (a) label whether the
   sold-out SKUs are *premium finite product* (whole-animal share, dry-aged
   cut, allocation bottle, aged-cheese wheel, weekend pastry drop) vs commodity
   / merch / gift card, and (b) emit a one-line `trigger_summary` sales can
   quote. Prefix with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

7. **Apply the ICP gate (curation half).** Run `reclassify.py`
   (`partner_type` / `business_type_v2`, wine-bar claw-back) and join
   `detect_clubs.py` (`has_club` — existing club is a positive switch signal,
   not a DQ). Reject anti-ICP before scoring:

```
DISQUALIFY if:
  partner_type == liquor_store, or wine commodity-SKU leak in catalog
      (Tito's, Smirnoff, Veuve, BuzzBallz, Budweiser, Josh, Cupcake, Barefoot,
       Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic,
       Andre, Cloud Break) or ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
  gift-cards/merch-only OOS (the OOS isn't on real product)

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery   # OOS real but headroom capped
  static-social-only / thin metrics in small market (never DQ — understates brand)
  very small catalog (product_count < 5)  # one-off OOS, not a pattern

oos_strength:
  +3 oos_ratio >= 0.40 on a premium catalog AND recurrence_flag == True
  +3 cyclical restock detected (restock_cadence_days present, regular gap)
  +2 oos_ratio >= 0.25 on premium SKUs (single snapshot)
  +2 back_in_stock_alert == True (actively managing demand overflow)
  +1 oos_ratio 0.10-0.25 / single OOS premium product
  +1 if has_club == True (proven recurring demand)

QUALIFY (engine output) if: passes ICP gate AND oos_strength >= 2
```

8. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). OOS
   columns ride as evidence; `oos_strength` orders the outbound queue inside a
   tier.

## Output schema

```
output/shopify_oos/shopify_out_of_stock_patterns_<YYYYMMDD>.csv
source = "shopify_out_of_stock_patterns"
tier = <1|2|3>     # 1 = butcher/wine/cheese/specialty + high recurring OOS; 2 = bakery or single-snapshot; 3 = ICP-soft
business_type = butcher | wine_store | cheese | bakery | specialty | restaurant
distinction = "Shopify catalog runs {oos_ratio} sold-out (recurring) — capture demand w/ Table22"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    is_shopify             # bool
    product_count          # int
    oos_ratio              # float, sold-out variants / total variants
    oos_products           # int, fully sold-out products
    top_oos_types          # the product_types selling out (e.g. "dry-aged | charcuterie")
    aov_proxy              # median variant price (price-tier proxy)
    back_in_stock_alert    # bool — restock-notify app installed
    back_in_stock_vendor   # klaviyo | swym | back_in_stock | restock_rocket | ...
    recurrence_flag        # bool — SKU OOS across >=2 snapshots
    restock_cadence_days   # median restock gap (null on first snapshot)
    oos_persistence_days   # days the still-OOS SKUs have been unavailable
    oos_evidence_url       # /products.json or a sold-out product permalink
    oos_snippet            # sample sold-out product titles
    oos_strength           # int, intra-tier outbound ordering
    trigger_summary        # one-line Claude-written outbound hook
    has_club               # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped: **~8–12K
  rows**. The step-1 `has_ecommerce` flag pre-filters; Shopify is ~25–35% of
  commerce-capable indie food sites, so expect **~2.5–4K Shopify shops**.
- Shopify detection: free (rides the step-1 10-thread crawl; +1 parse pass).
- `/products.json` pulls: free-ish (public endpoints, httpx, no API cost) on
  ~3.5K shops × a few paginated requests — only bandwidth + politeness time.
- Back-in-stock app detection: free (same crawl pass).
- Claude Haiku classify pass on `top_oos_types` for shops with any OOS
  (~1.5K rows, short prompts): **≈ $2–4**.
- **Per-run total: ~$4–8** (well under target; cost scales only if we add the
  optional `.js` per-variant pulls broadly).
- **Net-new qualified leads per run:** of ~3.5K Shopify shops, meaningful OOS
  hits **~30–40%** (≈1–1.4K); after ICP gate + `oos_strength >= 2`, expect
  **~300–500 qualified rows** on the first run. Recurrence-flagged rows (the
  highest-converting cut) only appear from the **second** run onward.

## Refresh cadence

**Weekly.** This engine is built on *cadence* — a single snapshot is just a
point-in-time OOS ratio; the differentiated signal (cyclical restocks,
recurrence, persistence) only emerges from repeated measurement. Weekly is
frequent enough to catch a butcher's whole-animal share or a bakery's weekend
drop selling out on a regular rhythm, and to compute reliable
`restock_cadence_days`. Pull a heavier pass pre-holiday (turkeys, pies,
charcuterie boxes, allocations all spike OOS then). Keep the persisted history
indefinitely — it's the moat.

## Risks

- **Single-snapshot false positives.** A high OOS ratio on one run can mean a
  shop mid-restock, a seasonal catalog wind-down, or a permanently abandoned
  store. `recurrence_flag` and `oos_persistence_days` separate live demand
  pressure from a dead/stale catalog — never assign a hard trigger on one
  snapshot alone; gate `oos_strength` +3 on recurrence.
- **`/products.json` not always exposed.** Some shops disable the endpoint or
  password-protect the storefront; `available` can also be `true` with
  `inventory_management: null` (Shopify reports "available" when not tracking
  inventory). Fall back to the `.js` endpoint and to step-1 sold-out *badge*
  text; treat a missing endpoint as no-signal, not OOS.
- **Merch / gift-card / pre-order OOS noise.** Sold-out tote bags, gift cards,
  or "coming soon" pre-order placeholders inflate `oos_ratio` without real
  demand. The Claude classify pass must confirm OOS is on *premium finite
  product*; DQ gift-cards/merch-only OOS.
- **ICP leakage through the trigger.** A liquor store, a hype-merch drop, or a
  12-location chain can all run Shopify with sold-out SKUs. Keep
  `config.CHAIN_KEYWORDS`, the commodity-SKU catalog scan, and ESP-red-flag
  (City Hive, Spot Hopper) checks *upstream* of `oos_strength`.
- **Wine-bar / liquor-store false positives.** Enforce wine-bar exclusion
  (except geographic-monopoly) and the `reclassify.py` claw-back; a bottle-shop
  whose catalog reads as commodity liquor must drop.
- **Small-market metrics run low.** A rural butcher with a tiny Shopify catalog
  may sell out everything yet have thin social volume. Weight relative local
  dominance + the OOS trigger; **never DQ on static-only social** — it
  understates brand. (But guard against `product_count < 5` reading as a
  "pattern" — demote.)
- **Sweets-only demotion.** A cupcake shop selling out daily is a real trigger
  but a single-product bakery — cap Tier 2.
- **Rate-limit fragility.** Public JSON endpoints will 429 under aggressive
  pulls. Throttle, jitter, cache by ETag, and back off; never hammer a single
  domain.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler
as a library and adding a persisted snapshot store (genuinely new infra — no
existing lane keeps cross-run history).

```
shopify_oos/
  __init__.py                  # engine constants; registers detection + leak lists
  signals.py                   # SHOPIFY_FINGERPRINTS, BACK_IN_STOCK_VENDORS, commodity-SKU/ESP leak lists
  detect_shopify.py            # parse layer over enrich.py step-1 crawl output (is_shopify + base URL)
  pull_catalog.py              # httpx /products.json + /products/<handle>.js, computes per-shop OOS metrics
  snapshot_store.py            # persist + diff per-shop OOS history (restock cadence, recurrence)
  classify.py                  # Claude haiku-4-5: premium-vs-commodity OOS, trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), oos_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_shopify_oos.py        # orchestrator: seed -> detect -> pull -> snapshot-diff -> classify -> gate -> finalize
output/shopify_oos/_history/   # NEW persisted store: per-run shopify_oos_<YYYYMMDD>.parquet snapshots
```

Refactor target: extract the `enrich.py` **step-1** platform-detection +
ecommerce-flag parsing into a shared `enrich_websites_lib` so both `enrich.py`
and `shopify_oos/detect_shopify.py` detect Shopify identically without
duplicating the crawl (same shared-lib argument Engines 02 and 05 raise). The
**snapshot history store** (`snapshot_store.py` + `_history/`) is net-new infra
this engine requires — no other lane persists cross-run state. Keep it append-
only and date-stamped; never overwrite a prior snapshot in place.

## Open questions

1. **Recurrence threshold + cold-start.** First run can't compute recurrence —
   do we ship single-snapshot rows at lower `oos_strength` immediately, or hold
   the whole list until a second snapshot exists? How many snapshots prove
   *cyclical* (regular cadence) vs *chronically out* (persistently OOS, maybe
   just under-supplied)?
2. **`available` vs real inventory.** Shopify reports `available: true` when a
   shop doesn't track inventory, so `oos_ratio` undercounts those. Is the
   `.js` `inventory_management` check worth the extra per-variant pulls, or do
   we accept the undercount and lean on badge text as backup?
3. **Snapshot store format/location.** Parquet under `output/shopify_oos/_history/`
   keeps it in the gitignored output tree, but it's now load-bearing state, not
   a disposable artifact. Does it belong somewhere more durable (a small DB), and
   who owns its retention?
4. **Cross-engine overlap with Engine 03.** Shopify badge text already feeds the
   sold-out-language engine. Do we merge the structured OOS metrics onto those
   rows as additional evidence, or keep this as a distinct higher-confidence
   list with its own outbound timing?
```