# Lead Engine 24 — Equipment Expansion Signals

**Motion:** Curation
**Vertical fit:** Bakeries, butchers (also cheese, deli/specialty-grocer where charcuterie/aging gear applies)
**Suggested list name(s):** `equipment_expansion_signals`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run

## Premise

A merchant only buys a deck oven, a dry-aging room, a smoker rig, a second
walk-in, or a new fulfillment-grade packaging line when existing demand has
outrun current capacity. Capital equipment is the most expensive, least
reversible commitment a small food business makes — far more committing than a
"now shipping" caption — and it lands months *before* the new output needs to
be sold. That gap is exactly the window a Table22 club fills: convert the
fresh capacity into prepaid, recurring demand instead of speculative walk-in
volume. This is the demand-over-capacity thesis in its purest physical form.

Engine 05 (Capacity Expansion Trigger) mines what the *merchant* says about
their own growth. This engine attacks the same signal from the **supply
side** — the equipment vendors. Oven makers, dry-aging companies, smoker
brands, walk-in installers, and packaging/POS vendors all publicize their
installs: IG tags of the customer, case-study pages, "now installed at…"
posts, project galleries. The vendor surface is higher-precision (a vendor
naming a shop is near-certain proof an install happened) and reaches shops
that never announce expansion themselves — the quiet butcher who just dropped
$40k on a dry-aging room but only posts brisket photos.

In the two-score model this is a **Trigger** overlay. ICP Fit comes from the
verticals it targets (butcher is the top-AGMV partner type at $75.9k; bakery
has strong headroom). What this adds is "a reason to contact now," and an
unusually strong one: a recent equipment install is a near-irrefutable proxy
for capacity-ahead-of-demand. A high-ICP butcher tagged in a Friedr. Dick /
DCS dry-aging install post is both-high → route to sales immediately. A weak
or anti-ICP match (a pizza chain in an oven-vendor gallery) gets filtered
hard before it reaches a rep.

## Recipe

This engine has two halves: (A) harvest install events from a curated set of
**equipment-vendor surfaces** (the novel part), and (B) resolve each tagged
business to the enriched ICP universe and attach a trigger. It does **not**
discover net-new businesses cold — every candidate must resolve to a real,
ICP-classifiable shop before a trigger is attached.

1. **Build the vendor source registry.** Hand-curate a `VENDORS` table keyed
   by category, each with its IG handle(s) and case-study/gallery URL. Seed:

   ```
   ovens/bakery:     Bongard, Bakers Pride, Marra Forni (deck/hearth),
                     Polin, Empire (bake oven), Picard Ovens, Gemini Bakery Equip
   dry_aging:        DRY AGER, UMAi/Steak Locker, DCS/Dry Aged Custom Spaces,
                     Lockhart, The Dry Ager Co
   smokers/bbq:      Ole Hickory, Southern Pride, Cookshack, FEC/Fast Eddy's
   walk_in_cooler:   US Cooler, Kolpak, Master-Bilt, Nor-Lake (+ local refrigeration
                     installers — regional, lower priority)
   packaging/fulfil: sealed-air / vacuum-seal vendors, label/box co-packers,
                     ShipStation-style fulfillment case studies
   pos:              Toast, Square for Restaurants, Lightspeed case studies
   charcuterie/aging:curing-chamber + sausage-equipment vendors
   ```

   POS vendors are deliberately lowest-priority — high volume, weak
   capacity signal (a POS swap is not new output) — included only as a
   corroborating signal, never a Tier-1 trigger on its own.

2. **Harvest vendor install events (two extraction modes).**
   - **Tagged-posts (Apify).** For each vendor IG handle, run the
     `instagram-tagged-posts-scraper` actor (already in `config.py`) — posts
     where the vendor is *tagged by* customers — plus the
     `instagram-post-scraper` over the vendor's own feed (their "installed at
     @shop" posts). Tagged posts are the gold lane: a customer tagging the
     oven maker the week the oven lands is the freshest possible install
     signal. Batch handles like the rest of the IG pipeline.
   - **Case-study / gallery pages (httpx + selectolax, Playwright fallback).**
     Mirror the `best_wine_shops/` pattern: fetch each vendor's case-study /
     "our installs" / project-gallery page on the httpx happy path, fall back
     to Playwright when blocked. These pages name the shop, city, and often
     the equipment model in clean text.

3. **Extract the install → (shop, equipment, date) tuple (Claude).** Run
   matched captions, alt-text, and case-study HTML through an
   `awards/llm_extract.py`-style pass (`claude-haiku-4-5-20251001` for the
   bulk caption/gallery classification, Sonnet for ambiguous press). Prefix
   the script with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).
   Emit per event: `shop_name`, `city`/`state` (when present),
   `equipment_type`, `equipment_model`, `install_date` (post date or
   case-study date), and a verbatim `evidence_quote`. Discard vendor
   marketing that names no specific customer.

4. **Resolve the tagged shop to a real business.** A vendor caption gives a
   handle or a name, not a row. Resolve in order: (a) IG handle → match against
   existing `output/2_enriched_*.csv` `ig_handle`; (b) name + city → Serper
   Maps lookup (reuse `discover.py` / `scripts/fresh_icp_search.py`) to pull
   the Maps record, website, phone, address; (c) fail → drop to a
   `needs_manual_resolution` sidecar CSV rather than guessing. Resolution is
   the make-or-break step; an unresolved tag is worthless to sales.

5. **Establish ICP Fit on the resolved shop.** Run `reclassify.py` to set
   `partner_type` (fine) + `business_type_v2` (coarse), then the standard
   `score.py` /100 ICP score using the unchanged SHAP-aligned
   `config.SCORING_WEIGHTS`. Run `config.CHAIN_KEYWORDS` + the liquor/wine-bar
   exclusions and (for the butcher cohort) `BANNED_STATES = {HI, IN, IA, KS,
   NV, ND, SD}` to strip anti-ICP leakage. For butcher/deli/specialty-grocer,
   run `enrich.py` step 3 (`facebook`) alongside step 2 (`instagram`) — FB
   engagement often beats IG for these verticals — and `detect_clubs.py` to
   flag any existing club (positive platform-switch signal, not a DQ).

6. **Score the trigger.** Weight by capacity-to-channel directness × recency
   decay × equipment-vertical fit. Capital equipment ages slower than a
   caption, so use a longer decay horizon than Engine 05's job postings:

```
EQUIP_TRIGGER_WEIGHTS = {
    "dry_aging_room":        1.0,   # butcher: new sellable, premium, recurring output
    "deck_or_hearth_oven":   0.95,  # bakery: direct production-capacity jump
    "new_smoker_rig":        0.85,
    "second_walk_in":        0.8,   # storage capacity → can hold more inventory/preorders
    "curing_chamber":        0.85,  # charcuterie program → proto-subscription product
    "packaging_fulfillment": 0.8,   # implies a ship/preorder channel being stood up
    "second_production_oven":0.75,
    "pos_install":           0.4,   # weak alone — corroborating only
}

recency      = max(0, 1 - months_since_install / 18)   # capital decays slower than captions
equip_fit    = 1.0 if equipment_type matches the shop's partner_type else 0.5
              # e.g. dry-aging at a butcher = 1.0; dry-aging at a bakery = noise (0.5 / review)
trigger_score = EQUIP_TRIGGER_WEIGHTS[equipment_type] * recency * equip_fit

# multiple distinct installs compound, capped:
combined = min(1.0, sum(trigger_scores) * 0.85 ** (n_installs - 1))

tier = 1 if (combined >= 0.7 and high_icp_vertical) else \
       2 if (combined >= 0.45) else 3
```

   The trigger score is a **separate sales-sort column**, not a replacement
   for the ICP /100 score. Do not re-tune `config.SCORING_WEIGHTS`.

7. **Dedupe and merge.** Phone-first then name+address via `dedupe_existing.py`.
   Where a shop already carries an Engine 05 self-announced expansion trigger,
   stack the signals (vendor-confirmed + self-announced = highest conviction)
   rather than double-counting.

Preserve the vendor evidence verbatim so outbound can cite it ("saw DRY AGER
posted your new aging room last month…").

## Output schema

```
output/triggers/equipment_expansion_signals_<YYYYMMDD>.csv
source = "equipment_expansion_signals"
tier = <1|2|3>
business_type = <butcher | bakery | cheese | specialty_grocer | deli>
distinction = "<human-readable trigger, e.g. 'New dry-aging room — DRY AGER install (Mar 2026)'>"
year = <YYYY of most recent install>
+ evidence cols:
    equipment_type          # normalized enum from EQUIP_TRIGGER_WEIGHTS
    equipment_model         # extracted model when present (e.g. "Bongard Cervap")
    vendor_name             # the equipment vendor that named the shop
    vendor_category         # ovens | dry_aging | smokers | walk_in | packaging | pos
    trigger_score           # combined, recency- + fit-decayed
    install_date            # post / case-study date driving the trigger
    trigger_source          # ig_tagged | ig_vendor_post | case_study
    evidence_url            # vendor post / case-study URL (sales must cite)
    evidence_quote          # exact caption/snippet that fired the match
    equip_fit               # 1.0 matched vertical, 0.5 cross-vertical (review flag)
    n_installs              # distinct install events stacked
    resolution_method       # ig_handle | serper_maps | manual
    icp_score               # /100 from score.py (unchanged weights)
    partner_type, business_type_v2, has_club, fb_likes, ig_handle, follower_count
```

A sidecar `output/triggers/equipment_expansion_signals_<YYYYMMDD>_unresolved.csv`
holds install events that couldn't be resolved to a business — input for a
later manual or improved-resolution pass, never shipped to sales.

## Volume & cost

The constraint is install-event supply, not candidate-pool size — vendors
publicize a finite number of named installs.

- ~30–40 vendor handles × tagged-posts + own-feed scrape (Apify, ~recent 50
  posts each): ~70 actor runs × ~$0.01 ≈ **$1–2**.
- Case-study / gallery fetch: free (httpx + selectolax; Playwright fallback on
  a handful of blocked vendors).
- Claude extraction over ~1,500–3,000 captions/snippets (Haiku bulk, Sonnet on
  borderline): ≈ **$4–6**.
- Serper Maps resolution for shops not already in the enriched universe
  (~300–600 lookups): ≈ **$2**.
- FB/IG enrichment via Apify on the resolved survivor set (~200–400 handles ×
  ~$0.015): ≈ **$5**.
- **Per-run total: ~$12–18.**

Expected yield: across all vendor surfaces, perhaps **400–900 named install
events** per run, collapsing after resolution + ICP filtering + recency to
**~120–250 triggered rows**, of which **~40–90 are Tier 1** (high-ICP vertical,
fresh ≤18mo, vertical-matched equipment). First run captures the standing
backlog of case studies; later runs trickle as new installs post.

## Refresh cadence

**Monthly**, with the IG tagged-posts sub-lane optionally **biweekly**. New
install posts arrive episodically; capital equipment stays actionable for a
quarter or two (the 18-month decay handles aging), so monthly is enough to stay
fresh without re-burning Apify. Re-run the bakery oven lane harder in
**August–September** ahead of the holiday baking ramp, when oven installs
cluster. Keep an `output/triggers/raw/` archive and diff month-over-month so a
newly-posted install fires a clean "newly triggered" flag rather than
re-scoring a standing case study.

## Risks

- **Vendor-marketing false positives.** Vendors reshare aspirational/stock
  content or tag distributors and trade-show booths, not real installs. The
  Claude extraction gate must drop any event that names no specific customer
  storefront; tune on a labeled sample before trusting Tier 1.
- **Resolution failure / wrong-shop binding.** A name like "Main Street
  Bakery" matches many shops; an IG handle may be a personal account. Require a
  confident IG-handle or name+city Maps match; route everything else to the
  unresolved sidecar. A mis-bound trigger that sends a rep to the wrong shop is
  worse than a miss.
- **Cross-vertical equipment noise.** A deck oven at a pizza chain, a walk-in
  at a convenience store, a POS at a cocktail bar all surface in vendor
  galleries. `equip_fit` down-weights mismatches and `config.CHAIN_KEYWORDS` +
  liquor/wine-bar exclusions hard-drop anti-ICP shops before scoring.
  Specialty-grocer is the leakiest resolved bucket — confirm it isn't a
  convenience chain.
- **POS over-firing.** POS installs are common and weakly tied to capacity;
  capped at 0.4 and never Tier 1 alone — corroboration only.
- **Pizza-first / restaurant leakage on the oven lane.** Oven-vendor galleries
  are dominated by pizzerias. Demote pizza-first per the disqualifier rules
  unless the resolved shop is artisanal bakery; the Claude pass should classify
  pizza-first vs. bakery.
- **Sweets-only / single-product demotion.** A cupcake-only bakery with a new
  oven still caps at Tier 2 per the cheat-sheet; carry the single-product flag
  forward and cap.
- **Small-market understatement.** A rural butcher's new dry-aging room is a
  strong signal even with thin reviews/social. This engine only *adds* leads on
  positive signal — never down-rank a quiet shop for low post/review volume.
  Static-only social understates brand.
- **Platform / scrape fragility.** Apify IG actors and vendor case-study markup
  both break and rate-limit. Degrade gracefully: if the tagged-posts actor
  fails, fall back to case-study-only; log per-vendor coverage so a silent
  Apify outage doesn't read as "no installs this month."
- **Banned states.** Enforce the butcher-lane `BANNED_STATES` before output for
  the butcher cohort.

## Repo placement

Lands in the same `triggers/` package proposed by Engine 05, sharing its
`_lib.py` (SCHEMA, weights, decay) and the press/social/extraction wrappers.

```
triggers/
  __init__.py
  _lib.py                          # shared: SCHEMA, decay, evidence-preserve helpers
  equipment_expansion.py           # main engine: harvest → extract → resolve → score
  vendors.py                       # VENDORS registry (handles + case-study URLs by category)
  vendor_harvest.py                # Apify tagged/own-post pull + httpx/Playwright gallery fetch
  install_extract.py               # Claude (Haiku/Sonnet) install-event extraction
  shop_resolve.py                  # ig_handle match → Serper Maps fallback → unresolved sidecar
discover_equipment_expansion.py    # orchestrator (mirrors discover_awards.py shape)
```

Shared-code refactors this engine wants (overlapping with Engine 05):

- Expose `enrich.py` steps 2/3 (Apify IG profile + FB scrape) as importable
  functions so the resolution/enrichment step calls them without
  re-implementing actor auth.
- Add a thin `instagram-tagged-posts-scraper` wrapper alongside the existing IG
  actor wrappers (the actor ID is already in `config.py`; no current lane
  drives it — confirm it is exercised).
- Add to `config.py`: `EQUIPMENT_VENDORS` (or keep in `triggers/vendors.py`),
  `EQUIP_TRIGGER_WEIGHTS`, and the recency/fit decay constants, alongside the
  Engine-05 trigger blocks.

## Open questions

1. How well does the `instagram-tagged-posts-scraper` actually surface
   customer→vendor tags at the volume we need, and is the tag noise (resellers,
   trade shows, employees) tractable for the Claude gate? Worth a one-vendor
   probe before committing the lane.
2. Is a single vendor-confirmed install enough for Tier 1, or should Tier 1
   require the install **plus** an independent ICP-fit floor (e.g. ICP B+) so we
   don't route a marginal shop just because it bought an oven?
3. How do we treat a shop that is both an existing-club operator and just
   installed capacity — the platform-switch + fresh-capacity stack? Likely the
   single hottest combination here; auto-route to senior BDRs like the
   job×competitor intersection in Engine 02?
4. Walk-in coolers and POS are dual-use (any food business buys them) — do they
   earn their place as corroborating signals, or do they dilute precision enough
   that we cut them and keep only ovens / dry-aging / smokers / curing?
