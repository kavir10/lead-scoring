# Lead Engine 50 — Facebook-Heavy Butcher and Deli List

**Motion:** Curation
**Vertical fit:** Butchers, delis, specialty grocers, legacy bakeries (the low-IG / Facebook-native cohort)
**Suggested list name(s):** `facebook_heavy_butcher_deli`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $12/run

## Premise

Our engagement signals (avg video views, shares, likes) and `follower_count`
all lean Instagram-first. For butchers, delis, specialty grocers, and legacy
neighborhood bakeries that's the wrong lens: their customer base is older,
local, and lives on Facebook. The community is in the FB comments — weekly
specials, meat-bundle drops, holiday preorder threads ("turkey list is open"),
and high comment volume on plain product photos. The ICP cheat-sheet says this
directly: Facebook engagement often beats IG for butcher/deli/specialty-grocer,
and static-only social *understates* brand for these verticals — so a thin or
absent IG must never DQ them. Real confirmed examples (Gartners, B&W Meat,
Carnivore Oak Park, Don & Joe's) land at Tier 2 on the strength of FB alone.

This is an **ICP-Fit harvester with a Trigger overlay**. ICP fit is excellent
by construction — butcher ($75.9k Peak AGMV), market/deli ($48.7k), specialty
grocer ($27.9k) are exactly the partner types SHAP ranks highest, and FB
engagement is a *credible proxy for the engaged-audience feature the IG-only
pipeline misses*. The Trigger half comes from the practical-commerce posting
rhythm: a shop running weekly bundle posts and a recurring holiday preorder
thread is already operating a manual proto-subscription with a captive,
responsive base — the behavioral analog to a Table22 program, productized by
the operator and visible in the comment volume.

The catch is infrastructure: today `enrich.py` step 3 (`facebook`) and
`scripts/augment_butcher_facebook.py` only scrape a static **follower/like
count** (`fb_likes`). They capture no engagement (comments, reactions, post
recency, "people talking about this"). This engine's net-new work is turning
that static count into an *engagement* signal.

## Recipe

A curation overlay that runs over butcher/deli/grocer/bakery rows we already
discover, re-weights them on Facebook engagement instead of IG, and surfaces
the FB-native cohort the IG-first scoring buries.

1. **Assemble the candidate set.** Don't re-discover from scratch — union the
   FB-relevant verticals from existing outputs: the butcher lane
   (`output/butcher/1_discovered_butchers.csv` via `discover_butchers.py`,
   `BANNED_STATES` already enforced) plus deli / specialty-grocer / bakery rows
   from the generic pipeline. For net-new coverage, run a narrow `discover.py` /
   `scripts/fresh_icp_search.py` Serper Maps pass keyed on FB-native shop types
   (bias geography to `research/trendy_neighborhoods/` seeds):

   ```
   FB_NATIVE_QUERIES = [
     "old fashioned butcher shop", "italian deli", "german deli",
     "polish deli", "neighborhood butcher", "meat market",
     "specialty grocer", "salumeria", "smokehouse butcher",
     "old world bakery", "appetizing shop",
   ]
   ```

   Niche floors (≥20 reviews / ≥4.0), require a website, run
   `config.CHAIN_KEYWORDS` to strip supermarket/chain counters. Dedupe with
   `dedupe_existing.py` (phone-first, then name+address).

2. **Resolve each shop's Facebook page.** Reuse
   `augment_butcher_facebook.find_facebook_url()` (crawls the business website
   for an `facebook.com/<page>` link, with the `FACEBOOK_SKIP_RE` filter that
   drops `/sharer`, `/events`, `/groups`, `/reel`, login URLs). For shops with
   no website FB link, fall back to a Serper Web lookup
   (`google.serper.dev/search` for `"<name>" "<city>" facebook`). Emit
   `facebook_url`, `has_facebook` (0/1). No-FB shops drop out — this engine is
   FB-defined.

3. **Scrape FB engagement, not just the like count (NET-NEW).** Extend the
   public-page scrape currently in `enrich.py:scrape_facebook_likes()` /
   `augment_butcher_facebook.scrape_facebook_followers()` (both only pull
   `"follower_count"`). Add extraction of the engagement surface from the public
   page HTML / `__bootloader` JSON:

   ```
   fb_likes / fb_followers      # existing
   fb_talking_about             # "X people are talking about this" (weekly activity proxy)
   fb_recent_post_age_days      # days since most recent visible post (freshness)
   fb_avg_comments_recent       # mean comments across last ~10 visible posts
   fb_avg_reactions_recent      # mean reactions across last ~10 visible posts
   fb_preorder_thread           # 0/1: recent post matches PREORDER_RE (below)
   ```

   Public FB markup is fragile; gate hard behind a freshness check and degrade
   gracefully (missing engagement → keep `fb_likes`, flag `fb_engagement=unknown`
   rather than dropping the row). Use `curl_cffi` (already the canonical fetch
   path in the augment script) for browser-fingerprinted requests.

4. **Mine post text for practical-commerce / preorder triggers.** Over the
   visible recent posts and pinned post, run a regex bank (mirrors the Engine 03
   text-signal approach):

   ```
   PREORDER_RE  = (holiday|thanksgiving|christmas|easter|new year)?\s*
                  (pre[- ]?order|reserve your|turkey list|ham order|
                   bundle|meat share|box drop|order deadline|cut-off)
   SPECIALS_RE  = (weekly special|this week|fresh today|just in|now in stock|
                   selling fast|while supplies last|sold out|limited)
   ```

   Emit `practical_commerce_signal` (0/1) + the matched snippet, preserved
   verbatim for outbound. A recurring preorder thread is the strongest single
   trigger here.

5. **Compute a Facebook engagement score (the qualifier).** IG-anchored scoring
   under-rates these shops, so rank on FB instead:

   ```
   # normalize within the candidate pool, not against absolute IG benchmarks
   fb_eng_rate  = (fb_avg_comments_recent + 0.3*fb_avg_reactions_recent)
                  / max(fb_followers, 200)          # comments weighted > reactions
   freshness    = 1 if fb_recent_post_age_days <= 14 else \
                  0.5 if fb_recent_post_age_days <= 45 else 0

   fb_score = 45 * percentile(fb_eng_rate, pool)        # engaged audience
            + 20 * freshness                            # actively posting
            + 20 * fb_preorder_thread                   # proto-subscription trigger
            + 15 * percentile(fb_talking_about, pool)   # weekly community activity
   # 0–100; comment volume on practical product posts is the load-bearing input
   fb_tier  = 1 if fb_score>=60 else 2 if fb_score>=35 else 3
   ```

   Comment volume on practical posts (not raw follower count) is what predicts a
   responsive base — consistent with the engagement hierarchy (views > shares >
   comments > likes; follower *count* is a separate weaker signal).

6. **Enrich, FB-weighted, and skip what doesn't apply.** Run `enrich.py` step 1
   (`websites` — ecommerce flag, email-signup form, social links) and step 3
   (`facebook`, extended per step 3 above) on the candidate set. Run step 2
   (`instagram`) only to record handle + IG follower count for `follower_count`
   completeness — **never as a gate** (thin IG is expected). Skip the expensive
   reservation lanes (steps 5/8): butchers/delis/grocers have no reservation
   grid, so `reservation_difficulty` is null here and must not zero out the row.

7. **Classify, club-check, qualify.** Run `reclassify.py`
   (`partner_type` ∈ {butcher, deli, specialty_grocer, bakery};
   `business_type_v2 = retail`) and `detect_clubs.py` (an existing meat
   share / preorder club = positive platform-switch signal, **not** a DQ). Then:

   ```
   final = has_facebook
           AND fb_score >= 35
           AND partner_type in {butcher, deli, specialty_grocer, bakery}
           AND not anti_icp          # post chain/supermarket/ghost-kitchen filters
   tier  = 1 if (fb_score>=60 AND practical_commerce_signal) else \
           2 if fb_score>=35 else 3
   ```

   `score.py` can still compute an ICP-fit score for reference, but the FB score
   is the qualifier — the whole point is that IG-anchored absolute scoring
   under-rates this cohort. `fb_preorder_thread=1` rows go to the top of the
   sales queue.

## Output schema

```
output/facebook_heavy/facebook_heavy_butcher_deli_<YYYYMMDD>.csv
source = "facebook_heavy_butcher_deli"
tier = <1|2|3>                       # = fb_tier; 1 = high FB engagement + preorder/specials trigger
business_type = butcher | deli | specialty_grocer | bakery
distinction = "Facebook-native {partner_type} — fb_score {fb_score}/100, {fb_avg_comments_recent} avg comments/post, preorder={Y/N}"
year = <YYYY>
source_url = <facebook page url — sales cites the live FB activity>
blurb = <one-line, e.g. "Weekly meat-bundle posts pull 40+ comments; holiday turkey list runs every Nov">
+ evidence cols:
    facebook_url, has_facebook,
    fb_followers, fb_likes, fb_talking_about,
    fb_recent_post_age_days, fb_avg_comments_recent, fb_avg_reactions_recent,
    fb_eng_rate, fb_score, fb_tier,
    fb_preorder_thread, practical_commerce_signal, signal_snippet,   # verbatim quote for outbound
    ig_handle, ig_followers, follower_count,                         # IG = context only, never a gate
    has_ecommerce, has_email_signup,
    partner_type, business_type_v2, has_club, club_type,
    icp_fit_score,                                                   # from score.py, reference only
    scan_date
```

Per-run master union: `output/facebook_heavy/facebook_heavy_butcher_deli_all_<YYYYMMDD>.csv`.

## Volume & cost

The candidate universe is the limiter, not search budget — FB scraping is the
free path; Serper/Apify are thin.

- Candidate assembly: butcher lane is free (alt-source scrape); the FB-native
  Serper Maps pass is ~11 queries × ~130 cities ≈ thin result sets, ~2–3K Maps
  calls × ~$0.001 ≈ **$2–3**. Nets ~400–700 net-new deli / grocer / legacy-
  bakery rows the IG-first pipeline never surfaced.
- FB page resolution: website crawl is free; ~20–30% need a Serper Web fallback
  (~$0.001 each) ≈ **$1**.
- FB engagement scrape: free (`curl_cffi`, concurrent, the existing 30-thread
  pattern). This is the bulk of the work and costs nothing per call.
- IG handle/follower enrich via Apify profile scraper on survivors only
  (~600 handles, batches of 30) × ~$0.015 ≈ **$8**. Skipped if IG is absent.
- Website ecommerce/email crawl: free (`enrich.py` step 1, 10 threads).
- **Per-run total: ~$10–12.**
- **Net-new qualified leads per run:** ~**350–600** clearing `fb_score ≥ 35` +
  ICP fit, of which ~**100–200** carry a preorder/specials trigger (tier 1).
  Most are *genuinely net-new* — they're the low-IG shops the engagement-weighted
  pipeline structurally buried.

## Refresh cadence

**Quarterly for discovery, monthly for the trigger.** The FB-native universe is
slow-moving (legacy delis/butchers don't churn), so the full candidate sweep +
classification runs quarterly. But the *trigger* layer (steps 3–4: post
freshness, preorder threads, weekly specials) decays fast and is seasonal — run
it **monthly** on the already-qualified set, and add a **September–November**
pass to catch holiday preorder threads (Thanksgiving turkey lists, Christmas
ham/roast orders) opening, which flips dormant tier-2 rows to tier-1.

## Risks

- **Static FB count ≠ engagement (the core trap).** A 20k-like page that hasn't
  posted in 8 months is dead. The whole engine fails if it scores on
  `fb_likes` alone — `freshness` and `fb_avg_comments_recent` must be
  load-bearing. If engagement extraction fails, flag `fb_engagement=unknown` and
  route to manual review; do not score on the like count by default.
- **Public FB markup fragility / rate limits.** FB aggressively varies markup
  and blocks scrapers. Use `curl_cffi` fingerprinting, throttle, checkpoint per
  chunk, and treat partial extraction as the norm. If FB hard-blocks at scale,
  fall back to Apify (no FB actor is wired today — see open questions) or degrade
  to the like-count-only path with the `unknown` flag.
- **IG-absence must not DQ.** Thin/absent IG is the expected state for this
  cohort and is *why the engine exists*. `follower_count` and IG metrics are
  context columns only; never gate on them.
- **Liquor-store / supermarket leakage.** "Deli" can mean a bodega/liquor
  combo, and "meat market" can be a supermarket counter. Enforce
  `config.CHAIN_KEYWORDS` + supermarket negatives; for any wine-adjacent
  specialty-grocer rows apply the liquor-license filter and wine commodity-SKU
  exclusion (Tito's/Veuve/Yellowtail-grade SKUs, City Hive/Spot Hopper ESP red
  flags).
- **Chain / franchise leakage.** Regional deli chains (10+ locations) hit every
  keyword. Run the chain filter and drop on location count.
- **Comment-bot / giveaway inflation.** A viral "tag 3 friends to win a
  brisket" post spikes comment counts without signaling a real recurring base.
  Use median across recent posts, not the max, and discount giveaway-pattern
  posts in the engagement mean.
- **Small-market metrics run low.** A genuine small-town butcher/deli posts to a
  small but devoted FB following — weight relative engagement rate
  (`fb_eng_rate`, normalized within pool) over absolute comment counts, and
  flag sub-floor rows for review rather than dropping.
- **Sweets-only demotion.** A legacy *bakery* that is cupcake/single-product
  caps at tier 2 per the sweets-only rule even with strong FB engagement — the
  subscription thesis is narrower for single-SKU sweets.
- **BANNED_STATES for butchers.** Apply the butcher-lane
  `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter to butcher rows before
  handoff (already enforced if sourced via `discover_butchers.py`; re-apply for
  Serper-sourced butcher rows).

## Repo placement

A new top-level package mirroring the `best_wine_shops/` / awards orchestrator
shape, plus a shared refactor of the FB scrape so the new engagement fields are
available to the main pipeline too:

```
facebook_heavy/
  __init__.py            # FB_NATIVE_QUERIES, FIT_VERTICALS, fb_score thresholds
  candidates.py          # union butcher lane + deli/grocer/bakery rows + Serper FB-native sweep
  fb_resolve.py          # reuses augment_butcher_facebook.find_facebook_url + Serper Web fallback
  fb_engagement.py       # NET-NEW: scrape talking_about / recency / comments / reactions / preorder
  score.py               # fb_eng_rate + fb_score + fb_tier (pool-normalized)
  finalize.py            # reclassify + detect_clubs + DQ filter + master union
discover_facebook_heavy.py   # orchestrator (mirrors discover_butchers.py / discover_awards.py CLI)
```

Refactor targets to share, not fork:

- Promote the FB scrape in `enrich.py:scrape_facebook_likes()` and
  `scripts/augment_butcher_facebook.py:scrape_facebook_followers()` into one
  shared `fb_engagement.scrape_fb_page(url) -> dict` that returns the **full**
  engagement dict (likes + talking_about + recency + comments + reactions +
  preorder). Have `enrich.py` step 3 call it so `follower_count` math is
  unchanged but the engagement columns flow into the main pipeline too. This is
  the one genuinely new piece of infra this engine requires.
- Reuse the Engine 03 text-signal regex bank for `PREORDER_RE` / `SPECIALS_RE`
  (don't duplicate the regex).
- Reuse `dedupe_existing.py`, `reclassify.py`, `detect_clubs.py` as-is on the
  CSV outputs.

`config.py` knobs to add: `FB_NATIVE_QUERIES`, `FB_SCORE_WEIGHTS` (the
step-5 map), `FB_SCORE_TIER_THRESHOLDS`, `FB_FRESHNESS_DAYS`.

## Open questions

1. Can the public-FB HTML reliably yield per-post comment/reaction counts and
   "talking about this" at scale, or do we need an Apify Facebook page/posts
   actor (none is wired in `config.py` today) — and what's its per-page cost vs.
   the free `curl_cffi` path?
2. What's the right normalization base for `fb_eng_rate` — followers,
   talking_about, or a fixed floor — given that small-town shops with 800
   followers and 30 comments/post should outrank a 15k-follower dead page?
3. Should `fb_preorder_thread=1` split into its own higher-priority list
   (mirroring Engine 01's existing-club transition), since a recurring preorder
   thread is both ICP fit *and* a clean platform-switch trigger?
4. Do the engagement columns feed the SHAP model as a new FB-engagement feature
   (the IG-only feature set demonstrably misses this cohort), or stay a
   qualification overlay that never touches `config.SCORING_WEIGHTS`?
