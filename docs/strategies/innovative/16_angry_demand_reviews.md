# Lead Engine 16 — "Angry Demand" Review Mining

**Motion:** Curation (with a hard Trigger overlay — the complaint *is* the trigger)
**Vertical fit:** Restaurants (destination + neighborhood), bakeries, butchers; secondary cheese / deli / specialty grocer
**Suggested list name(s):** `angry_demand_reviews`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run (rides the existing step-5 Apify Google Maps Reviews pull; net-new cost is a Claude classify pass)

## Premise

The most predictive ICP pattern in the model is demand-over-capacity, and
`reservation_difficulty` (the #2 SHAP feature behind Partner Type) is the
proxy that tries to measure it. **A specific class of one- and two-star
reviews measures the same thing more honestly than the operator ever will.**
"Waited 45 minutes for a table I had a reservation for," "got there at 10am
and the croissants were already gone," "drove an hour and they were sold out
of the brisket," "impossible to get a reservation — booked solid a month
out," "preorder window closed in minutes" — these read as *angry*, but every
one of them is a customer documenting that demand outstripped supply. The
business isn't bad; it's **supply-constrained**. That is precisely the
business Table22 monetizes: a recurring-access / preorder / membership layer
turns the line-out-the-door and the lost reservation into captured,
predictable revenue.

Unlike operator-authored sold-out copy (Engine 03) or customer ship-intent
comments (Engine 13), this signal is **adversarial and therefore credible**:
the reviewer has no incentive to manufacture scarcity — they're frustrated
they couldn't buy. It also reaches a surface those engines miss. Restaurants
rarely post "we're booked solid" but their reviews are full of it, and a
neighborhood bakery that never touches Instagram still accumulates "sold out
again" complaints on Google. Mapped to the two-score model, this is a strong
**Trigger** ("your own customers are publicly mad they couldn't buy — let's
capture that demand") that correlates with **ICP Fit** because you only
generate angry-demand reviews when finite premium product or limited seating
sells out faster than people can get it.

This is a **Curation** engine: angry-demand language is genuinely
ICP-correlated, but ordinary one-star reviews ("rude server," "overpriced,"
"dirty bathroom") vastly outnumber demand complaints, so the gate that
separates *supply-constrained* from *just bad* is load-bearing.

## Recipe

The detection surface already exists: `enrich.py` **step 5**
(`Google-Maps-Reviews` via Apify) already pulls review text and mines it for
reservation-difficulty signals. This engine extends that same mining pass to
a broader **angry-demand lexicon**, polarity-aware (we want *negative-star*
reviews that are *positive* demand signals), and emits the verbatim complaint
as a quotable trigger.

1. **Seed the universe, don't re-discover.** Run primarily over the existing
   enriched / scored corpus (`output/2_enriched_reviews.csv`, any
   `custom-serper-scoring_*_all.csv`) and the niche lanes (`butcher/`,
   `best_wine_shops/`, awards/directories masters) — these rows cleared
   discovery quality floors and already carry `place_id` / Maps URL needed for
   the reviews actor. For net-new geography, seed Serper Maps off
   `research/trendy_neighborhoods/` (~56.5% of partners sit in trendy
   neighborhoods) for destination/neighborhood restaurant, `bakery`, and
   `butcher` queries, then resolve `place_id`.

2. **Pull reviews biased toward low-star (reuse step-5 actor).** Reuse the
   `Google-Maps-Reviews` Apify actor `enrich.py` step 5 already drives,
   batched the same way. Request enough recent reviews per place (~50–100,
   newest-first) and **keep `stars` per review**. The angry-demand signal
   lives almost entirely in 1–3 star text, so the classifier runs over the
   low-star slice, not the 5-star praise wall — this also bounds cost and LLM
   tokens. Carry `reviewDate` so recency can be scored.

3. **Mine review text for angry-demand language** with a polarity-aware regex
   pass first (no LLM for the gate), over the 1–3 star slice, counting
   *distinct reviewers* per business:

   - **Sold-out / ran-out:** `sold[\s-]?out`, `ran out`, `(all|completely)
     gone`, `nothing left`, `out of (the )?(everything|brisket|bread|
     croissants?|sourdough|special|\w+)`, `by the time (we|i) (got|arrived)`
   - **Line / wait length:** `line (was )?(out the door|around the block|so
     long|huge)`, `waited (over |almost )?\d+ ?(min|minutes|hour|hours)`,
     `\d+[\s-]?(hour|hr|minute|min)\s*wait`, `hour[\s-]?long (line|wait)`
   - **Reservation impossible:** `(couldn'?t|could not|impossible to|can'?t)
     get a (reservation|table|booking)`, `booked (solid|out|up)( a)?
     (month|weeks?|days?)`, `no (reservations?|tables?|availability)`,
     `fully booked`, `reservations? (gone|sold out) in`
   - **Preorder / drop missed:** `pre[\s-]?order(s)? (gone|sold out|closed)
     (instantly|in minutes|so fast|immediately)`, `couldn'?t (pre[\s-]?order|
     order in time)`, `(turkey|pie|share|box|allocation) (gone|sold out)
     before`
   - **Couldn't-get / turned-away:** `turned away`, `had to leave`, `gave up
     waiting`, `never (have it|in stock| available)`, `always (sold out|out|
     packed|a wait)`, `come back earlier`, `get there early or`

   These overlap step-5's existing reservation-difficulty mining; consolidate
   into one shared regex bank (see Repo placement) so both consume it.

```
demand_complaints = DISTINCT 1–3★ reviewers matching any family above
sellout_hits      = reviewers matching the sold-out / ran-out family
res_hits          = reviewers matching the reservation-impossible family
wait_hits         = reviewers matching the line/wait family
recency_days      = days since most-recent matching review
recurrence        = #distinct months in last 12 with a matching review
```

4. **Classify polarity + intent (Claude, cheap pass — load-bearing).** Send
   the matched 1–3★ snippets to Claude (`claude-haiku-4-5-20251001`, the model
   `scrape_beli` uses) to (a) confirm the complaint is *supply-constraint /
   demand-pressure*, not generic dissatisfaction ("slow service because
   understaffed," "rude," "overpriced," "I waited because the kitchen was
   disorganized"), (b) label `complaint_type`, and (c) emit a one-line
   `trigger_summary` a BDR can quote. The distinction between "45-minute wait
   because they're slammed by demand" and "45-minute wait because they're
   badly run" is exactly what regex cannot do and the LLM must. Prefix the
   script with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

5. **Cross-check real-time scarcity where it exists (restaurants).** For
   destination/neighborhood restaurants, join the `enrich.py` **step-8
   availability** signal (OpenTable via Apify + Resy API). A row whose reviews
   complain "impossible to book" AND that shows zero real-time availability
   for the next 14 days is a *verified* angry-demand hit, not just an
   anecdote. Treat as a bonus, not a gate (Resy client is fragile).

6. **Apply the ICP gate + score demand-complaint strength.** Run
   `reclassify.py` (`partner_type` / `business_type_v2`, wine-bar claw-back)
   and carry `has_club` from `detect_clubs.py` (existing club = positive
   switch signal).

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
  sweets-only / single-product bakery   # demand is real but headroom is capped
  static-social-only / thin metrics in small market (never DQ — understates brand)

angry_demand_strength:
  +3 verified res-scarcity (reviews say impossible AND Resy/OT shows zero)
  +3 sellout OR reservation complaints from >=3 distinct reviewers
  +2 line/wait complaints from >=3 distinct reviewers
  +2 recurrence: matching complaint in >=3 distinct months (chronic, not a one-off)
  +1 most-recent matching review <90d (live trigger)
  +1 if has_club == True (proven recurring demand)
```

7. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   complaint columns ride as evidence; `angry_demand_strength` orders the
   outbound queue inside a tier. **Final list = passes ICP gate AND
   `angry_demand_strength >= 3`.** High-strength / weak-ICP routes to nurture,
   never straight to sales.

## Output schema

```
output/demand_signals/angry_demand_reviews_<YYYYMMDD>.csv
source = "angry_demand_reviews"
tier = <1|2|3>     # 1 = restaurant/butcher + verified/recurring scarcity; 2 = bakery/single-cluster; 3 = ICP-soft
business_type = restaurant | bakery | butcher | cheese | deli | specialty
distinction = "Customers publicly mad they couldn't buy: {complaint_summary} — capture demand w/ Table22"
year = <YYYY of most-recent matching review>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    complaint_type           # sold_out | line_wait | reservation_impossible | preorder_missed | turned_away
    angry_demand_strength    # int, intra-tier outbound ordering
    demand_complaints        # distinct 1–3★ reviewers with a demand complaint
    sellout_hits / res_hits / wait_hits
    recency_days             # days since most-recent matching review
    recurrence_months        # distinct months in last 12 with a matching review
    rt_availability_zero     # bool — Resy/OpenTable showed no availability (restaurants)
    review_snippet           # verbatim quote ("got there at 10, croissants already gone")
    review_url               # Google Maps review/place permalink
    review_stars             # star rating of the quoted review (1–3)
    trigger_summary          # one-line Claude-written outbound hook
    has_club                 # carried from detect_clubs.py (positive signal)
    partner_type             # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched + scored corpus + niche lanes), deduped:
  **~8–12K rows**, all with a resolvable `place_id`. No new discovery spend.
- Google Maps Reviews pull: most of the corpus already ran through step 5, so
  for rows with cached reviews this is **free**. Net-new / refresh pulls (rows
  not yet reviewed, or stale): ~3–4K places × ~$0.005–0.008/place for ~50–100
  reviews ≈ **$15–25**.
- Real-time availability cross-check (Resy/OpenTable) on destination/neighborhood
  restaurant subset only (~2K): reuses step-8 actors, **≈ $4–6**.
- Claude Haiku classify pass over matched 1–3★ snippets only (~2–3K rows,
  short prompts): **≈ $2–4**.
- **Per-run total: ~$20–30** (lower if review cache is warm).
- **Net-new qualified leads per run:** of ~10K screened, the angry-demand
  pattern surfaces in the low-star slice for **~12–18%** (≈1.2–1.8K); after
  ICP gate + Claude polarity confirm + `angry_demand_strength >= 3`, expect
  **~350–600 qualified rows**. Most already exist in the corpus — the value is
  the *adversarially-credible trigger* that re-prioritizes them for outbound.

## Refresh cadence

**Monthly.** Reviews accumulate slowly and a single new complaint isn't a
trigger; the engine's strength comes from *recurrence* (chronic sell-outs over
many months) and *recency* (a complaint in the last 90 days proves the
constraint is still live). A monthly pass keeps `recency_days` fresh without
re-burning the reviews actor. Pull a heavier run pre-holiday (turkeys, pies,
holiday reservations, charcuterie boards all generate "sold out / couldn't
book" complaints in November–December), and only re-scrape places with new
reviews since the last run.

## Risks

- **Generic one-star noise is the dominant failure mode.** Most negative
  reviews are about service, price, cleanliness, or food quality — not demand.
  The Claude polarity pass (step 4) is not optional; gate on *distinct
  reviewers with confirmed supply-constraint intent*, never raw 1–3★ count.
- **"Bad" masquerading as "demanded."** A 45-minute wait can mean
  understaffed-and-disorganized, not slammed-by-demand. The classifier must
  separate capacity pressure from operational failure; require corroborating
  positive sentiment about the *product* in the same or nearby reviews where
  possible.
- **ICP leakage through the trigger.** A liquor store ("Pappy allocation gone
  instantly"), a hyped 12-location chain, or a delivery-only spot can all
  accrue sold-out complaints. Keep `config.CHAIN_KEYWORDS`, commodity-SKU, and
  ESP-red-flag (City Hive, Spot Hopper) checks *upstream* of the strength score.
- **Wine-bar / liquor-store false positives.** Enforce wine-bar exclusion
  (except geographic-monopoly) and the `reclassify.py` wine-bar claw-back.
- **Small-market metrics run low.** A rural butcher who sells out every
  Saturday may have few total reviews and thus few complaints in absolute
  terms. Weight relative local dominance and the *recurrence* of the complaint
  over raw counts; **never DQ on thin review/social volume** — it understates
  brand in small markets.
- **Sweets-only demotion.** A cupcake shop that constantly sells out is a real
  trigger but a single-product bakery — cap at Tier 2, don't promote on the
  trigger alone.
- **Recency / staleness.** Apify returns historical reviews; a "sold out"
  complaint from three years ago is not a live trigger. Always record
  `recency_days` and weight it; treat >12 months as low-confidence.
- **Apify / Google Maps fragility.** The reviews actor can return truncated or
  sampled review sets and rate-limits at scale. Checkpoint per batch, support
  `--resume`, and confirm the actor returns enough recent reviews per place on
  a probe before locking thresholds.
- **Resy/OpenTable fragility.** The Resy client is reverse-engineered and
  rate-limits; treat verified real-time zero-availability as a *bonus* hard
  signal, not a gate — fall back to review text when the check fails.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-5 reviews
actor and the step-8 availability functions as libraries.

```
demand_signals/                  # may co-house Engine 03 if both built
  __init__.py                    # engine constants; registers angry-demand lexicon
  signals.py                     # ANGRY_DEMAND_REGEX (by family), SKU/ESP leak lists, negation rules
  fetch_reviews.py               # wraps the Google-Maps-Reviews Apify actor (reuse step-5 batching),
                                 # low-star-biased pull, keeps stars + reviewDate
  mine_complaints.py             # polarity-aware regex over 1–3★ slice; distinct-reviewer counts
  check_availability.py          # wraps step-8 Resy/OpenTable for restaurant subset
  classify.py                    # Claude haiku-4-5: confirm demand-pressure vs bad, complaint_type, trigger_summary
  aggregate.py                   # ICP gate (reclassify + detect_clubs join), angry_demand_strength, recency/recurrence, dedupe
  finalize.py                    # canonical schema writer, date-stamped output
discover_angry_demand.py         # orchestrator: seed -> fetch-reviews -> mine -> classify -> avail-check -> gate -> finalize
```

Refactor targets so we don't duplicate logic:

- Lift the `enrich.py` **step-5** Google Maps Reviews pull (actor call,
  batching, review-text mining) into a shared `enrich_reviews_lib` so both
  `enrich.py` and `demand_signals/fetch_reviews.py` use one implementation and
  one regex bank. Step-5 already mines reservation-difficulty text — this
  engine generalizes that lexicon, so consolidating avoids two diverging
  pattern banks.
- Extract the `enrich.py` **step-8** availability functions (OpenTable Apify +
  Resy lookup) into a shared `enrich_availability_lib` (same shared-lib
  argument Engines 03 and 05 raise).

`config.py` knobs to add: `ANGRY_DEMAND_REGEX` (the families above),
`ANGRY_DEMAND_STRENGTH_THRESHOLDS`, the reviews-per-place cap, and the low-star
slice ceiling (default ≤3★).

## Open questions

1. **Recurrence vs volume threshold.** Does "demand complaints from ≥3 distinct
   reviewers" over-favor high-traffic big-city places and starve small-market
   shops that genuinely sell out but get few reviews? Should the threshold be
   *relative* (demand complaints as a share of all negative reviews) rather
   than absolute?
2. **Polarity precision.** Can Haiku reliably separate "slammed by demand" from
   "badly run / understaffed" on short snippets, or does it need the
   surrounding 4–5★ reviews as context to confirm the product is actually
   loved? A labeled probe set should set the precision floor before launch.
3. **Verified-res slice as its own list?** The "reviews say impossible AND
   Resy/OpenTable shows zero" subset is the highest-confidence, lowest-volume
   cut — it overlaps the `reservation_impossible` strategy and may belong there
   rather than folded into this master.
4. **Feeding `reservation_difficulty`.** Should confirmed angry-demand review
   sentiment from this engine write back into the phase-8
   `reservation_difficulty` composite (35% review-text sentiment), or stay
   evidence-only to avoid double-counting against SHAP weights?
