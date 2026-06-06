# Lead Engine 29 — Supplier and Importer Graph

**Motion:** Curation
**Vertical fit:** Wine, butcher, cheese, bakery (the highest-AGMV curation verticals; weakest fit for restaurants, which buy too broadly to leave a clean upstream signature)
**Suggested list name(s):** `supplier_importer_graph`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run (mostly Serper Web backlink discovery + concurrent site crawl; Haiku only for stockist-list extraction)

## Premise

What a merchant *buys upstream* is a sharper curation signal than anything it
puts on its own website. A wine shop that carries Skurnik, Louis/Dressner, and
Zev Rovine is, by revealed preference, a curated natural-wine retailer — no
keyword sweep needed. A butcher sourcing from Heritage Foods, Niman Ranch,
Marin Sun, or White Oak Pastures is doing whole-animal / pasture-raised work by
definition of its supply chain. A cheese counter buying from a named affineur,
or a bakery milling from a regional grain farm, has self-selected into the craft
tier. The supplier roster is the **third party doing our ICP vetting for us**:
respected upstream producers only sell to merchants who fit their brand, so an
importer's stockist list is a pre-curated lead list.

This is a pure **ICP-Fit amplifier**, not a Trigger engine — it answers "is this
the right *kind* of business?" with high precision but says nothing about *when*
to call. The mechanism is the inverse of Engine 11's Channel D: rather than
asking "which two of my partner-seeds share a supplier," it starts from the
**supplier** and harvests every merchant downstream of it via stockist pages and
backlink mining. Per partner-type economics this is deliberately pointed at the
top four ceilings — butcher ($75.9k), wine ($68.2k), cheese ($63.8k), bakery
($34.7k) — where a named upstream producer is both common and discriminating.
Output pairs with any Trigger overlay (Engines 03/04/08): the supplier graph
hands you the right universe; the trigger tells you when to dial.

## Recipe

Build inside the existing **`directories/`** package, which already implements
exactly this contract — stockist backlink mining via `directories/_stockists.py`
and registered sources `stockist_zev_rovine` / `stockist_jenny_francois`. This
engine generalizes that lane across four verticals and adds a backlink-discovery
front end. Each source is a module exposing `def scrape(**kwargs) ->
pandas.DataFrame` in the canonical `awards._lib.SCHEMA`, registered in
`directories/__init__.py:ALL_SOURCES`, orchestrated by `discover_directories.py`.

1. **Build the supplier lexicon — the load-bearing input.** Curate
   `directories/supplier_registry.csv` (`supplier, vertical, tier, stockist_url,
   mining_mode, notes`). Seed per vertical:
   - **Wine importers** (ICP trust list): `Skurnik`, `Louis/Dressner`,
     `Jenny & Francois`, `Selection Massale`, `Zev Rovine`, `Rosenthal`,
     `Polaner`, `Vom Boden`, `T. Edward`, `Jose Pastor`.
   - **Butcher / ranch upstream:** `Heritage Foods`, `Niman Ranch`,
     `Marin Sun Farms`, `White Oak Pastures`, `Joyce Farms`, plus regional
     regenerative ranches surfaced from EatWild / Good Meat Finder.
   - **Cheese affineurs / distributors:** `Crown Finish Caves`, `Jasper Hill`,
     `Murray's wholesale`, `Columbia Cheese`, `Essex St. Cheese` — plus
     `ACS Certified Cheese Professional (CCP)` staff credentials as a parallel
     curation signal mined off shop About pages.
   - **Bakery grain / flour mills:** `Central Milling`, `Janie's Mill`,
     `Maine Grains`, `Anson Mills`, `Camas Country Mill`, plus regional
     naturally-leavened / wild-yeast networks.

2. **Mode A — direct stockist-page harvest (highest precision).** Where a
   supplier publishes a public "where to buy" / "find a retailer" page, scrape it
   with the `directories/_stockists.py` happy path (httpx + selectolax; Playwright
   fallback via `directories/_browser_fetch.py` when blocked). Many traditional
   wine importers treat retailer lists as proprietary — `directories/__init__.py`
   already documents which have *no* public page (Louis/Dressner, Kermit Lynch,
   Selection Massale, Vom Boden, Rosenthal, T. Edward, Polaner, Skurnik). Mark
   those `mining_mode=backlink` and route them to Mode B.

3. **Mode B — backlink / co-mention mining (when no stockist page exists).**
   Run **Serper Web** (`google.serper.dev/search`, the primitive the `press`
   enrich step uses) with site-agnostic queries that surface retailers naming the
   supplier in inventory, blog, or press copy:

   ```
   SUPPLIER_QUERIES = [
     '"{supplier}" wine shop -site:{supplier_domain}',
     '"{supplier}" "now in stock"',
     '"{supplier}" "we carry" OR "available at"',
     '"{supplier}" butcher OR farm share',        # butcher
     '"{supplier}" cheese shop OR fromagerie',     # cheese
     '"{supplier}" flour OR "freshly milled" bakery',  # bakery
   ]
   ```

   Take the organic result domains, drop the supplier's own domain and known
   aggregators (Wine-Searcher, Yelp, Instagram, marketplaces), and treat each
   surviving retailer domain as a candidate. This is the same backlink logic
   `directories/_stockists.py` already applies to importer pages, just driven by
   search instead of an on-site link list.

4. **Mode C — on-site supplier-name confirmation.** For every candidate from A/B,
   confirm the upstream tie by crawling the candidate's own site for supplier
   mentions (concurrent crawl, the `detect_clubs.py` 50-thread pattern). A page
   that names the supplier in product, sourcing, or About copy is a hard edge; a
   single Serper hit with no on-site confirmation is a soft edge. Capture the
   exact matched string + URL for outbound evidence.

5. **Resolve candidates to businesses.** Resolve each domain to a real venue
   (homepage → name/city/state; cross-check against Google Maps where ambiguous)
   so the standard funnel can enrich it. Drop the suppliers themselves,
   wholesalers, and any pure marketplace.

6. **Score supplier curation (promotion gate — not `config.SCORING_WEIGHTS`):**

   ```
   tier1_supplier   = candidate names a Tier-1 supplier (Skurnik, Heritage, Jasper Hill, Central Milling, ...)
   supplier_count   = distinct registry suppliers the candidate names
   confirmed        = on-site mention found (Mode C), not just a search hit
   has_ccp          = ACS CCP credential found on staff/About page (cheese only)

   if confirmed and (tier1_supplier or supplier_count >= 2):  tier = 1
   elif confirmed or supplier_count >= 2:                      tier = 2
   elif supplier_count >= 1:                                   tier = 3   # unconfirmed single edge -> corroborate
   else: drop
   ```

7. **Hand resolved candidates to the standard funnel.** Emit the canonical CSV
   below, union into `output/directories_all_<YYYYMMDD>.csv` via
   `discover_directories.py --master-only`, then feed Tier 1/2 into
   `main.py --enrich` + `score.py` for ICP scoring and `reclassify.py` for the
   wine-bar claw-back and partner-type demotions. Supplier tier is the
   *curation-quality* annotation; `score.py` stays the source of truth for ICP Fit.

## Output schema

```
output/directories/supplier_importer_graph_<YYYYMMDD>.csv
source = "supplier_importer_graph"
tier = <1|2|3>                       # supplier-curation tier (seed-quality), not score.py tier
business_type = <wine_store | butcher | cheese | bakery — from supplier vertical, reclassify later>
distinction = "Stocks {n} respected suppliers ({verticals}): {top_supplier_names}"
year = <scan year>
source_url = <stockist page or strongest backlink article>
blurb = <matched on-site sourcing sentence, verbatim>
+ evidence cols:
    name, city, state, country, website,
    matched_suppliers,            # verbatim registry names matched
    supplier_count, tier1_supplier,
    mining_mode,                  # stockist_page | backlink | both
    confirmed,                    # on-site mention found (Mode C)
    matched_quote, matched_url,   # exact sourcing copy + page for the cite
    has_ccp,                      # cheese: ACS Certified Cheese Professional on staff
    scan_date
```

`matched_suppliers` + `matched_quote` preserve the exact upstream tie so a BDR
can open with "saw you carry {Skurnik / Heritage Foods / Jasper Hill}" — the
cite-the-trigger evidence that justifies a Curation list.

## Volume & cost

- Registry: ~30-40 suppliers across four verticals.
- Mode A stockist pages: ~10-15 suppliers with public pages, free to scrape
  (httpx; occasional Playwright). Each yields ~50-400 retailers ⇒ ~1,500-3,000
  raw rows.
- Mode B backlink: ~25 suppliers × ~6 queries = ~150 Serper Web calls ≈ **~$1**.
  Yields ~1,000-2,000 more candidate domains (heavy overlap with Mode A).
- Mode C confirmation crawl: ~3,000-4,000 unique domains, concurrent site crawl,
  free. Haiku is *not* needed for confirmation (regex over registry names);
  reserve Haiku only for parsing messy HTML stockist lists in Mode A ≈ **~$3-5**.
- **Per-run total: ~$5-15.**
- **Net-new candidates per run: ~2,000-3,500 unique, of which ~300-600 reach
  Tier 1** (confirmed + Tier-1 or multi-supplier). Substantial overlap with the
  existing wine/butcher universe is expected; the value is the *supplier-curation
  annotation* that re-prioritizes those rows and surfaces craft retailers no
  keyword Maps sweep cleanly isolates.

## Refresh cadence

**Quarterly.** Stockist relationships and supplier rosters are durable — a
retailer that carries Heritage Foods this quarter carries it next quarter — so
frequent re-scraping wastes effort. The *registry*, not the graph, is what moves:
add a supplier (a new respected importer, a regenerative ranch surfaced from
EatWild) and re-run to harvest a fresh neighborhood. Trigger an off-cycle run
when the supplier lexicon grows materially rather than on a fixed clock alone.

## Risks

- **Registry quality is everything.** An off-ICP supplier (a volume distributor,
  a commodity brand) pollutes the entire downstream harvest. Keep the registry
  curated and tier-weighted; never auto-ingest suppliers from an unvetted list.
- **Liquor-store / commodity leakage (wine).** A "where to buy" page for a
  large importer will list grocery and liquor stores alongside curated shops.
  Screen wine candidates for commodity/liquor SKUs (Tito's, Smirnoff, Veuve,
  Josh, Barefoot, Kendall Jackson, Meiomi, Duckhorn, Yellowtail, etc.) and
  liquor-store ESP red flags (City Hive, Spot Hopper) before any sales handoff.
  A shop carrying Skurnik *and* Tito's is a liquor store with a natural-wine
  shelf, not a curated wine merchant — net the SKUs against the supplier match.
- **Chain / franchise leakage.** Whole Foods, Total Wine, regional grocery chains
  all carry "respected" suppliers. Run `config.CHAIN_KEYWORDS` filtering and
  `reclassify.py` on resolved candidates; drop 10+-location operators.
- **Wine-bar exclusion.** A wine *bar* may carry the same importers as a retail
  shop. Carry partner_type through and apply the `reclassify.py` wine-bar
  claw-back — wine bars are mostly excluded except geographic-monopoly cases.
- **Sweets-only demotion (bakery).** A bakery surfaced via a flour-mill tie is
  still capped at Tier 2 per ICP single-product rules; the supplier edge can't
  mint a Tier 1 sweets-only shop.
- **False positives from blog/press mentions.** A retailer that *blogged about*
  visiting Jasper Hill once is not a stockist. This is why Mode C on-site
  *current-inventory* confirmation matters; unconfirmed single backlinks land
  Tier 3 for corroboration, never auto-promoted.
- **Small-market thinness.** A dominant rural butcher sourcing from a named ranch
  may have minimal social/review volume — don't DQ on raw metrics; the supplier
  edge *is* the signal. Static-only social understates these brands.
- **Stale / proprietary stockist data.** Many traditional importers publish no
  public retailer list (already documented in `directories/__init__.py`), and
  published lists go stale. Mode B backlink mining is the fallback; expect
  partial coverage and never block a run on one supplier returning nothing.

## Repo placement

```
directories/
  __init__.py                        # ADD: register supplier_importer_graph_* sources in ALL_SOURCES
  supplier_registry.csv              # NEW: curated supplier lexicon (supplier, vertical, tier, stockist_url, mining_mode)
  _stockists.py                      # EXISTING: reuse stockist-page + backlink scrape lib
  _browser_fetch.py                  # EXISTING: Playwright fallback for blocked pages
  _supplier_graph.py                 # NEW: shared engine — Mode A harvest, Mode B Serper backlink,
                                     #      Mode C on-site confirmation, curation scoring
  wine/supplier_importer_graph.py    # NEW: scrape() over wine importer registry rows
  meat/supplier_importer_graph.py    # NEW: scrape() over ranch/farm registry rows
  cheese/supplier_importer_graph.py  # NEW: scrape() over affineur registry rows + CCP mining
  specialty/supplier_importer_graph_bakery.py  # NEW: scrape() over flour-mill registry rows
discover_directories.py              # EXISTING orchestrator — no change; picks up new ALL_SOURCES rows
                                     # (--source supplier_importer_graph / --category wine|meat|cheese)
config.py                            # ADD: aggregator/marketplace deny-list for backlink filtering
```

Refactor target: the per-vertical `scrape()` modules should be thin wrappers
that pass their registry slice to `_supplier_graph.py`; all four verticals share
one engine and differ only in registry rows and the confirmation lexicon. Reuse
the wine commodity/liquor SKU deny-list from Engine 07 and the butcher upstream
lexicon from Engine 06 rather than re-listing them.

## Open questions

1. Which suppliers actually publish a **public, scrapeable stockist page** today
   vs. require Mode B? `directories/__init__.py` lists the wine importers with no
   public list as of last probe — re-verify, and establish whether butcher
   ranches (Heritage, Niman) and mills (Central Milling) expose retailer locators.
2. Is **on-site confirmation (Mode C)** strict enough on its own, or do we need a
   recency check (current-inventory page vs. an old blog post) to keep stale
   mentions out of Tier 1?
3. For **cheese**, is the ACS CCP credential mined reliably off shop About pages,
   or is it sparse enough that affineur stockist ties carry the vertical alone?
4. Should a supplier-graph hit **stamp the upstream evidence onto an existing
   high-ICP row** as well as mint net-new candidates — like Engine 04 — so the
   "you carry {supplier}" cite is available even for already-known shops?
