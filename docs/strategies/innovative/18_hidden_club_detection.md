# Lead Engine 18 — Hidden Club Detection

**Motion:** Curation (a Trigger-rich overlay that re-reads already-discovered, in-vertical rows for an un-labeled recurring product)
**Vertical fit:** Wine, butcher, bakery, cheese, specialty grocers (the high-headroom, recurring-product-native partner types)
**Suggested list name(s):** `hidden_club_detection`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$10–18 per run (one extra `detect_clubs`-style site crawl + a small Claude classification pass; no Apify, no Serper Web)

## Premise

`detect_clubs.py` is tuned to find businesses that *call* their program a club, subscription, or membership. But the most valuable prospects are the ones running a proto-Table22 product **without subscription language**: an "allocation" list at a wine shop, a "monthly pickup" or "standing order" at a butcher, a "bread share" at a bakery, a "case club" or "wine allotment," a "members-only" tasting list, "first access" drops, a "butcher box," a "farm box." These shops have already manufactured recurring demand and a captive buyer list — they have proven the behavior Table22 monetizes — but their tooling is a spreadsheet, a Google Form, a text thread, or a DM-to-reserve flow. They are not searching for "how do I start a subscription"; they already run one and don't know it.

That makes them the sharpest two-score leads in the book: **high ICP Fit** (we run only over already-qualified, in-vertical rows in the recurring-product-native partner types — butcher $75.9k, wine $68.2k, cheese $63.8k) and **high Trigger** ("You already run an allocation list / a bread share / a standing-order book — Table22 turns that manual program into recurring revenue without the spreadsheet"). This is squarely the demand-over-capacity thesis: a hidden club is *demonstrated* repeat demand that has outrun the operator's capacity to administer it manually. Existing-club is already a known positive signal for a platform-switch sale; a *hidden* club is the same signal earlier in its lifecycle — proven demand, zero platform lock-in, nothing to rip out.

It is **Curation**, not Volume: the output is small, hand-citable, and each row carries the exact phrase that proves the program exists. The engine's job is precision on a fuzzy, un-labeled signal — extending `detect_clubs.py`'s vocabulary and adding an LLM adjudication layer so "allocation" the wine term is caught while "allocation" the accounting word is not.

## Recipe

A **postprocessing overlay**: it consumes an already-discovered + (ideally) `websites`-enriched CSV and emits a small, evidence-tagged CSV. It does not run Serper discovery itself.

1. **Input.** Take a `websites`-enriched or scored CSV (`output/2_enriched_websites.csv` or a `custom-serper-scoring_*_all.csv`). Every row already has a `website`, passed quality floors, and cleared `CHAIN_KEYWORDS`. Restrict to recurring-product-native verticals: `business_type in {wine, butcher, bakery, cheese, specialty_grocer}`. Do not re-discover.

2. **Run the standard club scan first (`detect_clubs.py`).** Run `detect_clubs.py` / `detect_clubs_v2.py` (50-thread crawl, `--resume`) to populate `has_club`, `club_type`, `club_url`, `club_signals`. Rows already flagged `has_club == True` by explicit language are **not this engine's catch** — they belong to the labeled-club transition lists (Engine 01). This engine targets the *gap*: rows `detect_clubs` marked `has_club == False`.

3. **Extend the signal vocabulary (the core of this engine).** Add a `HIDDEN_CLUB_SIGNALS` lexicon to `detect_clubs.py` (or a sibling module) and re-scan the crawled HTML + a link probe over `/allocations`, `/standing-order`, `/share`, `/box`, `/list`, `/members`, `/reserve`. These are the un-labeled recurring-program tells, grouped so the matched group becomes evidence:

   ```
   wine:        allocation(s), wine allotment, case club, bottle list,
                first access, library release, "join the list", "get on the list",
                offer email, mailing list (release), futures, en primeur
   butcher:     standing order, monthly pickup, butcher box, meat box,
                whole/half/quarter share, "reserve your" (cut|roast|bird),
                holiday pre-order list, animal share, cow share, hog share
   bakery:      bread share, bread club (unlabeled), weekly pickup,
                standing bread order, pre-order (loaf|baguette), croissant subscription-by-text
   cheese:      cheese share, monthly cheese, affinage/aging reserve list,
                "by allocation"
   grocer/CSA:  farm box, CSA, market share, weekly box, members only,
                "text us to reserve", standing grocery order
   generic:     waitlist, "DM to reserve", "first dibs", "members get",
                "limited", "drops" (recurring), preorder calendar
   ```

   Emit `hidden_signal_hits` (pipe-joined matched phrases) and `hidden_signal_groups` (which lexicon buckets fired).

4. **LLM adjudication (`awards/llm_extract.py` pattern, Claude Haiku).** Regex over fuzzy terms ("allocation," "share," "members only," "list") is noisy. For any row with ≥1 hidden-signal hit, pass the surrounding HTML snippet(s) + the page text to a Claude classifier (reuse `awards/llm_extract.py` plumbing; `claude-haiku-4-5-20251001` as in `scrape_beli`). Prompt it to answer a tight schema:

   ```
   is_recurring_program: bool        # is this an actual recurring/standing buyer program?
   program_type: allocation|standing_order|share|box|members_list|preorder|none
   labeled_as_subscription: bool     # did they use sub/club/membership words? (if true -> not "hidden")
   recurrence_evidence: str          # the verbatim phrase proving recurrence
   confidence: 0.0-1.0
   ```

   Keep rows where `is_recurring_program == True` AND `labeled_as_subscription == False` (i.e. a real program, not called a subscription) AND `confidence >= 0.6`. Remember the empty-`ANTHROPIC_API_KEY` shell gotcha — prefix the run with `unset ANTHROPIC_API_KEY &&`.

5. **Tiering by program concreteness × vertical economics.** A standing-order book with named pickup cadence is a stronger trigger than a vague "join the list." Weight toward the high-AGMV verticals.

   ```
   strength = confidence
            + 0.3 if program_type in {standing_order, share, box}     # committed recurrence
            + 0.2 if business_type in {butcher, wine, cheese}         # top-3 AGMV headroom
            + 0.2 if has_esp (from websites crawl)                    # a list to migrate
   tier 1  if is_recurring_program and program_type in {allocation,standing_order,share,box} and strength >= 1.1
   tier 2  if is_recurring_program and strength >= 0.8
   tier 3  if is_recurring_program (members_list / preorder / weak signal)
   drop    otherwise
   ```

6. **Liquor-store / commodity-wine guard.** "Allocation" and "futures" are genuine fine-wine terms but also appear on liquor sites pushing allocated Bourbon/commodity SKUs. For `business_type == wine`, demote to tier 3 and flag `liquor_store_suspect=True` if the page surfaces commodity/exclusion SKUs (Tito's, Veuve, Josh, Barefoot, Kendall Jackson, Meiomi, Yellowtail, Apothic, etc.) or runs a liquor-store ESP (City Hive, Spot Hopper). Trust signals push the other way — an importer logo (Skurnik, Louis/Dressner, Jenny & Francois, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor) on the same page is a curated-wine confirmation; record `importer_trust_hit`.

7. **Reclassify + dedupe + state filter before handoff.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, wine-bar claw-back), then `dedupe_existing.py` (phone-first, then name+address). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter to `partner_type == butcher` rows only.

8. **(Optional) Score for ranking.** If the input was only `websites`-enriched, hand qualifying rows to the remaining `enrich.py` steps + `score.py` so the hidden-club trigger rides on top of the SHAP-aligned score. The hidden-club fields are overlay evidence — do **not** touch `SCORING_WEIGHTS`.

## Output schema

```
output/hidden_club/hidden_club_detection_<YYYYMMDD>.csv
source = "hidden_club_detection"
tier = <1|2|3>                       # program-concreteness tier from recipe step 5
business_type = wine | butcher | bakery | cheese | specialty_grocer
distinction = "Hidden club: runs a <program_type> ('<recurrence_evidence>') with no subscription label"
year = 2026
+ canonical: name, city, state, country, source_url (= website or program page), blurb
+ evidence cols (preserve so sales can quote the exact program phrase in outbound):
    program_type              # allocation|standing_order|share|box|members_list|preorder
    recurrence_evidence       # verbatim proof phrase from the LLM pass
    hidden_signal_hits        # pipe-joined regex matches that triggered the LLM pass
    hidden_signal_groups      # lexicon buckets that fired
    confidence                # LLM 0.0-1.0
    strength                  # tiering score from step 5
    has_club                  # must be False (explicit-label clubs route to Engine 01)
    labeled_as_subscription   # must be False
    has_esp                   # list-to-migrate signal from websites crawl
    importer_trust_hit        # wine: respected-importer confirmation
    liquor_store_suspect      # wine-only demote flag
    program_url               # the /allocations, /share, /box page if found
```

## Volume & cost

Bounded by input size, not fresh discovery. Over a ~2,500-row vertical-mix batch, after restricting to the five recurring-product-native verticals (~40–55% of a mixed batch → ~1,100–1,350 in-scope rows):

- `detect_clubs` flags ~15–25% as *labeled* clubs → those are excluded here (Engine 01's catch).
- Of the remaining ~850–1,050 `has_club==False` rows, hidden-signal regex fires on a wide ~20–30% → ~200–300 rows go to the LLM pass.
- LLM adjudication confirms a real-but-unlabeled program on roughly 25–40% of those → **~60–110 net-new tier-1+2 hidden-club leads per 2,500-row batch**, skewed toward wine (allocation lists) and butcher (standing orders / shares).

Cost arithmetic: the hidden-signal re-scan folds into a `detect_clubs`-style crawl over ~1,100 rows at 50 threads (near-free compute, bandwidth only). The LLM pass is ~200–300 Haiku calls of a few-KB snippet each ≈ **$3–8**. No Apify, no Serper Web, no Resy calls. Total marginal: **~$10–18** (lower if `has_club` is already populated upstream so step 2 is skipped).

## Refresh cadence

**Quarterly per vertical, with an opportunistic diff.** Hidden programs are stable — a butcher's standing-order book or a wine shop's allocation list persists for years, so monthly re-runs mostly re-surface the same rows. The high-value event is *transition*: a previously-tier-1 hidden-club lead that since added explicit subscription/ESP tooling, or that an SDR has confirmed is overwhelmed by manual administration. A quarterly diff (this run's hidden-club set ∩ rows whose `hidden_signal_hits` grew, or that flipped to `has_esp==True`) is itself a "they're scaling the manual program — now's the moment" trigger. Run off the back of large discovery batches rather than on a fixed clock.

## Risks

- **Fuzzy-term false positives.** "Allocation," "share," "members only," "list," "drops" are heavily overloaded — "allocation" appears in accounting/legal pages, "members" in loyalty punch-cards, "share" in social-share buttons. The LLM adjudication (step 4) is the primary guard; keep `recurrence_evidence` + `hidden_signal_hits` in output and sample via `sample_clubs_for_qa.py` before sales handoff. Bias toward precision — a noisy hidden-club list erodes the trigger's credibility in outbound.
- **Overlap with Engine 01 (labeled clubs).** If `detect_clubs` already flagged the row by explicit language, it is not "hidden" — `labeled_as_subscription==True` must hard-exclude, or the two lists collide and double-touch the prospect.
- **Liquor-store / commodity-wine leakage.** "Allocation"/"futures" on a liquor site pushing allocated Bourbon and Tito's is anti-ICP. The commodity-SKU + City Hive/Spot Hopper demote (step 6) is mandatory; without it the wine slice over-produces liquor stores.
- **Static-social / thin-web shops understate.** Many real hidden clubs live entirely on Instagram DMs, a Google Form, or a text thread — invisible to a homepage crawl. Absence of a web signal is **not** absence of a program; do not DQ in-vertical rows on a clean crawl, and consider an IG-bio/`scrape_beli`-style caption pass as a future extension (see Open questions). This is the same caveat as static social understating brand.
- **Small-market metrics run low.** Rural butchers/CSAs often run the strongest hidden programs (whole-animal shares, farm boxes) but have the thinnest digital footprint. Weight relative local dominance and the program concreteness over raw web/social volume for non-metro rows.
- **Wine-bar exclusion.** A wine bar with a "members' table" or "allocation pour" can trip the lexicon; wine bars are mostly out (avg AGMV $36.2k) except geographic monopolies. The `reclassify.py` wine-bar claw-back must run before scoring.
- **Sweets-only / single-product demotion.** A bakery whose "bread share" is actually a cookie-of-the-month is tech-eligible but caps at Tier 2 on ICP grounds; the hidden-club signal must not override the sweets-only demotion baked into scoring.
- **LLM cost/latency creep & prompt rot.** If the regex pre-filter is too loose, the Haiku pass balloons. Keep the regex gate tight and re-validate the classifier prompt against a labeled hidden/not-hidden sample periodically.

## Repo placement

An overlay package plus a thin orchestrator, with one vocabulary extension to `detect_clubs.py`.

```
detect_clubs.py
  + HIDDEN_CLUB_SIGNALS lexicon (per-vertical groups from recipe step 3)   # NEW
  + scan_hidden_signals(html, links) -> {hits, groups}                     # NEW, exported
  +   (reuses the existing 50-thread crawl + --resume; no second crawler)

hidden_club/                             # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                            # HIDDEN_CLUB_SIGNALS thresholds, tiering weights
  fetch.py                               # detect_clubs crawl + scan_hidden_signals over input CSV
  classify.py                            # Claude Haiku adjudication via awards/llm_extract.py plumbing
  aggregate.py                           # exclude labeled clubs, score strength, tier, liquor-guard
  finalize.py                            # reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical schema

discover_hidden_clubs.py                 # NEW orchestrator (mirrors discover_butchers.py)
  python discover_hidden_clubs.py --input output/2_enriched_websites.csv
  python discover_hidden_clubs.py --input output/custom-serper-scoring_*_all.csv --verticals wine,butcher,cheese
  python discover_hidden_clubs.py --master-only

config.py
  + reuse commodity-wine exclusion SKUs + City Hive/Spot Hopper red-flag + importer trust list
    (all already present for other engines)
```

No new external tool is required — every primitive (the `detect_clubs` crawl, `awards/llm_extract.py`, `reclassify.py`, `dedupe_existing.py`) already exists. The genuinely new code is the `HIDDEN_CLUB_SIGNALS` lexicon + `scan_hidden_signals` in `detect_clubs.py` and the small classify/aggregate overlay that joins, adjudicates, and tiers.

## Open questions

1. Should the LLM adjudication run on the homepage crawl alone, or also fetch and pass the probed `/allocations`, `/share`, `/box` program page when present? The program page has far richer evidence but adds a fetch + bigger snippet per row — confirm the precision lift justifies the cost.
2. How do we reach hidden clubs that live only on Instagram (DM-to-reserve, bio "join the list")? A `scrape_beli`-style IG-bio/caption pass over the in-vertical rows would catch them but is a meaningfully larger build — separate engine, or a flagged sub-mode here?
3. What `confidence` floor and `strength` thresholds actually separate a sales-ready hidden club from noise? Needs a labeled backtest against onboarded partners who *did* run a manual program pre-Table22, if that history exists.
4. For the wine "allocation" ambiguity, is the commodity-SKU + ESP guard sufficient, or do we need the importer-trust-hit to be a hard *requirement* (not just a positive flag) for tier-1 wine rows?
