# Lead Engine 46 — Office and Corporate Gift Potential List

**Motion:** Hybrid (Curation ICP gate + a geo-and-language Trigger overlay)
**Vertical fit:** Cheese, wine, bakery, specialty grocers (shippable/giftable retail; butcher where product ships)
**Suggested list name(s):** `corporate_gift_potential`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (rides the existing step-1 crawl; net-new spend is office-density geocoding + link-in-bio resolution + a small Claude classify pass)

## Premise

A shippable food merchant that (a) sits inside a dense office corridor and (b)
already speaks the language of B2B gifting — "corporate gift," "client gift,"
"office catering," "team gift," "bulk orders," "holiday gifting,"
"employee appreciation," "swag," "minimum order" — is sitting on recurring,
seasonal, high-AOV revenue it services by hand. Corporate gifting is the
cleanest demand-over-capacity story in the catalog: the buyer is an office
manager or EA placing repeat orders (Q4 holiday, client thank-yous, new-hire
welcome boxes, end-of-quarter), the order sizes are large, and the operator is
running it off a Google Form and a spreadsheet. A Table22 prepaid-bundle /
recurring-box product turns that ad-hoc B2B inbound into a managed,
self-serve, repeat program.

In the two-score model this is a **Hybrid** engine. ICP Fit is the gate — the
high-AGMV shippable retail types where a gift box is a literal object: cheese
($63.8k), wine ($68.2k), bakery ($34.7k), specialty grocer ($27.9k), butcher
($75.9k) where product is shippable (charcuterie, steak/jerky boxes). The
**Trigger** is the *intersection* of two independent public signals —
office-density proximity (a captive B2B buyer base within ordering distance)
**and** corporate-gifting language (proof they already field these asks).
Either alone is weak; together they say "this operator has the demand and the
geography for recurring B2B volume but no platform to run it on."

This engine is the B2B sibling of Engine 21 (gift-ready, no gift product),
which targets *consumer* gift copy with a missing SKU. Engine 46 inverts the
buyer and adds geography: the value is bulk/recurring corporate volume, and the
qualifier is "are they near offices AND do they already talk corporate?" — not
whether a single consumer gift box exists.

## Recipe

The crawl and bio-resolution primitives already exist (Engine 21 reuses them);
the genuinely new piece is the **office-density layer**. This is a curation
gate (ICP) wrapped around a two-part trigger (geo × language).

1. **Seed the universe — don't cold-discover.** Feed the existing enriched
   corpus (`output/2_enriched_*.csv`) plus the niche lanes (`best_wine_shops/`,
   `directories/`, awards master, `butcher/`). These rows already cleared
   discovery floors and carry `website`, lat/lng, and social handles. For
   net-new geography, bias Serper Maps off `research/trendy_neighborhoods/`
   (≈56.5% of partners sit there, and trendy + office-dense overlap heavily) for
   `cheese | wine_store | bakery | specialty | butcher`.

2. **Score office-density proximity.** For each candidate's lat/lng, compute a
   corridor score. Two grounded options (pick per Open Question 1):
   - **Serper Maps reverse query** — for each candidate, a Serper Maps sweep at
     its coordinates for `office | coworking | corporate headquarters |
     office building | WeWork` within ~1 mile; count + density of hits. This
     reuses the existing Serper Maps client, no new vendor.
   - **Static corridor frame** — a curated `config.OFFICE_CORRIDORS` list
     (CBD / tech-hub ZIP clusters: SF SoMa/FiDi, Manhattan Midtown/FiDi,
     Chicago Loop, Boston Seaport, Austin Downtown, Seattle SLU, etc.) and a
     point-in-polygon / radius test. Cheaper, no per-row Serper cost.

   ```
   office_density = serper_office_hits_within_1mi      # option A
                  OR in_office_corridor (0/1) + corridor_tier   # option B
   ```

3. **Crawl the site for CORPORATE-GIFTING language** (extend the `enrich.py`
   **step 1 (websites)** 10-thread crawler's parse layer — same hook Engine 21
   uses; scan page HTML, nav/anchor text, visible copy; case-insensitive):

   ```
   CORPORATE_GIFT_PATTERNS = (
     r"corporate\s*gift", r"client\s*gift", r"business\s*gift",
     r"office\s*(catering|gift|snack|delivery)", r"team\s*gift",
     r"employee\s*(gift|appreciation|welcome)", r"company\s*gift",
     r"bulk\s*(order|gift|discount)", r"wholesale", r"volume\s*discount",
     r"minimum\s*order", r"corporate\s*(account|order|program|holiday)",
     r"holiday\s*gift(ing)?", r"end[\s-]?of[\s-]?year\s*gift",
     r"swag", r"branded\s*(gift|box)", r"custom(ize|ization)?\s*(box|order)",
     r"net\s*30", r"invoice", r"purchase\s*order", r"po\b",
     r"events?\s*(catering|gifting)", r"gift\s*concierge",
   )
   ```

   Record `corp_gift_score` = distinct pattern families matched, the pages they
   sit on (`/corporate`, `/gifting`, `/wholesale`, `/bulk`, contact/FAQ), and
   verbatim matched phrases for outbound.

4. **Detect the B2B-volume tell.** Beyond the keyword, look for the operational
   fingerprints of existing corporate trade — these separate "we'll do a big
   order" from "fill out this form": a corporate-gifting form / order minimum,
   `net 30` / invoice / PO language, a "request a quote" or "contact our gifting
   team" CTA, or a B2B price-break table. Reuse step-1's form-detection logic.

   ```
   b2b_signals = {corporate_form, order_minimum, net30_invoice_po,
                  quote_request_cta, volume_pricing}
   manual_b2b  = any(b2b_signals) AND NOT has_self_serve_corporate_checkout
   ```

   `manual_b2b` is the load-bearing Table22 hook — they field corporate demand
   *by hand*. A live self-serve corporate-bundle checkout lowers urgency (they
   already solved it), not the ICP fit.

5. **Resolve link-in-bio + scan social for B2B asks.** "DM us for corporate
   gifting" / "office orders → link in bio" often live only in the IG/FB bio or
   pinned posts. Resolve the bio target (Linktree/Beacons/raw URL) via the
   **Apify instagram-profile-scraper** (already wired, batches of 30 — reuse the
   step-2 hook), re-run steps 3–4 against the destination, and carry
   `found_on ∈ {website, link_in_bio, both}`. Note: for butcher / deli /
   specialty-grocer, **Facebook** engagement often beats IG — check the FB page
   bio/about too (step-3 FB scrape).

6. **Classify + write the outbound hook (Claude, cheap pass).** For ambiguous
   rows, send the corporate-page snippet + the b2b-signal findings to Claude
   (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to confirm real
   B2B intent (not a stray "corporate office" address), label
   `corp_gift_type ∈ {dedicated_corporate_page, bulk_wholesale, office_catering,
   scattered_mentions, none}`, and emit a one-line `trigger_summary` a BDR can
   quote. Prefix the script with `unset ANTHROPIC_API_KEY &&` (empty-key shell
   gotcha).

7. **Apply the ICP gate (the curation half).** Run `reclassify.py` for
   `partner_type` / `business_type_v2` (+ wine-bar claw-back), then
   `detect_clubs.py` (an existing club is a *positive* platform-switch signal —
   carry `has_club`). Reject anti-ICP before tiering:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  OR wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, Meiomi, ...) OR
         ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar  -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
     product not shippable (dine-in-only, perishable-no-ship) -> drop

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery
     static-social-only (understates brand — never DQ on this)

   QUALIFY (engine output) if: passes ICP gate AND corp_gift_score >= 1
       AND (office_density signal OR corp_gift_score >= 2)
     tier 1: cheese/wine/butcher + manual_b2b + high office_density
     tier 2: bakery/specialty, or office_density without manual_b2b, or vice versa
     tier 3: ICP-soft / single signal only (nurture)
   ```

8. **Hand off to scoring.** Emit the canonical CSV (below) and let `score.py`
   run unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned).
   The corporate columns ride as evidence; `corp_gift_score` + `office_density`
   order the outbound queue inside a tier.

## Output schema

```
output/corporate_gift/corporate_gift_potential_<YYYYMMDD>.csv
source = "corporate_gift_potential"
tier = <1|2|3>
business_type = cheese | wine_store | bakery | specialty | butcher
distinction = "Office-dense corridor + corporate-gifting demand ({corp_gift_type}), serviced manually — build a Table22 recurring B2B gift program"
year = <discovery_year>
source_url = <website / corporate-gifting page URL — sales cites the exact page>
blurb = <one-line: e.g. "Cheese shop in SF FiDi taking corporate holiday orders by email; no recurring program">
+ evidence cols (preserve so sales can cite the trigger in outbound):
    corp_gift_score            # distinct corporate-gifting families matched
    corp_gift_type             # dedicated_corporate_page | bulk_wholesale | office_catering | scattered_mentions
    matched_terms              # pipe-delim verbatim corporate phrases
    corp_pages                 # pipe-delim URLs (/corporate, /wholesale, /bulk)
    office_density             # serper hits within 1mi OR corridor_tier
    office_corridor            # named corridor/CBD if matched (FiDi, Loop, Seaport...)
    manual_b2b                 # bool — fields corporate orders by hand
    b2b_signals                # pipe-delim: corporate_form|order_minimum|net30_invoice_po|quote_request_cta|volume_pricing
    found_on                   # website | link_in_bio | both
    trigger_summary            # one-line Claude-written outbound hook
    has_club                   # carried from detect_clubs.py (positive signal)
    partner_type               # from reclassify.py
    scan_date
```

Per-run master union: `output/corporate_gift/corporate_gift_potential_all_<YYYYMMDD>.csv`.

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped:
  **~8–12K rows**. No discovery spend — already-crawled businesses.
- Office-density layer: **option B (static corridor frame) ≈ free** (point-in-radius
  on existing lat/lng); **option A (Serper Maps reverse query)** is ~1 sweep/row
  on the in-corridor or unknown-location subset (~4–5K) × ~$0.001 ≈ **$4–5**.
- Step-1 crawl extension (corporate-language + b2b-signal parse): **free** — rides
  the existing 10-thread crawl as +1 parse pass, no new fetch.
- Link-in-bio resolution via Apify profile scraper: only rows with a social handle
  and no website-side corporate CTA (~30%, ≈3K) at batches of 30,
  ~$0.002–0.004/profile ≈ **$8–12**.
- Claude Haiku classify pass on ambiguous rows (~1.5–2K, short prompts): **≈ $2–4**.
- **Per-run total: ~$15–25** (lower with the static corridor frame).
- **Net-new / re-surfaced qualified leads per run:** of ~10K screened,
  corporate-gifting language alone hits ~10–15%; intersected with office-density
  the qualifying cohort is **~5–8%** (≈500–800). After the ICP gate, expect
  **~200–350 qualified rows**, strongest being cheese/wine/butcher in a CBD
  corridor running corporate orders by hand. Many already sit in our corpus —
  fine; the value is the fresh, specific B2B build-this trigger that
  re-prioritizes them.

## Refresh cadence

**Monthly, with a heavy run in late September / early October.** Corporate
gifting is sharply seasonal — Q4 holiday corporate orders are placed Oct–Dec,
and catching `corp_gift_type=office_catering` / `holiday gifting` copy *while
it's live but still manual* makes the outbound land ("you're taking corporate
holiday orders by email — let's give your office buyers a self-serve program
before December"). Office-density geography is structurally stable (rebuild the
corridor frame quarterly at most), so monthly cadence is driven by the language
layer, not the geo layer.

## Risks

- **Office-density false positives.** A shop's own "corporate office" address,
  a coworking space next door, or a generic business district doesn't prove
  *food-gift* demand — it just proves geography. Require the **intersection**
  with corporate-gifting language; never qualify on office density alone (single
  signal caps at tier 3).
- **"Corporate" keyword noise.** "Corporate office," "corporate events" (venue
  rental), or boilerplate footer legalese trip the regex without real gifting
  intent. The Claude pass (step 6) and the `manual_b2b` b2b-signal check guard
  this — demand a gifting/order context, not a bare "corporate" token.
- **Caterers vs gift merchants.** Pure caterers are anti-ICP (DQ), but a cheese
  shop *also* offering office catering is in-fit. Let `reclassify.py` set
  `partner_type`; only DQ when catering is the whole business, not an add-on.
- **Non-shippable product.** Office-catering language can come from a dine-in /
  perishable-only operator that can't ship a gift box. Require shippability
  (step 7 drop) — corporate gifting that's local-delivery-only still works, but
  flag fulfilment mode for sales.
- **Liquor-store / chain leakage through gift copy.** Liquor stores and chains
  push "corporate gift baskets" hard. Keep `config.CHAIN_KEYWORDS`,
  commodity-SKU, and ESP-red-flag (City Hive, Spot Hopper) checks *upstream* of
  the trigger.
- **Wine-bar exclusion.** Wine bars mostly excluded except geographic-monopoly;
  let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake shop advertising "corporate holiday gift
  boxes" is a real trigger but single-product — cap at Tier 2 per the demotion
  rule, don't promote on trigger alone.
- **Small-market metrics run low / static-social understates brand.** A great
  operator in a smaller market may show thin office density and thin social.
  Weight the language + manual-B2B trigger and relative local dominance; **never
  DQ on static-only social** — it understates brand.
- **Link-in-bio fragility.** Apify IG profile scraper rate-limits and Linktree
  HTML changes; batch at 30, back off, and fall back to website-only matches
  when bio resolution fails (don't block the row).

## Repo placement

Standalone package mirroring Engine 21's `gift_gap/` shape, reusing the step-1
crawler and the step-2 Apify hook as libraries.

```
corporate_gift/
  __init__.py                  # engine constants; registers pattern banks + tier thresholds
  signals.py                   # CORPORATE_GIFT_PATTERNS, B2B_SIGNAL_RULES, SKU/ESP leak lists
  office_density.py            # corridor frame OR Serper Maps reverse-query density scorer
  crawl_signals.py             # corporate-language + b2b-signal parse over enrich.py step-1 crawl output
  resolve_link_in_bio.py       # wraps Apify instagram-profile-scraper (reuse step-2 batching)
  classify.py                  # Claude haiku-4-5 corp_gift_type + trigger_summary
  aggregate.py                 # geo × language intersection, ICP gate (reclassify + detect_clubs join), tiering, dedupe
  finalize.py                  # canonical schema writer, date-stamped output + master union
discover_corporate_gift.py     # orchestrator: seed -> office-density -> crawl -> bio-resolve -> classify -> gate -> finalize
```

Refactor targets to share, not fork:

- Extract `enrich.py` **step-1** parsing (ecommerce flag, forms, social links)
  into a shared `enrich_websites_lib` so both `enrich.py` and
  `corporate_gift/crawl_signals.py` parse identically without re-crawling — the
  same shared-lib argument Engines 02 and 21 make.
- Reuse the Apify instagram-profile-scraper batching wrapper (don't refork it
  per engine).
- `config.py` knobs to add: `CORPORATE_GIFT_REGEX`, `B2B_SIGNAL_RULES`, the
  corporate-gift tier thresholds, and — if option B — a new
  `config.OFFICE_CORRIDORS` frame (named CBD/tech-hub ZIP clusters + radius).
  The office-density frame is the one genuinely new piece of infra this engine
  needs.

## Open questions

1. **Office-density source.** Serper Maps reverse-query (live, per-row cost,
   captures any office cluster) vs a static `config.OFFICE_CORRIDORS` frame
   (free, stable, but misses non-CBD office parks)? A 50-site labeled probe
   should decide; a hybrid (corridor frame first, Serper fallback for unknowns)
   is likely best.
2. **B2B-volume threshold for tier 1.** Is `manual_b2b` (any one b2b signal)
   enough to call tier 1, or do we require a corporate *page* plus an explicit
   order-minimum / PO / invoice tell to avoid promoting shops that merely *say*
   "ask us about corporate gifts"?
3. **Self-serve corporate checkout = disqualifier or different motion?** A shop
   already running self-serve corporate bundles solved the problem — is that a
   nurture/lower-tier, or a separate "switch the platform" cut like the wine
   transition path?
4. **Cross-engine merge with Engine 21.** Consumer gift-gap (21) and corporate
   gift-potential (46) overlap heavily on the same rows. Phone-first dedupe via
   `dedupe_existing.py`, but do we merge both triggers onto one partner row (B2C
   + B2B angle) or keep distinct outbound lists with distinct hooks?
```