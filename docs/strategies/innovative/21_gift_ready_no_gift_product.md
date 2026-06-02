# Lead Engine 21 — Gift-Ready But No Gift Product List

**Motion:** Curation
**Vertical fit:** Cheese, wine, bakery, specialty grocers (shippable/giftable retail; deli/market secondary)
**Suggested list name(s):** `gift_ready_no_gift_product`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $18/run (rides the existing step-1 crawl; net-new spend is link-in-bio resolution + a small Claude classify pass)

## Premise

A merchant whose site is full of gift *language* — "holiday gift," "corporate
gifting," "Mother's Day," "Valentine's," "care package," "host gift," "gift
box," "gift basket" — but who offers **no bundled, purchasable gift product**
is broadcasting demand it can't capture. Customers arrive wanting to gift the
brand; the operator answers with prose and a "call us" instead of a SKU. That
gap is the cleanest possible expression of the demand-over-capacity thesis:
proven gifting intent (you don't write gift copy for a product nobody wants to
give) colliding with a missing fulfilment mechanism. A Table22 prepaid bundle,
seasonal drop, or multi-month gift subscription is the exact product the page
is begging for.

In the two-score model this is a **Curation** engine with a built-in Trigger.
ICP Fit is the gate (is this the right kind of business?) and the gift-copy /
no-gift-SKU mismatch is the Trigger (here's a reason to call now: "you talk
about gifting everywhere but can't sell a gift"). The fit verticals are the
high-AGMV, shippable retail types — cheese ($63.8k), wine ($68.2k), bakery
($34.7k), specialty grocer ($27.9k) — where a gift box is a literal,
monetizable object, not a metaphor. Butcher ($75.9k) qualifies where product
is shippable (jerky, charcuterie, steak boxes); destination restaurants do
not, since their gifting equivalent is a gift card, not a bundle.

This engine pairs naturally with Engine 02 (manual preorder) but inverts the
signal: Engine 02 finds operators *doing* gift commerce painfully by hand;
this one finds operators *announcing* gift demand with **no commerce path at
all** — an even earlier, greenfield Table22 build.

## Recipe

The detection primitive already exists. `enrich.py` **step 1 (websites)** is a
concurrent 10-thread crawl that pulls ecommerce flags, email-signup forms,
social links, and reservation-platform detection. We extend its parse layer
with a **gift-language extractor** plus a **gift-SKU detector**, then compute
the mismatch.

1. **Seed the universe — don't cold-discover.** Feed the existing enriched
   corpus (`output/2_enriched_*.csv`) plus the niche lanes (`best_wine_shops/`,
   `directories/`, awards master, `butcher/`). These rows already cleared
   discovery quality floors and carry `website` + social handles. For net-new
   geography, seed Serper Maps off `research/trendy_neighborhoods/` (≈56.5% of
   partners sit in trendy neighborhoods) for `cheese | wine_store | bakery |
   specialty | butcher`.

2. **Crawl the site for gift LANGUAGE** (extend the step-1 crawler to scan page
   HTML, nav/anchor text, and visible copy; case-insensitive regex):

   ```
   GIFT_LANGUAGE_PATTERNS = (
     r"gift", r"gifting", r"gift\s*(box|basket|set|guide|card)",
     r"corporate\s*gift", r"holiday\s*gift", r"host(ess)?\s*gift",
     r"care\s*package", r"mother'?s\s*day", r"father'?s\s*day",
     r"valentine'?s", r"thanksgiving", r"christmas", r"hanukkah",
     r"easter", r"graduation", r"housewarming", r"thank[\s-]?you\s*gift",
     r"the\s*perfect\s*gift", r"give\s*the\s*gift\s*of",
     r"makes?\s*a\s*great\s*gift", r"send\s*(a|some)\b",
   )
   ```

   Record `gift_language_score` = distinct pattern families matched, and the
   pages they sit on (`/gifts`, `/corporate`, blog posts, homepage hero).

3. **Detect whether a gift PRODUCT actually exists.** This is the load-bearing
   half — a "/gifts" *page* with no add-to-cart is exactly our target. Reuse
   the step-1 ecommerce-flag logic and extend it to look for a **purchasable
   bundle**:

   - Product/collection URLs or page titles matching `gift|bundle|box|set|
     basket|sampler|subscription|club` *with* an add-to-cart / price element
     nearby (Shopify `product-form`, `/products/`, `add to cart`, `$` price
     token in a buy context).
   - Platform hints from step 1 (`has_ecommerce`, Shopify/Squarespace
     Commerce/WooCommerce) — a live store raises confidence the gift gap is
     deliberate, not a tech limitation.

   ```
   gift_product_present = True if (gift-named product URL/collection
       has a price + add-to-cart) else False
   ```

4. **Compute the mismatch (the trigger).** The qualifying signal is
   **high gift language AND no gift product**:

   ```
   gift_intent      = gift_language_score (distinct families, capped at 6)
   gift_gap         = (gift_intent >= 2) AND (gift_product_present == False)
   commerce_capable = has_ecommerce from step 1   # can build a SKU today
   seasonal_hook    = any holiday/occasion family matched (Mother's/Valentine's/Xmas/Thanksgiving)
   ```

5. **Resolve link-in-bio + check social for gift asks.** Gift CTAs and "DM us
   about gift boxes" often live only in the IG/FB bio or pinned posts. Resolve
   the bio target (Linktree/Beacons/raw URL) via the **Apify
   instagram-profile-scraper** (already wired, batches of 30 — reuse the step-2
   hook) and re-run steps 2–3 against the resolved destination. Carry a
   `found_on ∈ {website, link_in_bio, both}` flag.

6. **Classify + write the outbound hook (Claude, cheap pass).** For ambiguous
   rows, send the gift-page snippet + the no-SKU finding to Claude
   (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to confirm the
   gap is real (not a missed cart), label `gift_copy_type ∈ {dedicated_gift_page,
   corporate_gifting, seasonal_occasion, scattered_mentions, none}`, and emit a
   one-line `trigger_summary` a BDR can quote. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

7. **Apply the ICP gate (the curation half).** Run `reclassify.py` for
   `partner_type` / `business_type_v2` (+ wine-bar claw-back), then
   `detect_clubs.py` (an existing club is a *positive* platform-switch signal,
   not a DQ — carry `has_club`). Reject anti-ICP before scoring:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  OR wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, Meiomi, ...) OR
         ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar  -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery
     static-social-only (understates brand in small markets — never DQ on this)

   QUALIFY (engine output) if: passes ICP gate AND gift_gap == True
     tier 1: cheese/wine/butcher + gift_gap + commerce_capable + seasonal_hook
     tier 2: bakery/specialty, or no live store yet, or scattered mentions only
     tier 3: ICP-soft but gift_gap holds (nurture)
   ```

8. **Hand off to scoring.** Emit the canonical CSV (below) and let `score.py`
   run unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned).
   The gift columns ride as evidence; `gift_intent` orders the outbound queue
   inside a tier.

## Output schema

```
output/gift_gap/gift_ready_no_gift_product_<YYYYMMDD>.csv
source = "gift_ready_no_gift_product"
tier = <1|2|3>
business_type = cheese | wine_store | bakery | specialty | butcher
distinction = "Heavy gift language ({gift_copy_type}) but no purchasable gift product — build a Table22 gift bundle"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    gift_language_score        # distinct gift-copy families matched
    gift_copy_type             # dedicated_gift_page | corporate_gifting | seasonal_occasion | scattered_mentions
    gift_pages                 # pipe-delim URLs where gift copy lives (/gifts, /corporate, blog)
    gift_product_present       # bool (the no-SKU finding)
    commerce_capable           # has_ecommerce from step 1 (can build a bundle today)
    seasonal_hook              # bool + which occasion(s)
    matched_terms              # pipe-delim verbatim gift phrases
    found_on                   # website | link_in_bio | both
    trigger_summary            # one-line Claude-written outbound hook
    has_club                   # carried from detect_clubs.py (positive signal)
    partner_type               # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped:
  **~8–12K rows**. No discovery spend — already-crawled businesses.
- Step-1 crawl extension (gift-language + gift-SKU parse): **free** — rides the
  existing 10-thread crawl as +1 parse pass, no new fetch.
- Link-in-bio resolution via Apify profile scraper: only for rows with a social
  handle and *no* website-side gift CTA (~30%, ≈3K). At batches of 30 and
  ~$0.002–0.004/profile ≈ **$8–12**.
- Claude Haiku classify pass on ambiguous rows (~1.5–2K, short prompts):
  **≈ $2–4**.
- **Per-run total: ~$12–16.**
- **Net-new / re-surfaced qualified leads per run:** of ~10K screened, gift
  language is common (~35–45%) but the *gap* (gift copy AND no gift SKU) hits
  **~8–12%** (≈800–1.2K). After ICP gate, expect **~300–500 qualified rows**;
  the strongest are cheese/wine with a live store, a dedicated gift page, and a
  seasonal hook. Many already sit in our corpus — that's fine; the value is the
  fresh, specific build-this trigger that re-prioritizes them.

## Refresh cadence

**Monthly, with heavy runs in early November and late January.** Gift language
spikes seasonally — "holiday gift" copy goes up in Oct–Nov, "Valentine's" and
"Mother's Day" in Jan–Apr. Catching a `seasonal_hook` row *while the occasion
copy is live but the SKU is still missing* makes the outbound land ("you're
promoting holiday gifts but there's nothing to buy — let's ship a box before
Dec"). Off-season the evergreen `gift box / corporate gifting` slice is sticky
and turns over slowly, so monthly suffices.

## Risks

- **Stale / cached pages read as live gaps.** A merchant may have *added* a gift
  bundle since the last crawl, or the page is cached. Re-fetch at run time and
  record fetch timestamp + HTTP status; require the gift page and the no-SKU
  finding from the *same* fetch. Treat a 404'd gift page as low confidence, not
  a hit.
- **"No gift product" false positives.** A site with a gift SKU rendered in JS
  (Shopify Buy Button, an embedded cart, a third-party gift-card widget) can
  look bare to a static crawl. The Claude pass (step 6) and the
  `commerce_capable` check guard this — if `has_ecommerce` is true, demand
  stronger evidence that the gift collection genuinely lacks a buyable bundle.
- **Gift-card ≠ gift bundle.** Many sites sell only a digital gift *card*. A
  gift card is not the prepaid-bundle / subscription product Table22 builds —
  count it as `gift_product_present=False` for *bundle* purposes but flag it so
  sales doesn't open with a wrong assumption.
- **Liquor-store / chain leakage through gift copy.** Liquor stores and chains
  push "gift baskets" hard. The ICP gate must run *upstream* of the trigger —
  keep `config.CHAIN_KEYWORDS`, commodity-SKU, and ESP-red-flag (City Hive,
  Spot Hopper) checks before qualifying.
- **Wine-bar exclusion.** Wine bars mostly excluded (low AGMV) except
  geographic-monopoly; let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake shop advertising "the perfect Valentine's
  gift" is a real trigger but single-product — cap at Tier 2 per the demotion
  rule, don't promote on trigger alone.
- **Small-market metrics run low.** A great rural cheesemonger with gift copy
  may have thin social/review volume. Weight relative local dominance and the
  trigger itself; **never DQ on static-only social** — it understates brand.
- **Link-in-bio fragility.** Apify IG profile scraper rate-limits and Linktree
  HTML changes; batch at 30, back off, and fall back to website-only matches
  when bio resolution fails (don't block the row).

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler
and the step-2 Apify hook as libraries.

```
gift_gap/
  __init__.py                  # engine constants; registers pattern banks
  signals.py                   # GIFT_LANGUAGE_PATTERNS, GIFT_PRODUCT_RULES, SKU/ESP leak lists
  crawl_signals.py             # gift-language + gift-SKU parse over enrich.py step-1 crawl output
  resolve_link_in_bio.py       # wraps Apify instagram-profile-scraper (reuse step-2 batching)
  classify.py                  # Claude haiku-4-5 gift_copy_type + trigger_summary
  aggregate.py                 # gift_gap computation, ICP gate (reclassify + detect_clubs join), tiering, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_gift_gap.py           # orchestrator: seed -> crawl -> bio-resolve -> classify -> gate -> finalize
```

Refactor target: extract `enrich.py` **step-1** parsing (ecommerce flag,
forms, social links) into a shared `enrich_websites_lib` so both `enrich.py`
and `gift_gap/crawl_signals.py` parse identically without duplicating the
crawl — the same shared-lib argument Engine 02 makes. `config.py` knobs to
add: `GIFT_LANGUAGE_REGEX`, `GIFT_PRODUCT_RULES`, and the gift-gap tier
thresholds.

## Open questions

1. **Gift-card vs gift-bundle disambiguation.** How reliably can the static
   crawl + Haiku pass tell a digital gift *card* (not our product) from a
   missing physical gift *bundle* (our product)? A wrong read flips the
   trigger. Worth a labeled probe on 50 known sites.
2. **JS-rendered carts.** What fraction of target sites render the gift SKU
   client-side (Shopify Buy Button, embedded widgets) and slip past a static
   fetch? If high, do we need a Playwright fallback (as `best_wine_shops/`
   uses) for `commerce_capable` rows before declaring a gap?
3. **Corporate-gifting as its own list?** B2B "corporate gifting" copy implies
   bulk/recurring volume and a different buyer — it may convert better as a
   dedicated `corporate_gifting_<YYYYMMDD>` cut with its own outbound angle.
4. **Cross-engine merge key.** Many rows overlap Engine 02 (manual preorder)
   and the niche lanes. Phone-first dedupe via `dedupe_existing.py`, but how do
   we *merge* the gift-gap trigger onto an existing partner row rather than emit
   a duplicate?
