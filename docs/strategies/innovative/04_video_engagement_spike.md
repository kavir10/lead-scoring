# Lead Engine 04 — Video Engagement Spike List

**Motion:** Curation
**Vertical fit:** Destination + neighborhood restaurants, bakeries, butchers, wine shops (any operator whose product breaks down well on camera)
**Suggested list name(s):** `video_engagement_spike`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $35/run (Apify reel + post actors over a pre-filtered candidate set)

## Premise

The SHAP model is loud here: **Avg Video Views is the #3 predictor of Peak
AGMV and Avg Shares is #9** — both rank above raw Follower Count, which sits
mid-table. The engagement hierarchy is video views > shares/saves > comments
> likes; follower count is a separate, weaker signal. So a business whose
reels materially *outperform their own audience size and history* is showing
exactly the property the model rewards: an audience that watches, saves, and
re-circulates the product, not just a vanity follower number.

This is a pure **Trigger** engine layered on the ICP-Fit our pipeline already
scores. The trigger is a recent video breakout: a butcher's whole-animal
breakdown, a bakery's Friday-drop reel, a sommelier's wine-pick, a tasting-menu
walkthrough — that pulls views >> follower count and views >> the account's own
median, especially when the comments fill with **buying intent** ("how do I
order", "do you ship", "when's the next drop", "where can I get this"). That
comment pattern is latent demand the operator currently can't capture — which
is the demand-over-capacity thesis and the exact gap a Table22 subscription
program closes. High-ICP + this trigger = top of the call list; weak-ICP with a
viral fluke gets filtered before sales.

## Recipe

This engine **reuses `enrich.py` step 6 (reels) and step 7 (posts) wholesale**
— it is not a new scraping primitive, it's a new *selection* layer plus a
breakout-detection score on top of data we already pay to collect. Run it as a
postprocessing overlay on an existing enriched/scored CSV (CSV-in / CSV-out,
like `detect_clubs.py`), not a fresh discovery crawl.

1. **Seed the candidate set, don't re-discover.** Start from the most recent
   `output/2_enriched_posts.csv` (steps 1-7 already run) or any scored
   `custom-serper-scoring_*_all.csv`. Require a resolved IG handle and
   `follower_count` already populated (IG + FB from `enrich_facebook()`). This
   keeps Apify spend bounded to known-ICP operators.

2. **Pull recent reels + posts** via the same Apify actors `enrich.py` uses
   (`instagram-reel-scraper`, `instagram-post-scraper`), batched in groups of
   30 handles. Grab the last ~20 reels and last ~30 posts per handle with
   per-item `videoViewCount`, `shares`, `saves`/`reshareCount` where exposed,
   `likes`, `commentsCount`, `timestamp`, and the top N comment texts.

3. **Establish each account's own baseline.** From the last ~20 video items
   compute `median_views`, `median_shares`, `median_saves`. Define "recent" as
   items within the last 30 days; "spike window" is the recent subset.

4. **Compute the breakout signals:**

```
views_to_follower   = best_recent_reel_views / max(follower_count, 1)
views_vs_median     = best_recent_reel_views / max(median_views, 1)
share_rate          = recent_shares / max(recent_views, 1)
save_rate           = recent_saves  / max(recent_views, 1)
buy_intent_hits     = count of recent comments matching BUY_INTENT_PATTERNS
prep_video_flag     = any recent reel caption/cover matches PREP_PATTERNS
```

5. **Mine comments for buying intent** with a cheap regex pass first (no LLM
   needed for the gate), then optionally confirm ambiguous hits with
   `claude-haiku-4-5-20251001` the same way `scrape_beli` mines captions
   (remember the `unset ANTHROPIC_API_KEY &&` prefix). Seed patterns:

   - `BUY_INTENT_PATTERNS` (regex, case-insensitive): `do you ship`,
     `can i (order|buy|get)`, `how (do|can) i (order|buy|get)`, `where can i`,
     `next drop`, `when('?s| is) the next`, `pre[- ]?order`, `do you deliver`,
     `restock`, `wholesale`, `is this available`, `shipping`.
   - `PREP_PATTERNS` (caption/hashtag): `breakdown`, `whole animal`,
     `nose to tail`, `dry[- ]?age`, `charcuterie`, `bake`, `drop`,
     `proof`, `lamination`, `tasting menu`, `wine pick`, `somm`, `cellar`,
     `behind the (pass|counter)`.

6. **Score the trigger** (this is the engine's promotion gate, *not* a change
   to `config.SCORING_WEIGHTS`):

```
spike = (
    views_to_follower >= 3.0          # video out-reaches the audience
    and views_vs_median >= 2.5        # breakout vs the account's own history
    and recent_views >= 5000          # absolute floor; kills micro-account noise
)
demand = (buy_intent_hits >= 3) or (share_rate >= 0.02) or (save_rate >= 0.03)

if spike and demand and prep_video_flag:  tier = 1   # product video + breakout + intent
elif spike and demand:                     tier = 2
elif spike:                                tier = 3   # breakout, weak intent -> nurture
else: drop
```

7. **Small-market adjustment.** For operators in non-top-30 metros (use
   `config.CITIES` rank / market size), relax the absolute floor to
   `recent_views >= 1500` and lean on `views_to_follower` + `views_vs_median`,
   which are scale-free. Static-only social understates small-market brand —
   don't DQ on raw volume.

8. **Stamp the trigger onto the ICP score, not into it.** Emit the canonical
   evidence CSV below; this engine annotates rows so the existing `score.py`
   output (Avg Video Views / Avg Shares weights) stays the source of truth for
   ICP Fit. The spike score is the *contact-now* overlay.

## Output schema

```
output/social_signals/video_engagement_spike_<YYYYMMDD>.csv
source = "video_engagement_spike"
tier = <1|2|3>
business_type = <restaurant|bakery|butcher|wine|...>   # carried from input row
distinction = "Reel breakout: {best_views} views ({views_to_follower}x followers, {views_vs_median}x median), {buy_intent_hits} buy-intent comments"
year = <YYYY of spike window>
+ evidence cols:
    ig_handle, follower_count,
    best_recent_reel_url, best_recent_reel_views, best_recent_reel_date,
    median_views, views_to_follower, views_vs_median,
    recent_shares, share_rate, recent_saves, save_rate,
    buy_intent_hits, buy_intent_samples,   # 1-3 verbatim comments for outbound
    prep_video_flag, prep_video_type,      # breakdown|drop|bake|tasting|wine_pick
    spike_score, scan_date
```

`buy_intent_samples` preserves verbatim comment text so a BDR can quote the
exact "do you ship?" in the first outbound line. That cite-the-trigger evidence
is the whole point of a Curation list.

## Volume & cost

Overlay on a known set, so spend is bounded by candidate count, not a fresh
crawl:

- Candidate pool from one enriched run with a valid IG handle: ~3,000-5,000.
- Reel scrape (~20 items/handle) + post scrape (~30 items/handle) at Apify IG
  rates ≈ $0.004-0.006 per handle combined. 4,000 × $0.005 ≈ **$20**.
- Comment-intent regex is free; optional Haiku confirmation on the ~10-15% of
  ambiguous buy-intent hits ≈ **$3-5**.
- **Per-run total: ~$25-30.**
- **Net-new / re-surfaced leads per run: ~120-300 spike-positive operators**,
  of which ~40-80 hit Tier 1 (breakout + intent + product video). Many will
  already be in the universe — the value is the *fresh trigger stamp*, which
  moves a dormant high-ICP row to the top of the call queue.

## Refresh cadence

**Bi-weekly.** A video breakout is perishable — the "do you ship?" comment wave
decays within days, and the outbound line lands hardest while the reel is still
circulating. Bi-weekly keeps the spike window (last 30 days) fresh without
re-burning Apify on accounts that haven't posted. Re-scrape only handles with a
new post since last run.

## Risks

- **Apify IG rate-limits / anti-bot.** Same fragility as `enrich.py` steps 6-7;
  expect partial coverage. Mitigation: batch of 30, retry the misses in a second
  pass, never block the whole run on one batch.
- **One-hit viral fluke ≠ ICP.** A pizza-first spot or a chain location can pop
  off once. Gate hard on ICP Fit *before* this overlay — run only over rows that
  already passed discovery quality floors and chain filtering
  (`config.CHAIN_KEYWORDS`). High-trigger / weak-ICP must be filtered, not sold.
- **Sweets-only demotion.** A bakery whose breakout is a pure dessert/single-SKU
  drop is still capped at Tier 2 per ICP rules (single-product heavy demotion,
  not DQ). Carry the input row's `partner_type` and apply the cap; don't let a
  viral cinnamon-roll reel mint a Tier 1.
- **Liquor-store / wine-bar leakage.** A wine *spike* on a liquor store or an
  excluded wine bar should not promote. Respect upstream `reclassify.py` /
  wine-bar claw-back; don't re-admit DQ'd partner types on video strength alone.
- **Static-vs-video mismatch.** Follower count can be low while video reach is
  high — that's the *signal*, not a defect. Do not let a low-follower /
  low-likes flag suppress a genuine views breakout. Conversely, high likes +
  flat views is the low-engagement trap; weight views and shares, never likes.
- **Comment-intent false positives.** Sarcasm, bots, and tagging-a-friend
  ("@dave we NEED this") inflate `buy_intent_hits`. Keep the Haiku confirmation
  pass for borderline rows; require ≥3 distinct authors, not 3 comments.
- **Butcher/deli/grocer FB blind spot.** For these verticals Facebook
  engagement often beats IG, and FB video views aren't in the IG actors. This
  engine will undercount them. Flag as a known gap (see Open questions).

## Repo placement

```
social_signals/
  __init__.py
  fetch_video_signals.py      # batches handles through instagram-reel-scraper
                              # + instagram-post-scraper (wraps enrich.py 6/7)
  detect_spike.py             # baseline + breakout math, comment-intent regex,
                              # optional Haiku confirmation
  finalize.py                 # emits canonical CSV with evidence cols
discover_video_spike.py       # orchestrator, mirrors discover_awards.py shape;
                              # takes --input <enriched_or_scored.csv>, --resume
```

Refactor target: lift the reel/post pull bodies out of `enrich.py` steps 6-7
into a small shared lib (e.g. `enrich_ig_lib.py`) so both `enrich.py` and
`social_signals/fetch_video_signals.py` call one Apify-actor wrapper instead of
duplicating actor IDs, batching, and retry logic. This mirrors the
`enrich.py` step 8 → `_availability_lib.py` refactor proposed for Engine 05.

## Open questions

1. Do the Apify IG reel/post actors reliably expose `shares` and `saves`, or
   only `videoViewCount` + `likes` + `commentsCount`? If saves/shares are
   sparse, `share_rate`/`save_rate` degrade to a views-only gate — acceptable,
   but worth confirming on a 30-handle probe before committing thresholds.
2. Is a 30-day spike window the right horizon, or should "recent" track the
   account's own posting cadence (e.g. last 10 posts) so low-frequency posters
   aren't penalized for a quiet month?
3. How do we capture the **butcher/deli/grocer FB-video** breakout that IG
   actors miss? Does any current FB scraping path (the `enrich_facebook()` HTML
   scrape) surface FB Reel view counts, or is this a genuinely new source lane?
4. Should a spike auto-elevate the BDR priority on an *existing* T22-adjacent
   row, or only mint net-new leads? The cite-the-trigger value argues for
   stamping both.
