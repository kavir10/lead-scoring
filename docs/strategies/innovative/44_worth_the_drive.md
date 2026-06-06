# Lead Engine 44 — Worth-the-Drive List

**Motion:** Curation (with a Trigger overlay — the destination language is the trigger)
**Vertical fit:** Butchers, bakeries, cheese, wine, destination-town restaurants (shippable / preorderable product + travel-friction product)
**Suggested list name(s):** `worth_the_drive`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (rides the step-5 Google Maps Reviews pull + step-6/7 IG comment actors over a pre-filtered set; net-new cost is a Haiku classify pass)

## Premise

Demand-over-capacity is the dominant ICP pattern, and the most overlooked form
of it is **demand that survives inconvenience**. When customers write "worth
the drive," "drove an hour for this," "the only place I'll buy beef," "we
detour every time we're upstate," they are documenting a brand whose pull
already exceeds its geographic reach. The product is destination-grade; the
location is the only thing standing between the operator and more revenue. That
is the cleanest possible Table22 setup: a subscription / preorder / ship layer
removes the travel friction **without diluting the brand value** — the
customer keeps the product they drive for, minus the drive.

This is distinct from raw scarcity (Engine 16's "couldn't buy") and from
out-of-market begging (Engine 14's "please ship to my city"). Worth-the-drive
is a *loyalty-under-friction* signal: the customer already made the trip and is
publicly endorsing the trade. It correlates with **ICP Fit** because only a
genuinely differentiated, premium product earns a multi-hour pilgrimage —
exactly the whole-animal butcher, the cult bakery, the destination cheesemonger,
the small-town wine shop with an owner-somm reputation. It is strongest in the
high-AGMV-x-headroom verticals (butcher $75.9k, wine $68.2k, cheese $63.8k) and
in **destination-town restaurants** whose customers are tourists or
day-trippers who'd happily prepay for a return box, a frozen line, or a
standing preorder.

On the two-score model this is a high-conviction **Trigger** that rides on top
of the **ICP Fit** the pipeline already scores. The outbound hook writes
itself: "your customers are publicly saying you're worth the drive — let them
keep buying without it."

## Recipe

A **trigger-overlay** engine, CSV-in / CSV-out like `detect_clubs.py`. It does
not re-discover; it scans an existing enriched / scored universe across three
text surfaces (Google reviews, IG comments, public food forums) for
destination-despite-distance language and emits the matches with verbatim
quotes. The new primitive versus Engines 14/16 is a **travel-distance + brand
loyalty classifier** and an optional **forum lane**.

1. **Seed the universe, don't re-discover.** Start from the latest
   `output/2_enriched_reviews.csv` / `output/2_enriched_posts.csv` and any
   `custom-serper-scoring_*_all.csv`, plus the niche masters (`butcher/`,
   `best_wine_shops/`, awards & directories masters). Require a resolvable
   `place_id` (for reviews) and/or an IG handle (for comments), and a known
   operator home metro from `city`/`state`. Bias toward **non-metro and
   destination-town** rows — a worth-the-drive endorsement means far more for a
   shop two hours from a city than for one in a dense urban core where nobody
   drives far. Seed any net-new geography from `research/trendy_neighborhoods/`
   plus rural/destination-town queries through Serper Maps (`discover.py`).

2. **Pull text from three surfaces (reuse existing actors).**
   - **Reviews** — reuse the `Google-Maps-Reviews` Apify actor `enrich.py`
     step 5 drives (batched the same way), newest-first, keep `stars` +
     `reviewDate`. Worth-the-drive language concentrates in **4–5★** reviews
     (the opposite slice from Engine 16), so scan the high-star slice here.
   - **IG / FB comments** — reuse the `instagram-post-scraper` /
     `instagram-reel-scraper` actors (`enrich.py` steps 6–7), batches of 30
     handles, top-N comments per recent post. Butcher / deli / specialty-grocer
     loyalty skews to **Facebook**, so also scan FB comment text from the
     step-3 (`facebook`) surface where available.
   - **Forums (new lane, optional)** — Serper Web (`google.serper.dev/search`,
     the same primitive the press step uses) against forum/community domains
     for the operator name + travel language: `reddit.com`, `chowhound`-style
     archives, `seriouseats.com/community`, local subreddits
     (`r/<city>`, `r/food`, `r/Cooking`, `r/steak`, `r/Charcuterie`,
     `r/winemaking`, `r/cheesemaking`). This catches the "best X within 100
     miles?" recommendation threads that never touch the operator's own pages.

3. **Regex gate for worth-the-drive language** (cheap, runs first, no LLM),
   counting *distinct authors* per business. A trailing capture group harvests
   a stated travel distance/time where present:

```
WORTH_THE_DRIVE = (
  r"worth\s*the\s*(drive|trip|detour|trek|wait|hour)",
  r"(drove|drive|driving|travel(ed)?)\s*(over\s*)?(\d+\+?)\s*(hour|hr|min|minute|mile)",
  r"(\d+\+?)\s*(hour|hr|mile)s?\s*(each\s*way|round\s*trip|drive|away)",
  r"(an?\s*hour|two\s*hours?|all\s*the\s*way)\s*(for|to\s*get)",
  r"(every\s*time|whenever)\s*(we'?re|i'?m|we\s*go)\s*(in|up|out|near|through|to)\s*[A-Z][\w.\- ]+",
  r"(make|made)\s*(the|a)\s*(special\s*)?(trip|detour|pilgrimage)",
  r"the\s*only\s*place\s*(i|we)('?ll|\s*will|\s*buy|\s*go)",
  r"we\s*(stop|always\s*stop|detour|go\s*out\s*of\s*our\s*way)",
  r"out\s*of\s*the\s*way\s*but",
  r"destination\s*(bakery|butcher|shop|spot|restaurant)",
  r"plan\s*(our|a)\s*(trip|day)\s*around",
)
```

4. **Classify distance + loyalty intent (Claude, cheap pass — load-bearing).**
   Send matched snippets to `claude-haiku-4-5-20251001` (the model
   `scrape_beli` / `awards/llm_extract.py` use; prefix the script with
   `unset ANTHROPIC_API_KEY &&` for the empty-key shell gotcha) to (a) confirm
   the snippet describes a *deliberate trip for this product*, not a passing
   "it was on our drive" or sarcasm; (b) extract a normalized `travel_minutes`
   / `travel_miles` when stated; (c) judge `repeat_intent` (one-off vs "every
   time"); (d) emit a one-line `trigger_summary` a BDR can quote.

5. **Score the worth-the-drive strength.** Distance and repetition are the
   load-bearing dimensions — a chronic, multi-author, long-distance pilgrimage
   is the bullseye:

```
wtd_authors    = DISTINCT authors with a confirmed worth-the-drive snippet (across all surfaces)
max_travel_min = max stated one-way travel time across snippets (LLM-normalized)
repeat_hits    = #authors expressing recurring/"every time" travel
surfaces       = #distinct surfaces hit (review | ig/fb | forum)
recency_days   = days since most-recent confirmed snippet

wtd_strength =
    +3 if wtd_authors >= 3
    +2 if max_travel_min >= 60                 # hour-plus pilgrimage
    +2 if repeat_hits >= 2                       # recurring, not a one-off
    +1 if surfaces >= 2                          # corroborated across surfaces
    +1 if recency_days <= 180                    # still a live reputation
    +1 if forum recommendation thread present    # third-party endorsement
trigger_tier = 1 if wtd_strength>=6 else 2 if wtd_strength>=4 else 3
```

6. **Apply the ICP gate + qualify.** Run `reclassify.py` (`partner_type` /
   `business_type_v2`, wine-bar claw-back) and carry `has_club` from
   `detect_clubs.py` (existing club = positive platform-switch signal, not a
   DQ). Hard-filter leakage before scoring:

```
DISQUALIFY if:
  partner_type == liquor_store, or wine commodity-SKU leak (Tito's, Smirnoff,
      Veuve, BuzzBallz, Barefoot, Yellowtail, Josh, Cupcake, Kendall Jackson,
      Meiomi, Apothic, ...) or ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery        # demand real, headroom capped
  static-social-only / thin metrics, small market (never DQ — understates brand)
```

7. **Hand off to scoring.** Emit the canonical CSV (below) and run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   worth-the-drive columns ride as evidence; `wtd_strength` orders the outbound
   queue inside a tier. **Final list = passes ICP gate AND `wtd_strength >= 4`.**
   High-strength / weak-ICP routes to nurture, never straight to sales. Verbatim
   snippets and stated distances are preserved so a BDR can open with the exact
   "your customers drive 90 minutes for this" line.

## Output schema

```
output/demand_signals/worth_the_drive_<YYYYMMDD>.csv
source = "worth_the_drive"
tier = <1|2|3>     # 1 = butcher/wine/cheese + long-distance multi-author recurring; 2 = single-surface/single-cluster; 3 = ICP-soft
business_type = butcher | wine_store | cheese | bakery | restaurant
distinction = "Customers say it's worth the drive: {wtd_authors} fans travel up to {max_travel_min}min for this — remove the drive w/ a Table22 club"
year = <YYYY of most-recent confirmed snippet>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    wtd_strength             # int, intra-tier outbound ordering
    wtd_authors              # distinct authors with confirmed worth-the-drive snippet
    max_travel_min           # max LLM-normalized one-way travel time stated
    repeat_hits              # authors expressing recurring/"every time" travel
    surfaces                 # #distinct surfaces (review|ig/fb|forum)
    surface_breakdown        # e.g. "review:3|forum:1|ig:0"
    recency_days             # days since most-recent confirmed snippet
    snippet_samples          # 1-3 verbatim quotes w/ source surface (outbound hooks)
    forum_thread_url         # link to a "best X within N miles" thread if present
    review_url               # Google Maps review/place permalink
    trigger_summary          # one-line Haiku-written outbound hook
    home_metro               # operator metro (for "non-metro" weighting)
    has_club                 # carried from detect_clubs.py (positive signal)
    partner_type             # from reclassify.py
    icp_fit_score            # joined from score.py
```

## Volume & cost

Overlay on a known set, so spend is bounded by candidate count, not a fresh
crawl.

- Input universe (enriched + scored corpus + niche masters), deduped and scoped
  to worth-the-drive-fit verticals & non-metro bias: **~6–9K rows**, most with a
  cached `place_id` and/or IG handle.
- Review pull: most rows already ran step 5, so cached reviews are **free**.
  Net-new / stale refresh (~2–3K places × ~$0.005–0.008 for ~50 reviews) ≈
  **$12–18**.
- IG/FB comment scrape on the handle-bearing subset (reuses steps 6–7, view +
  comment pull) ≈ **$4–6**.
- Forum lane: Serper Web, ~1–2 queries per candidate name only for the
  high-promise residual (no IG/review hit yet) — a few thousand calls at Serper
  rates ≈ **$2–3**.
- Haiku classify over matched snippets only (~2–3K rows, short prompts) ≈
  **$2–3**.
- **Per-run total: ~$20–25** (lower with a warm review cache).
- **Net-new / re-surfaced qualified leads per run:** of ~7K screened, the
  worth-the-drive pattern surfaces for **~8–12%** (≈550–840); after ICP gate +
  Haiku confirm + `wtd_strength >= 4`, expect **~150–300 qualified rows**, of
  which ~40–80 hit Tier 1 (long-distance, multi-author, recurring,
  multi-surface). Most already exist in the corpus — the value is the
  *travel-friction trigger* that re-prioritizes a dormant high-ICP row.

## Refresh cadence

**Monthly to quarterly.** A worth-the-drive reputation is durable, not
perishable — unlike Engine 14's out-of-town comment waves, it accrues slowly
over years and the *recurrence* matters more than any single fresh quote. A
monthly pass refreshes `recency_days` and catches new forum threads cheaply;
quarterly is fine for stable rural lanes. Pull a heavier run pre-holiday and
pre-summer (destination-town traffic and "worth the drive for the holiday roast/
pie" language both spike), and only re-scrape places with new reviews/posts
since the last run.

## Risks

- **"On our way" ≠ "worth the drive."** A passing "we stopped on the way to
  the lake" is not a pilgrimage. The Haiku pass (step 4) must separate
  *deliberate trips for this product* from incidental stops and sarcasm
  ("worth the drive… NOT"); the regex gate alone over-counts.
- **Distance is self-reported and noisy.** "Drove forever," "miles away,"
  hyperbole, and missing distances are common. Treat `max_travel_min` as a
  bonus dimension, never a sole gate; require multi-author corroboration for
  Tier 1 rather than one effusive long-distance quote.
- **Liquor-store / chain leakage.** "Worth the drive" appears on liquor stores
  pushing commodity SKUs and on hyped multi-location chains. Run
  `config.CHAIN_KEYWORDS`, liquor-license, wine commodity-SKU, and City Hive /
  Spot Hopper ESP red-flag checks *upstream* of the strength score.
- **Wine-bar exclusion.** Wine bars mostly excluded (low Peak AGMV) except a
  geographic-monopoly case — and a wine bar can't ship a club anyway. Let the
  `reclassify.py` claw-back gate them.
- **Sweets-only demotion.** A cupcake-only shop people drive for is still
  single-product; cap at Tier 2, don't promote on the trigger alone.
- **Small-market metrics run low.** A rural butcher with a 100-mile catchment
  may have few total reviews and thin social, so absolute author counts
  understate the brand. Weight *relative local dominance*, stated distance, and
  recurrence over raw volume; **never DQ on thin metrics** — static-only social
  understates exactly these destination operators.
- **Urban false-negative / inverse bias.** A great urban shop nobody "drives"
  to is a true ICP miss for *this* engine, not a low-quality business — it
  should surface through other engines, not be penalized here. Keep the
  non-metro weighting as a prioritizer, not a hard filter.
- **Forum lane fragility & dedupe.** Reddit/forum results are noisy, may name
  the wrong location of a same-named business, and Serper Web throttles. Treat
  forum hits as corroboration (+1), require name+metro match before crediting,
  and checkpoint per batch.
- **Apify / IG / Maps rate-limit fragility.** Comment and review scraping at
  30-batch scale throttles; checkpoint per batch and support `--resume` like
  `detect_clubs.py`.

## Repo placement

Standalone package mirroring the niche-lane / Engine-16 shape, reusing the
step-5 reviews actor and step-6/7 comment actors as libraries, plus a Serper-Web
forum lane.

```
demand_signals/                  # co-houses Engine 16; shares ICP-gate + dedupe
  __init__.py                    # engine constants; registers worth-the-drive lexicon
  signals.py                     # WORTH_THE_DRIVE_REGEX, SKU/ESP leak lists, distance parser
  fetch_reviews.py               # wraps Google-Maps-Reviews actor (reuse step-5 batching),
                                 #   HIGH-star-biased pull, keeps stars + reviewDate
  fetch_comments.py              # wraps step-6/7 IG post/reel comment pull (+ step-3 FB surface)
  fetch_forums.py                # Serper Web over reddit/community domains for name + travel language
  mine_drive.py                  # regex gate over all surfaces; distinct-author counts; distance capture
  classify.py                    # Haiku 4.5: deliberate-trip vs incidental, travel_minutes, repeat_intent, trigger_summary
  aggregate.py                   # ICP gate (reclassify + detect_clubs join), wtd_strength, recency/recurrence, cross-surface dedupe
  finalize.py                    # canonical schema writer, date-stamped output
discover_worth_the_drive.py      # orchestrator: seed -> fetch (reviews|comments|forums) -> mine -> classify -> gate -> finalize; --input, --resume
```

Refactor targets so we don't duplicate logic (the same shared-lib argument
Engines 14 and 16 raise):

- Lift the `enrich.py` **step-5** Google Maps Reviews pull into a shared
  `enrich_reviews_lib` so `enrich.py` and both `demand_signals/` engines use one
  actor wrapper and one review-mining regex bank.
- Lift the `enrich.py` **step-6/7** IG post/reel pull into a shared
  `enrich_ig_lib` returning comment objects, so the comment lane reuses one
  Apify wrapper instead of re-declaring actor IDs/batching/retries.
- Reuse `config.CITIES` (and `config.CITY_ALIASES` if Engine 14 adds it) so the
  non-metro / home-metro buckets are consistent across engines.

`config.py` knobs to add: `WORTH_THE_DRIVE_REGEX` (the bank above),
`WTD_STRENGTH_THRESHOLDS`, `FORUM_DOMAINS`, the reviews-per-place cap, and a
`NON_METRO_WEIGHT` toggle.

## Open questions

1. **Non-metro weighting — prioritizer or filter?** Should an urban shop with
   genuine worth-the-drive language be capped/demoted (because "drive" means
   less in a dense core), or surfaced equally and left for the BDR to judge? A
   labeled sample of urban vs. destination-town hits should set this.
2. **Forum-lane precision & attribution.** Can Serper Web + Haiku reliably tie a
   "best butcher within 100 miles?" thread to the *correct* same-named business
   and metro, or does ambiguity make the forum lane evidence-only (never enough
   to mint Tier 1 alone)?
3. **Overlap with Engines 14 & 16.** A row that shows worth-the-drive (loyalty),
   sold-out complaints (scarcity), and out-of-town ship-asks (geo-demand) is the
   highest-conviction shippable-club target. Should these three demand engines
   roll into a single composite `demand_signals` cohort with a combined score,
   or stay separate lists that a BDR cross-references?
4. **Does it write back to `reservation_difficulty`?** Worth-the-drive is a
   demand signal but not a capacity/availability signal — should it stay
   evidence-only to avoid double-counting against the SHAP-aligned phase-8
   composite?
```