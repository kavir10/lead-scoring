# Lead Engine 45 — Affluent Convenience Gap List

**Motion:** Curation (affluent-geo ICP gate) with a commerce-infra-absence Trigger overlay → Hybrid in practice
**Vertical fit:** Wine, butchers, cheese, bakeries (high-AGMV, recurring-household-need verticals)
**Suggested list name(s):** `affluent_convenience_gap`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (rides existing Serper Maps discovery + `enrich.py` step-1 crawl; net-new cost is geo-tagging and a small link-in-bio + Claude classify pass)

## Premise

The model is Lincoln Park (Chicago): a premium butcher, cheese shop, or wine
store sitting in a dense, high-income, low-patience residential neighborhood —
a customer base with money, recurring household need (meat, bread, wine,
cheese every week), and zero tolerance for friction — but the shop itself has
**no delivery, no preorder, no subscription, no online ordering**. The demand
is sitting in the catchment area; the shop has built no machinery to capture
it on a recurring basis. That gap is the buy signal.

This is the demand-over-capacity thesis read through *geography* rather than
through social or reservation signals. We're not asking "is this shop
popular?" — we're asking "does this shop sit in a catchment that proves
recurring, affluent, repeat-purchase demand, while the shop has no recurring
commerce surface to serve it?" The affluent-neighborhood layer is the cleanest
public proxy for household disposable income + repeat-purchase cadence we can
get without paid demographic data, and we already have the geography file:
`research/trendy_neighborhoods/` shows 56.5% of active partners sit in trendy
neighborhoods, and the tiered/discovered lists carry per-city neighborhood
granularity.

This is a **Hybrid**: affluent-geo is a strong *ICP* gate (right kind of
business, right kind of catchment) and commerce-infra-absence is the *Trigger*
("reason to contact now — you have the demand, you're leaving recurring
revenue on the table"). Best rows score high on both. A high-ICP shop that
*already* has a club is not disqualified — it just routes to the Engine 01
transition motion instead. A shop with infra-absence but in a non-affluent,
non-recurring catchment gets filtered before sales.

## Recipe

We reuse the generic Serper Maps discovery to enumerate premium shops, the
`enrich.py` step-1 crawler to detect commerce infrastructure, and the
`research/trendy_neighborhoods/` files to score the affluent-geo half. The
only genuinely new primitive is a **neighborhood/affluence geo-tagger** that
maps a discovered address to a neighborhood and joins it against the trendy
lists — proposed below as a shared lib, not a one-off.

1. **Discover the premium-shop universe (affluent-geo first).** Drive Serper
   Maps off the affluent neighborhood seeds rather than raw city centroids.
   Read `research/trendy_neighborhoods/trendy_neighborhoods_top100_us_tiered_20260531.csv`
   and `trendy_neighborhoods_uncovered_cities_20260601.csv` (schema
   `city, state, partner_count, neighborhood, notes`), and issue per-neighborhood
   Serper Maps queries (`"{neighborhood} {city}"` geo-bias) for
   `butcher | cheese shop | wine store | bakery | specialty grocer`. Reuse
   `scripts/fresh_icp_search.py` query shape and `discover.py` quality floors
   (niche ≥20 reviews / ≥4.0, requires website) and the `config.CHAIN_KEYWORDS`
   chain filter. Dedupe by phone against the existing corpus.

2. **Geo-tag each result to a neighborhood + affluence band.** New step. For
   each discovered row, map its Google Maps address → neighborhood and join
   against the trendy lists to set `neighborhood`, `matched_trendy_neighborhood`,
   `neighborhood_tier`, and `affluence_band`. Mirror the classification method
   already proven in `research/trendy_neighborhoods/` (address → neighborhood
   via Claude geography knowledge, then list match). Carry `confidence`. Rows
   in `uncovered_cities_no_trendy_area_20260601.csv` cities (no genuine trendy
   district) are flagged `affluence_band = none` and demoted, not discarded —
   small affluent suburbs can still qualify on relative local dominance.

3. **Detect the commerce gap (the Trigger).** Run `enrich.py` **step 1
   (websites)** — the existing concurrent 10-thread crawl that already emits
   `has_ecommerce`, email-signup form, social links, and reservation-platform
   detection. Extend its parse layer to set explicit absence flags:

   - **No ecommerce / online ordering:** no Shopify/Squarespace/WooCommerce
     cart, no `square.link`/`checkout.square.site`, no Toast/Olo/online-order
     CTA.
   - **No delivery:** no DoorDash/UberEats/Mercato/Instacart link, no "we
     deliver" / "local delivery" / "shipping" CTA.
   - **No preorder / subscription:** no preorder form, no
     `subscribe|membership|club|box|CSA|meat share|wine club` CTA. Reuse the
     phrase scan from Engine 02's manual-order extractor.
   - **Static contact-only:** primary CTA is phone / address / hours only.

4. **Resolve link-in-bio before declaring "no commerce."** A shop's only
   ordering link is often in the IG bio, not the site. For rows with a social
   handle and no website-side commerce, resolve the bio target (Linktree,
   Beacons, raw URL) via the **Apify instagram-profile-scraper** (reuse the
   step-2 batching, batches of 30) and re-run the step-3 detection against the
   resolved destination. This prevents false "gap" reads.

5. **Classify the gap (Claude, cheap pass).** For ambiguous rows, send the
   crawl snippet to Claude (`claude-haiku-4-5`, same model `scrape_beli` uses)
   to emit `commerce_gap_type ∈ {no_commerce_at_all, retail_no_recurring,
   delivery_no_subscription, has_recurring}` and a one-line `trigger_summary`
   sales can quote. Prefix with `unset ANTHROPIC_API_KEY &&` (shell empty-key
   gotcha).

6. **Cross-check existing club state.** Run `detect_clubs.py` and carry
   `has_club` / `club_type` / `club_url`. A shop that already runs a
   subscription is **not** a `affluent_convenience_gap` lead — it routes to
   Engine 01 (existing-club transition). Existing club is a positive signal,
   just for a different motion; tag it and exclude from this list's QUALIFY set.

7. **Apply the ICP gate + score the gap.** Run `reclassify.py` for
   `partner_type` / `business_type_v2`, reject anti-ICP, then compute the
   composite:

```
DISQUALIFY if:
  partner_type in {liquor_store} or wine commodity-SKU leak (Tito's, Veuve,
      Barefoot, Yellowtail, BuzzBallz, Smirnoff, Kendall Jackson, ...) or
      ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar  -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
  has_club == True  -> route to Engine 01, drop from this list

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery (caps Tier 2)
  static-social-only (small markets understate brand — never DQ on this)
  affluence_band == none (no trendy district; keep only if relative-dominance high)

icp_geo_score (affluent catchment, 0-3):
  +2 neighborhood_tier == 1 (top trendy/affluent)
  +1 neighborhood_tier == 2
  +1 partner_count in neighborhood high (peer-density = proven catchment)

trigger_strength (commerce gap, 0-3):
  +3 no_commerce_at_all (no site cart, no delivery, no preorder, no club)
  +2 retail_no_recurring (one-time ecommerce but no subscription/preorder)
  +1 delivery_no_subscription (delivery exists, no recurring program)
  +1 partner_type in {butcher, wine_store, cheese}  # highest-AGMV recurring need

QUALIFY (engine output) if: passes ICP gate AND icp_geo_score >= 2 AND trigger_strength >= 2
```

8. **Hand off to scoring.** Emit the canonical CSV (below) and let `score.py`
   run unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned).
   The geo + gap columns ride as evidence; sort the outbound queue by
   `icp_geo_score + trigger_strength` inside each tier.

## Output schema

```
output/affluent_convenience_gap/affluent_convenience_gap_<YYYYMMDD>.csv
source = "affluent_convenience_gap"
tier = <1|2|3>     # 1 = butcher/wine/cheese in tier-1 neighborhood + no_commerce_at_all
                   # 2 = bakery/specialty, or tier-2 geo, or partial gap
                   # 3 = ICP-soft / affluence_band none kept on relative dominance
business_type = butcher | wine_store | cheese | bakery | specialty | restaurant
distinction = "Affluent {neighborhood} catchment, {commerce_gap_type} — recurring demand, no recurring commerce"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    neighborhood                 # mapped from address
    matched_trendy_neighborhood  # joined trendy-list entry, if any
    neighborhood_tier            # 1 | 2 | none
    affluence_band               # high | mid | none
    neighborhood_partner_count   # peer density in catchment (proven demand)
    commerce_gap_type            # no_commerce_at_all | retail_no_recurring | delivery_no_subscription
    has_ecommerce                # from enrich step 1
    has_delivery                 # extended step-1 flag
    has_preorder                 # extended step-1 flag
    found_on                     # website | link_in_bio | both | neither
    icp_geo_score                # int
    trigger_strength             # int
    trigger_summary              # one-line Claude-written outbound hook
    has_club                     # carried from detect_clubs.py (routes to Engine 01 if True)
    partner_type                 # from reclassify.py
```

## Volume & cost

- **Discovery:** ~600 affluent neighborhoods (tiered + uncovered lists) × 5
  business types, geo-biased Serper Maps. Many neighborhoods are tiny; expect
  ~3–6 net-new premium shops per (neighborhood × type) after dedupe and chain
  filtering. Realistically **~3K–5K Serper Maps calls** → at Serper Maps
  pricing (~$1 / 1K credits) ≈ **$3–6**.
- **Step-1 crawl:** rides the existing 10-thread crawler; +1 parse pass for
  the absence flags, no new fetch cost.
- **Link-in-bio resolution (Apify profile scraper):** only for rows with a
  social handle and no website commerce (~35–45%, ≈1.5–2.5K) at batches of 30,
  ~$0.002–0.004/profile ≈ **$5–10**.
- **Claude Haiku classify pass** on ambiguous rows (~2–3K short prompts):
  **≈ $3–5**.
- **Per-run total: ~$11–21.**
- **Net-new qualified leads per run:** of ~6K–10K discovered premium shops,
  affluent-geo gate (`icp_geo_score >= 2`) keeps ~40–55%; commerce-gap trigger
  (`trigger_strength >= 2`) holds on ~30–45% of those; after the ICP gate +
  `has_club` routing, expect **~500–900 qualified rows**, weighted toward
  butcher/wine/cheese in tier-1 neighborhoods.

## Refresh cadence

**Quarterly.** Commerce-infrastructure absence is a *slow-moving* state — a
shop that hasn't built online ordering this year probably won't next month,
and the affluent-neighborhood layer barely changes. A quarterly run catches
(a) newly opened shops in known affluent catchments and (b) shops that *added*
delivery/preorder since last run (which exit the list into Engine 01/02
territory). Pair the geo refresh with the `research/trendy_neighborhoods/`
list whenever that file is regenerated.

## Risks

- **Liquor-store / chain leakage through affluent geo.** Affluent
  neighborhoods are *full* of liquor stores and chain markets. The geo gate is
  loud; the ICP gate must filter. Keep `config.CHAIN_KEYWORDS`, commodity-SKU,
  and ESP-red-flag (City Hive, Spot Hopper) checks upstream of `icp_geo_score`.
- **False "gap" reads.** A shop with full ordering in its IG bio, on a Mercato
  storefront, or via a third-party marketplace looks gap-y on the website
  alone. Step-4 link-in-bio resolution is mandatory before assigning
  `no_commerce_at_all`; record `found_on` so a `neither` is auditable.
- **Affluence ≠ recurring-need fit.** A wine bar or cocktail-forward spot in
  an affluent area scores high on geo but is mostly anti-ICP. Enforce the
  wine-bar exclusion (except geographic-monopoly) and the `reclassify.py`
  wine-bar claw-back. Geo alone never qualifies a row.
- **Small-market / suburban undercount.** A great butcher in an affluent but
  *non-trendy* suburb gets `affluence_band = none` from the trendy list and
  looks weak. Don't DQ — weight relative local dominance and the trigger;
  static-only social understates brand in these markets.
- **Sweets-only demotion.** A cupcake bakery in a tier-1 neighborhood with no
  online ordering is a real gap but a single-product business — cap at Tier 2,
  don't promote on geo + trigger alone.
- **`has_club` mis-route.** A shop already running a club is high-value but
  belongs in Engine 01, not here. If `detect_clubs.py` misses a club (false
  negative), we'll cold-pitch a shop that already has one — keep the
  detect_clubs join strict and carry `club_url` for manual verification.
- **Neighborhood-tagging accuracy.** Address → neighborhood mapping is
  LLM-based and fuzzy at neighborhood boundaries; a shop one block outside a
  trendy line gets mis-tiered. Carry `confidence` and treat low-confidence geo
  as Tier 2, not Tier 1.
- **Geo file drift / coverage gaps.** Cities absent from the trendy lists
  silently get `affluence_band = none`; new affluent areas won't surface until
  the research file is regenerated. Re-probe the `uncovered_cities` file each
  quarter.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing Serper Maps
discovery, the step-1 crawler, and the step-2 Apify hook as libraries.

```
affluent_convenience_gap/
  __init__.py                  # engine constants; registers gap-detection flags
  geo.py                       # NEW: address -> neighborhood -> trendy-list join + affluence_band
  discover.py                  # neighborhood-seeded Serper Maps (reuse fresh_icp_search shape + discover.py floors)
  detect_gap.py                # parse layer over enrich.py step-1 crawl (ecommerce/delivery/preorder absence)
  resolve_link_in_bio.py       # wraps Apify instagram-profile-scraper (reuse step-2 batching)
  classify.py                  # Claude haiku-4-5 commerce_gap_type + trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), geo/trigger scoring, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_affluent_convenience_gap.py   # orchestrator: discover -> geo-tag -> detect-gap -> bio-resolve -> classify -> gate -> finalize
```

Refactor targets: (1) extract the `enrich.py` step-1 commerce-detection
parsing (ecommerce flag, social links, plus new delivery/preorder flags) into
a shared `enrich_websites_lib` so `enrich.py` and `detect_gap.py` parse
identically without duplicating the crawl (same shared-lib argument as
Engine 02). (2) Promote the `research/trendy_neighborhoods/` address →
neighborhood → trendy-list join into the reusable `geo.py` so other geo-aware
engines (Engine 10 small-market dominance) can call it.

## Open questions

1. **Affluence proxy depth.** Is the trendy-neighborhood list a strong enough
   stand-in for household income + repeat-purchase cadence, or do we need a
   paid demographic overlay (median income / household density by ZIP) to
   separate "trendy but young-renter" from "affluent recurring-household"
   catchments? Trendy ≠ affluent in some neighborhoods.
2. **Marketplace presence = gap or not?** A shop on Mercato/Instacart has
   *some* recurring surface but no owned subscription. Is that a
   `delivery_no_subscription` qualify (Table22 owns the relationship) or a
   demote (already monetizing recurring)? Likely qualify, but confirm the
   outbound line lands.
3. **Geo granularity for boroughs.** The trendy file has a known
   Brooklyn/Queens undercount (boroughs filed under "New York"). Do we union
   borough neighborhoods into NYC before tagging, or treat boroughs as their
   own cities? Affects tier assignment for a dense, high-value market.
4. **Cross-engine dedupe + merge.** Many qualifying shops already exist in
   awards/directories/butcher lanes. Phone-first via `dedupe_existing.py`, but
   should the affluent-geo + gap evidence *merge onto* an existing partner row
   rather than emit a duplicate, the way Engine 02 raises the same question?
```