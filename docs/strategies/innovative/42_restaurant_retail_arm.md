# Lead Engine 42 — Retail Arm of Restaurant List

**Motion:** Curation (with a structural retail-SKU Trigger overlay → Hybrid in practice)
**Vertical fit:** Restaurants that have grown a retail/CPG arm — sauces, pasta kits, butcher/meat boxes, wine packs, bread programs, pantry goods, meal kits, holiday/gift packages. Secondarily butcher-/bakery-leaning restaurants whose retail line is the real ICP.
**Suggested list name(s):** `restaurant_retail_arm`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$8–16/run (rides the step-1 websites crawl; net-new cost is a shop/product-page detection pass + a small Claude classify pass; optional Apify link-in-bio resolution)

## Premise

Restaurants are the *lowest*-AGMV partner types we touch (neighborhood
restaurant $32.0k, destination $60.5k) and the hardest to qualify on
reservations alone — many great restaurants simply do not run scarce books.
But a restaurant that has stood up a **retail arm** — bottling its own sauce,
shipping pasta kits, selling a weekly bread program, packaging butcher boxes
or curated wine packs, running a holiday gift catalog — is broadcasting that
it already thinks in *products and repeat purchase*, not just covers. That is
a restaurant behaving like a butcher/wine/cheese operator, which is exactly
the headroom Table22 wants. The retail arm is the bridge from restaurant
demand to recurring commerce for operators who would never clear a
reservation-difficulty gate.

In the two-score model this is a strong **ICP Fit** lift (the operator has
proven it can build and merchandise a sellable SKU line) plus a clean
**Trigger** ("you already sell {product} as a one-off — a Table22 club turns
that into recurring revenue"). It maps to demand-over-capacity: a restaurant
selling out of jarred sauce or holiday pasta boxes has demand the kitchen
floor can't capture, and a subscription is the obvious capacity expansion.

It is **Curation-first**: a retail SKU line is the qualifying signal, but the
same shape catches gift-card pages, branded-merch (t-shirt/hat) stores, and
third-party CPG resale. So we curate hard — the retail-arm trigger only counts
once the row clears an ICP-fit floor and the SKUs are *the restaurant's own
food/beverage products*, not swag or gift cards.

## Recipe

A **postprocessing overlay** over restaurant rows that already cleared
discovery + `websites` enrichment, plus a thin shop/product-page detection
pass. It reuses the step-1 crawler, an optional Apify link-in-bio resolve, a
Claude classify pass, `detect_clubs.py`, and `reclassify.py`. No fresh Serper
discovery is required to start.

1. **Seed the universe (restaurant-biased).** Take a scored or at-least
   `websites`-enriched CSV — `output/2_enriched_websites.csv`, a
   `custom-serper-scoring_*_all.csv`, or the `scrape_beli/` restaurant output.
   Favor `business_type in {restaurant}` and `partner_type in
   {destination_restaurant, neighbourhood_restaurant, deli, market}`. For
   net-new geography, seed Serper Maps off `research/trendy_neighborhoods/`
   (~56.5% of partners sit in trendy neighborhoods) with restaurant keyword
   queries. The point of this engine is to *rescue* restaurants that score low
   on reservations but have a real retail line.

2. **Detect a shop / retail line (rides step-1 crawl + a NEW page-class pass).**
   The step-1 `websites` crawl already emits `has_ecommerce`, social links,
   email-signup, and reservation-platform detection. Extend the parse layer to
   look for a *restaurant-operated retail surface* — nav links, anchor text,
   button CTAs, sitemap entries, and platform fingerprints:

   ```
   SHOP_SURFACE (nav/anchor/CTA/path — flags a retail arm exists):
     /shop, /store, /market, /provisions, /pantry, /merch (food only),
     /order-online (retail vs reservation — disambiguate), /gift(s)?,
     /products?, /collections?, "shop our", "ship nationwide", "order a box",
     "buy our {sauce|pasta|bread|sausage|spice|wine}", "send a gift box",
     "nationwide shipping", "now shipping", "frozen + shipped"
   COMMERCE PLATFORM globals (corroborate a real cart, not brochure):
     window.Shopify / cdn.shopify.com / x-shopid, squarespace-commerce,
     square-online (squareup/weebly), bigcommerce, ecwid, snipcart, foxycart,
     goldbelly (3P shipped-food marketplace — strong retail-arm tell)
   ```

3. **Classify the SKU line (regex seed → Claude confirm).** Read product/menu
   page titles + descriptions and bucket the retail line. The product *type*
   matters for ICP and for outbound copy:

   ```
   RETAIL_SKU_PATTERNS (the qualifying SKUs):
     sauce|marinara|hot sauce|chili crisp|salsa|condiment|jam|preserve
     pasta (kit|dried|fresh)|ravioli kit|lasagna kit|meal kit|cook-at-home
     bread|loaf|focaccia|bagel|babka|laminated|"bake at home"
     butcher box|meat box|sausage|charcuterie|dry-aged|whole-animal|"meat share"
     wine pack|bottle club|"3-pack"|"6-pack"|case|cellar pick
     pantry|spice|oil|vinegar|coffee|granola|honey
     holiday (box|kit|package)|thanksgiving|easter|gift box|"feed N"
   NON_QUALIFYING (swag / not a food retail arm — do NOT count):
     t-?shirt|hoodie|hat|cap|tote|sticker|mug|merch (apparel)
     gift card|e-gift|"buy a gift card"
     cookbook only (book — soft, ties to Engine 07, not a retail SKU)
   ```

   For ambiguous rows, send the sampled SKU titles + the richest descriptions
   to Claude (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to
   label `retail_arm_kind ∈ {own_food_cpg, meal_kit, butcher_box, wine_pack,
   bread_program, pantry_line, holiday_gift_only, swag_or_giftcard_only,
   third_party_resale, none}` and emit a one-line `trigger_summary` sales can
   quote. Prefix the invocation with `unset ANTHROPIC_API_KEY &&` (shell
   empty-key gotcha).

4. **Resolve link-in-bio (optional, Apify).** Restaurants often park the shop
   link only in the IG/FB bio (Goldbelly, Shopify subdomain, Linktree). For
   rows with a social handle and *no* website-side shop surface, resolve the
   bio destination via the **Apify instagram-profile-scraper** (already wired;
   batches of 30 — reuse the step-2 hook) and re-run step-2/3 matching against
   the resolved URL. Fall back to website-only matches when bio resolution
   fails — don't block the row.

5. **Negative-monetization corroboration (reuse `detect_clubs.py`).** Run
   `detect_clubs.py` (50-thread scrape) for `has_club`, `club_type`,
   `club_url`, `club_signals`. A restaurant already running a sauce-of-the-month
   or wine club is a **positive** switch signal — tag `route =
   nurture_transition` and hand to Engine 01, do not discard. The pure-play
   target is a retail arm present (`retail_arm_kind != none`) with **no
   subscription rail yet** (`has_club == False`) — they sell one-off, we make
   it recurring.

6. **Apply the ICP gate (curation half).** Run `reclassify.py` (`partner_type` /
   `business_type_v2`, wine-bar claw-back) and reject anti-ICP before scoring:

   ```
   DISQUALIFY if:
     retail_arm_kind in {swag_or_giftcard_only, third_party_resale, none}
     partner_type == liquor_store, or wine commodity-SKU leak in the pack
        (Tito's, Smirnoff, Veuve, BuzzBallz, Budweiser, Josh, Cupcake, Barefoot,
         Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic,
         Andre, Cloud Break) or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher-lane row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     holiday_gift_only          # seasonal-only line — real but thin recurring base
     sweets-only / single-product (cookie-only bread program)
     static-social-only / thin metrics in small market   # never DQ; understates brand

   retail_strength:
     +3 own_food_cpg|butcher_box|wine_pack on a real cart, named/described SKUs
     +2 meal_kit|bread_program|pantry_line with a shipping/order box
     +2 Goldbelly presence or "ship nationwide" (proven D2C ambition)
     +1 holiday_gift_only (seasonal recurring spike pattern)
     +1 has_email_list (audience to convert — ties to Engine 20)
     +1 if has_club == True (proven recurring demand -> route nurture_transition)

   QUALIFY (engine output) if: passes ICP gate AND retail_strength >= 2
   ```

7. **Reclassify + dedupe + hand off to scoring.** `reclassify.py` then
   `dedupe_existing.py` (phone-first, then name+address). Emit the canonical CSV
   (below) and run `score.py` **unmodified** — do not touch
   `config.SCORING_WEIGHTS` (SHAP-aligned). The retail-arm columns ride as
   evidence; `retail_strength` orders the outbound queue inside a tier. Note: a
   qualified row here will often score low on the SHAP model (restaurant
   partner type, no reservation difficulty) — that is expected; this engine's
   value is the *trigger*, not the base score, so surface `retail_strength`
   prominently to sales rather than relying on tier alone.

## Output schema

```
output/restaurant_retail_arm/restaurant_retail_arm_<YYYYMMDD>.csv
source = "restaurant_retail_arm"
tier = <1|2|3>     # 1 = own CPG / butcher box / wine pack on a real cart; 2 = meal kit / bread / pantry / holiday-only; 3 = ICP-soft
business_type = restaurant | deli | market | bakery | butcher
distinction = "Restaurant sells {retail_arm_kind} retail ({n} SKUs) one-off — make it recurring with Table22"
year = <discovery_year>
+ canonical: name, city, state, country, source_url (= website), blurb
+ evidence cols (preserve verbatim so sales can cite the trigger in outbound):
    retail_arm_kind        # own_food_cpg | meal_kit | butcher_box | wine_pack | bread_program | pantry_line | holiday_gift_only
    shop_surface_url        # the actual /shop, /store, /provisions, or Goldbelly URL
    retail_sku_count        # int — number of distinct food SKUs detected
    sample_sku_titles       # 2-3 example product names sales can name in outbound
    sample_sku_snippet      # verbatim product copy for the cold-email hook
    has_ecommerce           # from step-1 (true if a real cart backs the retail arm)
    commerce_platform       # shopify | squarespace | square | goldbelly | none
    ships_nationwide        # bool ("ship nationwide" / Goldbelly tell)
    found_on                # website | link_in_bio | both
    has_email_list          # from step-1 / Engine 20 overlay
    has_club                # from detect_clubs.py (positive switch signal)
    club_signals            # raw detect_clubs output
    retail_strength         # int, intra-tier outbound ordering
    trigger_summary         # one-line Claude-written outbound hook
    partner_type            # from reclassify.py
    route                   # sales | nurture_transition (club-present spillover)
```

Master union: `output/restaurant_retail_arm/restaurant_retail_arm_all_<YYYYMMDD>.csv`.

## Volume & cost

Bounded by input size, not fresh discovery. Over a typical restaurant-heavy
corpus (the generic-pipeline enriched set + `scrape_beli/` restaurant rows),
restaurants are the largest slice — assume **~6–10K restaurant rows** in scope.

- Shop-surface detection (rides step-1 parse + cheap SHOP_SURFACE/platform
  scan): zero marginal fetch on already-crawled rows. **Roughly 10–18%** of
  indie restaurants run any retail surface beyond gift cards →
  **~700–1.6K candidates**.
- Classify pass filters swag/gift-card-only and third-party resale: of those,
  **~55–70%** carry a real own-food retail line → **~450–1.1K** retail-positive.
- After the ICP gate + `retail_strength >= 2` (drops swag-only, holiday-only
  demotions that fall below 2, liquor/chain leakage): expect
  **~250–500 qualified net-new leads per run**, ~80–150 of them tier-1
  (own CPG / butcher box / wine pack on a real cart).

Cost arithmetic: shop detection folds into the step-1 crawl (zero marginal
request). `detect_clubs.py` is a second 50-thread fetch (near-free compute).
Paid lines: Claude Haiku classify on candidates (~700–1.6K short prompts) ≈
**$2–5**; optional Apify link-in-bio resolution only for candidates with a
handle and no website-side surface (~25–35%, ≈250–500 profiles at batches of
30, ~$0.002–0.004/profile) ≈ **$1–2**. No Serper Web, no Resy, no reviews
calls added. **Per-run total: ~$8–16.**

## Refresh cadence

**Quarterly per vertical, with a heavy pre-holiday run in late September and
late October.** A restaurant's retail arm turns over slowly once built, so
monthly mostly re-surfaces the same rows. The two high-value diffs are
seasonal and structural: (1) the **holiday gift catalog** appears for only
~6–8 weeks and is the best one-off-to-recurring pitch window — catch it live;
(2) a previously-qualified row that **launches a subscription** between runs
(this run's `has_club == True` ∩ last run's set) flips to Engine 01 / 09 as a
platform-switch lead. Pull a heavier pass pre-holiday, when restaurants stand
up gift/preorder boxes they currently process by hand.

## Risks

- **Branded-merch / gift-card false positives.** A `/shop` selling t-shirts,
  hats, and gift cards reads as a retail surface but is not a food retail arm.
  The NON_QUALIFYING regex + the Claude `retail_arm_kind` label must drop
  `swag_or_giftcard_only` *before* `retail_strength` — this is the single
  biggest false-positive trap for this engine.
- **Anti-ICP leakage on a loud trigger.** A 12-location group or a
  cocktail-bar-with-merch can run a Shopify store too. Keep
  `config.CHAIN_KEYWORDS`, the wine commodity-SKU list, and the City Hive /
  Spot Hopper ESP red flags upstream of `retail_strength`.
- **Low base score is expected, not a defect.** A neighborhood restaurant
  ($32.0k) with a sauce line will land mid/low tier on the SHAP model (no
  reservation difficulty, restaurant partner type is the dominant negative
  feature). Do not let scoring tier alone gate sales — `retail_strength` and
  `retail_arm_kind` are the qualification here. Risk is sales deprioritizing
  genuinely good leads because the /100 is modest.
- **Third-party resale vs own product.** A restaurant selling another brand's
  olive oil or coffee on its shop page is reselling, not merchandising its own
  demand. The Claude classify must separate `own_food_cpg` /
  `third_party_resale`; only the former is the recurring-revenue thesis.
- **Holiday-only thinness.** A restaurant that only sells a Thanksgiving box
  has a real but seasonal line — cap at Tier 2, don't promote on trigger alone;
  the recurring base is thin outside the season.
- **Off-domain / Goldbelly-only commerce.** The retail arm may live entirely on
  Goldbelly or a Shopify subdomain not linked from the marketing nav. Follow
  obvious "shop / order a box / ship nationwide" outbound links one hop and
  resolve link-in-bio before declaring "no retail arm," or we miss the best
  D2C-ambitious operators.
- **Wine-pack / liquor-store nuance.** A restaurant selling curated wine packs
  is great; a place reselling commodity bottles is a liquor-adjacent leak.
  Enforce the commodity-SKU exclusion and the `reclassify.py` wine-bar claw-back
  before scoring. Wine bars stay out except geographic monopolies.
- **Small-market metrics run low; static social understates brand.** A
  destination restaurant in a small market with a famous sauce may under-index
  on raw followers/reviews. Weight relative local dominance + the retail signal
  over raw social; never DQ on static-only social (`follower_count` is IG + FB).
- **Sweets-only / single-product demotion.** A restaurant whose only retail SKU
  is cookies is a real line but single-product — cap Tier 2; `retail_strength`
  must not override the demotion.
- **Rate-limit fragility.** Shop-surface + sitemap + link-in-bio resolution over
  thousands of domains will 429 if aggressive. Throttle, jitter, cache by ETag,
  back off per-domain; batch Apify profiles at 30.

## Repo placement

An overlay package mirroring the niche-lane shape (cf. Engines 02 and 32),
reusing the step-1 crawler as a library and adding a shop/product detection
pass.

```
restaurant_retail_arm/
  __init__.py                  # engine constants; SHOP_SURFACE + RETAIL_SKU_PATTERNS + NON_QUALIFYING
  signals.py                   # shop-surface/platform fingerprints, SKU regex, swag/giftcard + commodity-SKU/ESP leak lists
  detect_retail_arm.py         # parse layer over enrich.py step-1 crawl output (shop surface + commerce platform + Goldbelly)
  classify.py                  # Claude haiku-4-5: retail_arm_kind (own CPG vs swag/resale/none), trigger_summary
  resolve_link_in_bio.py       # wraps Apify instagram-profile-scraper (reuse step-2 batching) for bio-only shop links
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), retail_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_restaurant_retail_arm.py   # orchestrator (mirrors discover_butchers.py / discover_product_story_no_ecomm.py)
  python discover_restaurant_retail_arm.py --input output/2_enriched_websites.csv
  python discover_restaurant_retail_arm.py --input output/custom-serper-scoring_*_all.csv
  python discover_restaurant_retail_arm.py --master-only
config.py
  + reuse existing commodity-SKU exclusion list + City Hive / Spot Hopper red flags
  + optional new RETAIL_SKU_PATTERNS / GOLDBELLY tells if shared with other engines
```

Refactor target: extract the `enrich.py` **step-1** platform-detection +
`has_ecommerce` parsing into a shared `enrich_websites_lib` so `enrich.py`,
Engine 19's `detect_shopify.py`, Engine 32's `detect_ecommerce.py`, and this
engine's `detect_retail_arm.py` all detect carts/platforms identically without
duplicating the crawl — the same shared-lib argument Engines 02, 05, 09, 19,
20, and 32 raise; build it once. The only genuinely new code here is the
SHOP_SURFACE classifier + Goldbelly detection in `detect_retail_arm.py` and the
SKU-type classifier in `classify.py`; both are stateless and read public
endpoints only.

## Open questions

1. **Where does the retail arm "live" for scoring?** A restaurant with a real
   CPG line arguably behaves like a `specialty_grocer` or even `butcher`
   economically, not a restaurant. Should `reclassify.py` get a rule to
   reclassify a restaurant with a strong own-food retail arm into a
   retail-leaning `partner_type` so it scores against the right (higher) AGMV
   band, or do we leave the SHAP model alone and lean entirely on
   `retail_strength`?
2. **Goldbelly as a standalone source.** Goldbelly is a curated marketplace of
   restaurant-operated shipped-food shops — should it be its own
   `directories/` source (backlink/stockist mining like the importer lanes)
   that *seeds* this engine, rather than only a fingerprint we detect on
   already-discovered sites?
3. **Cross-engine merge with 02 / 20 / 32.** A restaurant with a retail arm but
   no cart and an email list is simultaneously this engine, Engine 32, and
   Engine 20. Do these merge into one "restaurant → recurring commerce" master
   with overlay flags, or stay distinct lists with separate outbound timing?
4. **Holiday slice as its own list.** Does a late-September
   `restaurant_holiday_box_<YYYYMMDD>` cut with its own outbound timing convert
   better than folding seasonal `holiday_gift_only` rows into the evergreen
   master?
