# Lead Engine 32 — No Ecomm, But Many Product Pages List

**Motion:** Hybrid (Curation-grade ICP gate + a structural "merchandising-but-no-commerce" Trigger)
**Vertical fit:** All retail — butcher, wine, cheese, bakery, specialty grocer, deli/market (retail-leaning; restaurants only via merch/menu-as-catalog)
**Suggested list name(s):** `product_story_no_ecomm`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$6–14/run (rides the step-1 websites crawl; net-new cost is a sitemap/page-count pass + a small Claude classify pass)

## Premise

Engine 19 reads operators who *have* a transaction layer and are selling out of
it. This engine reads the opposite shape: operators with rich product/menu
**storytelling** — named cuts, single-vineyard bottles, aged-cheese profiles,
weekly bake lists, farm provenance — but **no actual transaction layer**. They
have built a catalog in their head and on their site (many product/menu pages,
detailed descriptions, photography, provenance copy) and have *not* built the
commerce infrastructure to sell it: no cart, no checkout, no Shopify/ecommerce
flag. This is the `enrich.py` step-1 ecommerce detection **inverted** — many
product pages, ecommerce flag false.

The thesis is demand-over-capacity at the *infrastructure* layer. An operator
who merchandises this hard has the imagination and the SKU narrative a
subscription program needs, but has never stood up the rails to monetize repeat
demand. In the two-score model this raises **ICP Fit** (catalog depth +
merchandising sophistication is exactly the operator mindset that runs a Table22
club well) and supplies a clean **Trigger**: "You've already done the hard part —
you've built and described the catalog. You just have no way to sell it
recurring." It is the structural cousin of Engine 20 (list but no monetization)
and Engine 09 (tech-ready, no subscription): all three find the asset present and
the monetization rail absent.

It is explicitly **Hybrid**. "Many pages, no cart" is a strong ICP-and-trigger
prior for an indie retailer, but the same shape also catches restaurant menu
sites, brochure-ware, and dead catalogs — so the OOS-equivalent here (catalog
depth) is the Trigger, and the ICP gate does the filtering. High-trigger /
weak-ICP rows get dropped before sales, not nurtured.

## Recipe

A **postprocessing overlay** plus a thin catalog-depth pass. It consumes an
already-discovered + `websites`-enriched CSV and emits a filtered, depth-tagged
CSV. No fresh Serper discovery is required; it reuses the step-1 crawler, a
public sitemap pull, `detect_clubs.py`, and `reclassify.py`.

1. **Seed the universe.** Take a scored or at-least-`websites`-enriched CSV
   (`output/2_enriched_websites.csv`, a vertical-lane master under `butcher/`,
   `best_wine_shops/`, `directories/`, or a `custom-serper-scoring_*_all.csv`).
   Every row already has a `website`, cleared quality floors, and survived
   `CHAIN_KEYWORDS`. The retail bias is intentional — favor `business_type in
   {butcher, wine_store, cheese, bakery, specialty, deli}`. For net-new
   geography, seed Serper Maps off `research/trendy_neighborhoods/`.

2. **Read the ecommerce flag (rides step-1 crawl, no new fetch).** The step-1
   `websites` crawl already emits `has_ecommerce`, the email-signup flag, social
   links, and reservation-platform detection. Keep **only `has_ecommerce ==
   False`** rows as candidates. Also record the platform fingerprints the same
   parse can cheaply emit so we can confirm the *absence* of a cart, not just a
   missing flag:

   ```
   ECOMM_PRESENT (any -> disqualify as candidate, they already transact):
     cart/checkout DOM:  add-to-cart, /cart, /checkout, data-cart, "add to bag",
                         woocommerce-cart, snipcart, foxycart, ecwid, squarespace-commerce
     platform globals:   window.Shopify / cdn.shopify.com / x-shopid,
                         bigcommerce, wix-stores, square-online (squareup/weebly),
                         toast-online-ordering, chownow, popmenu-ordering, slice (pizza)
   ```

3. **Measure catalog depth (NEW sitemap/page-count pass).** A no-ecomm site with
   one page is brochure-ware; a no-ecomm site with 60 product/menu pages is a
   merchandiser without a rail. For each candidate, httpx-pull the public
   structure (polite rate, cache by ETag) and count storytelling pages:

   - `sitemap.xml` (+ nested sitemaps) — fastest path to a page inventory.
   - Fallback: BFS the homepage nav 1–2 levels deep when no sitemap.
   - Classify URLs by path/anchor against product/menu patterns:

   ```
   PRODUCT_PAGE_PATTERNS (count toward catalog depth):
     /product(s)?/, /shop/<item>, /menu/, /our-(meats|cuts|wines|cheeses|breads)/,
     /catalog/, /selection/, /bottles?/, /charcuterie/, /pantry/, /goods/,
     individual item slugs under a listing page; menu sections w/ item-level copy
   STORY_SIGNALS (depth quality, not just count):
     provenance/farm names, varietal/vineyard, "dry-aged N days", tasting notes,
     "this week's bread", importer credits, breed/heritage, allergen/origin copy
   ```

   Compute per shop:

   ```
   product_page_count   = pages matching PRODUCT_PAGE_PATTERNS
   total_page_count      = pages in sitemap/crawl
   story_density         = product_page_count / total_page_count
   has_cart              = step-2 ECOMM_PRESENT match (must be False)
   story_richness        = avg story-signal hits per sampled product page
   ```

4. **Classify catalog vs brochure (Claude, cheap pass).** Send a sample of
   product/menu page titles + the richest excerpts to Claude
   (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to label whether
   the pages are a *real merchandised catalog with sellable SKUs* (named cuts,
   specific bottles, individual breads/cheeses with descriptions) vs a *static
   restaurant menu, a single "about our products" page, or filler*, and to emit a
   one-line `trigger_summary` sales can quote. Prefix the invocation with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

5. **Negative monetization corroboration (reuse `detect_clubs.py`).** Run
   `detect_clubs.py` (50-thread site scrape) to populate `has_club`, `club_type`,
   `club_url`, `club_signals`. Per the standing repo principle, existing club is a
   **positive** switch signal — club-positive rows are *not* discarded, they are
   tagged `route=nurture_transition` and handed to Engine 01. The pure-play
   target for this engine is `has_ecommerce == False` AND `has_club == False`:
   catalog depth, zero rail of any kind.

6. **Apply the ICP gate (curation half).** Run `reclassify.py` (`partner_type` /
   `business_type_v2`, wine-bar claw-back) and reject anti-ICP before scoring:

   ```
   DISQUALIFY if:
     partner_type == liquor_store, or wine commodity-SKU leak across pages
        (Tito's, Smirnoff, Veuve, BuzzBallz, Budweiser, Josh, Cupcake, Barefoot,
         Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic,
         Andre, Cloud Break) or ESP/site red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
     catalog is a static restaurant dinner menu only (no sellable retail SKUs)

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery       # depth real but headroom capped
     static-social-only / thin metrics in small market   # never DQ; understates brand
     product_page_count < 8                     # thin catalog, not a merchandiser

   depth_strength:
     +3 product_page_count >= 40 AND high story_richness AND retail partner_type
     +2 product_page_count 15-39 with named/described SKUs
     +2 wine importer street-cred present (Skurnik, Louis/Dressner, Jenny & Francois,
        Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor)
     +2 butcher premium signals (whole-animal, named farms, in-house charcuterie/dry-aging)
     +1 product_page_count 8-14 / moderate story_richness
     +1 has_email_list (audience present, ties to Engine 20)
     +1 if has_club == True (proven recurring demand -> route nurture_transition)

   QUALIFY (engine output) if: passes ICP gate AND depth_strength >= 2
   ```

7. **Reclassify + dedupe + hand off to scoring.** `reclassify.py` then
   `dedupe_existing.py` (phone-first, then name+address). Emit the canonical CSV
   (below) and run `score.py` **unmodified** — do not touch
   `config.SCORING_WEIGHTS` (SHAP-aligned). Catalog-depth columns ride as
   evidence; `depth_strength` orders the outbound queue inside a tier.

## Output schema

```
output/product_story_no_ecomm/product_story_no_ecomm_<YYYYMMDD>.csv
source = "product_story_no_ecomm"
tier = <1|2|3>     # 1 = butcher/wine/cheese/specialty + deep described catalog; 2 = bakery or thinner catalog; 3 = ICP-soft
business_type = butcher | wine_store | cheese | bakery | specialty | deli | restaurant
distinction = "Deep merchandised catalog ({product_page_count} product pages), no cart/checkout"
year = <discovery_year>
+ canonical: name, city, state, country, source_url (= website), blurb
+ evidence cols (preserve verbatim so sales can cite the trigger in outbound):
    has_ecommerce          # must be False
    has_cart               # must be False (ECOMM_PRESENT scan)
    product_page_count     # int — the headline number for outbound
    total_page_count       # int
    story_density          # product pages / total pages
    story_richness         # avg provenance/varietal/dry-age story hits per page
    catalog_kind           # claude: real_catalog | restaurant_menu | brochure | filler
    sample_product_pages   # 2-3 example URLs sales can open
    sample_story_snippet   # verbatim provenance/SKU copy for the cold-email hook
    has_email_list         # from step-1 / Engine 20 overlay (audience present)
    has_club               # from detect_clubs.py (positive switch signal)
    club_signals           # raw detect_clubs output
    depth_strength         # int, intra-tier outbound ordering
    trigger_summary        # one-line Claude-written outbound hook
    partner_type           # from reclassify.py
    route                  # sales | nurture_transition (club-present spillover)
```

Master union: `output/product_story_no_ecomm/product_story_no_ecomm_all_<YYYYMMDD>.csv`.

## Volume & cost

Bounded by input size, not fresh discovery. Over a typical ~8–12K-row deduped
retail-leaning corpus (existing enriched corpus + niche lanes):

- The step-1 `has_ecommerce` flag is the first cut. In the indie food long tail,
  **roughly 55–70% of retail sites have NO cart** (brochure sites, menu sites,
  "call to order" shops) → **~5–8K no-ecomm candidates**.
- Catalog-depth pass keeps the merchandisers: of those, **~20–30%** carry a real
  described catalog (`product_page_count >= 8`, `catalog_kind == real_catalog`) →
  **~1.2–2.2K depth-positive rows**.
- After the ICP gate + `depth_strength >= 2` (drops restaurant-menu-only, thin
  catalogs, liquor/chain leakage): expect **~400–700 qualified net-new leads per
  run**, ~150–250 of them tier-1 (deep described catalog on a butcher/wine/cheese/
  specialty partner type).

Cost arithmetic: ecommerce detection folds into the existing step-1 crawl (zero
marginal request). The sitemap/page-count pass is httpx against public
`sitemap.xml` (no API cost; bandwidth + politeness only). `detect_clubs.py` is a
second site fetch at 50 threads (near-free compute). The only paid line is the
Claude Haiku classify pass on depth-positive rows (~1.5–2K short prompts) ≈
**$3–6**. No Apify, no Serper Web, no Resy calls added. **Per-run total:
~$6–14**, most of it the optional Claude pass.

## Refresh cadence

**Quarterly per vertical**, run opportunistically off any large discovery batch.
The signal moves slowly — a shop that hasn't built a cart in years rarely flips
in a month, so monthly re-runs mostly re-surface the same rows. The high-value
diff is a previously-qualified depth-positive lead that **stands up a cart or
launches a club** between runs: that intersection (this run's `has_ecommerce ==
True` ∩ last run's `product_story_no_ecomm` set) is itself a fresh trigger —
"they finally built commerce; talk to them now before a competitor's platform
locks them in" — and routes to Engine 01 / Engine 09. Pull a heavier pass
pre-holiday, when brochure-only shops scramble to take gift/preorder demand they
can't currently process.

## Risks

- **Restaurant-menu false positives.** A restaurant with a deep, beautifully
  written dinner menu reads as "many product pages, no cart." But a static
  dinner menu is not a sellable retail catalog and the restaurant verticals
  monetize differently (and lower: neighborhood restaurant $32.0k vs butcher
  $75.9k). The Claude `catalog_kind` label and the retail `partner_type` gate
  must drop `restaurant_menu`-only rows; keep restaurants only where there's a
  genuine merch/retail SKU set.
- **Brochure-ware vs merchandiser.** Many pages of generic "about / our story /
  hours" content can inflate `total_page_count` without a real catalog. Gate on
  `product_page_count` and `story_richness`, not raw page count; demote
  `product_page_count < 8`.
- **Sitemap absent or misleading.** Wix/Squarespace/WordPress sometimes hide,
  paginate, or bloat sitemaps; a JS-rendered catalog may not appear in static
  HTML at all (false "thin catalog"). Treat a missing/sparse sitemap as
  no-signal, fall back to nav BFS, and never DQ on page count alone.
- **Liquor-store / commodity-wine leakage.** A liquor store can have many bottle
  pages and no cart. Enforce the commodity-SKU exclusion list, the City Hive /
  Spot Hopper ESP/site red flags, and the `reclassify.py` liquor adjudication
  upstream of `depth_strength`.
- **Chain / franchise leakage.** Multi-location groups often run a deep brochure
  catalog with ordering handled elsewhere (a separate app/domain). `CHAIN_KEYWORDS`
  runs at discovery, but reconfirm independence on tier-1 rows.
- **Wine-bar exclusion.** A wine bar with a deep bottle list but no cart is still
  mostly out (avg AGMV $36.2k) except geographic monopolies — the reclassify
  claw-back must run before scoring.
- **Sweets-only / single-product demotion.** A bakery with a gorgeous described
  bake list selling only cookies is depth-real but caps at Tier 2 on ICP grounds;
  `depth_strength` must not override the sweets-only demotion.
- **Hidden commerce off-domain.** "No cart on the marketing site" can hide a
  Square/Toast/ChowNow ordering page on a subdomain or third-party link. The
  ECOMM_PRESENT scan must follow obvious "order online / shop now" outbound links
  one hop before declaring no rail; otherwise we pitch a shop that already
  transacts.
- **Small-market metrics run low.** A dominant rural butcher with a deep
  hand-written catalog will under-index on raw reviews/followers and may present a
  thin web footprint elsewhere. Weight relative local dominance + reservation
  difficulty + catalog depth over raw social. Static-only social understates
  brand — never DQ on thin IG; butcher/deli/specialty audiences skew to Facebook
  (`follower_count` is IG + FB).
- **Rate-limit fragility.** Sitemap + nav BFS over thousands of domains will 429
  if aggressive. Throttle, jitter, cache by ETag, back off per-domain.

## Repo placement

An overlay package mirroring the niche-lane shape, reusing the step-1 crawler as
a library and adding a sitemap/page-count pass.

```
product_story_no_ecomm/
  __init__.py                  # engine constants; ECOMM_PRESENT + PRODUCT_PAGE_PATTERNS + STORY_SIGNALS
  signals.py                   # ECOMM_PRESENT fingerprints, product/menu path patterns, commodity-SKU/ESP leak lists
  detect_ecommerce.py          # parse layer over enrich.py step-1 crawl output (has_cart + platform fingerprints)
  catalog_depth.py             # httpx sitemap.xml / nav BFS, product_page_count, story_density, story_richness
  classify.py                  # Claude haiku-4-5: real_catalog vs restaurant_menu/brochure, trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), depth_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_product_story_no_ecomm.py   # orchestrator (mirrors discover_butchers.py / discover_shopify_oos.py)
  python discover_product_story_no_ecomm.py --input output/2_enriched_websites.csv
  python discover_product_story_no_ecomm.py --input output/custom-serper-scoring_*_all.csv --verticals wine,butcher,cheese
  python discover_product_story_no_ecomm.py --master-only
config.py
  + reuse existing commodity-SKU exclusion list + City Hive / Spot Hopper red flags + importer street-cred list
```

Refactor target: extract the `enrich.py` **step-1** platform-detection +
`has_ecommerce` parsing into a shared `enrich_websites_lib` so `enrich.py`,
`shopify_oos/detect_shopify.py` (Engine 19), and this engine's
`detect_ecommerce.py` all detect carts/platforms identically without duplicating
the crawl — same shared-lib argument Engines 02, 05, 09, 19, and 20 raise; build
it once. The only genuinely new code is `catalog_depth.py` (sitemap/nav page
inventory + story scoring), which no existing lane has; it is stateless (no
cross-run history needed, unlike Engine 19's snapshot store) and reads public
endpoints only.

## Open questions

1. **Catalog depth threshold by vertical.** A butcher with 12 named cuts is a
   deep catalog; a specialty grocer with 12 pages is thin. Should
   `product_page_count` thresholds be per-`partner_type` rather than a single
   global `>= 8`?
2. **JS-rendered catalogs.** Squarespace/Wix often render product grids
   client-side, invisible to a static httpx pull. Is a Playwright fallback (as in
   `best_wine_shops/`) worth the cost on the subset with sparse static sitemaps,
   or do we accept the undercount and lean on the Claude pass over whatever HTML
   loads?
3. **Off-domain commerce detection depth.** How many outbound "order/shop" hops
   do we follow before declaring "no rail"? One hop is cheap but may miss a Toast
   subdomain; deeper following risks false negatives that pitch a shop that
   already sells online.
4. **Overlap with Engines 09 and 20.** A row that is no-ecomm + no-club + has a
   list is simultaneously this engine, Engine 20, and Engine 09. Do these merge
   into one "no monetization rail" master with overlay flags, or stay as distinct
   lists with separate outbound timing and messaging?
```