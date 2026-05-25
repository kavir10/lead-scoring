# Channel 08 — Specialty Distributor Customer Logos (Multi-Vertical)

**Motion:** Curation, vertical-specific
**Vertical fit:** All — distributor list = vertical filter
**Status:** Not yet built (extends Wave 1 #1 case-studies + existing `directories/_stockists.py` pattern)
**Owner:** TBD
**Cost target:** ≤ $15/run

## Premise

Strategy doc Wave 1 #2 (WineSearcher) and the existing `directories/wine/`
stockist pattern prove that **importer/distributor "where to buy" pages are
the cheapest, highest-density source of vertically-aligned operators**.

This channel **extends the same pattern across non-wine verticals** by
hitting the most prestigious specialty distributors in each category. Each
distributor names ~50-200 restaurant or retail customers on their site
(often as case studies, "our partners," or "find us on a menu near you"
pages).

## Source distributors by vertical

### Meat / charcuterie

| Distributor | Region | Restaurant customers? | Access |
|---|---|---|---|
| **D'Artagnan** (game, duck, charcuterie) | National | Yes, "Where to dine" page | Public |
| **Niman Ranch** (premium pork, beef) | National | Yes, restaurant partners page | Public |
| **Pat LaFrieda** (NYC steakhouse beef) | Northeast | Partner restaurants | Public |
| **Heritage Foods USA** | National | Yes | Public |
| **DeBragga & Spitler** (NYC) | Northeast | Restaurant accounts | Public |

### Cheese

| Distributor | Region | Access |
|---|---|---|
| **Murray's Cheese — wholesale partner list** | National | Public |
| **Forever Cheese** (Italian + Spanish import) | National | Restaurant accounts page |
| **Cellars at Jasper Hill** | National | Restaurant placements |
| **Cowgirl Creamery wholesale** | West | Restaurant accounts |
| **Saxelby Cheesemongers wholesale** | NYC-area | Restaurant accounts |

### Bakery / flour / specialty grocery

| Distributor | Region | Access |
|---|---|---|
| **Bien Cuit wholesale** (bread to restaurants) | Northeast | Partner list |
| **Olde Hearth Bread Company wholesale** | Southeast | Partner list |
| **Caputo / Caputo USA importers** (Italian flour) | National | Restaurant customers |
| **Atalanta Corp** (specialty grocery import) | National | Retailer + restaurant accounts |
| **Sahadi's wholesale** | NYC | Restaurant accounts |

### Seafood

| Distributor | Region | Access |
|---|---|---|
| **Greenpoint Fish & Lobster wholesale** | NYC-area | Partner restaurants |
| **F. Rozzo & Sons** | NYC | Restaurant accounts |
| **Pierless Fish** | NYC | Restaurant accounts |
| **True World Foods** (sushi-grade national) | National | Partner restaurants |
| **Browne Trading Company** | New England + national | Restaurant accounts |

### Produce / regional

| Distributor | Region | Access |
|---|---|---|
| **Baldor** (already in Wave 1 list — confirm) | Northeast | Partner restaurants |
| **Bowery Provisions** | Northeast | Restaurant accounts |
| **Coast Catering Truck** (regional CA) | West | Restaurant accounts |
| **Imperfect Foods wholesale** | National | Restaurant partners |
| **Greenmarket Co.** (NYC GrowNYC wholesale) | NYC | Restaurant accounts |

After dedupe and aliveness check, target = **~25-30 distributor pages**, each
yielding 50-200 restaurant customers = **~3,000-5,000 unique restaurant
mentions** before cross-distributor dedupe.

## Recipe

Reuse the existing `directories/_stockists.py` pattern. For each
distributor:

1. **Locate the "where to buy / partners / customers" page** — usually
   linked from the site footer or top nav.
2. **httpx + selectolax** to extract the list of customer names.
3. **Format varies wildly** — some are clean lists, some are JS-rendered, some
   are city-grouped, some are PDF. Build a per-distributor parser. Worst
   case: Playwright fallback.
4. **Geo-locate** via Serper Maps to canonicalize (lat, lng, phone) and tag
   `business_type`.

## Output schema

`output/directories/specialty_distributors_<YYYYMMDD>.csv`:

```
source = "distributor_<slug>"
tier = 1   # distributor customers are by definition curated
business_type = restaurant | wine_store | butcher | cheese | bakery | specialty
distinction = "Customer of {distributor_name}"
year = <discovery_year>
+ extra cols: distributor_slug, distributor_vertical (meat | cheese |
              bakery | seafood | produce | charcuterie), page_url,
              distributor_count (cross-channel rollup)
```

## Aggregation

Cross-distributor rollup is the **whole point**. A restaurant named on
D'Artagnan + Pat LaFrieda + Heritage = clearly a serious meat program,
priority lead. `distributor_count >= 2` auto-promotes to A-list.

## Volume & cost

- ~25 distributor pages × ~150 customers each = ~3,750 records pre-dedupe
- Direct fetch / Playwright: free
- Serper Maps geocoding: 3,750 × $0.30/1K = ~$1.20
- Sonnet for vertical classification + canonical name normalization: ~$10
- **Per-run total: ~$10-15**
- **Net-new venues per run (first run): ~2,000-2,500 unique post-dedupe**
- **Subsequent: ~5-10% incremental per quarter**

## Refresh cadence

Quarterly. Distributor pages are stable but customer lists rotate slowly.

## Risks

- **Distributor pages are wildly inconsistent in structure.** Per-distributor
  parser is unavoidable; budget ~1-2 hours per source to write the parser.
  The `directories/_stockists.py` shared helpers will cover ~60% of cases.
- **Aspirational customer names** — some distributors list past customers
  who've stopped buying. Cross-reference against Google Maps for "currently
  open" check.
- **PR-page-only customers** — some distributors only name big-press
  customers (Le Bernardin, Per Se) and exclude their bread-and-butter
  accounts. Those venues are too well-known to be net-new. Filter by
  cross-checking against existing T22 partner list and downstream awards
  corpus.
- **Distributor consolidation** — Sysco / US Foods buying specialty
  distributors. Track whether the customer-list page survives M&A.

## Repo placement

Extends existing `directories/_stockists.py` infrastructure across more
verticals.

```
directories/
  _stockists.py                  # existing shared helpers
  meat/
    __init__.py
    distributor_dartagnan.py
    distributor_niman_ranch.py
    distributor_lafrieda.py
    distributor_heritage_foods.py
    distributor_debragga_spitler.py
  cheese/
    distributor_murrays_wholesale.py
    distributor_forever_cheese.py
    distributor_jasper_hill.py
    distributor_cowgirl_creamery.py
    distributor_saxelby.py
  bakery/
    distributor_bien_cuit.py
    distributor_olde_hearth.py
    distributor_caputo.py
  seafood/
    distributor_greenpoint.py
    distributor_browne_trading.py
    distributor_true_world_foods.py
  specialty/
    distributor_atalanta.py
    distributor_sahadis.py
    distributor_baldor.py
    distributor_bowery.py
```

Each module registered in `directories/__init__.py:ALL_SOURCES` with
`(slug, "meat" | "cheese" | "bakery" | "seafood" | "specialty", tier=1,
 module, business_type, requires_auth=False)`.

## Open questions

1. **Wholesale liquor distributors** (Southern Glazer's, Republic National)
   are gigantic but customer-list scraping is unlikely — they don't publish
   accounts. Skip.
2. **Wine importer "where to buy"** is already covered in `directories/wine/`
   (Skurnik, Polaner equivalents). Don't double up.
3. Worth treating **distributor_count >= 3** as a separate ultra-high-priority
   bucket? Probably — almost every venue with 3+ distributor mentions is a
   serious operator.
4. **Cross-vertical mentions** are noise. Filter customers to those whose
   inferred business_type matches the distributor's vertical (or restaurants,
   which buy from all). E.g., a wine shop appearing on D'Artagnan's customer
   list is a parse error or noise — drop.
