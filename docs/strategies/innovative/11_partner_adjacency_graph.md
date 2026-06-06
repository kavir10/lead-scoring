# Lead Engine 11 — Partner-Adjacency Graph

**Motion:** Curation
**Vertical fit:** All high-fit verticals, strongest for wine / butcher / cheese / destination restaurants (the high-AGMV, socially-clustered partner types)
**Suggested list name(s):** `partner_adjacency_graph`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $45/run (Apify IG actors over seeds + first-degree candidates, Serper Web for co-press, Haiku for comment/supplier mining)

## Premise

Great merchants cluster. A whole-animal butcher follows the three other
whole-animal butchers they respect; a natural-wine shop reposts the importer
tasting it just poured; a destination chef tags the cheesemonger who supplies
the board. These ties are **practitioner endorsements** — the people best
positioned to judge ICP fit are *already signaling it for us* through who they
follow, who they collaborate with, who they share suppliers with, and who they
publish alongside. "Followed by current Table22 partners" is the single
strongest seed-quality signal we can construct, because it's a revealed
judgment from operators we've already qualified and closed.

Engine 01 (`somm_chef_ig_graph`) rode the *person* graph from editorial seeds
(JBF semifinalists, Master Somms). This engine flips the seed set: it starts
from the **known-good business graph** — closed Table22 partners plus hand-picked
high-fit exemplars — and traverses outward across *four* adjacency channels
(follow-graph, co-press, event/collab tags, shared suppliers) rather than one.
The multi-channel intersection is the point: a candidate that shows up in two
or more channels is far more likely to be a real peer than a single-follow
artifact.

This is a pure **ICP-Fit amplifier**, not a Trigger engine. It answers "is this
the right *kind* of business?" with unusually high precision because the
judgment is borrowed from proven partners. It pairs naturally with any Trigger
overlay (Engines 03/04/05/08): adjacency gives you the right universe, the
trigger tells you when to call. On its own, a high-adjacency candidate with no
trigger is a strong **nurture** lead. Per the partner-type economics, biasing
seeds toward butcher / wine / cheese / destination keeps the highest-ceiling
peers at the front of the traversal.

## Recipe

Build as a new traversal mode inside the existing **`social_graph/`** package
(home of `discover_ig_graph.py` + `fetch_seed_posts.py` + `aggregate_venues.py`),
reusing its fetch/aggregate scaffolding. It is a discovery lane (emits canonical
rows), not a postprocessing overlay.

1. **Build the partner seed set — the load-bearing input.** Assemble
   `social_graph/partner_seeds.csv` (`name, partner_type, ig_handle, fb_handle,
   website, city, state, status`). Rows:
   - **Closed Table22 partners** with a resolved IG handle (status=`partner`) —
     the highest-weight seeds. Source from the partner roster / HubSpot export;
     this is a one-time manual build, refreshed as partners close.
   - **High-fit exemplars** (status=`exemplar`) — hand-picked best-in-class
     operators per vertical (the butcher/wine/cheese names sales already
     reveres) for verticals thin on closed partners.
   Bias the seed mix toward butcher / wine / cheese / destination per
   partner-type AGMV. Verify handles once; cheap.

2. **Channel A — Follow graph (who partners follow / who follows partners).**
   For each seed, pull the profile via the IG profile scraper (the actor
   `enrich.py` step 2 uses — register its ID in `config.py` alongside
   `APIFY_ACTOR_IG_REELS` / `APIFY_ACTOR_IG_POSTS`; it is not yet present).
   *Following* and *follower* lists are login-gated, so use the same
   cheaper-fallback Engine 01 settled on: pull each seed's last ~30 posts +
   reels (`instagram-post-scraper` / `instagram-reel-scraper`, batches of 30)
   and extract **collab authors, tagged accounts, and co-authors** as
   first-degree candidates. If a session token is available, the true
   following list is strictly better — gate it behind `--with-following`.

3. **Channel B — Tagged-by / collab graph.** Use `instagram-tagged-posts-scraper`
   (register the actor ID in `config.py`) to grab the last ~100 posts that tag
   each seed. The accounts doing the tagging are frequently the *venues
   themselves* (a wine bar tagging the importer, a restaurant tagging the
   butcher). Extract `tagged_by_handle` + `location.name/id`.

4. **Channel C — Co-press.** For each seed, run **Serper Web** (the primitive the
   `press` enrichment step uses) against food-media domains for articles that
   name the seed, then re-extract *other business names* co-listed in the same
   article via `awards/llm_extract.py` (Haiku, `unset ANTHROPIC_API_KEY &&`
   prefix). "Listed in the same Eater/Bon Appétit/Punch roundup as a known
   partner" is a strong co-membership edge.

5. **Channel D — Shared suppliers / importers / farms.** Mine seed websites
   and recent post captions for shared upstream entities (concurrent crawl, the
   `detect_clubs.py` 50-thread pattern). Two candidates that both name the same
   respected importer or farm are peers. Seed the entity lexicon from the ICP
   trust lists:
   - **Importers (wine):** `Skurnik`, `Louis/Dressner`, `Jenny & Francois`,
     `Selection Massale`, `Zev Rovine`, `Rosenthal`, `Polaner`, `Vom Boden`,
     `T. Edward`, `Jose Pastor`.
   - **Butcher upstream:** named local farms, `whole animal`, `nose to tail`,
     in-house `charcuterie` / `dry-age` (reuse Engine 06 lexicon).

6. **Resolve candidates to businesses.** Dedupe handles across channels;
   resolve each to a real venue (website + Google Maps) so the downstream
   pipeline can enrich it. Drop seeds themselves and any already-closed partner.

7. **Score adjacency (promotion gate — not `config.SCORING_WEIGHTS`):**

```
seed_weight        = 3 if status=="partner" else 1          # partner > exemplar
channel_hits       = distinct channels {A,B,C,D} candidate appears in
seed_frequency     = # distinct seeds referencing candidate
adjacency_quality  = sum(seed_weight over referencing seeds)
geo_bonus          = +1 if same metro as a referencing seed (peers cluster geographically)
recency_ok         = most-recent edge within 12 months

if channel_hits >= 2 and adjacency_quality >= 6:  tier = 1   # multi-channel, partner-endorsed
elif channel_hits >= 2 or adjacency_quality >= 4: tier = 2
elif seed_frequency >= 1 and recency_ok:          tier = 3   # single thin edge -> corroborate
else: drop
```

8. **Hand resolved candidates to the standard funnel.** Emit the canonical CSV
   below, then feed Tier 1/2 handles into `main.py --enrich` + `score.py` for
   ICP scoring, and `reclassify.py` for the wine-bar claw-back / partner-type
   demotions. Adjacency tier is the *seed-quality* annotation; `score.py`
   remains the source of truth for ICP Fit.

## Output schema

```
output/social_graph/partner_adjacency_graph_<YYYYMMDD>.csv
source = "partner_adjacency_graph"
tier = <1|2|3>                      # adjacency tier (seed-quality), not score.py tier
business_type = <best-guess from location.category + name heuristics; reclassify later>
distinction = "Adjacent to {n} T22 partners/exemplars via {channels}: {top_seed_names}"
year = <max edge year>
+ evidence cols:
    ig_handle, fb_handle, website, city, state,
    channel_hits, channels,                 # e.g. "follow,co_press"
    seed_frequency, adjacency_quality, geo_bonus,
    referencing_seeds,                       # verbatim seed names+types for outbound cite
    follow_edges, tagged_by_edges,           # sample handles
    co_press_articles,                       # source_urls of shared roundups
    shared_suppliers,                        # matched importers/farms
    last_edge_at, scan_date
```

`referencing_seeds` + `co_press_articles` preserve the exact endorsement so a
BDR can open with "you're followed by / written up alongside {partner}" — the
cite-the-trigger evidence that justifies a Curation list.

## Volume & cost

- Seeds: ~150-250 (partners + exemplars).
- Channel A/B IG pulls: ~250 seeds × (30 posts + 30 reels + 100 tagged) at
  Apify IG rates ≈ $0.015-0.02/seed ⇒ **~$5**.
- First-degree candidate profile confirmations (~1,500 raw → ~600 unique):
  profile scraper batches of 30 ≈ **~$8-12**.
- Channel C co-press: ~250 Serper Web queries (~$1) + Haiku co-name extraction
  on ~150 articles ≈ **~$5**.
- Channel D supplier mining: site crawl free; Haiku caption pass ≈ **~$3-5**.
- **Per-run total: ~$25-40.**
- **Net-new candidates per run: ~500-900 unique, of which ~80-160 reach Tier 1**
  (multi-channel, partner-endorsed). Overlap with the existing universe is
  expected; the value is the *partner-endorsement annotation* that re-prioritizes
  and surfaces peers no keyword search reaches.

## Refresh cadence

**Quarterly**, with an event-driven re-run whenever a batch of new partners
closes. The follow/collab/supplier graph moves slowly — a peer relationship is
durable — so frequent re-scraping wastes Apify spend. The seed set, not the
graph, is what changes: every new closed partner is a new high-weight seed that
can surface a fresh neighborhood of peers, so trigger a re-run on partner-roster
growth rather than on a fixed clock alone.

## Risks

- **Seed-list quality is everything.** Garbage or off-ICP seeds propagate
  outward. Keep seeds curated and partner-weighted; never auto-ingest exemplars
  from an unvetted list.
- **Homophily ≠ ICP.** Partners follow vendors, media, friends, and personal
  accounts, not only peers. A high follow-count alone is noise — that's why the
  gate requires `channel_hits >= 2` or strong `adjacency_quality`. Single-follow
  edges land Tier 3 for corroboration only.
- **Anti-ICP leakage through the graph.** A wine shop seed will be adjacent to
  liquor stores, distributors, and excluded wine bars; a restaurant seed to
  cocktail bars and ghost kitchens. Run `reclassify.py` (wine-bar claw-back) and
  `config.CHAIN_KEYWORDS` chain filtering on resolved candidates *before* any
  sales handoff. Screen wine candidates for commodity/liquor SKUs (Tito's,
  Veuve, Josh, Barefoot, Kendall Jackson, Yellowtail, etc.) and ESP red flags
  (City Hive, Spot Hopper) — these are liquor-store tells, not curated-wine peers.
- **Sweets-only / single-product demotion.** A bakery surfaced via a pastry-chef
  seed is still capped at Tier 2 per ICP rules; carry partner_type and apply the
  cap downstream — adjacency strength can't mint a Tier 1 single-SKU shop.
- **Small-market peers look thin.** A dominant small-town butcher adjacent to a
  partner may have low follower/post volume. Don't DQ on raw social — the
  adjacency edge *is* the signal; lean on `geo_bonus` and relative local
  dominance. Static-only social understates these brands.
- **FB blind spot.** For butcher / deli / specialty-grocer, Facebook engagement
  and collab tagging often beat IG, and the IG actors miss FB edges entirely.
  Channel A/B will undercount exactly the highest-AGMV verticals. Carry
  `fb_handle` and flag as a known gap (see Open questions).
- **Platform fragility.** Following/follower lists are login-gated; tagged-posts
  and profile actors hit IG anti-bot and return partial coverage. Mirror
  `enrich.py` batching/retry; never block the run on one failed batch. The true
  follow graph behind `--with-following` is fragile and optional.

## Repo placement

```
social_graph/                        # existing package (Engine 01 lives here)
  __init__.py
  partner_seeds.csv                  # NEW: closed partners + exemplars (hand-built)
  fetch_partner_graph.py             # NEW: channels A/B — profile + post/reel +
                                     #      tagged-posts pulls per seed (batches of 30)
  fetch_copress_edges.py             # NEW: channel C — Serper Web + llm_extract co-names
  mine_shared_suppliers.py           # NEW: channel D — site/caption importer+farm match
  aggregate_adjacency.py             # NEW: dedupe edges, score adjacency, emit canonical CSV
discover_partner_adjacency.py        # NEW orchestrator at repo root, mirrors
                                     # discover_ig_graph.py: --fetch --copress
                                     # --suppliers --aggregate --limit --with-following
config.py                            # ADD: APIFY_ACTOR_IG_PROFILE,
                                     #      APIFY_ACTOR_IG_TAGGED actor IDs (not yet present)
```

Refactor target: lift the IG profile/post/reel Apify wrapper (actor IDs,
batching of 30, retry) out of both `enrich.py` (steps 2/6/7) and Engine 01's
`fetch_seed_posts.py` into a shared `enrich_ig_lib.py`, so all three IG lanes
call one client. Reuse the importer/farm lexicon from Engine 06's butcher and
Engine 07's wine modules rather than re-listing it.

## Open questions

1. Where is the canonical list of **closed Table22 partners with IG handles** —
   HubSpot export, a maintained roster CSV, or does this need a one-time manual
   build? This is the engine's critical input and determines launch effort.
2. Is the login-gated **true following list** worth the session-token fragility,
   or does the post/reel collab-tag fallback (Engine 01's choice) capture enough
   of the follow signal to skip it?
3. How do we close the **Facebook adjacency gap** for butcher / deli / grocer —
   does the `enrich_facebook()` HTML scrape expose FB page likes/tagged collabs,
   or is FB-graph traversal a genuinely new source lane needing its own actor?
4. Should a partner-adjacency hit **auto-re-prioritize an existing high-ICP row**
   (stamp the endorsement) as well as mint net-new candidates? The cite-the-
   partner value argues for stamping both, like Engine 04.
```
