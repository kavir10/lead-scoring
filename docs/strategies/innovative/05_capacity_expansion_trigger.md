# Lead Engine 05 — Capacity Expansion Trigger List

**Motion:** Curation
**Vertical fit:** Bakeries, butchers, cheese, specialty grocers (artisan retail/production cohort)
**Suggested list name(s):** `capacity_expansion_trigger`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run

## Premise

A merchant adding operational capacity — a new production kitchen, a second
oven, a fulfillment hire, a "now shipping nationwide" banner, a new pickup
window — is at the exact moment they can finally *support* a new recurring
revenue channel. For the production-retail verticals (bakery especially),
the ICP cheat-sheet calls growth phase the single strongest *timing* signal:
these shops are demand-saturated relative to current capacity and are
spending capital to close the gap. A subscription/club program converts that
new capacity into predictable, prepaid demand instead of speculative walk-in
volume.

This is a pure **Trigger** engine in the two-score model. ICP Fit is supplied
by the verticals it targets (butcher/cheese are the top-AGMV partner types;
bakery has strong headroom). What this engine adds is the "reason to contact
now" — the expansion announcement. A high-ICP butcher with a fresh "we just
added a smokehouse / hiring a production butcher" post is both-high: route to
sales immediately. A weak-ICP match with an expansion signal (e.g. a coffee
chain "now open") gets filtered hard before it reaches a rep.

The thesis is demand-over-capacity: shops only announce expansion when
existing demand justifies the spend. The announcement is a public proxy for
"demand exceeds what we can currently sell," which is exactly the condition a
Table22 club monetizes.

## Recipe

This engine fuses three public surfaces — Serper Web (press/announcements),
Apify Instagram/Facebook (captions), and food-job-board postings — into one
trigger-scored list. It does **not** discover new businesses from scratch; it
runs against the existing enriched universe plus a thin Serper top-up, so
ICP Fit is already established before a trigger is attached.

1. **Seed the candidate set.** Start from the existing
   `output/2_enriched_*.csv` universe filtered to the four verticals
   (`business_type in {butcher, cheese, bakery, specialty_grocer}` via
   `reclassify.py`'s `business_type_v2`/`partner_type`). Top up with a Serper
   Maps pass for any of the four types not yet enriched, using the standard
   `config.py` keyword queries and niche quality floors (≥20 reviews / ≥4.0).
2. **Press/announcement scan (Serper Web).** Reuse the press enrichment step
   (`enrich.py` step 4 `press`) machinery — Serper Web against food-media
   domains and local-press — but swap the award keywords for the expansion
   keyword set below, scoped per candidate (`"<name>" "<city>" <expansion
   phrase>`). Local business journals, Eater regional, and Patch are the high
   hit-rate domains here.
3. **Social caption mining (Apify IG + FB).** Reuse `enrich.py` step 2
   (`instagram`, Apify instagram-profile-scraper, batches of 30) and step 7
   (`posts`, instagram-post-scraper) plus the step 3 Facebook HTML scrape.
   Pull the most recent ~12 posts per handle and regex/Claude-scan captions
   for the expansion phrases. **For butcher/cheese/specialty-grocer, weight
   Facebook captions at least as heavily as IG** — per the cheat-sheet, FB
   engagement and posting often beats IG for these verticals.
4. **Job-posting cross-check.** Reuse `scripts/discover_jobs.py` lane (Serper
   Web `site:indeed.com`/`site:poached.com` + direct fetch) scoped to
   *production/fulfillment* roles, not front-of-house. A "hiring production
   baker / fulfillment lead / shipping coordinator / events manager" posting
   is the strongest single expansion signal because it implies capacity that
   already exists and needs to be filled.
5. **Extract + normalize the trigger (Claude).** Run matched press snippets
   and captions through `awards/llm_extract.py`-style extraction (Claude;
   prefix the script with `unset ANTHROPIC_API_KEY &&` per the repo gotcha) to
   produce a one-line human-readable `distinction` and a normalized
   `trigger_type` enum. Discard matches where Claude judges the phrase is not
   a genuine capacity expansion (e.g. "new oven roasted pizza" menu copy).
6. **Date the trigger and decay.** Every match carries `trigger_date`
   (post date, article date, or posting date). Expansion intent decays — a
   24-month-old "new location" is stale.
7. **Score and tier.** Combine trigger strength with ICP fit. Trigger weights
   reflect capacity-to-channel directness:

```
TRIGGER_WEIGHTS = {
    "now_shipping":            1.0,   # net-new fulfillment channel — strongest
    "hiring_fulfillment":      0.9,
    "new_production_kitchen":  0.9,
    "hiring_production_baker": 0.85,
    "new_location":            0.8,
    "new_oven_equipment":      0.7,
    "hiring_events_manager":   0.65,
    "new_pickup_window":       0.6,
    "expanded_hours":          0.45,  # weakest — could be seasonal
}

recency = max(0, 1 - months_since_trigger / 24)
trigger_score = TRIGGER_WEIGHTS[trigger_type] * recency
# multiple distinct triggers compound (capped):
combined_trigger = min(1.0, sum(trigger_scores) * 0.85 ** (n_triggers - 1) ... )

# ICP fit reuses existing partner-type prior (butcher/cheese high, bakery mid)
tier = 1 if (combined_trigger >= 0.7 and high_icp_vertical) else \
       2 if (combined_trigger >= 0.45) else 3
```

   Feed the row through the normal `score.py` weighting for the /100 ICP
   score (do **not** re-tune `config.SCORING_WEIGHTS`); the trigger score is a
   **separate column** the sales team sorts on, not a replacement for the
   SHAP-aligned ICP score.

**Expansion phrase seed list** (case-insensitive; tune in `config.py`):

```
"new production kitchen", "new commissary", "second kitchen", "new bakeshop",
"new oven", "added an oven", "deck oven", "new hearth", "new smokehouse",
"now shipping", "ship nationwide", "nationwide shipping", "we now ship",
"new location", "second location", "opening soon", "now open in",
"expanded hours", "new hours", "now open mondays", "extended hours",
"new pickup window", "pickup now available", "preorder now open",
"now hiring production", "hiring a production baker", "fulfillment lead",
"shipping coordinator", "wholesale manager", "events manager", "events coordinator"
```

**Anti-trigger / menu-noise blocklist** (drop matches containing these):

```
"wood-fired pizza", "oven-roasted", "oven-baked special", "new menu item",
"happy hour", "new cocktail", "back by popular demand"
```

## Output schema

```
output/triggers/capacity_expansion_trigger_<YYYYMMDD>.csv
source = "capacity_expansion_trigger"
tier = <1|2|3>
business_type = <butcher | cheese | bakery | specialty_grocer>
distinction = "<human-readable trigger summary, e.g. 'Now shipping nationwide (Apr 2026)'>"
year = <YYYY of most recent trigger>
+ evidence cols:
    trigger_type            # normalized enum from the weights table
    trigger_score           # combined, recency-decayed
    trigger_date            # post/article/posting date driving the trigger
    trigger_source          # press | instagram | facebook | job_posting
    evidence_url            # article / post / listing URL (sales must be able to cite)
    evidence_quote          # exact phrase/snippet that fired the match
    n_triggers              # how many distinct triggers stacked
    icp_score               # /100 from score.py (unchanged weights)
    partner_type            # fine bucket from reclassify.py
    fb_or_ig                # which social surface carried the signal
```

Preserve `evidence_url` + `evidence_quote` on every row — outbound copy cites
the specific announcement ("saw you just added the smokehouse…"), so the proof
must survive into the CSV.

## Volume & cost

Candidate pool for the four verticals from the existing universe is on the
order of ~4–6K rows (butcher universe alone is only ~1,000–1,200 US shops, so
this skews bakery/specialty-grocer heavy).

- Serper Web press scan: ~5K candidates × 2 queries × $0.30/1K ≈ **$3**
- IG/FB caption pull (Apify, reuse already-scraped profiles where possible;
  only fetch recent posts for the subset missing fresh data, ~2K handles ×
  ~$0.004) ≈ **$8**
- Job-board Serper pass (production roles, per-metro): ~$0.50
- Claude extraction/normalization (Haiku for caption classification, Sonnet
  for borderline press): ~$8
- **Per-run total: ~$20–25**

Expected yield: of ~5K candidates, perhaps **8–15%** carry a live (<24mo)
expansion signal → **~400–700 triggered rows**, of which **~120–200 are
Tier 1** (high-ICP vertical + strong fresh trigger). Many will already be in
the pipeline; the value is the freshly-attached trigger, which routes a known
ICP-fit shop to sales *now*.

## Refresh cadence

**Monthly.** Expansion announcements are episodic but not as perishable as a
job posting — a "new production kitchen" stays actionable for a quarter or
two. Monthly catches new signals while the 24-month recency decay handles
aging. Run the *job-posting* sub-lane on its own **weekly** cadence (piggyback
on `discover_jobs.py`) since postings decay fast, and merge into the monthly
master.

## Risks

- **Menu/marketing false positives.** "New oven-roasted special," "now open
  for brunch," "new pickup window for our holiday menu" all match naively.
  The anti-trigger blocklist plus the Claude classification gate exist
  specifically for this; tune on a labeled sample before trusting Tier 1.
- **Expanded-hours weakness.** Seasonal hour changes (summer Sunday hours)
  masquerade as capacity expansion. Weighted lowest (0.45) and never enough
  to reach Tier 1 alone.
- **Anti-ICP leakage.** "Now open" / "second location" fires for chains,
  franchises, ghost kitchens, and liquor stores. Run every candidate through
  the existing `config.CHAIN_KEYWORDS` filter and the liquor-store/wine-bar
  exclusions *before* attaching a trigger. Specialty-grocer is the leakiest
  bucket — confirm it isn't a convenience chain.
- **Sweets-only / single-product demotion.** A bakery that is cupcakes-only
  still caps at Tier 2 per the cheat-sheet even with a strong trigger; carry
  the single-product flag forward and cap.
- **Small-market understatement.** Rural butchers/cheesemongers post rarely
  and have thin local press. Don't penalize absence of signal — this engine
  only *adds* leads on positive signal; it must not down-rank a shop for being
  quiet. Static-only social understates brand; do not DQ on low post volume.
- **Platform fragility.** Apify IG/FB scrapers and Serper SERPs both break.
  Caption mining degrades gracefully to press-only if IG fetch fails; log
  per-surface coverage so a silent IG outage doesn't look like "no triggers."
- **Banned states.** If the butcher sub-cohort is included, enforce the
  butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` before output.

## Repo placement

```
triggers/
  __init__.py
  _lib.py                       # SCHEMA, TRIGGER_WEIGHTS, phrase + blocklist seeds
  capacity_expansion.py         # main engine: seed → scan → mine → extract → score
  press_scan.py                 # thin wrapper over enrich.py step-4 press machinery
  social_caption_mine.py        # thin wrapper over enrich.py steps 2/3/7 (IG+FB)
  job_subscan.py                # production-role filter over discover_jobs.py output
discover_capacity_expansion.py  # orchestrator (mirrors discover_awards.py shape)
```

Two shared-code refactors this engine wants:
- Expose `enrich.py` step 4 (press Serper) and steps 2/3/7 (IG/FB caption
  fetch) as importable functions rather than in-pipeline steps, so
  `triggers/` can call them without re-implementing Serper/Apify auth. Same
  refactor Engine 05 (reservation-impossible) wants for the availability funcs.
- Add the expansion phrase list, blocklist, and `TRIGGER_WEIGHTS` to
  `config.py` alongside the existing keyword/press-domain blocks.

## Open questions

1. Is a job posting alone (no social/press corroboration) enough for Tier 1,
   or should Tier 1 require trigger from ≥2 distinct surfaces? Job postings
   are the cleanest production-capacity proxy but lowest volume.
2. Should we diff month-over-month to detect *changes* (new oven this month
   vs. mentioned six months ago) rather than re-scoring the same standing
   announcement? An archive at `output/triggers/raw/` + diff would give a
   true "newly fired" flag.
3. How do we treat a shop that is *both* a known existing-club operator and
   newly expanding capacity? That's a platform-switch + expansion stack —
   arguably the single hottest combination; should it auto-route to senior
   BDRs the way the job×competitor intersection does in Engine 02?
4. Do we trust Apify FB caption coverage enough to lean on it for the
   butcher/specialty-grocer cohort, given FB is their primary surface but the
   FB scrape is HTML-based and brittle?
