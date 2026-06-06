# Lead Engine 15 — Cult Product List

**Motion:** Hybrid (ICP-correlated curation with a strong per-product Trigger overlay)
**Vertical fit:** Bakeries, butchers, restaurants, cheese, wine
**Suggested list name(s):** `cult_product_demand`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run (rides existing crawl + IG hooks + press step; net-new cost is a Claude entity-extraction + clustering pass)

## Premise

The strongest Table22 prospects often have demand concentrated in **one hero
product**: a specific sourdough loaf, a fried-chicken sandwich, a single
sausage or pâté, a holiday lasagna, a named pastry, a cheese box, a wine
allocation. When one SKU develops its own following — customers naming it
repeatedly in reviews and comments, the item selling out before the rest of
the menu, press headlines written about *that one thing* — the business has
already done the hardest part of building a subscription program: it has a
product people will pre-commit to. A cult product converts almost mechanically
into a drop, a club, a preorder, or a gift bundle, which is exactly the
recurring-revenue motion Table22 sells.

This sits cleanly in the two-score model. The **Trigger** is sharp and
quotable ("your [hero item] has a following — let's turn it into a recurring
drop"), and it correlates with **ICP Fit** because product-cult formation is a
demand-over-capacity tell: you don't form a cult around commodity goods. It
overlaps Engine 03 (sold-out) but is distinct — Engine 03 detects *that*
something sells out; this engine identifies *which specific product* carries
the brand and whether it's productizable. The hero-product framing also
de-risks the sweets-only demotion: a bakery whose cult product is a celebration
cake or a seasonal pie box has a giftable, recurring SKU even if its everyday
counter is single-category.

This is a **Hybrid** engine: the cult-product signal is genuinely
ICP-correlated, but a viral one-off or a chain "secret menu" item can fake it,
so we curate the business hard (partner type, chain, liquor/ESP leakage) before
trusting the product trigger.

## Recipe

Three of the detection surfaces already exist as primitives — the step-1 site
crawl, the Apify review and IG-post scrapers, and the step-4 press search. The
net-new work is a **product-entity extractor** that names the hero SKU and
measures how concentrated demand is on it.

1. **Seed the universe.** Run primarily over the enriched corpus
   (`output/2_enriched_*.csv`) and the niche lanes (`butcher/`,
   `best_wine_shops/`, `directories/`, awards master) — these rows already
   cleared discovery floors and carry `website` + IG handle. For net-new
   geography, seed Serper Maps off `research/trendy_neighborhoods/`
   (~56.5% of partners are in trendy neighborhoods) for `bakery | butcher |
   cheese | wine_store` and destination-restaurant queries.

2. **Extract candidate product mentions from reviews (reuse step-5).** The
   **step-5 Apify Google-Maps-Reviews** scraper already pulls review text. The
   cult signal here is *repetition of the same product name* across many
   reviewers. Mine review text for noun-phrase product mentions and count
   distinct reviewers naming each candidate. A product named by ≥15% of recent
   reviewers (or an absolute floor of ~12 distinct reviewers) is a strong cult
   candidate. This is the single highest-signal surface — organic, third-party,
   and naturally weighted toward the item people care about.

3. **Mine IG post/comment captions for the same product (reuse step-6/7).**
   Reuse the **step-7 instagram-post-scraper** and **step-6 instagram-reel-scraper**
   (batched 30 handles) — and where comment payloads are returned, the comment
   text — to count how often a single product name recurs in the operator's own
   posts and in audience replies. The `scrape_beli/` lane already demonstrates
   the caption-mining pattern (claude-haiku-4-5 over captions); reuse that
   approach. Audience comments naming a product ("need the [item] back") are the
   purest cult tell.

4. **Catch hero-item press headlines (reuse step-4).** Reuse the **step-4 press
   step** (Serper Web vs food-media domains) but add product-centric query
   templates so a headline written about *one item* surfaces:

   - `"best <food> in <city>"`, `"<business> <hero-noun>"`
   - hero-noun seed list (extend per vertical):
     `sourdough | baguette | croissant | kouign-amann | bagel | cinnamon roll |
     pie | cake | cookie | sandwich | sub | hoagie | smash burger | fried
     chicken | sausage | hot dog | bratwurst | pâté | terrine | charcuterie |
     dry-aged | porchetta | lasagna | dumpling | taco | cheese box | raclette |
     allocation | release | bottling`
   - editorial cult markers: `the best`, `famous for`, `cult`, `legendary`,
     `worth the trip`, `you have to try`, `obsessed`, `iconic`, `signature`

5. **Detect productized demand on the site (reuse step-1 crawl).** Extend the
   step-1 crawler's parse layer to flag drop/preorder/waitlist mechanics on a
   specific product page — `pre[\s-]?order`, `next drop`, `restock`,
   `waitlist`, `notify me when (back|available)`, `limited (run|batch|edition)`,
   product-platform stock badges (Shopify `sold-out`, WooCommerce `outofstock`,
   Square `out_of_stock`). A hero product *with* a preorder/waitlist page is
   already half-built into a Table22 drop. These ride the existing crawl — no
   new fetch.

6. **Cluster + name the hero product (Claude, cheap pass).** Send the matched
   review/IG/press snippets per business to Claude (`claude-haiku-4-5`, the
   model `scrape_beli` uses) to (a) cluster mentions into a single canonical
   `hero_product` name (resolve "the chocolate babka" / "babka" / "their babka"
   into one entity), (b) confirm it's a *real product cult* vs generic praise
   ("great food") or a permanently-discontinued item, (c) judge
   `productizable` (can it ship as a drop / club / preorder / gift bundle?), and
   (d) emit a one-line `trigger_summary` sales can quote. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

7. **Apply the ICP gate + score cult strength.** Run `reclassify.py`
   (`partner_type` / `business_type_v2`, wine-bar claw-back) and carry
   `has_club` from `detect_clubs.py` (existing club = positive switch signal).

```
DISQUALIFY if:
  partner_type == liquor_store, or wine commodity-SKU leak (Tito's, Veuve,
      Barefoot, Yellowtail, BuzzBallz, Josh, Cupcake, Meiomi, Apothic, ...) or
      ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)   # "secret menu" cults often = chains
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}        # butcher lane only

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery WHERE hero_product is NOT giftable/seasonal
  static-social-only / thin metrics in small market (never DQ — understates brand)

cult_strength:
  +3 hero product named by >=15% of recent reviewers (or >=12 distinct reviewers)
  +3 dedicated product-page preorder/waitlist/drop mechanic present
  +2 hero-item press headline on a food-media domain
  +2 productizable == True AND giftable/shippable (charcuterie, cheese box, pies, allocation)
  +1 recurring IG/comment demand naming the product (<60d, >=2 mentions)
  +1 if has_club == True (proven recurring demand)

QUALIFY (engine output) if: passes ICP gate AND cult_strength >= 3 AND hero_product is named
```

8. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   cult columns ride as evidence; `cult_strength` orders the outbound queue
   inside a tier.

## Output schema

```
output/cult_product_demand/cult_product_demand_<YYYYMMDD>.csv
source = "cult_product_demand"
tier = <1|2|3>     # 1 = butcher/wine/cheese/destination + named hero + productizable; 2 = bakery/specialty or single-surface hit; 3 = ICP-soft
business_type = bakery | butcher | restaurant | cheese | wine_store | specialty
distinction = "Cult product: {hero_product} — turn into a Table22 drop/club"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    hero_product            # canonical Claude-resolved product name ("chocolate babka")
    cult_strength           # int, intra-tier outbound ordering
    found_on                # reviews | ig | press | product_page | multiple
    reviewer_mention_share  # % of recent reviewers naming the product
    reviewer_mention_count  # distinct reviewers naming the product
    press_headline_url      # food-media headline about the hero item (if any)
    ig_demand_mentions      # count of distinct IG/comment mentions naming the product
    product_page_url        # dedicated SKU page (if it exists)
    has_preorder_waitlist   # bool — drop/preorder/waitlist mechanic present
    productizable           # bool — Claude judgment: shippable/giftable as drop/club/bundle
    cult_recency_days       # days since most recent product mention
    cult_evidence_snippet   # verbatim quote ("you HAVE to get the babka")
    trigger_summary         # one-line Claude-written outbound hook
    has_club                # carried from detect_clubs.py (positive signal)
    partner_type            # from reclassify.py
```

## Volume & cost

- Input universe (enriched corpus + niche lanes), deduped: **~8–12K rows**. No
  new discovery spend on existing rows.
- Review mining: rows that already ran step-5 are free (parse pass over stored
  text). Net-new review pulls on rows missing reviews (~30%, ≈3K) via
  Google-Maps-Reviews at ~$0.003–0.005/row ≈ **$10–15**.
- IG post/reel/comment mining via Apify, only for rows with an IG handle and no
  strong review-side hit (~35%, ≈3.5K handles, batches of 30) at
  ~$0.002–0.004/profile-pull ≈ **$8–12**.
- Press step (Serper Web, product-centric queries): rides existing step-4 quota;
  marginal cost **≈ $2–3**.
- Claude Haiku cluster/name pass on businesses with ≥1 candidate mention
  (~3K rows, short prompts): **≈ $3–5**.
- **Per-run total: ~$23–30** (lower if the corpus already carries step-5 reviews).
- **Net-new qualified leads per run:** of ~10K screened, a *named* hero product
  with `cult_strength >= 3` lands on **~6–10%** (≈600–1,000 candidates); after
  the ICP gate, expect **~300–500 qualified rows**. Many already live in our
  corpus — the value is the *named, productizable trigger* that re-prioritizes
  them for outbound.

## Refresh cadence

**Monthly.** Cult-product formation is slower-moving than a single sellout
event — a hero item builds its following over months and persists. The press
and review surfaces turn over slowly; the IG/comment slice is the fastest and
worth a lighter mid-cycle pass. Run a **heavier pre-holiday pass** (Oct–Dec):
holiday hero items (turkeys, pie boxes, charcuterie boards, panettone,
allocations) are the most directly productizable into gift bundles, and the
trigger window is sharpest in the weeks before.

## Risks

- **Generic praise mistaken for a cult.** "Great food," "best in town" with no
  named product is not a hero-item signal. The extractor must require a named
  product entity; the Claude pass discards businesses where mentions don't
  cluster on one SKU.
- **Viral one-off vs durable cult.** A single TikTok-driven spike can name a
  product for a month and fade. Weight `cult_recency_days` and recurrence;
  prefer multi-surface confirmation (reviews + press) over a single channel.
- **Chain "secret menu" leakage.** Chains generate cult-item chatter (the
  In-N-Out / Shake Shack pattern). Keep `config.CHAIN_KEYWORDS` and the
  ≥10-location check *upstream* of `cult_strength`.
- **Liquor-store / wine-bar false positives.** An allocation cult at a bottle
  shop that's really a liquor store must drop — enforce commodity-SKU and ESP
  red-flag (City Hive, Spot Hopper) checks and the `reclassify.py` wine-bar
  claw-back (wine bars excluded except geographic-monopoly).
- **Sweets-only nuance.** A cult cookie at a single-product bakery is real but
  headroom-capped — only promote past Tier 2 when the hero item is giftable or
  seasonal (cake/pie/holiday box), otherwise cap at Tier 2.
- **Small-market metrics run low.** A rural butcher whose sausage everyone names
  may have few total reviews; the 15% *share* threshold protects against this
  better than an absolute count. Weight relative local dominance; never DQ on
  static-only social — it understates brand.
- **Entity-resolution errors.** "The babka," "chocolate babka," and "their
  bread" may or may not be the same SKU; over-merging inflates `cult_strength`,
  under-merging hides it. The Claude clustering pass is load-bearing here — QA a
  sample of `hero_product` names per run.
- **Productizability misjudged.** Not every cult item ships (a dine-in-only
  soufflé). `productizable` is a Claude judgment and will err; treat it as a
  prioritization input, not a gate — sales can still pitch an in-store drop.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawl,
the step-5 review scraper, the step-6/7 IG hooks, and the step-4 press search as
libraries.

```
cult_product_demand/
  __init__.py                  # engine constants; registers hero-noun + cult-marker lexicons
  signals.py                   # HERO_NOUNS, CULT_MARKERS, product-page regex, SKU/ESP leak lists
  mine_reviews.py              # parse layer over step-5 Google-Maps-Reviews; per-product reviewer counts
  mine_captions.py             # wraps Apify instagram-post/reel-scraper (reuse step-6/7 batching) + comments
  search_press.py              # wraps step-4 Serper Web with product-centric query templates
  crawl_product_pages.py       # parse layer over enrich.py step-1 crawl for preorder/waitlist/drop mechanics
  classify.py                  # Claude haiku-4-5: cluster/name hero_product, confirm cult, productizable, trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), cult_strength, recency/recurrence, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_cult_product_demand.py # orchestrator: seed -> reviews -> captions -> press -> product-pages -> classify -> gate -> finalize
```

Refactor targets: extract the **step-5 review-text mining** logic from
`enrich.py` into a shared `enrich_reviews_lib` (the review-difficulty miner and
this product-mention miner should share one tokenizer/parse pass), and reuse the
step-1 crawl parse layer and step-4 press search rather than re-fetching — the
same shared-lib argument Engines 03 and 05 raise.

## Open questions

1. **Mention-share threshold.** Is 15% of recent reviewers (or 12 distinct) the
   right cut to separate a true cult product from a merely popular menu item,
   and should the threshold scale down for small-review-count businesses?
2. **Comment payload availability.** How reliably do the Apify IG post/reel
   scrapers return *comment* text (the purest cult tell)? If comments aren't
   in the payload, do we need the `instagram-tagged-posts-scraper` or a separate
   comment-scraper actor — and is the marginal signal worth the extra cost?
3. **Overlap with Engine 03.** Should `cult_product_demand` and
   `sold_out_demand_signals` share a single review/caption mining pass and
   diverge only at scoring, to avoid double-crawling the same corpus twice a
   month?
4. **Productizability as gate vs evidence.** Should a hero item judged
   non-shippable (dine-in-only) be demoted, or kept at full strength since an
   in-store preorder/club still works — and who owns that call, the engine or
   sales triage?
