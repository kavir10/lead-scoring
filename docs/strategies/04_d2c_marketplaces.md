# Channel 04 — Direct-to-Consumer Food Marketplaces

**Motion:** Curation
**Vertical fit:** All retail (butcher, cheese, bakery, specialty grocer) +
chef-driven restaurants with D2C arm
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run

## Premise

Operators on D2C food marketplaces have **already done the hard part of a
Table22 deployment**: shipping, fulfillment, perishable logistics, customer
data capture, recurring revenue infrastructure. They've proven they can
monetize off-premise demand and they've proven customers will pay shipping
on perishable goods.

This is the **closest behavioral analog to a Table22 subscriber that exists
in public data**. Estimated universe is ~3-5K total US operators across all
marketplaces (after dedupe).

## Source marketplaces

| Marketplace | Volume estimate | Vertical mix | Access |
|---|---:|---|---|
| **Goldbelly** | ~1,000 merchants | Restaurants (60%), specialty retail (40%) | Public catalog, well-structured HTML |
| **Mouth.com** | ~500 if still alive — verify | Specialty retail (cheese, charcuterie, sweets) | Public catalog; site may be inactive |
| **Eat Boutique** | ~200 | Artisan specialty | Public catalog |
| **Murray's Cheese — affineur partners** | ~80 cheesemakers + ~30 restaurants | Cheese, deli | Murray's "Cheese 101" / partner page |
| **Caviar Originals** | ~300 (no longer active separately — has merged into Caviar / DoorDash; verify) | Restaurants | Confirm before building |
| **Williams-Sonoma Marketplace** | ~600 vendors | Specialty retail | Public vendor pages |
| **Zingerman's mail-order partners** | ~50 | Specialty | Zingerman's catalog |
| **Stonewall Kitchen partner brands** | ~100 | Specialty pantry | Stonewall site |
| **Foodtopia / Aisle / regional D2C aggregators** | varies | Mixed | Per-site |

Suggested initial build = **Goldbelly + Williams-Sonoma + Murray's**. These
are the three biggest, most clearly alive, with cleanest catalogs. The
remaining are tier-2 additions.

## Recipe

For each marketplace:

1. **Crawl the catalog** — httpx + selectolax over paginated category pages.
2. **Extract merchant card** — each product card carries a "by {Merchant}"
   link to the merchant page. Pull merchant name + merchant page URL.
3. **Fetch merchant page** — extract location, vertical, blurb, founded year
   if shown.
4. **Geo-locate** — merchants often only list city/state. Run through Serper
   Maps to get canonical (lat, lng, phone) for dedup vs other channels.

## Output schema

`output/directories/d2c_marketplaces_<YYYYMMDD>.csv`:

```
source = "d2c_<marketplace>"
tier = 1
business_type = restaurant | butcher | wine_store | bakery | cheese | specialty
distinction = "Sells on {marketplace} since {year_if_known}"
year = <discovery_year>
+ extra cols: merchant_url, marketplace_count (how many marketplaces this
              merchant is on — multi-marketplace is a meta-signal),
              ships_nationwide_bool, founded_year
```

## Aggregation

After per-marketplace scrape, **roll up by merchant identity** (name +
city). A merchant on ≥2 marketplaces gets a `marketplace_count >= 2` flag
and is auto-promoted to A-list — high signal that this operator is *trying
hard* to monetize D2C.

## Volume & cost

- 8 marketplaces × ~500 merchants each = ~4K records pre-dedupe, ~2.5K post-dedupe
- httpx + selectolax: free
- Sonnet for vertical classification + canonical name dedup: ~$15
- Serper Maps enrichment for 2.5K rows × $0.30/1K = ~$1
- **Per-run total: ~$15-25**
- **Net-new venues per run (first run): ~2,500 unique**
- **Subsequent: ~5-10% incremental per quarter**

## Refresh cadence

Quarterly. Catalogs don't churn fast.

## Risks

- **Mouth.com** may be defunct. Verify before building a scraper for it.
- Caviar Originals merged into DoorDash; the standalone catalog is dead.
  Skip.
- Many merchants are pure-online with no physical retail footprint — those
  *are* still leads (they're proven D2C operators), but `business_type`
  defaults will need a `is_online_only` flag mirroring the `best_wine_shops/`
  pattern.
- Williams-Sonoma vendors include big-brand CPG (e.g., All-Clad). Filter to
  food/bev brands only, exclude cookware/hardware vendors via category
  filter at crawl time.

## Repo placement

```
directories/
  specialty/
    d2c_goldbelly.py
    d2c_williams_sonoma.py
    d2c_murrays.py
    d2c_mouth.py             # only if confirmed alive
    d2c_eat_boutique.py
    d2c_zingermans.py
    d2c_stonewall_kitchen.py
  _d2c_lib.py                # merchant-card extraction shared logic
```

Each module registered in `directories/__init__.py:ALL_SOURCES`.

## Open questions

1. Are subscription-program Goldbelly merchants observable from outside?
   (e.g., merchants with a "weekly box" SKU) — if yes, that's an even
   sharper sub-signal worth carving out.
2. Should pure-online merchants flow into the main pipeline or get their own
   B2C lane? Current scoring assumes physical presence. Decide before
   scoring.
3. Murray's Cheese partner list — Murray's is an affiliated retailer
   (Kroger-owned), so partners may be wholesale-only. Need to disambiguate
   wholesale-to-Murray's vs sells-direct-to-consumer through Murray's.
