# Lead Engine 14 — Out-of-Town Demand List

**Motion:** Curation
**Vertical fit:** Bakeries, wine, butchers, cheese (shippable / drop-model retail)
**Suggested list name(s):** `out_of_town_demand`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run (Apify post/reel actors over a pre-filtered candidate set + Haiku geo-inference)

## Premise

Demand-over-capacity is the strongest ICP pattern we have, and this engine
reads its purest *geographic* form: people outside the operator's metro
publicly begging to be served. The comments are unmistakable — "please come
to LA," "need this in Chicago," "wish you shipped to NYC," "I'd order every
month if you delivered." Each one is a non-local superfan telling us the brand
has already traveled emotionally before it travels operationally. That latent,
out-of-market demand is exactly what a Table22 subscription program converts:
prepaid, recurring, shippable access to a base that the storefront physically
can't reach today.

This is a pure **Trigger** overlay on the **ICP Fit** our pipeline already
scores — the two-score model wants both, and out-of-town demand is a
contact-now reason, not a business-quality measure. It is strongest precisely
in the high-AGMV-x-headroom verticals: butcher ($75.9k), wine ($68.2k), cheese
($63.8k), and bakery, because those products *ship* and the "do you deliver?"
question is answerable with a Table22 club. A destination restaurant can also
trigger (merch, sauce, frozen-pasta lines), but the shippable retail verticals
are the bullseye.

It differs from Engine 04 (video-engagement spike, which scores buying-intent
comments broadly) by isolating the **geo-displaced** subset: the commenter is
demonstrably *not* in the operator's market, so converting them requires
shipping/subscription — the literal Table22 motion. It complements Engine 03
(sold-out text) by reading the *audience's* mouth instead of the operator's.

## Recipe

A **trigger-overlay** engine, CSV-in / CSV-out like `detect_clubs.py`. It does
not re-discover businesses; it scores an existing enriched/scored universe for
geo-displaced demand in their own comment threads and emits the matches. The
new primitive versus Engine 04 is **commenter geo-inference**.

1. **Seed the candidate set, don't re-discover.** Start from the latest
   `output/2_enriched_posts.csv` (steps 1–7 already run) or a scored
   `custom-serper-scoring_*_all.csv`. Require a resolved IG handle, populated
   `follower_count`, and a known operator **home metro** (derive from `city` /
   `state` already on the row). Restrict to shippable fit verticals (bakery,
   wine, butcher, cheese) plus destination restaurants with a product line.

2. **Pull recent comments** via the same Apify actors `enrich.py` steps 6–7
   use (`instagram-post-scraper`, `instagram-reel-scraper`), batched in groups
   of 30 handles. Grab the last ~30 posts / ~20 reels per handle, and for each
   the top N comment objects with `text`, `ownerUsername`, and commenter
   profile fields where exposed (bio, name). Butcher / deli / specialty-grocer
   skew to **Facebook** engagement — also scan FB post comment text from the
   `enrich.py` step-3 (`facebook`) surface where available.

3. **Regex gate for travel/ship intent** (cheap, runs first, no LLM):

```
TRAVEL_INTENT = (
  r"come\s*to\s+([A-Z][\w.\- ]+)", r"open\s*(one|a\s*shop)?\s*in\s+([A-Z][\w.\- ]+)",
  r"need\s*(this|you|one)\s*in\s+([A-Z][\w.\- ]+)", r"wish\s*you\s*(were|shipped|delivered)",
  r"do\s*you\s*ship", r"ship\s*to\s+([A-Z][\w.\- ]+)", r"do\s*you\s*deliver",
  r"please\s*(come|ship|open)", r"bring\s*this\s*to\s+([A-Z][\w.\- ]+)",
  r"(move|relocate)\s*to\s+([A-Z][\w.\- ]+)", r"if\s*only\s*you\s*(shipped|delivered)",
  r"(i'?d|would)\s*order\s*(every|each)?\s*(month|week)", r"nationwide|mail\s*order|across\s*the\s*country",
)
```
   The trailing capture groups harvest a *named destination city* directly from
   the comment when the commenter states it ("come to **Chicago**").

4. **Infer commenter location** (the new primitive). For each comment that
   passes the gate, resolve a best-guess commenter metro from, in priority
   order: (a) an explicit destination city captured by the regex; (b) commenter
   profile location / bio string if Apify exposes it; (c) `claude-haiku-4-5-20251001`
   over the comment + bio to extract a US metro, the same LLM-extraction role
   `awards/llm_extract.py` and `scrape_beli` use (prefix any SDK script with
   `unset ANTHROPIC_API_KEY &&` for the empty-key shell gotcha). Mark
   `geo_confidence` = high (explicit city) / medium (profile) / low (LLM guess
   only).

5. **Compute the displacement signal.** A comment counts as out-of-town demand
   only when the inferred commenter metro differs from the operator home metro
   (or is unresolved-but-explicitly-asking-to-ship, e.g. "do you ship
   nationwide?"). Normalize metros to `config.CITIES` buckets where possible so
   "NYC"/"New York"/"Brooklyn" collapse to one market.

```
oot_comments   = comments where commenter_metro != home_metro (or ship-ask w/ no local context)
distinct_cities = count of distinct non-home metros requesting
distinct_authors = count of distinct commenter handles (kills one-user spam)
ship_ask        = 1 if any comment explicitly asks to ship/deliver/mail-order
recency_days    = days since most-recent out-of-town comment

oot_score = min(100,
              22*min(distinct_authors,3)        # breadth of demand
            + 14*min(distinct_cities,2)          # multi-market pull
            + (18 if ship_ask else 0)            # explicit ship intent = bullseye
            + (15 if recency_days<=30 else 0)    # perishable
            + (11 if distinct_authors>=5 else 0))  # bonus for crowd
trigger_tier = 1 if oot_score>=55 else 2 if oot_score>=35 else 3
```

6. **Qualify against ICP before handoff.** Run `reclassify.py` to set
   `partner_type` / `business_type_v2` and fire the wine-bar claw-back; run
   `detect_clubs.py` to set `has_club` (existing club = positive
   platform-switch signal, not a DQ — but flag whether the club already ships,
   which weakens the trigger). Hard-filter liquor-store / chain / delivery-only
   leakage via `config.CHAIN_KEYWORDS` + the liquor-license / commodity-SKU
   filters. Then join `score.py` for the /100 ICP-fit score.
   **Final list = high `oot_score` AND ICP Fit (A/B tier).** High-trigger /
   weak-ICP routes to nurture, never sales.

Comment text and the named destination city are preserved verbatim so a BDR can
open with the exact "your Chicago fans are asking" line.

## Output schema

```
output/triggers/out_of_town_demand_<YYYYMMDD>.csv
source = "out_of_town_demand"
tier = <1|2|3>                       # = trigger_tier from oot_score
business_type = bakery | wine_store | butcher | cheese | restaurant
distinction = "Out-of-town demand: {distinct_authors} non-local fans across {distinct_cities} metros asking to ship/visit (last seen {recency_days}d ago)"
year = <YYYY of comment window>
+ evidence cols:
    ig_handle, home_metro, follower_count,
    oot_score, trigger_tier,
    distinct_authors, distinct_cities, ship_ask, recency_days,
    requesting_cities (pipe-delim, normalized to config.CITIES),
    geo_confidence (high|medium|low),
    comment_samples (1-3 verbatim, with commenter handle),   # outbound quotes
    source_surface (ig|fb|multi), source_url, scan_date,
    icp_fit_score, partner_type, has_club, club_ships_bool   # joined
```

## Volume & cost

Overlay on a known set, so spend is bounded by candidate count, not a fresh
crawl.

- Candidate pool from one enriched run with a valid IG handle, scoped to
  shippable verticals: ~3,000–4,500.
- Post + reel comment scrape (~30 posts / ~20 reels, top-N comments) at Apify
  IG rates ≈ $0.005–0.008 per handle combined (comments add a little over
  Engine 04's view-only pull). 4,000 × $0.006 ≈ **$24**.
- Geo-inference: regex + explicit-city capture is free; Haiku only on the
  ambiguous residual (~15–20% of gated comments, a few hundred tokens each)
  ≈ **$2–4**.
- **Per-run total: ~$26–30.**
- **Net-new / re-surfaced leads per run:** ~**80–200** operators clearing
  `oot_score >= 35` AND ICP A/B, of which ~25–60 hit Tier 1 (multi-city +
  explicit ship-ask + multiple distinct authors). Most already exist in the
  universe — the value is the *fresh, quotable geo-demand trigger*, which moves
  a dormant high-ICP row to the top of the call queue.

## Refresh cadence

**Bi-weekly to monthly.** Out-of-town comment waves are perishable — "please
ship to Chicago" lands hardest while the post is still circulating, and the
`recency_days` column drives prioritization. Re-scrape only handles with a new
post since last run to spare Apify. Drop-model bakeries/butchers that post a
weekly drop accumulate fresh out-of-town asks every cycle and justify the
tighter bi-weekly pass during peak season.

## Risks

- **Geo-inference is the load-bearing weak point.** Commenter location is
  noisy: profile location is often absent, stale, or a joke ("planet earth").
  Lean on explicit-city captures (`geo_confidence=high`) for Tier 1; never let
  a low-confidence LLM guess alone mint a Tier 1. Require ≥2 *distinct authors*,
  not 2 comments, to suppress one superfan spamming.
- **Aspirational vs. transactional.** "I'd order every month" from someone who
  never would is cheap talk; weight explicit `ship_ask` and multi-author
  breadth over a single effusive comment. Sarcasm and tag-a-friend ("@dave we
  NEED this in Denver") inflate counts — keep a Haiku confirmation pass for
  borderline rows.
- **Operator already ships.** If the business has a national mail-order /
  existing club that already ships everywhere, the out-of-town ask is partly
  satisfied — the trigger weakens to a *platform-switch* angle, not a
  new-demand angle. `detect_clubs.py` + a `club_ships_bool` check should
  reclassify these toward the Engine 01 transition motion.
- **Liquor-store / chain leakage.** "Do you ship?" appears on liquor stores
  pushing Tito's/Veuve-grade SKUs and on chains with national footprints.
  Enforce `config.CHAIN_KEYWORDS` + liquor-license + wine commodity-SKU
  exclusions, and treat City Hive / Spot Hopper ESP footprints as a
  liquor-store red flag before scoring any wine row.
- **Wine-bar exclusion.** Wine bars mostly excluded (low Peak AGMV) except
  geographic-monopoly cases — let `reclassify.py`'s claw-back gate them; a wine
  bar can't ship a club anyway.
- **Sweets-only demotion.** A cupcake-only shop with out-of-town fans is still
  single-product; cap at Tier 2 per the sweets-only/single-product rule.
- **Small-market understatement.** A small-town operator with a regionally
  beloved brand may pull genuine out-of-state asks but post rarely and have low
  raw comment volume. Weight `distinct_cities` and explicit ship-asks over
  absolute counts; static-only social understates these brands — don't DQ.
- **Butcher/deli/grocer FB blind spot.** These verticals' demand often lives in
  Facebook comments, which the IG actors miss. The engine will undercount them
  unless the step-3 FB surface yields comment text (see Open questions).
- **Apify / IG rate-limit fragility.** Comment scraping at 30-batch scale can
  throttle; checkpoint per batch and support `--resume` like `detect_clubs.py`.

## Repo placement

```
triggers/
  __init__.py
  out_of_town_demand.py        # main: fetch comments -> travel-intent regex
                               #   -> geo-infer -> displacement score
  _geo_infer.py                # commenter-metro resolver (regex city capture,
                               #   profile parse, Haiku fallback) -> config.CITIES bucket
  _comment_fetch_lib.py        # wraps enrich.py step 6/7 Apify post/reel comment pull
discover_out_of_town_demand.py # orchestrator, mirrors discover_awards.py shape;
                               #   takes --input <enriched_or_scored.csv>, --resume
```

Refactor targets so we don't duplicate auth/scrape logic:

- Lift the reel/post pull bodies out of `enrich.py` steps 6–7 into a shared
  `enrich_ig_lib.py` (the same refactor Engine 04 proposes) and extend it to
  return comment objects, so both `enrich.py` and `triggers/` call one
  Apify-actor wrapper instead of re-declaring actor IDs, batching, and retries.
- `_geo_infer.py` should reuse `config.CITIES` and any city-normalization map
  already used by `discover.py` so metro buckets are consistent across engines;
  if no normalizer exists yet, add `config.CITY_ALIASES` (genuinely new).

`config.py` knobs to add: `TRAVEL_INTENT_REGEX` (the bank above),
`OOT_SCORE_THRESHOLDS`, comments-per-post cap, and `CITY_ALIASES`.

## Open questions

1. Does the Apify `instagram-post-scraper` reliably expose commenter **profile
   location / bio**, or only `text` + `ownerUsername`? If only text, geo-inference
   collapses to explicit-city captures + Haiku-over-text, which sharply lowers
   coverage for "wish you shipped" comments that name no city — worth a 30-handle
   probe before committing the geo pipeline.
2. How aggressively should an unresolved-but-explicit ship-ask ("do you ship
   nationwide?") count as out-of-town demand when no commenter metro is
   recoverable? It's clearly transactional but adds no `distinct_cities` — should
   it get its own credit so a clear ship-ask isn't penalized for vagueness?
3. Can we capture **Facebook** comment threads (where butcher/deli/grocer demand
   concentrates) from the existing `enrich_facebook()` HTML path, or is FB
   comment text a genuinely new source lane?
4. Should a strong out-of-town signal cross-corroborate with Engine 04's
   buy-intent spike on the same handle? A reel breakout *and* multi-city ship-asks
   is the highest-conviction shippable-club target — worth a dedicated top cohort.
