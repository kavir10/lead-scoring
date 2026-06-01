# Lead Engine 47 — Private Event Spillover List

**Motion:** Curation
**Vertical fit:** Destination restaurants (primary), wine, cheese, butchers, specialty grocers — any partner type that publishes a private-events / buyout page but sells no consumer-facing recurring product
**Suggested list name(s):** `private_event_spillover`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $15/run (Claude classify + a thin Serper Maps backfill; the source pages ride the existing step-1 crawl)

## Premise

A merchant with a developed **private-events / buyout / group-dining page** has
already cleared the hardest packaging hurdle Table22 underwrites: it can take a
premium hospitality experience, **price it as a discrete SKU**, write the terms
(minimums, deposits, prepayment, headcount caps), and **sell it up front** to a
buyer. A restaurant that runs a $5K chef's-table buyout or a wine shop that hosts
private tasting parties has proven it can monetize *packaged*, *prepaid*, *premium*
experience — it just sells it one big-ticket event at a time, to corporates and
party-planners, with no consumer-facing recurring product underneath it. Table22's
job is to take that same proven capability and turn it into a **scalable,
smaller-ticket, recurring** product (a club, a standing pairing series, a monthly
box) aimed at the operator's own audience rather than one-off event buyers.

This is the demand-over-capacity thesis read from the supply side: the operator has
built premium-experience capacity (private rooms, chef's tables, staff who can
execute a curated menu) and is currently renting it out episodically. The spillover
is the recurring consumer demand that capacity could serve but doesn't, because
nobody packaged it for the everyday customer. The negative half of the signal —
**no club, no prepaid recurring SKU** (`detect_clubs` returns clean) — is what makes
this a build-the-club new sale rather than a switch-the-platform one.

In the two-score model this is a **Curation** engine that is ICP-correlated by
construction (chains and ghost kitchens don't publish bespoke buyout pages) with a
co-located **Trigger**: the *quality and specificity* of the private-events offering
signals operator sophistication and packaging muscle (ICP Fit), while the **absence
of any consumer recurring product** is the open-territory reason-to-build-now
(Trigger). The cleanest rows are high-AGMV partner types with a polished buyout page
and `has_club == False`.

## Recipe

No cold discovery. This engine reads private-events signals off businesses we've
*already* surfaced and crawled, layers a buyout-page extraction pass, and gates on a
**negative** `detect_clubs` result. We reuse the `enrich.py` step-1 crawler, the
`scrape_beli` / `awards/llm_extract.py` Claude pattern, `detect_clubs.py`,
`reclassify.py`, and Serper Maps backfill — no new external surfaces.

1. **Seed the universe (no Serper Maps sweep).** Feed the existing enriched corpus
   (`output/2_enriched_*.csv`) plus the niche lanes (`butcher/`, `best_wine_shops/`,
   `directories/`, awards master). These rows already cleared discovery quality
   floors and carry `website`. For net-new geography, a small Serper Maps pass
   (`discover.py` / `scripts/fresh_icp_search.py`) biased to
   `research/trendy_neighborhoods/` (~56.5% of partners sit in trendy neighborhoods)
   for `restaurant | wine_store | cheese | butcher | specialty`.

2. **Crawl for private-events signals (extend `enrich.py` step 1).** The step-1
   10-thread crawler already pulls page HTML, anchor `href`s, and CTA text. Add a
   parse layer that scans the homepage plus `/private-events`, `/private-dining`,
   `/events`, `/buyout`, `/groups`, `/group-dining`, `/parties`, `/host`,
   `/celebrations`, `/corporate`, `/venue`, `/book-an-event` paths for:

   ```
   PRIVATE_EVENT_PHRASES = [
     "private dining", "private events", "private party", "private parties",
     "buyout", "buy out the", "full buyout", "exclusive use",
     "group dining", "large parties", "semi-private", "private room",
     "chef's table for", "private chef's table", "tasting for groups",
     "corporate events", "corporate dinners", "holiday parties",
     "rehearsal dinner", "bridal shower", "birthday party", "celebrations",
     "host your event", "book your event", "inquire about", "event inquiry",
     "food & beverage minimum", "f&b minimum", "room fee", "event deposit",
     "private tasting", "private wine tasting", "private cheese tasting",
   ]
   EVENT_SOPHISTICATION_PHRASES = [   # raise event_strength when present
     "minimum spend", "food and beverage minimum", "deposit", "prepayment",
     "custom menu", "prix fixe for groups", "wine pairing", "sommelier",
     "private room seats", "up to N guests", "chef-curated", "set menu",
   ]
   ```
   Capture the matched phrase + the private-events page URL + any
   minimum/deposit/headcount string so the offering is citable in outbound and
   feeds `event_strength`.

3. **Classify offering depth (Claude, cheap pass).** Send the matched
   private-events page text to Claude (`claude-haiku-4-5-20251001`, the model
   `scrape_beli` uses; the `awards/llm_extract.py` editorial-extraction scaffold
   applies) to label `event_offering ∈ {full_buyout, private_dining_room,
   private_chefs_table, private_tasting, group_menu_only, generic_large_party,
   none}`, score `offering_depth` (0–3: dedicated page + custom menu + stated
   minimum/deposit = 3; a single "large parties welcome" line = 1), and write a
   one-line `trigger_summary` for outbound. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

4. **The negative gate — `detect_clubs.py`.** Run `detect_clubs.py` (concurrent
   site scrape, 50 threads) over the candidate set. The whole engine pivots on the
   **inverse** of its usual use: here a clean result (`has_club == False`, no
   recurring/prepaid consumer SKU) is what *qualifies* a row. Rows where
   `has_club == True` are not discarded — they route to Engine 01
   (`existing_club_transition`, a switch-the-platform sale) instead of this list.
   Carry `has_club` / `club_type` through so the split is auditable.

5. **ICP gate (curation pass).** Run `reclassify.py` for `partner_type` /
   `business_type_v2` (incl. the wine-bar claw-back). Reject anti-ICP before
   scoring, score the trigger after:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  or  wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, ...) or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     event_offering == none   (no real private-events product, just a contact form)
     PURE event venue / banquet hall (private events are the ONLY product — that's a caterer)
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}    # butcher lane only
     has_club == True   -> route to Engine 01 (existing_club_transition), drop from THIS list

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product (a bakery that hosts birthday parties caps Tier 2)
     static-social-only / thin metrics in a small market (understates brand — never DQ)
     group_menu_only / generic_large_party (capability is thin — weak packaging proof)

   event_strength:
     +3 dedicated buyout / private-dining page with custom menu + stated minimum or deposit (offering_depth == 3)
     +2 private chef's table or private tasting offering (premium, packaged, prepaid-shaped)
     +2 high-AGMV partner type (butcher / wine / cheese / destination restaurant)
     +1 private dining room with a set group menu (offering_depth == 2)
     +1 if email-signup form present (step-1 signal: has an audience to sell the new club to)

   QUALIFY if: passes ICP gate AND has_club == False AND event_strength >= 3
   ```

6. **Hand off to scoring.** Emit the canonical CSV (below) and run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   private-events columns ride as evidence; `event_strength` orders the outbound
   queue inside a tier.

## Output schema

```
output/private_event_spillover/private_event_spillover_<YYYYMMDD>.csv
source = "private_event_spillover"
tier = <1|2|3>   # 1 = high-AGMV type + deep buyout offering + no club; 2 = thinner offering / sweets-only; 3 = ICP-soft
business_type = restaurant | wine_store | cheese | butcher | bakery | specialty
distinction = "Runs {event_offering} private events but has no consumer recurring product — proven packaging, open territory"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    event_offering          # full_buyout | private_dining_room | private_chefs_table | private_tasting | group_menu_only | ...
    offering_depth          # 0-3 (dedicated page + custom menu + stated minimum/deposit)
    event_page_url          # permalink to the private-events / buyout page
    event_evidence_snippet  # verbatim page text that matched
    stated_minimum          # parsed F&B minimum / deposit / room fee, if present
    max_party_size          # parsed headcount cap, if present
    has_email_signup        # bool, from enrich.py step 1 (audience to sell the new club to)
    has_club, club_type     # carried from detect_clubs.py — MUST be False to qualify here
    event_strength          # int, intra-tier outbound ordering
    trigger_summary         # one-line Claude-written outbound hook
    partner_type            # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped: **~8–12K
  rows**. No discovery spend — these are already-crawled businesses.
- Step-1 crawl extension: free (rides the existing 10-thread crawl; +1 parse pass
  against extra private-event paths, no new fetch budget).
- `detect_clubs.py` over candidates: free (existing script, 50 threads). Only the
  rows that show a private-events match (~20–30%, ≈2–3K) need the clubs check.
- Claude Haiku classify pass on matched private-events page text (~2.5K short
  prompts): **≈ $2–4**.
- Serper Maps backfill for net-new-geography seeds only (~600–900 queries at
  ~$0.001–0.003): **≈ $2–4**.
- Reclassify / dedupe postprocessing: free (existing scripts).
- **Per-run total: ~$6–12.**
- **Net-new qualified leads per run:** of ~10K screened, a real private-events
  offering hits **~20–25%** (≈2–2.5K); after the ICP gate, the `has_club == False`
  negative gate, and `event_strength >= 3`, expect **~300–500 qualified rows**. Many
  already sit in our corpus — that's fine; the value is the *open-territory trigger*
  (proven packaging + no recurring product), which re-prioritizes them for a
  build-the-club outbound now.

## Refresh cadence

**Quarterly.** Unlike calendar-driven engines (sold-out listings, holiday
preorders), a private-events page is a **stable structural** signal — it doesn't
expire week to week. What changes quarterly is the *negative* half: a merchant that
launches a club between runs should fall out of this list and into Engine 01. Re-run
`detect_clubs.py` each quarter to catch that transition, and dedupe against prior
outputs so we don't re-pitch the same untouched offering. A light pre-holiday pass
in October can help if outbound wants to lead with "your holiday-party calendar is
booked — here's how to fill the *other* eleven months."

## Risks

- **Caterer / pure event-venue leakage.** This engine deliberately hunts
  private-events pages, so banquet halls, event spaces, and pure caterers are the
  dominant false positive. They are anti-ICP — a business whose *only* product is
  private events has no core retail/restaurant to attach a club to. Require a
  resolved retail/restaurant `partner_type` from `reclassify.py` and a real
  consumer-facing storefront before qualifying; hard-DQ pure venues.
- **`detect_clubs` false-negative inverts the whole engine.** The qualification
  hinges on `has_club == False`. If `detect_clubs.py` misses an existing club
  (gated checkout, members-only page, club hidden behind a login), we pitch
  build-the-club to someone who already has one. Carry `club_signals` through and
  spot-check the high-`event_strength` rows; lean on Engine 18
  (`hidden_club_detection`) coverage if it has landed.
- **Contact-form-only false positive.** Many sites have a thin "for large parties,
  email us" line with no real packaged product. That's not proven packaging muscle —
  hard-DQ `event_offering == none` and require `offering_depth >= 2` (a real menu or
  stated minimum) before assigning `event_strength`.
- **Cocktail-bar / liquor-store leakage via "private tasting."** A cocktail bar's
  private buyout or a liquor store's "private wine tasting party" can match. Keep
  the wine-bar exclusion (except geographic-monopoly), the `reclassify.py` wine-bar
  claw-back, and commodity-SKU / ESP red-flag (City Hive, Spot Hopper) checks
  upstream of `event_strength`.
- **Sweets-only demotion.** A bakery that hosts birthday parties or kids' decorating
  events is a real signal but a single-product business — cap at Tier 2, don't
  promote on the offering alone.
- **Small-market metrics run low / static social understates brand.** A dominant
  small-market restaurant that does private buyouts may have thin social and review
  volume. Weight relative local dominance and the private-events trigger over raw
  follower/review floors; **never DQ on static-only social**.
- **Chain leakage.** Steakhouse groups and multi-location concepts publish polished
  private-dining pages too. Keep `config.CHAIN_KEYWORDS` + the `reclassify.py`
  coarse pass upstream, or high-AGMV partner-type weight inflates chain scores.

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler,
`detect_clubs.py`, and the `scrape_beli` / `awards/llm_extract.py` Claude pattern as
libraries.

```
private_event_spillover/
  __init__.py                  # engine constants; registers signal banks
  signals.py                   # PRIVATE_EVENT_PHRASES, EVENT_SOPHISTICATION_PHRASES, SKU/ESP leak lists
  crawl_private_events.py      # parse layer over enrich.py step-1 crawl (extra private-event paths)
  classify.py                  # Claude haiku-4-5: event_offering + offering_depth + minimum/headcount + trigger_summary
  aggregate.py                 # ICP gate (reclassify) + detect_clubs NEGATIVE join, event_strength, dedupe, Engine-01 split
  finalize.py                  # canonical schema writer, date-stamped output
discover_private_event_spillover.py  # orchestrator: seed -> crawl -> classify -> clubs-gate -> icp-gate -> finalize
```

Refactor target: extract `enrich.py` **step-1** website parsing (HTML, anchors, CTA
text, social links, email-signup detection) into a shared `enrich_websites_lib` so
`enrich.py` and `crawl_private_events.py` parse identically without duplicating the
crawl — the same shared-lib argument Engines 12 / 02 / 05 raise for the step-1 func.
Reuse Engine 12's (`events_programming`) crawl-extension and Claude scaffolding if it
lands first; the page-path sweep and classify shape overlap heavily — the difference
is the *negative* `detect_clubs` gate and the buyout-specific signal bank.

## Open questions

1. **Engine-01 routing vs. dedupe.** Rows with `has_club == True` should leave this
   list and feed Engine 01 (`existing_club_transition`). Do we emit the split as a
   second CSV from this orchestrator, or just tag and let a downstream merge route
   them — and phone-first dedupe (`dedupe_existing.py`) against Engine 01's output?
2. **Offering-depth threshold.** Is `event_strength >= 3` the right qualify bar, or
   does requiring a *stated minimum/deposit* (hard prepayment proof) cut volume too
   far for small-market partners who run buyouts informally without publishing terms?
3. **IG-only private events.** Some operators advertise buyouts only via DM / link in
   bio, not a site page. Worth adding an Apify post/profile mining pass (as Engine 12
   does), or does that drag in too much caterer noise to justify the cost?
4. **Does "no consumer recurring product" need positive corroboration** beyond a
   clean `detect_clubs` result — e.g. an email-signup form present (audience to sell
   to) — before we treat the open-territory trigger as Tier-1-worthy?
