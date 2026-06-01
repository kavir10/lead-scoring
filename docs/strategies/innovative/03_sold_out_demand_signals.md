# Lead Engine 03 — Sold-Out Demand List

**Motion:** Curation (with a hard Trigger overlay — sold-out language IS the trigger)
**Vertical fit:** Bakeries, destination restaurants, butchers, wine, cheese
**Suggested list name(s):** `sold_out_demand_signals`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (rides existing crawl + IG hooks; net-new cost is a Claude classify pass)

## Premise

Demand-over-capacity is the single most predictive ICP pattern in the model —
it is what `reservation_difficulty` (the #2 SHAP feature behind Partner Type)
is trying to measure indirectly. **Sold-out language is the cleanest public
expression of that pattern.** A bakery that posts "croissants sold out by
9am," a butcher with "this week's whole-animal share is fully claimed," a
cheese shop running "raclette night — waitlist only," a wine shop with
"allocation closed," a restaurant with "no reservations available this month"
— each is publicly broadcasting that demand exceeds supply. That is exactly
the business Table22 monetizes: the recurring-revenue ceiling is set by
capacity, not by interest.

Unlike review-text difficulty signals (which are noisy and backward-looking),
sold-out language is **first-party and current** — the operator wrote it, on
their own site or IG, about a real fulfilment constraint. It maps cleanly to
the two-score model: it's a strong **Trigger** ("you're selling out — let us
help you capture that demand on a recurring basis") that also correlates with
**ICP Fit** because the highest-AGMV partner types (butcher $75.9k, wine
$68.2k, cheese $63.8k, destination restaurant $60.5k) are precisely the ones
that sell out finite premium product.

This is a **Curation** engine: the sold-out signal is genuinely ICP-correlated
(you don't sell out commodity goods), so the gate is lighter than Engine 02 —
but a chain or a hype-drop sneaker-adjacent gimmick can fake scarcity, so we
still curate hard before sales.

## Recipe

Two of the three detection surfaces already exist as crawl primitives. We add
a **scarcity-language extractor** to the `enrich.py` step-1 site crawl, mine IG
captions via the Apify post/reel scrapers we already run, and cross-check
against the real-time availability lane.

1. **Seed the universe.** Run primarily over the existing enriched corpus
   (`output/2_enriched_*.csv`) and the niche lanes (`butcher/`,
   `best_wine_shops/`, `directories/`, awards master) — these rows already
   cleared discovery quality floors and carry `website` + IG handle. For
   net-new geography, seed Serper Maps off `research/trendy_neighborhoods/`
   (~56.5% of partners sit in trendy neighborhoods) for `bakery | butcher |
   cheese | wine_store` and destination-restaurant queries.

2. **Crawl the site for scarcity language.** Extend the step-1 crawler's parse
   layer to scan page HTML, product-page status text, menu pages, and
   button/badge text for the scarcity lexicon (regex, case-insensitive):

   - **Sold-out / out-of-stock:** `sold[\s-]?out`, `out of stock`,
     `unavailable`, `currently unavailable`, `fully claimed`, `all gone`,
     `none left`
   - **Drop / preorder cadence:** `next drop`, `restock`, `back (next week|in
     stock|soon)`, `pre[\s-]?order (closed|sold out)`, `back next (week|month)`
   - **Limited supply:** `limited (quantity|quantities|run|batch|edition|
     availability)`, `while supplies last`, `only \d+ (left|remaining|
     available)`, `first come first served`
   - **Waitlist:** `waitlist`, `wait list`, `join the (list|waitlist)`,
     `notify me when (back|available)`, `sign up to be notified`
   - **Reservation scarcity (restaurants):** `fully booked`, `booked out`,
     `no (reservations?|tables?) available`, `currently full`, `walk[\s-]?ins
     only`, `next availability`

   Product-platform stock badges are a high-confidence signal: detect Shopify
   `sold-out` button states, WooCommerce `outofstock` class, Square
   `out_of_stock`. These ride the same crawl — no new fetch.

3. **Mine IG captions for scarcity (reuse Apify hooks).** This is where
   bakeries and butchers actually announce sell-outs. Reuse the **step-7
   instagram-post-scraper** and **step-6 instagram-reel-scraper** (batched 30
   handles) to pull recent captions, then run the same scarcity regex over
   caption text. The Beli lane (`scrape_beli/`) already demonstrates the
   caption-mining pattern; reuse its caption-extraction approach. A caption
   like "SOLD OUT in 20 minutes 🥐 see you Saturday" is the strongest hit in
   this engine — it's scarcity + recurrence + recency in one line.

4. **Cross-check real-time reservation scarcity.** For destination
   restaurants, join the **step-8 availability** signal (OpenTable via Apify +
   Resy API): a row that *says* "no reservations available" AND shows zero
   real-time availability on Resy/OpenTable for the next 14 days is a hard,
   verified scarcity hit — not just marketing copy.

5. **Classify + score scarcity (Claude, cheap pass).** Send matched snippets to
   Claude (`claude-haiku-4-5`, the model `scrape_beli` uses) to (a) confirm the
   scarcity is *real demand pressure* vs a permanent "we're closed" / "menu
   item discontinued" / boilerplate, (b) label `scarcity_type`, and (c) emit a
   one-line `trigger_summary` sales can quote verbatim. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

6. **Apply the ICP gate + score scarcity strength.** Run `reclassify.py`
   (`partner_type` / `business_type_v2`, wine-bar claw-back) and carry
   `has_club` from `detect_clubs.py` (existing club = positive switch signal).

```
DISQUALIFY if:
  partner_type == liquor_store, or wine commodity-SKU leak (Tito's, Veuve,
      Barefoot, Yellowtail, BuzzBallz, Josh, Cupcake, ...) or ESP red flag
      (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery   # scarcity is real but headroom is capped
  static-social-only / thin metrics in small market (never DQ — understates brand)

scarcity_strength:
  +3 verified real-time res-scarcity (says full AND Resy/OT shows zero) | platform sold-out badge
  +3 IG caption "sold out" with recency (<30d) AND recurrence (>=2 posts)
  +2 site "sold out" / "limited quantity" / "next drop" on a premium SKU
  +2 waitlist / "notify me when back" mechanism present
  +1 single sold-out mention, no recurrence
  +1 if has_club == True (proven recurring demand)

QUALIFY (engine output) if: passes ICP gate AND scarcity_strength >= 2
```

7. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   scarcity columns ride as evidence; `scarcity_strength` orders the outbound
   queue inside a tier. The verified real-time slice should feed
   `reservation_difficulty` as additional input where the row reaches phase 8.

## Output schema

```
output/sold_out_demand/sold_out_demand_signals_<YYYYMMDD>.csv
source = "sold_out_demand_signals"
tier = <1|2|3>     # 1 = butcher/wine/cheese/destination + verified/recurring scarcity; 2 = bakery/specialty or single-mention; 3 = ICP-soft
business_type = bakery | restaurant | butcher | wine_store | cheese | specialty
distinction = "Publicly sells out: {scarcity_summary} — capture demand w/ Table22"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    scarcity_type          # sold_out | next_drop | preorder_closed | limited_qty | waitlist | fully_booked | res_unavailable
    scarcity_strength      # int, intra-tier outbound ordering
    found_on               # website | product_page | ig_caption | resy_ot | multiple
    scarcity_evidence_url  # the page / IG post permalink that matched
    scarcity_snippet       # verbatim matched text ("SOLD OUT in 20 minutes")
    scarcity_recency_days  # days since most recent scarcity signal
    scarcity_recurrence    # count of distinct scarcity mentions
    rt_availability_zero   # bool — Resy/OpenTable showed no availability (restaurants)
    has_waitlist_mechanism # bool — explicit waitlist/notify-me capture present
    trigger_summary        # one-line Claude-written outbound hook
    has_club               # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped:
  **~8–12K rows**. No new discovery spend — already-crawled businesses.
- Site scarcity crawl: free (rides the step-1 10-thread crawl; +1 parse pass).
- IG caption mining via Apify post/reel scrapers: only for rows with an IG
  handle and no strong site-side hit (~40–50%, ≈4.5K handles). At batches of
  30 and ~$0.002–0.004/profile-pull ≈ **$12–16**.
- Real-time availability check (Resy/OpenTable) on destination-restaurant
  subset only (~1.5K): reuses step-8 actors, **≈ $4–6**.
- Claude Haiku classify pass on matched snippets (~2.5K rows, short prompts):
  **≈ $2–4**.
- **Per-run total: ~$18–24.**
- **Net-new qualified leads per run:** of ~10K screened, scarcity signal hits
  **~15–22%** (≈1.5–2.2K); after ICP gate + `scarcity_strength >= 2`, expect
  **~500–800 qualified rows**. Many already exist in our corpus — the value is
  the *trigger*, which re-prioritizes them for outbound now.

## Refresh cadence

**Bi-weekly**, with the IG-caption slice driving the cadence. Scarcity is a
**recency** signal — "sold out last Saturday" is a live trigger; "sold out"
from six months ago is stale. The site-crawl slice (waitlist mechanisms,
permanent "limited batch" copy) turns over slowly and a monthly pass suffices,
but the high-converting caption hits decay in weeks, so bi-weekly keeps the
outbound line current ("saw you sold out again this weekend"). Pull a heavier
run pre-holiday (turkeys, pies, charcuterie, allocations all sell out then).

## Risks

- **Fake / permanent scarcity.** "Sold out" can mean a discontinued menu item,
  a permanently out-of-stock SKU, or boilerplate "limited edition" marketing
  with no real pressure. The Claude pass must distinguish *demand pressure*
  from *catalog state*; require recency and (ideally) recurrence before a hard
  trigger.
- **ICP leakage through the trigger.** A liquor store ("Pappy allocation sold
  out"), a hype-drop merch shop, or a 12-location chain can all post sold-out
  language. Keep `config.CHAIN_KEYWORDS`, commodity-SKU, and ESP-red-flag (City
  Hive, Spot Hopper) checks *upstream* of `scarcity_strength`.
- **Wine-bar / liquor-store false positives.** Enforce wine-bar exclusion
  (except geographic-monopoly) and the `reclassify.py` wine-bar claw-back; a
  bottle-shop running allocation FOMO that's really a liquor store must drop.
- **Small-market metrics run low.** A rural butcher who sells out every share
  may have thin social volume. Weight relative local dominance + the scarcity
  trigger; **never DQ on static-only social** — it understates brand.
- **Sweets-only demotion.** A cupcake shop that sells out is a real trigger but
  a single-product bakery — cap at Tier 2, don't promote on trigger alone.
- **Recency decay / stale captions.** Apify returns historical posts; a
  sold-out caption from last year is not a live trigger. Always record
  `scarcity_recency_days` and weight it; treat >90d as low-confidence.
- **Resy/OpenTable fragility.** The Resy client is reverse-engineered and
  rate-limits; treat real-time zero-availability as a *bonus* hard signal, not
  a gate — fall back to copy + caption hits when the availability check fails.
- **Negation / sarcasm.** "Never sold out" or "we won't sell out on quality"
  are false matches; the Claude pass handles negation that regex cannot.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler
and the step-6/7 Apify IG hooks as libraries.

```
sold_out_demand/
  __init__.py                  # engine constants; registers scarcity lexicon
  signals.py                   # SCARCITY_REGEX, PLATFORM_STOCK_BADGES, SKU/ESP leak lists, negation rules
  crawl_scarcity.py            # parse layer over enrich.py step-1 crawl output
  mine_captions.py             # wraps Apify instagram-post/reel-scraper (reuse step-6/7 batching)
  check_availability.py        # wraps step-8 Resy/OpenTable for restaurant subset
  classify.py                  # Claude haiku-4-5: confirm demand-pressure, scarcity_type, trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), scarcity_strength, recency/recurrence, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_sold_out_demand.py    # orchestrator: seed -> crawl -> caption-mine -> avail-check -> classify -> gate -> finalize
```

Refactor target: extract the `enrich.py` **step-8** availability functions
(OpenTable Apify call + Resy lookup) into a shared `enrich_availability_lib` so
both `enrich.py` and `sold_out_demand/check_availability.py` use one
implementation (same shared-lib argument Engine 05 raises). Likewise reuse the
step-1 crawl parse layer rather than re-fetching.

## Open questions

1. **Recurrence threshold.** How many distinct sold-out mentions over what
   window proves *recurring* demand vs a one-off viral day? Is 2 posts in 30
   days enough, or do we need a denser cadence to separate "consistently
   capacity-constrained" from "got lucky once"?
2. **Caption-mining scope.** Mining captions for the full ~10K corpus is the
   cost driver. Should we gate IG mining to rows that *already* show a weak
   site hit or high follower/engagement, rather than pulling captions blind?
3. **Verified-res slice as its own list?** The "says full AND Resy/OpenTable
   shows zero" subset is the highest-confidence, lowest-volume cut — it may
   deserve a separate `reservation_impossible`-style list with distinct
   outbound timing rather than folding into the master.
4. **Feeding `reservation_difficulty`.** Should verified real-time scarcity
   from this engine write back into the phase-8 `reservation_difficulty`
   composite (40% platform / 35% review-text / 25% real-time), or stay an
   evidence-only column to avoid double-counting against SHAP weights?
