# Lead Engine 40 — Chef and Sommelier Alumni Graph

**Motion:** Curation (a Trigger-first overlay; the *pedigree* of the departure also lifts ICP Fit)
**Vertical fit:** Restaurants (destination first), wine, bakery, butcher — anywhere a named operator's training pedigree predicts craft
**Suggested list name(s):** `chef_sommelier_alumni_graph`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$15–30 per run (Serper Web move-mining + Serper Maps resolution + a Haiku extraction pass; no new Apify spend unless the IG-announcement lane is enabled)

## Premise

The single best moment to start a Table22 relationship is **before the new
concept has SEO, review volume, or broad press** — when a respected chef, somm,
baker, or head butcher leaves a celebrated house to open their own place. At
that point the operator has maximum pedigree (revealed craft, borrowed from the
mothership) and minimum inbound competition (no one else is selling them
anything yet because they don't show up in Maps with 50 reviews). This engine
mines **departures and new-venture announcements** from the people whose
training is itself an ICP signal, and gets us in the room first.

It keys on the two-score model from both sides. The **departure is the
Trigger** ("congrats on the new place — saw you left {pedigree house}"); the
**pedigree is the ICP Fit lift** — an operator who ran the floor at a Master-Somm
program or cooked at a Michelin/JBF house is a high-craft bet even before the
metrics exist. This is exactly the lead the volume engines structurally miss:
static social and review counts **understate** a brand-new venue, so a discovery
lane gated on review floors will never see it. Pedigree is the substitute
signal. Partner Type still dominates SHAP, so a somm opening a wine shop or a
butcher opening a whole-animal counter outranks a line cook opening a fast-casual
spot — the *destination* concept, not just the move, is what we score.

It overlaps and shares infrastructure with `scripts/discover_ig_graph.py` and the
person-graph seed file behind Engine 01 / Engine 28 (`social_graph/industry_handles.csv`):
the same celebrated people whose **comments** endorse a merchant in Engine 28 are
the people whose **departures** mint a brand-new merchant here. High-pedigree but
no-concept-yet ("left, going dark") → nurture; high-trigger but weak-ICP
(corporate-chain promotion, a server "starting a delivery brand") → filter hard
before sales.

## Recipe

Build as a **discovery → match-to-known → enrich → score** loop (like Engine 25),
not a pure overlay: the move announcement surfaces businesses that by definition
are not yet in the corpus. CSV in (optional seed roster), CSV out, never mutates
input.

1. **Harvest departure / new-venture signals (Serper Web).** Reuse the press-step
   Serper Web primitive (`enrich.py` step 4, `google.serper.dev/search`) pointed
   at food-media + trade domains instead of award keywords. Two query families:

   ```
   MOVE_DOMAINS = [   # food trade + city-desk press that covers openings/departures
     "eater.com", "sfchronicle.com", "latimes.com", "chicagotribune.com",
     "nytimes.com", "bonappetit.com", "foodandwine.com", "robbreport.com",
     "winespectator.com", "sevenfifty.com/daily", "punchdrink.com",
     "guildofsommeliers.com", "starchefs.com", "restauranthospitality.com",
     "nrn.com", "thespoon.tech",
   ]
   MOVE_QUERIES = [
     # departure phrasing
     "leaves", "departs", "steps down", "exits", "no longer with",
     "former chef", "former sommelier", "former wine director",
     "alum of", "veteran of", "after years at",
     # new-venture phrasing
     "opening", "to open", "set to open", "debuts", "new restaurant from",
     "new wine shop from", "going out on their own", "first solo",
     "former {house} chef opens", "wine director leaves to open",
   ]
   ROLE_TERMS = ["chef","sommelier","wine director","head baker","pastry chef",
                 "head butcher","beverage director","general manager","partner"]
   ```

   Issue `"<role term>" (leaves OR opening OR "to open") site:<domain>` and the
   `former … opens` patterns. Bias the city-restricted passes toward
   `research/trendy_neighborhoods/` — new concepts cluster in trendy neighborhoods
   (~56.5% of partners). Capture article URL, headline, snippet, publish date.

2. **(Optional) IG announcement lane.** Founders announce the new place on
   personal IG before any press. For handles already in
   `social_graph/industry_handles.csv`, pull recent posts via
   `instagram-post-scraper` (the actor `enrich.py` step 7 already uses, batches of
   30) and keep only those whose caption matches the new-venture lexicon
   (`opening soon`, `my new`, `proud to announce`, `coming this {season}`,
   `@new_concept_handle`). This reuses cached `--enrich-remaining` payloads where
   present (cost-control rationale). Gate this lane behind a flag — press alone is
   the cheap happy path.

3. **Extract (person, pedigree house, new venture) with Haiku.** Run each article
   snippet + headline (and IG caption) through Claude
   (`claude-haiku-4-5-20251001`, the `scrape_beli` model;
   `awards/llm_extract.py` extraction style; prefix scripts with
   `unset ANTHROPIC_API_KEY &&` per the empty-key gotcha) to emit a structured row:
   `person_name, role, pedigree_house(s), pedigree_city, new_venture_name,
   new_venture_city, new_venture_type, status ∈ {announced|opening_soon|just_opened|rumored}`.
   Drop rows where the move is *into* a corporate role, a chain promotion, or where
   no distinct new self-owned venture is named.

4. **Score pedigree (the ICP-Fit lift).** Cross-reference `pedigree_house` against
   the existing award/editorial corpus we already scrape — `output/awards_all_*`
   (James Beard, Michelin via `michelin_direct`, World's 50 Best, Good Food
   Awards, etc.), Master Somm / Advanced Somm rosters, and the importer trust
   lexicon for wine pedigree (Skurnik, Louis/Dressner, Jenny & Francois, Selection
   Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor —
   "trained under / worked the book for {importer}"). A named, corpus-matched
   pedigree house is the high-confidence signal.

5. **Resolve new venture → business (Serper Maps + dedupe).** Many new ventures
   *won't* be in Maps yet (that's the point). For each `new_venture_name + city`,
   run `discover.py` / `scripts/fresh_icp_search.py` Serper Maps to attach a
   canonical record if one exists; **suspend the review/rating quality floors for
   this lane** (a 2-week-old venue has < 20 reviews by definition — the floor would
   wrongly drop our best leads). Then `dedupe_existing.py` (phone-first, then
   name+address) to tag `already_known` vs `net_new` and avoid double-counting.

6. **Enrich what exists, flag what doesn't.** For resolved venues run the standard
   `enrich.py` sequence as available — `websites` (step 1: ecommerce/email-signup/
   social/reservation-platform), `instagram`/`facebook` (steps 2–3:
   `follower_count`), and `availability` (step 8) for restaurants. For pre-open
   ventures with no website yet, carry the row as `status=announced` with the
   pedigree evidence and the founder's personal IG — enrichment fills in over
   subsequent refreshes.

7. **ICP gate + trigger score (curation pass).** Run `reclassify.py`
   (`partner_type`, wine-bar claw-back) and `config.CHAIN_KEYWORDS`. Then:

   ```
   DISQUALIFY if:
     new_venture is chain/franchise expansion (>=10 locations, CHAIN_KEYWORDS)
     move is INTO a corporate / restaurant-group role (not a self-owned venture)
     partner_type == liquor_store  OR  wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, Cupcake, BuzzBallz, ...)  OR  ESP red flag (City Hive, Spot Hopper)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first (non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}        # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery (pastry-chef pedigree is real but caps Tier 2)
     pre-open with no resolvable concept type yet (carry as nurture until concept firms up)

   pedigree_strength:
     +3 pedigree_house matches awards corpus (Michelin/JBF/World's-50/Good-Food)
     +3 somm/wine-director pedigree opening WINE/CHEESE/BUTCHER concept (top partner-type economics)
     +2 importer-trust pedigree on a wine concept (Skurnik/Dressner/ZRS/...)
     +2 Master/Advanced Somm roster match
     +1 status in {opening_soon, just_opened}        # hot, actionable trigger
     +1 new_venture_city in research/trendy_neighborhoods/

   QUALIFY if: passes ICP gate AND pedigree_strength >= 3
   ```

   Tier the trigger after ICP: pedigree match + named new self-owned venture +
   high-economics partner type = Tier 1. Qualified rows feed `main.py --enrich`
   (where resolvable) then `score.py` (standard `config.SCORING_WEIGHTS` — do not
   alter). Pedigree tier is an annotation that re-prioritizes, not a weight change.

## Output schema

```
output/social_graph/chef_sommelier_alumni_graph_<YYYYMMDD>.csv
source = "chef_sommelier_alumni_graph"
tier = <1|2|3>                       # pedigree-trigger tier (annotation), not score.py tier
business_type = <new_venture_type; reclassify downstream>
distinction = "{role} {person_name}, alum of {pedigree_house}, opening {new_venture_name} ({status})"
year = <year of the move/announcement>
+ evidence cols:
    person_name, role, pedigree_house, pedigree_city, pedigree_corpus_match,   # which award/roster matched
    new_venture_name, new_venture_city, new_venture_state, new_venture_type, status,
    founder_ig_handle, website,                       # website blank until venue exists
    pedigree_strength, importer_trust_match,          # wine pedigree tells
    already_known, net_new,
    source_url, headline_snippet,                     # verbatim press quote for outbound cite
    announcement_date, scan_date
```

`source_url` + `headline_snippet` + `pedigree_house` preserve the exact trigger
so a BDR opens with "saw you left {house} to open {venue} — congrats" and links
the article. That cite-the-trigger evidence is what makes this a Curation list,
not a cold blast.

## Volume & cost

- Move/opening coverage is naturally thin and time-bounded. Across `MOVE_DOMAINS`
  × `MOVE_QUERIES` (~16 domains × ~25 query stems, capped per query) ≈ **300–600
  Serper Web calls/run** at ~$0.001 each ⇒ **~$0.50–1.00 Serper Web**.
- Maps resolution on unique new ventures (~150–300 distinct names) ≈ **~$0.50**.
- Haiku extraction over ~300–600 snippets ≈ **~$3–6**.
- Optional IG-announcement lane (only if enabled): post pulls on seed handles ≈
  **$8–15**, mostly avoided by reusing cached payloads.
- **Per-run total: ~$5–10 press-only; ~$15–30 with the IG lane.**
- **Expected net-new qualified leads: ~30–80 per run**, of which a meaningful
  share are venues **not yet in the corpus** (the unique value). Low raw count by
  design — these are early, high-pedigree, low-competition leads, not a volume play.

## Refresh cadence

**Biweekly to monthly.** The signal is perishable: a departure is most valuable
in the announcement → opening window, and a stale "opening soon" from eight
months ago is either open (re-discoverable by normal lanes) or dead. Tighter than
the slow-moving comment graph (Engine 28) precisely because the trigger decays.
Re-run on demand when a major house publicly loses a name. The **pedigree corpus**
(awards/somm rosters) only needs refreshing when those upstream scrapes refresh.

## Risks

- **Pedigree ≠ ICP.** A celebrated chef can open a cocktail bar, a ghost kitchen,
  or a 12-unit fast-casual roll-out. The pedigree is real but the *concept* fails
  ICP. Gate on `new_venture_type` + `CHAIN_KEYWORDS` + `reclassify.py`, never on
  pedigree alone.
- **Suspended quality floors cut both ways.** Turning off the review/rating floor
  to catch new venues also lets in vaporware and rumor. Require a **named,
  corpus-matched pedigree** for Tier 1 and treat `status=rumored` as Tier 3
  nurture, not sales-ready.
- **Anti-ICP leakage.** Wine moves pull in liquor-store openings and excluded wine
  bars; restaurant moves pull cocktail bars and delivery brands. Screen wine rows
  for commodity/liquor SKUs (Tito's, Veuve, Barefoot, Yellowtail, Kendall Jackson)
  and ESP red flags (City Hive, Spot Hopper); apply the wine-bar claw-back.
- **Chain/group promotions masquerade as "moves."** "Chef X named culinary
  director of {20-unit group}" is a corporate promotion, not a self-owned venture.
  Drop in step 3 and re-screen with `CHAIN_KEYWORDS` — restaurant groups generate
  the most press noise here.
- **Sweets-only / single-product demotion.** A pastry chef opening a dessert-only
  shop is real pedigree but caps at Tier 2 per ICP rules; carry `partner_type` and
  apply the cap downstream.
- **Small-market understatement.** A regional chef opening in a secondary market
  gets little national press; lean on local city-desk domains and regional best-of
  context, and weight relative local pedigree — don't DQ for thin national coverage.
- **Butcher pedigree is sparse in press.** The butcher universe is tiny (~1,000–1,200
  shops) and head-butcher moves rarely make Eater; expect this lane to under-cover
  butcher and lean on `discover_butchers.py` alt-source lanes (Good Meat Finder,
  EatWild, Good Food Awards) for that vertical instead.
- **Platform / extraction fragility.** Press paywalls truncate snippets; Haiku can
  hallucinate a pedigree house not in the text. Constrain extraction to entities
  present in the snippet, require the `pedigree_corpus_match` to be a real corpus
  hit (not LLM assertion) for Tier 1, and flag low-confidence rows rather than
  scoring them up. Mirror `enrich.py` retry/never-block-the-run discipline on
  Serper batches.

## Repo placement

```
social_graph/                         # existing person-graph package (Engines 01/28 live here)
  __init__.py
  industry_handles.csv                # SHARED seed list — founders here are the same people
  pedigree_corpus.py                  # NEW: load + index awards_all_* / somm rosters / importer lexicon
  harvest_moves.py                    # NEW: Serper Web move/opening mining (MOVE_DOMAINS x MOVE_QUERIES)
  extract_moves.py                    # NEW: Haiku -> (person, pedigree, new venture, status)
  resolve_ventures.py                 # NEW: Serper Maps resolve + dedupe_existing, floors SUSPENDED
  score_alumni_graph.py               # NEW: pedigree gate + ICP screen, emit canonical CSV
discover_chef_sommelier_alumni_graph.py   # NEW orchestrator at repo root, mirrors discover_ig_graph.py:
                                      #   --harvest --extract --resolve --score
                                      #   --enable-ig-lane --limit --use-cache --resume
config.py                             # ADD: MOVE_DOMAINS, MOVE_QUERIES, ROLE_TERMS, new-venture lexicon
                                      #      (post-scraper actor ID already present for the IG lane)
```

Refactor targets: (1) lift the Serper Web wrapper out of `enrich.py` step 4
(press) into a shared `serper_web_lib.py` so the move-mining lane reuses one
retry/rate-limit client; (2) expose `discover.py` Maps resolution with a
`suspend_quality_floors` flag so this lane (and any pre-open lane) can resolve
brand-new venues without forking the function; (3) reuse Engine 07's wine
importer-trust lexicon for `pedigree_corpus.py`.

## Open questions

1. Where is the canonical **pedigree corpus** — do we already have Master/Advanced
   Somm rosters scraped anywhere, or is that a one-time build alongside
   `output/awards_all_*`? Pedigree matching quality is the whole engine.
2. What's the right **freshness window** to keep a row sales-ready — does an
   `opening_soon` row expire (and drop to nurture) after N weeks if it never
   resolves to a real Maps venue?
3. Should a **pre-open, no-website** Tier 1 row enter the sales funnel immediately
   (relationship-building play) or sit in a separate "watchlist" tab until the
   venue physically opens and `enrich.py` can score it?
4. Is the **IG-announcement lane** worth its Apify cost over press alone, given
   most newsworthy moves get at least a one-line Eater hit that the cheap Serper
   Web lane already catches?
