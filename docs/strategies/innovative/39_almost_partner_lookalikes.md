# Lead Engine 39 — Almost-Partner Lookalikes

**Motion:** Curation
**Vertical fit:** All high-fit verticals; strongest for the high-AGMV curation types (butcher / wine / cheese / destination restaurant) where the operational fingerprint is most distinctive
**Suggested list name(s):** `almost_partner_lookalikes`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $35/run (Apify IG actors over partner seeds + first-degree candidates, Serper Web for co-press, concurrent site crawl for fingerprint extraction, Haiku for menu-vocabulary + co-name mining)

## Premise

The strongest predictor of Table22 fit is "looks like a business we already
closed." But the naïve version of that — "find similar restaurants" — collapses
into the same keyword/Maps sweep `discover.py` already runs. The value here is
modeling the **actual operational and social fingerprint** of each strong
partner, not a category label. A great partner is identifiable by a *bundle* of
non-obvious traits: the same upstream suppliers, the same reservation platform,
the same neighborhood archetype, the same press outlets that cover it, the same
people who comment on its posts, the same chef-alumni lineage, and the same
menu/about-page vocabulary. A candidate that matches several of those fingerprint
dimensions against a strong partner is a near-twin — an "almost-partner" — with
ICP-Fit precision no single-signal lookalike can reach.

This is a pure **ICP-Fit amplifier**, not a Trigger engine: it answers "is this
the right *kind* of business?" with high precision by borrowing the revealed
judgment of proven, *high-performing* partners. It is the multi-fingerprint
generalization of the graph engines that came before it — Engine 11
(partner-adjacency, four social channels), Engine 28 (industry comment graph),
Engine 29 (supplier graph). Where each of those rides one edge type, Engine 39
fuses **seven fingerprint dimensions** into a single similarity score against
the partner roster, and — critically — weights seeds by *partner AGMV*, so
lookalikes of our best partners rank highest. On its own a high-similarity
candidate with no trigger is a strong **nurture** lead; it pairs with any Trigger
overlay (Engines 03/04/05/08) to tell you when to dial.

## Recipe

Build as a new mode inside the existing **`social_graph/`** package (home of
`discover_ig_graph.py` + the Engine 01/11 fetch/aggregate scaffolding), reusing
its Apify IG client and aggregation pattern. It is a discovery lane (emits
canonical rows), not a postprocessing overlay. The engine reuses the seed-set,
co-press, supplier, and comment-graph machinery from Engines 11/28/29 rather than
re-implementing them — it is the *fusion layer* on top.

1. **Build the partner fingerprint set — the load-bearing input.** Start from
   `social_graph/partner_seeds.csv` (Engine 11's hand-built roster of closed
   partners + exemplars: `name, partner_type, ig_handle, fb_handle, website,
   city, state, status`). **Filter to *strong* partners only** — join the
   partner roster / HubSpot export and keep rows above a Peak-AGMV floor (and
   exemplars hand-marked best-in-class). A lookalike of a mediocre partner is
   noise; a lookalike of a top-decile butcher is gold. Weight each seed by its
   AGMV band (or partner-type avg AGMV when per-partner AGMV is unavailable).

2. **Extract the seven fingerprint dimensions per strong partner.** For each
   seed, build a `fingerprint` record by reusing existing primitives:
   - **F1 — Suppliers / importers / farms.** Crawl seed site + recent captions
     for upstream entities (Engine 29's `_supplier_graph.py` Mode C lexicon:
     wine importers `Skurnik / Louis-Dressner / Jenny & Francois / Zev Rovine /
     Selection Massale / Rosenthal / Vom Boden`; butcher ranches `Heritage Foods /
     Niman Ranch / Marin Sun / White Oak Pastures`; cheese affineurs; bakery mills).
   - **F2 — Reservation platform.** From `enrich.py` step 1 (websites) + step 8
     (availability): which platform the seed uses (Resy / Tock / OpenTable / SevenRooms).
   - **F3 — Neighborhood archetype.** Map seed address to a `research/trendy_neighborhoods/`
     row; carry the neighborhood + its archetype tag (~56.5% of partners sit in trendy nbhds).
   - **F4 — Press outlets.** From `enrich.py` step 4 (press): the *set of food-media
     domains* that cover the seed (Eater/BA/Punch/local outlet), not just the count.
   - **F5 — IG commenters.** From Engine 28's comment-graph: the recurring handles
     commenting on the seed's posts (`instagram-post-scraper`, batches of 30; Haiku
     for handle extraction). A shared engaged-commenter cohort is a strong audience tie.
   - **F6 — Chef / owner alumni lineage.** Serper Web + `awards/llm_extract.py`
     (Haiku, `unset ANTHROPIC_API_KEY &&`) over bios/press: "previously at {restaurant}",
     "alum of {restaurant}", James Beard / opening-team mentions. Two venues sharing a
     pedigree node are peers.
   - **F7 — Menu / about-page vocabulary.** Crawl seed menu + About copy; build a
     TF-IDF-weighted lexicon of distinctive phrases (`whole animal`, `nose to tail`,
     `naturally leavened`, `pét-nat`, `dry-aged 45 days`, `daily-changing`, named
     cultivars). Haiku normalizes; store the top-N discriminating terms.

3. **Generate the candidate pool.** Union first-degree candidates from the
   fingerprint extractions: supplier-graph stockist neighbors (Engine 29 Modes A/B),
   comment-graph co-commented venues (Engine 28), co-press co-listed names
   (Engine 11 Channel C), and tagged/collab accounts (Engine 11 Channels A/B).
   This is the *recall* step — cheap, wide, noisy. Resolve handles/domains to real
   venues (website + Google Maps), drop seeds and already-closed partners.

4. **Score each candidate against the nearest strong partner (the *precision* step).**
   For every candidate, compute per-dimension match against each seed fingerprint
   and take the best-matching (highest-AGMV-weighted) partner:

   ```
   dims = {F1 supplier, F2 reservation, F3 neighborhood, F4 press, F5 commenters, F6 alumni, F7 vocab}
   dim_hits      = count of dims where candidate ~ seed (jaccard/overlap over each dim's set)
   seed_agmv_w   = AGMV band weight of the matched seed (top-decile=3, strong=2, exemplar=1)
   vocab_sim     = cosine over F7 TF-IDF vectors (the hardest dim to fake -> highest weight)
   sim_score     = seed_agmv_w * (1.5*vocab_sim + dim_hits)

   if dim_hits >= 3 and seed_agmv_w >= 2:  tier = 1   # multi-fingerprint twin of a strong partner
   elif dim_hits >= 2:                     tier = 2
   elif dim_hits == 1 and vocab_sim high:  tier = 3   # single thin edge -> corroborate
   else: drop
   ```

   The `dim_hits >= 2` gate is what beats naïve lookalikes: any one dimension
   (same neighborhood, same platform) is common and weak; the *intersection* of
   three is a near-twin. F7 vocabulary is weighted highest because it is the
   dimension hardest to share by coincidence.

5. **Hand resolved candidates to the standard funnel.** Emit the canonical CSV
   below, then feed Tier 1/2 handles into `main.py --enrich` + `score.py` for ICP
   scoring and `reclassify.py` for the wine-bar claw-back / partner-type demotions.
   The similarity tier is the *seed-quality* annotation; `score.py` stays the
   source of truth for ICP Fit.

## Output schema

```
output/social_graph/almost_partner_lookalikes_<YYYYMMDD>.csv
source = "almost_partner_lookalikes"
tier = <1|2|3>                       # similarity tier (seed-quality), not score.py tier
business_type = <best-guess from matched seed partner_type + Google type; reclassify later>
distinction = "Almost-partner of {best_seed} — matches on {matched_dims}"
year = <max evidence year>
source_url = <strongest evidence URL: shared press article / stockist page / seed profile>
blurb = <verbatim shared sourcing/vocab/alumni sentence for the cite>
+ evidence cols:
    name, city, state, country, website, ig_handle, fb_handle,
    best_seed, best_seed_partner_type, best_seed_agmv_band,
    dim_hits, matched_dims,             # e.g. "F1_supplier,F4_press,F7_vocab"
    shared_suppliers,                   # F1: verbatim matched upstream names
    reservation_platform,               # F2
    neighborhood, neighborhood_archetype, # F3
    shared_press_outlets,               # F4: media domains in common
    shared_commenter_handles,           # F5: recurring co-commenters (sample)
    alumni_node,                        # F6: shared restaurant pedigree
    vocab_sim, top_shared_terms,        # F7: cosine + discriminating phrases
    sim_score, scan_date
```

`best_seed` + `matched_dims` + the verbatim evidence preserve the exact tie so a
BDR can open with "you run the same kind of shop as {partner} — same suppliers,
same neighborhood, same crowd" — the cite-the-trigger evidence a Curation list needs.

## Volume & cost

- Strong seeds: ~80-150 (top-AGMV partners + exemplars; a strict subset of Engine
  11's full seed set).
- Fingerprint extraction per seed: F5 comment + F6/F4 press IG/Serper pulls
  ≈ $0.02/seed Apify + Serper ⇒ **~$3-5**; site crawl (F1/F2/F7) free.
- Candidate pool: ~2,000-4,000 raw (union of supplier, comment, co-press neighbors;
  heavy overlap with the existing universe). Resolution crawl free.
- Candidate-side fingerprint extraction (F1/F2/F7 over ~3,000 domains): concurrent
  crawl free; Haiku vocab normalization on ~3,000 pages ≈ **~$10-15**.
- F5 candidate comment confirmation (only for Tier-2 borderline cases) ≈ **~$5-8**.
- **Per-run total: ~$20-35.**
- **Net-new candidates per run: ~2,000-4,000 unique, of which ~150-300 reach
  Tier 1** (3+ dimensions matching a strong partner). Overlap with the existing
  universe is expected and fine — the value is the *almost-partner annotation*
  that re-prioritizes those rows and surfaces near-twins no keyword sweep isolates.

## Refresh cadence

**Quarterly**, with an event-driven re-run when a batch of new partners closes
or when partner AGMV data refreshes. The fingerprint dimensions are durable
(suppliers, neighborhood, pedigree, vocabulary move slowly), so frequent
re-scraping wastes Apify spend. What changes is the *seed set and its AGMV
weights*: a newly-closed top-decile partner is a fresh high-weight fingerprint
that can surface a new neighborhood of twins, so trigger off partner-roster /
AGMV growth rather than a fixed clock alone.

## Risks

- **Seed quality and AGMV weighting are everything.** This engine is only as good
  as the "strong partner" definition. A leaky AGMV floor (or stale AGMV data)
  lets lookalikes of mediocre partners rank as Tier 1. Keep the floor strict and
  the seed set partner-weighted; never auto-ingest exemplars unvetted.
- **Single-dimension false positives.** Same neighborhood OR same reservation
  platform alone is near-meaningless — half the destination restaurants in a
  metro share both. The `dim_hits >= 2` gate exists precisely for this; never
  promote a one-dimension match above Tier 3.
- **Anti-ICP leakage through the fingerprint.** A wine seed's neighbors include
  liquor stores and excluded wine bars; a restaurant seed's include cocktail bars
  and ghost kitchens. Run `config.CHAIN_KEYWORDS` + `reclassify.py` (wine-bar
  claw-back) before any handoff. Screen wine candidates for commodity/liquor SKUs
  (Tito's, Veuve, Josh, Barefoot, Kendall Jackson, Yellowtail) and liquor-store
  ESP red flags (City Hive, Spot Hopper) — a near-twin on platform/neighborhood
  that carries Tito's is a liquor store, not a wine merchant.
- **Sweets-only / single-product demotion.** A bakery surfaced as a lookalike of
  a pastry-led partner is still capped at Tier 2 per ICP single-product rules;
  carry partner_type and apply the cap downstream — fingerprint similarity can't
  mint a Tier 1 single-SKU shop.
- **Small-market thinness.** A dominant rural butcher that is a near-twin of an
  urban partner may have thin social/press, so F4/F5 will under-fire. Lean on
  F1/F3/F7 (supplier, neighborhood, vocabulary), weight relative local dominance,
  and don't DQ on raw social — static-only social understates these brands.
- **FB blind spot.** F5 (commenters) runs on IG only, but for butcher / deli /
  specialty-grocer, Facebook engagement often beats IG — the highest-AGMV
  verticals are exactly where F5 undercounts. Carry `fb_handle`; treat F5 as
  optional weight for those types and lean on F1/F7. Flag as a known gap.
- **Vocabulary overfitting.** F7 can match on generic foodie boilerplate
  ("locally sourced", "seasonal") rather than discriminating craft terms. TF-IDF
  against the full candidate corpus (not raw term presence) is required so common
  phrases self-deweight; audit the top-term list periodically.
- **Platform fragility.** IG comment/post actors and tagged-posts hit anti-bot
  and return partial coverage; the Resy client (F2) is reverse-engineered and
  fragile. Mirror `enrich.py` batching/retry; never block a run on one failed
  dimension — a fingerprint with 5 of 7 dims is still usable.

## Repo placement

```
social_graph/                          # existing package (Engines 01/11/28 live here)
  __init__.py
  partner_seeds.csv                    # EXISTING (Engine 11): closed partners + exemplars
  partner_fingerprints.py              # NEW: build per-seed F1-F7 fingerprint records
                                       #      (reuses supplier/comment/co-press/press extractors)
  fetch_lookalike_candidates.py        # NEW: union first-degree candidate pool from
                                       #      supplier(29)/comment(28)/co-press(11) neighbors
  score_lookalikes.py                  # NEW: per-dimension match + AGMV-weighted sim_score,
                                       #      tiering, emit canonical CSV
discover_almost_partner_lookalikes.py  # NEW orchestrator at repo root, mirrors
                                       #   discover_ig_graph.py: --fingerprint --candidates
                                       #   --score --limit --agmv-floor
config.py                              # ADD: APIFY_ACTOR_IG_PROFILE/_TAGGED if not already
                                       #      added by Engine 11; aggregator deny-list
```

Refactor target: this engine depends on Engines 11/28/29 existing as **importable
libraries**, not just CLI scripts. Lift the shared pieces into reusable modules
first — the IG Apify client (`enrich_ig_lib.py`, per Engine 11's refactor note),
Engine 29's `_supplier_graph.py` Mode-C confirmation, Engine 28's comment-graph
extractor, and the co-press `llm_extract` co-name pass — then `partner_fingerprints.py`
and `fetch_lookalike_candidates.py` orchestrate them. Also expose `enrich.py`
step-1 platform detection and step-8 availability helpers as a small lib so F2 can
call them without running the full enrichment pass.

## Open questions

1. Where does **per-partner Peak AGMV** live (HubSpot? a roster CSV?), and is it
   fresh enough to gate seeds on? Without per-partner AGMV the engine falls back
   to partner-type-average weighting — materially coarser. This is the critical input.
2. What is the right **`dim_hits` threshold and per-dimension weight**? Should F7
   (vocabulary) and F1 (suppliers) — the hardest dims to share by chance — count
   double toward the Tier-1 gate? Needs a calibration pass against known closed partners.
3. Do Engines 11/28/29 ship **before** this one (so their extractors exist to
   reuse), or does Engine 39 absorb their candidate-generation logic if they're
   not built? This determines whether 39 is a thin fusion layer or a much larger build.
4. Should an almost-partner hit **stamp the similarity evidence onto an existing
   high-ICP row** (like Engine 04) as well as mint net-new candidates, so the
   "twin of {partner}" cite is available even for already-known shops?
