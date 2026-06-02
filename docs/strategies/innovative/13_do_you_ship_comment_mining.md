# Lead Engine 13 — "Do You Ship?" Comment Mining

**Motion:** Curation
**Vertical fit:** Bakeries, wine, butchers, cheese (retail verticals where the product is shippable/transportable and there's no reservation grid)
**Suggested list name(s):** `do_you_ship_comment_mining`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $35/run

## Premise

The cleanest expression of demand-over-capacity isn't the operator admitting
they sold out — it's *the customer asking to buy and being told no*. When a
butcher's dry-age reel fills with "do you ship?", when a bakery's croissant
drop draws "wish you were in Chicago", when a cheese shop's wheel video pulls
"how can I order this", that is unmonetized, geographically-unreachable
demand stated in the customer's own words. The operator currently has no
channel to capture it. A Table22 recurring-access / ship-nationwide program
is the exact mechanism that closes that gap.

In the two-score model this is a pure **Trigger** harvester layered on the
ICP Fit our pipeline already scores. It differs from Engine 04
(video-engagement-spike), which gates on *breakout reach* and reads comments
only as a secondary corroborator. This engine inverts that: it mines
**comment text directly** for explicit purchase/shipping intent across IG,
TikTok, and Facebook, with no requirement that the underlying post went
viral. A modest post on a beloved local butcher can still carry ten "can you
send this to me" comments — that's a strong signal even at low reach.

The fit verticals are deliberately retail-skewed (butcher / wine / cheese /
bakery — the top of the partner-type AGMV table). These are shippable or
transportable products where "do you ship" is a literal, monetizable
question, unlike a destination restaurant where the equivalent demand is
captured by reservation-difficulty engines. Butcher/deli/specialty-grocer
audiences also skew to Facebook, so FB comment text is a first-class surface
here, not an afterthought.

## Recipe

A **trigger-overlay** engine, run CSV-in / CSV-out like `detect_clubs.py` —
it scores a known candidate universe for buy/ship-intent comments and emits
matches with verbatim quotes. It does not discover net-new businesses; it
stamps a quotable trigger onto operators we already know.

1. **Seed the candidate set, don't re-discover.** Start from the most recent
   `output/2_enriched_posts.csv` (steps 1–7 already run) or any scored
   `custom-serper-scoring_*_all.csv`. Require a resolved IG handle (and FB
   page where present). Restrict to fit verticals (butcher, wine, cheese,
   bakery) using `partner_type` from `reclassify.py`. This bounds Apify spend
   to known-ICP operators.

2. **Pull recent posts + reels with their comments.** Reuse the same Apify
   actors `enrich.py` steps 6–7 use (`instagram-post-scraper`,
   `instagram-reel-scraper`), batched in groups of 30. Critically, request
   the **comment payload** (top N comments per item with author handle + text
   + timestamp), not just the post-level metrics. Scan the last ~30 posts and
   ~20 reels per handle. For butcher/cheese/grocer rows, also scan FB post
   comment text captured via the `enrich.py` step-3 (`facebook`) path.

3. **TikTok comments are a new source lane.** The repo has no TikTok primitive
   today. Add a TikTok comment scraper as a *new* Apify actor (e.g. a
   `tiktok-comments-scraper` actor ID registered in `config.py` alongside the
   IG actor IDs). Match handles by name/website where a TikTok handle isn't
   already known — that resolution is itself an open question (see below).
   Gate TikTok behind a flag so the engine runs IG+FB-only until the actor is
   validated.

4. **Mine comment text for buy/ship intent** with a cheap regex pass first
   (no LLM for the gate), counting *distinct comment authors* per business:

```
SHIP_INTENT_PATTERNS = (
  r"do\s*you\s*ship",            r"can\s*you\s*ship",
  r"can\s*you\s*send\s*(this|me)", r"do\s*you\s*(deliver|mail)",
  r"can\s*i\s*(order|buy|get)\s*(this|one|these)?",
  r"how\s*(can|do)\s*i\s*(order|buy|get)",
  r"where\s*can\s*i\s*(buy|get|order)",
  r"wish\s*you\s*(were|shipped|delivered)\s*(in|to)",
  r"when('?s|\s*is)\s*the\s*next\s*drop",
  r"can\s*i\s*get\s*this\s*(delivered|shipped|sent)",
  r"ship\s*to\s*([A-Z][a-z]+)?",  r"nationwide", r"restock",
)

intent_authors = count of DISTINCT comment authors matching any family
ship_specific  = count of authors matching the ship/send/deliver/mail subset
geo_envy       = count of authors matching "wish you were in <city>" / "ship to <city>"
drop_demand    = count of authors matching "next drop" / "restock"
recency        = days since most-recent matched comment
breadth        = #surfaces with a match (ig | tiktok | fb)
```

5. **Score ship-intent intensity:**

```
intent_score = min(100,
      20*min(intent_authors,3)        # volume of distinct askers
    + 25*(1 if ship_specific>=2 else 0)  # explicit SHIP intent, not just "order"
    + 15*min(geo_envy,1)             # out-of-market demand = ship-program fit
    + 10*min(breadth,2)              # cross-surface corroboration
    + (10 if recency<=30 else 0))    # perishable; fresh asks land hardest

trigger_tier = 1 if intent_score>=55 else 2 if intent_score>=35 else 3
```

6. **LLM disambiguation pass (cheap, targeted).** For ambiguous rows, run an
   `awards/llm_extract.py`-style extraction with `claude-haiku-4-5-20251001`
   (the same model `scrape_beli` uses for caption/OCR mining) over the matched
   comment snippets, to reject sarcasm, friend-tagging ("@dave we NEED this"),
   bot spam, and rhetorical "can I order ten of these 😍" that isn't a real
   logistics ask. Require genuine first-person purchase/shipping intent.
   Prefix any SDK-importing script with `unset ANTHROPIC_API_KEY &&` (empty-key
   shell gotcha).

7. **Qualify against ICP before handoff.** Run `reclassify.py`
   (`partner_type` / `business_type_v2` + wine-bar claw-back) and
   `detect_clubs.py` (existing club = positive platform-switch signal, not a
   DQ). Hard-filter liquor-store / chain / delivery-only leakage and the wine
   commodity-SKU exclusion list. Feed survivors to `score.py` for the /100 ICP
   Fit. **Final list = high `intent_score` AND ICP Fit (A/B tier).** High-intent
   / weak-ICP routes to nurture, never straight to sales.

Matched comments are preserved verbatim (with author handle redacted to a
first-name/initial if needed) so a BDR can open with the exact "do you ship?"
the operator's own customers wrote.

## Output schema

```
output/social_signals/do_you_ship_comment_mining_<YYYYMMDD>.csv
source = "do_you_ship_comment_mining"
tier = <1|2|3>                       # = trigger_tier from intent_score
business_type = butcher | wine | cheese | bakery
distinction = "Customer ship-intent: {intent_authors} askers across {breadth} surfaces ({ship_specific} explicit ship asks), last seen {recency}d ago"
year = <YYYY of most-recent matched comment>
+ evidence cols:
    ig_handle, fb_url, tiktok_handle,
    intent_score, trigger_tier,
    intent_authors, ship_specific, geo_envy, drop_demand,
    recency_days, breadth, source_surface (ig|tiktok|fb|multi),
    matched_terms (pipe-delim),
    comment_samples,        # 1-3 verbatim "do you ship?" quotes for outbound
    sample_post_urls,       # the posts those comments sit under
    scan_date,
    icp_fit_score, partner_type, has_club   # joined from score.py / detect_clubs
```

## Volume & cost

Overlay on a known set; spend bounded by candidate count, not a fresh crawl.

- Candidate pool of fit-vertical operators with a valid IG handle from one
  enriched run: ~2,500–4,000 (butcher/wine/cheese/bakery is a smaller slice
  than the full universe).
- IG post + reel scrape *with comments* via Apify ≈ $0.006–0.010 per handle
  (comment payloads cost more than metrics-only). 3,500 × $0.008 ≈ **$28**.
- FB comment scrape on the butcher/cheese/grocer subset (~1,000 pages):
  cheap incremental on the existing step-3 path, ≈ **$3–5**.
- TikTok comment actor (when enabled): treat as a separate ~$10–15 line item
  on the subset with a known TikTok handle; keep off by default until proven.
- Haiku disambiguation on ~10–15% ambiguous hits (~400 rows) ≈ **$2–4**.
- **Per-run (IG+FB): ~$30–35.** With TikTok enabled: ~$45.
- **Net-new / re-surfaced triggered leads per run:** ~150–350 operators
  clearing `intent_score >= 35` AND ICP A/B; ~40–90 hit Tier 1 (≥2 explicit
  ship asks + cross-surface). Most are already in the universe — the value is
  the fresh, quotable trigger that moves a dormant high-ICP row to the top of
  the call queue.

## Refresh cadence

**Bi-weekly to monthly.** Ship-intent comments are perishable — a "do you
ship?" under last week's drop reel lands hardest while that post still
circulates, and the comment wave decays within days. The `recency_days`
column drives sales prioritization; re-scrape only handles with a new post
since the last run to avoid re-burning Apify. Tighten to bi-weekly for
weekly-drop bakeries/butchers during peak season.

## Risks

- **Comment false positives.** Sarcasm, friend-tagging ("@dave we NEED
  this"), bots, and rhetorical hype ("I could order ten 😍") inflate the raw
  count. The Haiku pass (step 6) is load-bearing, not optional; gate on
  *distinct authors with genuine first-person intent*, never raw comment
  count.
- **Static-social understates brand.** A respected butcher who simply doesn't
  attract chatty commenters scores zero here — do not DQ them. This engine
  only *adds* a trigger; absence of comment signal ≠ absence of demand.
- **Small-market metrics run low.** A one-location shop in a small town may
  have devoted out-of-town fans but a thin comment stream. Weight `geo_envy`
  and `ship_specific` (scale-free intent) over raw `intent_authors`, and lean
  on relative local dominance — don't let big-city comment volume crowd them
  out.
- **Liquor-store / chain leakage.** Wine "can I order / ship to me" comments
  show up under liquor stores pushing Tito's/Veuve-grade SKUs and chains.
  Enforce `config.CHAIN_KEYWORDS` + the liquor-license filter + the wine
  commodity-SKU exclusion list before scoring; City Hive / Spot Hopper ESP
  footprints flag a liquor store.
- **Wine-bar exclusion.** Wine bars mostly excluded (low Peak AGMV) except
  geographic-monopoly cases — let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake-only bakery drawing ship-intent is still
  single-product; cap at Tier 2 per the single-product demotion rule. Carry
  the input row's `partner_type` and apply the cap.
- **Apify / IG rate-limit fragility.** Comment-payload scraping at 30-batch
  scale throttles harder than metrics-only pulls; checkpoint per batch and
  support `--resume` like `detect_clubs.py`. Comment fields may be sparse or
  paginated — confirm the actor returns enough comments per item on a probe
  before committing thresholds.
- **TikTok is unbuilt and fragile.** No existing primitive; handle resolution
  is unsolved and TikTok comment actors are anti-bot brittle. Ship IG+FB
  first; treat TikTok as an opt-in extension, not a launch dependency.

## Repo placement

```
social_signals/                       # shared with Engine 04 if built first
  __init__.py
  fetch_comment_signals.py            # batches handles through
                                      # instagram-post-scraper + reel-scraper
                                      # requesting comment payloads; FB comments;
                                      # optional tiktok-comments-scraper
  detect_ship_intent.py               # SHIP_INTENT_PATTERNS regex bank,
                                      # distinct-author scoring, Haiku confirm
  finalize.py                         # emits canonical CSV with evidence cols
discover_ship_intent.py               # orchestrator, mirrors discover_awards.py
                                      # shape; --input <enriched_or_scored.csv>,
                                      # --resume, --enable-tiktok
```

Refactor targets so we don't duplicate auth/batching:

- Lift the reel/post pull bodies out of `enrich.py` steps 6–7 into a shared
  `enrich_ig_lib.py` Apify-actor wrapper (the same refactor Engine 04
  proposes), extended to request comment payloads, so both `enrich.py` and
  `social_signals/` call one wrapper instead of re-declaring actor IDs,
  batching, and retry.
- Reuse `enrich.py` step-3 (`facebook`) HTML/comment scrape for the FB
  surface rather than re-implementing it.

`config.py` knobs to add: `SHIP_INTENT_REGEX` (the bank above),
`INTENT_SCORE_THRESHOLDS`, the comments-per-item cap, and the
`tiktok-comments-scraper` actor ID alongside the existing IG actor IDs.

## Open questions

1. Do the Apify IG post/reel actors return enough comments per item (and
   stable `author` ids) to count *distinct askers* reliably, or are comment
   payloads truncated/sampled in a way that biases toward high-engagement
   posts? A 30-handle probe should settle this before locking thresholds.
2. How do we resolve a TikTok handle for an operator we only know by name +
   IG + website? Without a reliable handle-match, TikTok comment mining can't
   be scoped to known-ICP rows and risks re-introducing discovery noise.
3. Should `geo_envy` ("ship to <city>" / "wish you were in <city>") spawn its
   own sub-list? Out-of-market demand is the single most ship-program-aligned
   signal here and arguably deserves a dedicated, higher-priority bucket.
4. Do we cross-corroborate with Engine 03 (sold-out) and Engine 04 (video
   spike)? An operator whose viral reel both says "sold out" *and* draws a
   wall of "do you ship?" is a triple-confirmed demand-over-capacity target —
   the highest-conviction sub-cohort for outbound.
