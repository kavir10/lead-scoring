# Lead Engine 49 — Static Social, Strong Offline Demand Rescue List

**Motion:** Hybrid (a Curation rescue overlay that re-qualifies on non-social Trigger evidence)
**Vertical fit:** Old-school premium operators — butcher, wine, cheese, market/deli, destination-town restaurants (the verticals where Facebook beats IG and the owner barely posts)
**Suggested list name(s):** `static_social_offline_demand`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run (rides existing enriched corpus + press/reviews/availability hooks; net-new cost is a Serper Web pass + a Claude classify)

## Premise

Our SHAP model leans on social and engagement features — Avg Video Views, Follower Count, Avg Shares, Avg Likes all rank in the top half — and our discovery floors quietly assume a business that markets itself online. That assumption systematically penalizes a specific, *high-AGMV* cohort: the old-school premium operator. A third-generation butcher with whole-animal sourcing, a wine shop run by a working sommelier, a cheesemonger with a 30-year reputation — these brands are often nearly silent on Instagram (static feed, a post a month, no reels) while commanding intense **offline** demand. The ICP cheat-sheet is explicit: static-only social *understates* brand, and must never be a disqualifier.

The fix is to re-qualify these operators on the demand signals that *don't* live on a social feed: press and editorial coverage, review-text sentiment, reservation difficulty, sold-out language, Reddit / local-forum mentions, regional best-of recognition, and operating longevity (domain age, "since 19xx" copy). Each of these is a public expression of the demand-over-capacity thesis that the social metrics are too thin to capture. This is the highest-leverage rescue: the partner types most prone to static social — butcher ($75.9k Peak AGMV), wine ($68.2k), cheese ($63.8k), market/deli ($48.7k) — are exactly the top performers we most want to invest in.

In the two-score model this is a **Hybrid**: ICP Fit is established by partner type + offline reputation, and the **Trigger** is supplied by whichever offline-demand signal is freshest (recent press, an angry "I drove an hour and they were sold out" review, a no-availability reservation week). High offline-demand + thin social is the rescue cohort; we curate hard because a sleepy operator with thin social *and* thin offline signal is correctly low-ICP and should stay filtered.

## Recipe

This engine runs over rows that **already exist or already failed** our pipeline — it is a re-scoring overlay, not a discovery sweep. The input is the universe of leads that scored low primarily because of weak social metrics, plus niche-lane rows that never got social enrichment at all.

1. **Assemble the rescue candidate pool.** Union (a) the enriched corpus (`output/2_enriched_*.csv`) filtered to rows with **low social** (`follower_count` below the vertical median AND no reels/posts engagement, i.e. the "static social" flag), (b) C/D-tier rows from prior `score.py` runs whose score was dragged down by the social-weighted features, and (c) niche-lane rows that skip social entirely (`butcher/1_discovered_butchers.csv`, `best_wine_shops/`, awards + directories masters). Dedupe with `dedupe_existing.py` (phone-first, then name+address). Tag each row `static_social = True` when IG/FB metrics are present-but-thin vs absent.

   ```
   static_social = (
       (follower_count < vertical_median_followers)
       AND (avg_video_views in (0, null) OR posts_30d <= 1)
   ) OR (social_metrics_absent AND partner_type in FIT_VERTICALS)
   ```

2. **Confirm ICP Fit independent of social.** Run `reclassify.py` (`partner_type` / `business_type_v2` + wine-bar claw-back) so qualification rests on partner type, not follower count. Restrict to `FIT_VERTICALS = {butcher, wine, cheese, market_deli, specialty_grocer, destination_restaurant}`. Carry `has_club` from `detect_clubs.py` (existing club = positive platform-switch signal). This step is what lets us safely *ignore* the thin social — we have an ICP anchor that doesn't depend on it.

3. **Score press / editorial coverage (Serper Web, reuse step-4).** Run the `enrich.py` **step-4 press** path (Serper Web against food-media domains + award keywords) for any candidate that lacks it. Old-school operators over-index on press relative to social — a butcher with a NYT/Eater/local-magazine writeup and a dead IG is the canonical rescue. Also fold in awards-master / directories-master membership (`awards_all_*.csv`, `directories_all_*.csv`) as recognition evidence.

4. **Mine review text for offline-demand sentiment (reuse step-5).** Run the **step-5 reviews** path (Apify Google-Maps-Reviews, batched) and mine the *text*, not just the rating, for offline-demand language. The reviews are where a static-social operator's true brand lives. Regex seed bank (case-insensitive), fed to the Claude classifier in step 7:

   - **Travel-for-it / destination pull:** `drove (an hour|\d+ (miles|hours))`, `worth the (drive|trip)`, `came from (out of town|another state)`, `make the trip`, `pilgrimage`
   - **Scarcity / sold-out:** `sold out`, `get there early`, `gone by (noon|\d+ ?(am|pm))`, `line out the door`, `had to wait`, `always (busy|packed|a line)`
   - **Longevity / institution:** `been coming for \d+ years`, `since I was a kid`, `institution`, `family[\s-]?run`, `\d+ generations?`, `old[\s-]?school`, `the real deal`
   - **Best-in-region:** `best (butcher|wine shop|cheese|bakery) in (town|the city|\w+)`, `only place`, `nowhere else`, `nothing like it`

5. **Mine Reddit / local-forum mentions (Serper Web, new query lane).** Add a Serper Web query lane targeting community discussion: `site:reddit.com "<business name>" <city>` plus generic best-of threads (`reddit best butcher <city>`, `<city> where to buy <vertical>`). Locals recommend old-school operators in forums far more than those operators self-promote on IG. This is genuinely new query infra — a thin extension of the existing Serper Web client in the press step, scoped to reddit + forum domains. Pass hits to the Claude classifier for relevance + a quotable snippet.

6. **Check reservation difficulty / longevity (reuse step-8 + crawl).** For the destination-restaurant sub-cohort, run the **step-8 availability** probe (OpenTable via Apify + Resy API) — a fully-booked old-school spot with a static feed is a textbook rescue. For all rows, capture **domain age** (already a SHAP feature; reuse the step-1 website crawl) and scan site copy for "since 19xx / established / family-owned for N generations" longevity language. Longevity is a durable offline-ICP tell that social can't show.

7. **Classify + synthesize the offline-demand case (Claude, cheap pass).** Send matched press snippets, review quotes, reddit threads, and longevity copy to Claude (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to (a) confirm each signal is real demand pressure vs boilerplate/negation, (b) label `offline_signal_types`, and (c) emit a one-line `trigger_summary` sales can quote ("Eater calls it 'the best dry-age in the state' — and they have 11 IG posts total"). Prefix the script with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

8. **Compute offline-demand strength + qualify.** The whole point is that low social cannot demote here; offline strength is the qualifier.

   ```
   DISQUALIFY (anti-ICP, upstream of strength):
     partner_type == liquor_store, or wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Josh, Cupcake, Meiomi, Duckhorn, ...)
         or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag (reclassify claw-back)
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery
     # NOTE: thin social NEVER demotes in this engine — it is the entry criterion

   offline_strength:
     +3 recent (<12mo) press in a recognized food-media domain
     +3 verified reservation scarcity (Resy/OpenTable zero availability)  # dest-restaurant
     +2 multiple review-text demand hits (travel-for-it / sold-out / institution)
     +2 awards-master OR directories-master membership (recognition)
     +2 multiple organic reddit/local-forum recommendations
     +1 domain_age >= 10 years OR "since 19xx / N generations" longevity copy
     +1 if has_club == True (proven recurring demand)

   QUALIFY (engine output) if:
     static_social == True AND partner_type in FIT_VERTICALS
     AND not anti_icp AND offline_strength >= 4
   ```

9. **Hand off.** Emit the canonical CSV (below). `score.py` may run for a reference `icp_fit_score`, but do **not** treat its social-weighted score as a gate and do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). `offline_strength` orders the outbound queue inside a tier. The verified-reservation slice can feed `reservation_difficulty` as additional input where the row reaches phase 8.

## Output schema

```
output/offline_demand/static_social_offline_demand_<YYYYMMDD>.csv
source = "static_social_offline_demand"
tier = <1|2|3>     # 1 = FIT vertical + offline_strength>=6 (press OR verified-res + corroboration); 2 = strength 4-5; 3 = soft
business_type = butcher | wine_store | cheese | restaurant | market_deli | specialty_grocer
distinction = "Strong offline demand, quiet on social: {offline_summary}"
year = <discovery_year>
source_url = <best evidence url — press article, top review thread, or reddit thread>
blurb = <one-line: "30-yr institution, Eater-rated, books out 2 weeks — 9 IG posts total">
+ evidence cols (preserve so sales can cite the trigger in outbound):
    static_social           # bool — entry criterion; the rescue flag
    follower_count          # context only, NOT a gate
    avg_video_views, posts_30d   # context only — documents the social silence
    offline_signal_types    # press | review_demand | reddit | reservation_scarcity | longevity | awards
    offline_strength        # int, intra-tier outbound ordering
    press_count, press_top_url, press_top_domain
    review_demand_hits      # count of demand-language review matches
    review_demand_quote     # verbatim review snippet for outbound
    reddit_mentions, reddit_top_url
    rt_availability_zero    # bool — Resy/OpenTable showed no availability (restaurants)
    domain_age_years, longevity_claim   # "since 1962" / "3 generations"
    in_awards_master, in_directories_master
    trigger_summary         # one-line Claude-written outbound hook
    has_club, partner_type
    scan_date
```

Per-run master union: `output/offline_demand/static_social_offline_demand_all_<YYYYMMDD>.csv`.

## Volume & cost

This is a rescue overlay, so most rows already exist in our corpus — the value is *re-qualifying* leads the social-weighted model buried.

- Rescue candidate pool (static-social + low-tier + niche-lane rows), deduped: **~6–9K rows**.
- Press pass (Serper Web) only for rows missing it (~50%, ≈3.5K) × ~5 queries × ~$0.001 ≈ **$15–18**. (Serper Web is the main cost.)
- Reddit/forum query lane: ~2 queries × ~3.5K candidates × ~$0.001 ≈ **$5–7**, but gate to FIT-vertical rows that already cleared step 2 to cut this to **~$3–4**.
- Review-text mining via Apify Google-Maps-Reviews: only for FIT-vertical candidates missing reviews enrichment (~1.5K) ≈ **$4–6**.
- Reservation probe (Resy/OpenTable) on the destination-restaurant subset only (~few hundred) ≈ **$1–2**.
- Claude Haiku classify pass on matched snippets (~2.5K rows, short prompts) ≈ **$2–4**.
- **Per-run total: ~$25–30.**
- **Net-new qualified leads per run:** of ~6–9K screened, expect **~600–1,000** to clear `offline_strength >= 4` + ICP fit. A large share are *resurrected* leads (previously C/D tier) rather than literally net-new — the value is converting "filtered out on weak social" into "qualified on offline demand," which is leads the standard model would never have surfaced for outbound.

## Refresh cadence

**Monthly**, with the press + review slices driving cadence. Offline reputation is durable (longevity, awards, institution status move slowly — a quarterly re-scan of those would suffice), but the *trigger* half decays: a fresh press hit or a recent "drove an hour, sold out" review is a live outbound reason that's stale in a few months. A monthly pass keeps the trigger current without re-running press/reviews enrichment on the whole corpus. Run a heavier pass after major regional best-of / awards cycles publish.

## Risks

- **Static-social understates brand — the core thesis.** Do **not** let thin `follower_count` / zero `avg_video_views` demote a row; they are the *entry* criterion here, context columns only. Flag any code path that reintroduces a social floor as a gate — it collapses the engine back to standard scoring.
- **Genuinely dead businesses.** Thin social + thin offline signal is correctly low-ICP. The `offline_strength >= 4` floor is what separates "quiet but beloved" from "quiet because no one cares." Don't relax it to chase volume.
- **Liquor-store / chain leakage.** An old liquor store can have longevity copy ("since 1948") and local reddit mentions yet be pure commodity. Keep `config.CHAIN_KEYWORDS`, the wine commodity-SKU list, and ESP red flags (City Hive, Spot Hopper) upstream of `offline_strength`. Respected-importer signals (Skurnik, Louis/Dressner, Jenny & Francois, Zev Rovine, Selection Massale, Vom Boden, etc.) on the site are a positive curated-wine tell.
- **Wine-bar exclusion.** Wine bars are mostly excluded — let `reclassify.py`'s claw-back handle the geographic-monopoly exception; don't blanket-rescue them on offline buzz.
- **Sweets-only demotion.** A beloved old single-product bakery is still capped at Tier 2 per the sweets-only rule, even with strong press and longevity.
- **Small-market metrics run low.** Many rescue targets sit in small markets; press and reddit volume are structurally thin there. Weight *relative* recognition (regional best-of, "only place in town") over national press count, and never DQ for low absolute volume.
- **Review-text false positives / negation.** "Used to be the best, now sold out of standards" or sarcasm are false matches. The Claude pass must handle negation/sarcasm that regex cannot; require corroboration (≥2 hits or press + review) before a hard trigger.
- **Reddit relevance & name collisions.** Common business names ("The Market", "Corner Butcher") collide across cities; require city co-occurrence in the thread and a Claude relevance check before counting a mention.
- **Resy/OpenTable fragility.** The Resy client is reverse-engineered and rate-limits; treat verified zero-availability as a bonus hard signal, not a gate — fall back to press + review + reddit when the probe fails.
- **Domain-age noise.** A recently re-platformed site can show a young domain for an old business; treat `domain_age` as supporting (+1), never as a primary qualifier, and prefer explicit "since 19xx" copy where present.

## Repo placement

A new top-level package mirroring the niche-lane orchestrator shape, reusing the `enrich.py` press/reviews/availability steps and `reclassify.py` / `detect_clubs.py` as libraries rather than forking them.

```
offline_demand/
  __init__.py            # FIT_VERTICALS, offline_strength weights, static_social rule
  candidates.py          # builds rescue pool: static-social filter + low-tier + niche-lane union, dedupe
  press.py               # wraps enrich.py step-4 Serper Web press path (food-media domains + awards kw)
  reddit.py              # NEW Serper Web query lane (site:reddit.com + forum best-of threads)
  reviews_demand.py      # wraps enrich.py step-5 Apify reviews; offline-demand regex bank over review text
  availability.py        # wraps enrich.py step-8 Resy/OpenTable for the restaurant subset
  longevity.py           # domain-age + "since 19xx / N generations" copy scan over step-1 crawl output
  classify.py            # Claude haiku-4-5: confirm demand-pressure, label signal types, trigger_summary, negation/relevance
  aggregate.py           # ICP gate (reclassify + detect_clubs join), offline_strength, dedupe
  finalize.py            # canonical schema writer, date-stamped output + master union
discover_offline_demand.py   # orchestrator (mirrors discover_awards.py / discover_butchers.py CLI shape)
```

Refactor targets to share, not fork:

- Expose the `enrich.py` **step-4 press**, **step-5 reviews** (incl. review-text mining), and **step-8 availability** functions as importable libs (`enrich_press_lib`, `enrich_reviews_lib`, `enrich_availability_lib`) so this engine reuses one implementation instead of shelling out to the full enrich pipeline. The step-8 lib is the same shared-lib argument Engines 03/05/10 raise.
- Reuse Engine 03's scarcity/offline text-signal regex bank (`triggers/_text_signals.py`) for the sold-out review language; add only the travel-for-it / longevity / best-in-region patterns this engine introduces.
- The Reddit/forum Serper Web query lane is the one genuinely new piece of infra — a thin extension of the existing Serper Web client scoped to reddit + forum domains.

## Open questions

1. **Static-social threshold.** What's the right cut for "thin social" per vertical — a fixed percentile of `follower_count` below the vertical median, an absolute floor (e.g. <2K followers, ≤1 post/30d), or an engagement-presence test (zero `avg_video_views`)? Mis-set, it either under-rescues real institutions or floods the pool with genuinely inactive businesses.
2. **Corroboration bar.** Is a single strong signal (one major press hit) enough to qualify, or do we require ≥2 independent offline signals (press + review, or reddit + longevity) to suppress false positives? This directly sets the `offline_strength` floor.
3. **Reddit lane ROI.** Does the reddit/forum query lane add enough net qualifications to justify its Serper Web cost and name-collision noise, or should it be a tier-1 *promotion* signal applied only to rows already qualified on press + reviews?
4. **Overlap with the live pipeline.** Should this engine write a `rescue_score` back onto the source rows so the main scoring run can flag "buried by social weighting," or stay a fully separate list to avoid any interaction with `config.SCORING_WEIGHTS`?
