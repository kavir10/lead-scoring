# Lead Engine 27 — Local Food Influencer Repetition List

**Motion:** Curation
**Vertical fit:** Restaurants (destination + neighborhood), bakeries, butchers, wine, cheese
**Suggested list name(s):** `local_influencer_repetition`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $40/run

## Premise

A single viral hit is noise — one tourist creator films a croissant, the post
pops, the shop never sees a durable demand bump. What actually predicts a
business worth a recurring-access program is *repetition*: the same merchant
showing up across **multiple independent local creators** inside a tight
window, and the same creators **returning** to cover it again. Repeated
independent coverage by people who actually live in the market is a proxy for
sustained local cultabuilding — the demand-over-capacity thesis stated through
the lens of the people whose job is to surface what's hot. Tourists chase
novelty; locals re-post what keeps being worth re-posting.

In the two-score model this is primarily a **Trigger** harvester with a strong
**ICP-Fit** correlate baked in: businesses that earn repeat local-creator
coverage skew exactly toward the high-AGMV partner types (butcher, wine,
cheese, destination restaurant). Crucially, the underlying signal is **video
views and shares** — the top of the SHAP engagement hierarchy — observed
*across multiple accounts*, which is far more robust than one account's
single breakout. It generalizes the `scrape_beli` motion (mining one tastemaker
account for merchant mentions) to a **fan of local creators per metro**, then
ranks merchants by cross-creator repetition rather than raw reach.

This pairs naturally with the reservation-difficulty and sold-out engines: a
merchant that three local creators keep filming *and* whose posts mention
sellouts/drops/waits is a triple-confirmed target. Repetition is the spine;
purchase-intent comments and scarcity language are the corroborators.

## Recipe

A **discovery + trigger** engine that mines a curated set of local food
creators per metro, aggregates merchant mentions, and ranks by repetition
breadth/recency. It generalizes `scrape_beli/`'s multi-phase IG-mining shape
(fetch → extract → context → merge → dedupe) from one account to a
per-metro creator fan-out.

1. **Build the local-creator seed registry (the hard part, do it once).** Per
   metro in a trendy-neighborhood-biased subset of `config.CITIES` (seed from
   `research/trendy_neighborhoods/` — ~56.5% of partners sit in trendy
   neighborhoods), assemble 8–20 *local* food creators. Two intake lanes:
   - **Serper Web** (`google.serper.dev/search`) queries like
     `"best <city> food instagram"`, `"<city> food blogger instagram"`,
     `"<neighborhood> eats reels"`, then Claude (`awards/llm_extract.py`
     pattern, `claude-haiku-4-5-20251001`) to extract handles from the result
     articles/listicles.
   - **Apify `instagram-tagged-posts-scraper`** seeded from a handful of
     known merchant handles: who keeps tagging this butcher/bakery? Recurring
     taggers *are* the local creators. This bootstraps the registry from the
     partner side.
   Persist the registry as `config.LOCAL_CREATORS_BY_METRO` (or a checked-in
   `data/local_creators.csv`) with `handle, metro, follower_band, is_local`.
   **Local-ness gate is load-bearing** — exclude national/tourist accounts
   (>250k followers or a bio listing multiple cities) so we measure local
   cult, not travel-influencer drive-by.

2. **Fetch each creator's recent posts + reels.** Reuse the Apify actors
   `enrich.py` steps 6–7 use (`instagram-post-scraper`,
   `instagram-reel-scraper`), batched in groups of 30. Pull the last ~30 posts
   / ~20 reels per creator over a **rolling 90-day window**, with per-item
   `video_view_count`, `share_count`, `like_count`, caption text, tagged
   accounts, location tag, and timestamp.

3. **Extract the mentioned merchant per item.** Mirror
   `scrape_beli/extract_captions.py` + `add_post_context.py`: resolve the
   merchant from (a) tagged business accounts, (b) location tag, (c) Claude
   caption/OCR extraction for handle-less mentions. Emit one
   `(merchant, creator, metro, post_url, ts, video_views, shares)` row per
   mention. Prefix any SDK-importing script with `unset ANTHROPIC_API_KEY &&`
   (empty-key shell gotcha).

4. **Aggregate to the merchant and compute repetition signals:**

```
window            = last 90 days
distinct_creators = # of DISTINCT local creators who mentioned merchant in window
repeat_creators   = # of creators who mentioned merchant >=2 times (returning coverage)
mention_count     = total mentions in window
recency_days      = days since most-recent mention
cadence_30d       = mentions in last 30d (is the repetition accelerating?)
sum_video_views   = summed video views across mentioning reels (engagement weight)
scarcity_hits     = # mentions whose caption matches DROP/SELLOUT/WAIT patterns
intent_comments   = # purchase-intent comments under those posts (reuse Engine 13 bank)
```

   Scarcity caption bank (the source idea's sellout/drop/wait/preorder cue):

```
SCARCITY_PATTERNS = (
  r"sold\s*out",  r"sells?\s*out",  r"sell[- ]?out",
  r"get\s*there\s*early",  r"line\s*(was|around|out)",
  r"(\d+\s*(min|hour)s?\s*)?wait",  r"pre[- ]?order",
  r"(weekly|friday|weekend)\s*drop",  r"limited\s*(batch|run|qty|quantity)",
  r"by\s*the\s*time\s*i\s*got\s*there",  r"restock",
)
```

5. **Score repetition intensity** (cross-creator breadth and returning
   coverage outrank single-account reach):

```
rep_score = min(100,
      22*min(distinct_creators,3)        # breadth: independent local voices
    + 20*min(repeat_creators,2)          # returning coverage = durable, not a flash
    + 12*(1 if cadence_30d>=2 else 0)    # accelerating, still live
    + 12*min(scale(sum_video_views),1)   # SHAP-top engagement, scale-normalized
    + 8 *min(scarcity_hits,2)            # demand-over-capacity corroborator
    + 6 *min(intent_comments,2)          # buy-intent corroborator (Engine 13 reuse)
    + (8 if recency_days<=30 else 0))    # fresh signal lands hardest

# single-viral guard: one creator, one post, no repeat -> hard cap
if distinct_creators < 2 and repeat_creators == 0:
    rep_score = min(rep_score, 20)       # demote one-off virals, never Tier 1

trigger_tier = 1 if rep_score>=55 else 2 if rep_score>=35 else 3
```

6. **Resolve merchants to canonical rows + enrich the net-new ones.** Many
   mentioned merchants won't be in our universe yet. For unknown merchants,
   resolve name + metro to a Serper Maps row (same primitive as `discover.py`,
   applying the niche quality floors ≥20 reviews / ≥4.0 and requiring a
   website), then run the standard `enrich.py` chain (websites → instagram →
   facebook). This is where the engine *discovers* net-new leads, not just
   re-stamps known ones.

7. **Qualify against ICP, then score.** Run `reclassify.py` (`partner_type` /
   `business_type_v2` + wine-bar claw-back) and `detect_clubs.py` (existing
   club = positive platform-switch signal, not a DQ). Hard-filter
   liquor-store / chain (`config.CHAIN_KEYWORDS` + liquor-license filter) /
   delivery-only / caterer leakage and the wine commodity-SKU exclusion list.
   Feed survivors to `score.py` for the /100 ICP Fit. **Final list = high
   `rep_score` AND ICP Fit (A/B tier).** High-repetition / weak-ICP routes to
   nurture; never straight to sales.

Every output row preserves the creator handles, post URLs, and a verbatim
caption/scarcity quote so a BDR can open with "three of <metro>'s food
creators keep filming you — and your last drop sold out."

## Output schema

```
output/social_signals/local_influencer_repetition_<YYYYMMDD>.csv
source = "local_influencer_repetition"
tier = <1|2|3>                       # = trigger_tier from rep_score
business_type = restaurant | butcher | wine | cheese | bakery
distinction = "Repeat local-creator coverage: {distinct_creators} creators / {mention_count} posts in 90d ({repeat_creators} returning), last seen {recency_days}d ago"
year = <YYYY of most-recent mention>
+ evidence cols:
    metro, ig_handle, website,
    rep_score, trigger_tier,
    distinct_creators, repeat_creators, mention_count, cadence_30d,
    recency_days, sum_video_views, scarcity_hits, intent_comments,
    creator_handles (pipe-delim),     # the local creators who covered them
    sample_post_urls,                 # 2-4 posts for outbound proof
    sample_captions,                  # 1-2 verbatim scarcity/hype quotes
    is_net_new,                       # discovered here vs already in universe
    scan_date,
    icp_fit_score, partner_type, has_club   # joined from score.py / detect_clubs
```

## Volume & cost

Spend is bounded by **creator count, not merchant count** — we crawl a fixed
fan of creators and merchants fall out for free.

- Metros: ~40 trendy-biased markets × ~12 creators ≈ **480 creators**.
- IG post + reel scrape (with captions/tags) via Apify ≈ $0.005–0.008 per
  creator handle. 480 × $0.007 ≈ **$3.4**. Cheap, because the universe is
  creators not businesses.
- Claude caption/OCR extraction over ~480 × ~50 items ≈ 24k items at Haiku
  rates ≈ **$8–12** (only handle-less mentions need the LLM; tagged/location
  mentions resolve free).
- Net-new merchant resolution: Serper Maps lookups for ~600–1,000 unknown
  merchants ≈ a few hundred calls ≈ **$3–5**; `enrich.py` websites/IG/FB on
  the net-new subset (~600 rows) ≈ **$6–10**.
- Registry build (Serper Web + tagged-posts bootstrap) is mostly a one-time
  cost amortized across runs; ≈ **$5** incremental for refresh.
- **Per-run: ~$30–40.**
- **Net-new / re-surfaced triggered leads per run:** ~400–700 merchants with
  ≥2 distinct local creators in 90d; after ICP A/B gating, **~150–300**
  qualified, of which **~40–80 are genuinely net-new** to the universe and
  ~50–110 hit Tier 1 (≥3 creators or ≥2 returning creators).

## Refresh cadence

**Monthly**, on a rolling 90-day window. Repetition is a slower signal than a
single viral spike by design — the point is durability, so we don't need to
catch it within days. Monthly cadence lets `cadence_30d` and `recency_days`
flag *accelerating* coverage (a merchant going from 1→3 creators month over
month is a sharper buy signal than a flat-but-high count). Re-scrape only
creators with new posts since last run to avoid re-burning Apify. The creator
**registry** itself should be re-audited quarterly — local creator rosters
churn, accounts go national, new ones emerge.

## Risks

- **Single-viral contamination.** One tourist creator's breakout post is the
  exact thing this engine must *not* reward. The `distinct_creators<2` hard
  cap (step 5) and the local-ness gate (step 1) are load-bearing, not optional.
- **Tourist / national-creator leakage.** A travel account that "lives
  everywhere" inflates breadth without reflecting local cult. Enforce the
  follower-band and single-metro-bio gate in the registry; when in doubt,
  exclude — false negatives are cheaper than polluting the repetition metric.
- **Creator-clique echo.** A tight group of creators who all film the same
  three openings cross-promote each other; their "independent" coverage isn't.
  Treat creators who *always* co-appear as correlated and discount breadth
  accordingly (an open question on how aggressively).
- **Small-market metrics run low.** A great butcher in a 3-creator town can't
  hit `distinct_creators>=3`. Weight `repeat_creators` (returning coverage,
  scale-free) and relative local dominance over raw breadth; don't let dense
  big-city creator scenes crowd out small-market operators.
- **Static-social understates brand.** A beloved shop that local creators
  simply don't post about scores zero here — this engine only *adds* a
  trigger; absence ≠ absence of demand. Never DQ on it.
- **Liquor-store / chain leakage.** Creator-tagged "wine" spots include liquor
  stores and chains. Enforce `CHAIN_KEYWORDS` + liquor-license filter + the
  wine commodity-SKU exclusion list; City Hive / Spot Hopper ESP footprints
  flag a liquor store. Let `reclassify.py`'s wine-bar claw-back gate wine bars
  (excluded except geographic-monopoly).
- **Sweets-only demotion.** A cupcake-only bakery that creators love is still
  single-product; cap at Tier 2 per the single-product demotion rule. Carry
  `partner_type` and apply the cap.
- **Merchant resolution ambiguity.** Caption mentions without a tag ("that
  spot in Bushwick") are hard to resolve to a canonical business; mis-resolution
  pollutes the count. Prefer tag/location resolution; gate Claude-resolved
  name-only mentions behind a confidence threshold.
- **Apify / IG rate-limit fragility.** Reel/post scraping at 30-batch scale
  throttles; checkpoint per batch and support `--resume` like `detect_clubs.py`.

## Repo placement

```
social_signals/                       # shared with Engines 04 / 13 if built first
  __init__.py
  creator_registry.py                 # build/refresh LOCAL_CREATORS_BY_METRO via
                                       # Serper Web + Claude + tagged-posts bootstrap;
                                       # local-ness gate
  fetch_creator_posts.py              # batches creator handles through
                                       # instagram-post-scraper + reel-scraper (90d)
  extract_mentions.py                 # tag/location/Claude merchant resolution
                                       # (mirrors scrape_beli extract+context)
  aggregate_repetition.py             # merchant rollup + rep_score + scarcity/intent
  finalize.py                         # canonical CSV with evidence cols
discover_influencer_repetition.py     # orchestrator, mirrors discover_awards.py shape;
                                       # --metros, --window-days, --resume, --refresh-registry
data/local_creators.csv               # checked-in seed registry (gitignored if large)
```

Refactor targets so we don't duplicate auth/batching:

- Lift the reel/post pull bodies out of `enrich.py` steps 6–7 into a shared
  `enrich_ig_lib.py` Apify-actor wrapper (the same refactor Engines 04/13
  propose), so `enrich.py` and `social_signals/` call one wrapper.
- Reuse `scrape_beli/`'s caption-extraction and post-context modules rather
  than re-implementing merchant resolution; this engine is essentially
  `scrape_beli` parameterized over a creator fan instead of one account.
- Reuse the Engine 13 purchase-intent comment bank for the `intent_comments`
  corroborator (shared `detect_ship_intent` regexes).

`config.py` knobs to add: `LOCAL_CREATORS_BY_METRO` (or path to the registry
CSV), `SCARCITY_PATTERNS` (the bank above), `REP_SCORE_THRESHOLDS`,
`CREATOR_LOCAL_FOLLOWER_CAP`, and the `instagram-tagged-posts-scraper` actor
ID (already in `config.py` per the Apify actor list) wired into the registry
bootstrap.

## Open questions

1. How do we build and maintain the local-creator registry at scale without
   it becoming a manual, per-metro curation chore? Can the tagged-posts
   bootstrap (who keeps tagging known partners) reliably surface the right
   creators, or does it need a human pass per metro on first build?
2. How aggressively should we discount **creator-clique echo** — co-appearing
   creators who cross-promote? A correlation/co-mention matrix could down-weight
   non-independent breadth, but that adds complexity; is the simpler
   distinct-author count good enough at launch?
3. Where's the local-vs-national cut line? A fixed follower cap (250k) is
   crude; a creator can be local-influential with a big following. Should
   "local" be defined by *content geography* (share of posts tagged in-metro)
   rather than follower count?
4. Do we cross-corroborate with Engine 03 (sold-out) and Engine 13 (ship-intent
   comments) to mint a triple-confirmed sub-cohort — repeat local coverage +
   scarcity captions + buy-intent comments — as the highest-conviction
   outbound bucket?
