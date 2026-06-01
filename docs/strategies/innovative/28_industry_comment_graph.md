# Lead Engine 28 — Industry Comment Graph

**Motion:** Curation
**Vertical fit:** All high-fit verticals; sharpest for wine / butcher / cheese / destination restaurants where peer endorsement carries the most ICP signal and where follower counts most badly misrepresent real brand
**Suggested list name(s):** `industry_comment_graph`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $40/run (Apify IG post/reel scrapes over a candidate pool + seed-handle matching + Haiku name resolution)

## Premise

A 2K-follower butcher whose every post draws comments from three respected
chefs, the somm down the street, and a current Table22 partner is a far better
prospect than a 50K-follower account that gets nothing but emoji from
randos. **Who is in the comments is a revealed practitioner judgment** — the
people best positioned to assess a merchant's craft are endorsing it publicly,
for free, in a way no follower count or review volume captures. This engine
turns that endorsement into a measurable, citeable signal.

It directly attacks two SHAP-aligned blind spots. First, Follower Count is a
weak, gameable signal and engagement (video views > shares > comments > likes)
is what predicts Peak AGMV — but *comment identity*, not comment volume, is an
even higher-resolution read on brand: ten comments from named industry people
beats a thousand from nobody. Second, static-only social **understates** small
and regional brands; a celebrated small-market shop with a thin feed but an
A-list comment section is exactly the lead the volume metrics miss.

This is an **ICP-Fit amplifier**, not a Trigger engine — it answers "is this
the right *kind* of business?" using borrowed judgment from operators we
already trust. It overlaps with and complements Engine 11 (Partner-Adjacency
Graph): Engine 11 traverses *outward* from partner accounts to find who they
collaborate with; this engine looks *inward* at any candidate's comment section
and scores the industry density of who shows up. The two share a seed list and
should share infrastructure. On its own a high-comment-density candidate with
no trigger is a strong **nurture** lead; pair with any Trigger overlay
(Engines 03/04/05/08) for both-high lists.

## Recipe

Build as a **postprocessing overlay**, not a discovery lane: it scores an
existing candidate pool (a `2_enriched_*` CSV or a `_discovered` CSV with IG
handles) by mining the comment authors on that candidate's own posts. It does
not mint net-new venues by itself — it re-prioritizes the universe by
endorsement density. CSV in, CSV out, never mutates input (the `detect_clubs.py`
contract).

1. **Build the industry-handle seed list — the load-bearing input.** Assemble
   `social_graph/industry_handles.csv` (`handle, person_name, role, vertical,
   weight, source`). This is the same person-graph universe Engine 01
   (`somm_chef_ig_graph`) and `scripts/discover_ig_graph.py` already seed from;
   **reuse and extend that seed file** rather than building a parallel one.
   Roles and weights:
   - `partner` (weight 5) — owner/operator handles of **closed Table22
     partners** (source from the partner roster / HubSpot export). Highest
     weight: a comment from a proven partner is the strongest endorsement.
   - `critic_writer` (weight 3) — national + **local** food writers/critics
     (Eater city editors, regional James Beard media seeds).
   - `chef` / `somm` / `baker` / `butcher` / `importer` (weight 3) — named
     practitioners; seed somms/chefs from JBF semifinalist + Master Somm lists
     (Engine 01's source), importers from the ICP trust list (Skurnik,
     Louis/Dressner, Jenny & Francois, Selection Massale, Zev Rovine, Rosenthal,
     Polaner, Vom Boden, T. Edward, Jose Pastor).
   - `peer_business` (weight 2) — high-fit exemplar business accounts per
     vertical (the names sales reveres).
   Resolve handles once; cheap and durable.

2. **Pull each candidate's own posts + their comment threads.** For every
   candidate with an `ig_handle`, scrape the last ~20-30 posts and ~10 reels via
   `instagram-post-scraper` / `instagram-reel-scraper` (Apify, batches of 30 —
   the actors `enrich.py` steps 6/7 already use). These actors return commenter
   handles per post (request comments in the actor input). This reuses the exact
   same Apify pulls Engine 01 and the reels/posts enrichment steps run — if a
   candidate already went through `--enrich-remaining`, **reuse the cached
   post/reel payload** instead of re-scraping (cost-control, mirrors the
   `--enrich-remaining` rationale).

3. **Match commenters against the seed list.** For each candidate, collect the
   set of distinct commenter handles across all pulled posts, normalize (strip
   `@`, lowercase), and intersect with `industry_handles.csv`. Count both
   *which* seeds commented and *how often*. Co-authors / collab tags from the
   same payload also count (a partner co-posting is a stronger endorsement than
   a comment) — fold them in at the same weight as the seed's role.

4. **Resolve ambiguous / unseeded high-signal commenters with Haiku.** Many real
   industry commenters won't be in the seed list. Take the top-N most-frequent
   *unseeded* commenters on high-fit candidates and run a cheap Haiku pass
   (`awards/llm_extract.py` style, `unset ANTHROPIC_API_KEY &&` prefix) over
   their handle + bio to classify role (`chef|somm|butcher|baker|importer|
   critic|civilian`). Confirmed practitioners get the role's weight and are
   appended back to `industry_handles.csv` so the seed list compounds run over
   run. Keep this bounded (only the top unseeded commenters) to cap LLM spend.

5. **Score comment-graph density (promotion gate — NOT `config.SCORING_WEIGHTS`):**

```
seed_hits          = distinct seeded handles that commented/collabbed on candidate
seed_weight_sum    = sum(weight over those seeds)          # partner=5, practitioner=3, peer=2
partner_present    = any commenting seed has role=="partner"
role_breadth       = distinct roles among commenting seeds  # chef+somm+critic > 3 chefs
recency_ok         = >=1 seeded comment within last 12 months
comment_quality    = seed_weight_sum / max(total_distinct_commenters, 1)   # density, not raw count

if partner_present and seed_hits >= 2:                tier = 1   # partner-endorsed peer
elif seed_weight_sum >= 9 or role_breadth >= 3:       tier = 1   # dense, cross-role endorsement
elif seed_hits >= 2 and recency_ok:                   tier = 2
elif seed_hits >= 1 and recency_ok:                   tier = 3   # single thin endorsement -> corroborate
else: drop (no industry signal in comments)
```

   `comment_quality` (density) is the antidote to vanity accounts: a 50K-follower
   page with two seeded comments out of thousands scores low; a 2K-follower shop
   where seeded handles are a meaningful share of the comment section scores high.

6. **Stamp the annotation back onto the candidate row and hand to the funnel.**
   Emit the canonical CSV below. The comment-graph tier is a *seed-quality*
   annotation; it re-prioritizes within `score.py`'s ICP ranking — it does not
   replace it. Run `reclassify.py` (wine-bar claw-back, partner-type demotions)
   and `config.CHAIN_KEYWORDS` filtering before any sales handoff. Tier 1/2 rows
   feed `main.py --enrich` (if not already enriched) + `score.py`.

## Output schema

```
output/social_graph/industry_comment_graph_<YYYYMMDD>.csv
source = "industry_comment_graph"
tier = <1|2|3>                       # comment-graph endorsement tier (seed-quality), not score.py tier
business_type = <carried from input candidate; reclassify downstream>
distinction = "Comment-endorsed by {n} industry handles ({roles}); incl. {top_named_seeds}"
year = <max seeded-comment year>
+ evidence cols:
    ig_handle, person_name_owner, website, city, state,
    seed_hits, seed_weight_sum, partner_present, role_breadth,
    comment_quality,                       # density ratio
    total_distinct_commenters,             # denominator (exposes vanity vs real)
    seeded_commenters,                      # verbatim handles+roles+person_name for outbound cite
    sample_comment_urls,                    # permalinks to the endorsing comments
    collab_coauthors,                       # handles that co-posted (stronger than a comment)
    newly_resolved_handles,                 # Haiku-confirmed practitioners added this run
    last_seeded_comment_at, scan_date
```

`seeded_commenters` + `sample_comment_urls` preserve the exact endorsement so a
BDR can open with "you've got {partner/chef} in your comments" and link the
proof — cite-the-trigger evidence that justifies a Curation list.

## Volume & cost

- This overlay scores an existing pool, so "net-new leads" = **re-prioritized
  rows surfaced from the existing universe**, not fresh venues. Typical pool:
  ~2,000-4,000 candidates with IG handles.
- Post/reel comment pulls: ~3,000 candidates × (~25 posts + ~10 reels w/
  comments) at Apify IG rates ≈ $0.015-0.025/candidate ⇒ **~$45-75 if scraped
  cold**. Reuse cached `--enrich-remaining` payloads where present to cut this
  by 50-70% ⇒ **~$15-25 in practice**.
- Haiku role-resolution on top unseeded commenters (~500-1,000 handle+bio
  classifications) ≈ **~$3-6**.
- Serper / website: none required (operates on handles already in the pool).
- **Per-run total: ~$20-35** with cache reuse; ~$60-80 fully cold.
- **Expected promotions: ~150-350 candidates reach Tier 1/2** out of a 3,000-row
  pool — i.e. the ~5-12% with genuine industry presence in their comments. The
  value is the re-ranking + the citeable endorsement, not raw count.

## Refresh cadence

**Quarterly**, or event-driven on a fresh discovery batch / new partner cohort.
The comment graph moves slowly — a chef who comments on a butcher this quarter
likely did last quarter too — so frequent re-scraping wastes Apify spend. The
**seed list** is what compounds: every new closed partner is a new weight-5 seed,
and step 4's Haiku-confirmed handles accrete each run, so a candidate that
scored Tier 3 last quarter can promote on seed-list growth alone without a
re-scrape. Trigger a re-run on partner-roster growth or a new discovery wave
rather than a fixed clock alone.

## Risks

- **Seed-list quality is everything.** Off-ICP or wrong-attribution seeds
  manufacture fake endorsements. Curate handles, verify person↔handle mapping,
  and never auto-promote a Haiku-classified handle to weight 5.
- **Comment volume ≠ endorsement.** A high *raw* seeded-comment count on a giant
  account can be noise; that's why the gate leans on `comment_quality` (density)
  and `role_breadth`. Three chefs is a weaker, narrower signal than chef + somm +
  critic together.
- **Reciprocal-comment / engagement-pod inflation.** Operators comment on each
  other to game reach. A single mutual-follow pair trading comments isn't an
  endorsement web — require `seed_hits >= 2` (distinct seeds) for Tier 1/2 and
  treat single-seed hits as Tier 3 corroboration only.
- **Anti-ICP leakage.** A wine candidate's comment section pulls in liquor
  stores, distributors, and excluded wine bars; restaurants pull cocktail bars
  and ghost kitchens. Run `reclassify.py` wine-bar claw-back + `CHAIN_KEYWORDS`
  on candidates, and screen wine rows for commodity/liquor SKUs (Tito's, Veuve,
  Josh, Barefoot, Kendall Jackson, Yellowtail, etc.) and ESP red flags (City
  Hive, Spot Hopper) before handoff — these are liquor-store tells, not peers.
- **Sweets-only / single-product demotion.** A bakery lit up by pastry-chef
  comments is still capped at Tier 2 per ICP rules; carry partner_type and apply
  the cap downstream — comment density can't mint a Tier 1 single-SKU shop.
- **FB blind spot.** For butcher / deli / specialty-grocer, Facebook comment
  engagement often beats IG, and the IG actors miss it entirely — this engine
  will *undercount* exactly the highest-AGMV verticals. `enrich_facebook()` today
  scrapes likes, not comment authors; FB comment mining is a genuine gap (see
  Open questions). Don't DQ a low-IG-comment butcher.
- **Small-market understatement.** A dominant small-town shop may have few posts
  and few commenters; a couple of seeded regional-critic comments *is* the
  signal. Lean on `comment_quality` density and don't DQ on raw volume — static
  social understates these brands.
- **Platform fragility.** Comment scraping hits IG anti-bot and returns partial
  threads (top comments only, truncated lists). Mirror `enrich.py` batching/retry;
  never block the run on a failed batch; treat coverage as best-effort and flag
  low-coverage candidates rather than scoring them zero.

## Repo placement

```
social_graph/                        # existing package (Engine 01 / 11 live here)
  __init__.py
  industry_handles.csv               # SHARED seed list (extend Engine 01's), grows via step 4
  fetch_candidate_comments.py        # NEW: post/reel+comment pulls per candidate (batches of 30),
                                     #      reuse cached --enrich-remaining payloads when present
  resolve_commenters.py              # NEW: step 4 — Haiku role-classify top unseeded commenters,
                                     #      append confirmed handles back to industry_handles.csv
  score_comment_graph.py             # NEW: intersect commenters w/ seeds, density score, emit CSV
discover_industry_comment_graph.py   # NEW orchestrator at repo root, mirrors discover_ig_graph.py:
                                     #   --input <candidates.csv> --fetch --resolve --score
                                     #   --limit --use-cache --resume
config.py                            # ADD: APIFY_ACTOR_IG_PROFILE actor ID if bio fetch needed
                                     #      for step 4 (post/reel actor IDs already present)
```

Refactor target: lift the IG post/reel Apify wrapper (actor IDs, batch-of-30,
retry, **comment extraction**) out of `enrich.py` steps 6/7 and Engine 01's
`fetch_seed_posts.py` into a shared `enrich_ig_lib.py`, so all three IG lanes
call one client and comment-author parsing lives in one place. Reuse the
importer trust lexicon from Engine 07's wine module for seeding importer handles.

## Open questions

1. Do the `instagram-post-scraper` / `instagram-reel-scraper` actors reliably
   return **full commenter handle lists** (vs only top-N comments), and at what
   per-post cost with comments enabled? This sets the real cost and coverage
   ceiling.
2. Where is the canonical **closed-partner owner-handle list**? Partner *business*
   handles are easier than the *owner/operator personal* handles that actually
   show up in comments — which do we have, and is a one-time manual build needed?
3. How do we close the **Facebook comment gap** for butcher / deli / grocer — can
   `enrich_facebook()` be extended to pull FB post comment authors, or is FB
   comment mining a genuinely new source lane needing its own actor?
4. Should the comment-graph hit **auto-stamp an existing high-ICP row** (re-rank
   in place) as well as drive a standalone list — and does a Tier 1 comment-graph
   endorsement justify nudging an otherwise-borderline row over the A/B tier line
   in `score.py`, or stay strictly an annotation?
