# Lead Engine 26 — Events-to-Subscriptions List

**Motion:** Curation
**Vertical fit:** Destination restaurants (primary), wine, cheese, butchers — any partner type that packages a prepaid dinner / tasting / class
**Suggested list name(s):** `events_to_subscriptions`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run (mostly Claude extraction + a thin Serper Maps backfill; the listing surfaces are scraped, not paid)

## Premise

A merchant who lists a **ticketed, prepaid experience** — a wine-pairing dinner,
a cheese-and-wine flight night, a butchery class, a chef's-table series, a
prix-fixe tasting menu sold as a ticket — on **Tock Experiences**
(`exploretock.com/join/experiences`) or **OpenTable Experiences**
(`opentable.com/experiences`) has already cleared the three operational hurdles
Table22 underwrites: it can **package** hospitality into a discrete SKU, it
**charges up front** for it (prepaid, non-refundable, scarce by design), and it
has chosen to **distribute that SKU on a platform** rather than just take walk-ins.
This is the closest public proxy we have to "already runs a subscription business
without calling it one." A merchant selling prepaid experience tickets is a
platform-switch / platform-add sale, not a cold-start.

Unlike Engine 12 (which reads programming signals off businesses we have *already*
crawled), this engine treats the experience platforms themselves as a **discovery
source** — net-new merchants we may never have surfaced through Serper Maps,
because their draw is the experience, not raw review volume. It maps to the
demand-over-capacity thesis directly: a ticketed experience is capacity-capped
(N seats, one seating, a cutoff), so a sold-out or near-sold-out listing is unmet
demand the operator is leaving on the table.

In the two-score model this is a **Curation** engine that is ICP-correlated by
construction (you don't sell prepaid tasting-menu tickets if you're a chain or a
ghost kitchen) with a co-located **Trigger**: the *kind* of experience signals
partner type and operator sophistication (ICP Fit), while a **listing with an
upcoming date and limited/sold-out inventory** is the reason-to-contact-now
(Trigger). The cleanest rows have both — a high-AGMV partner type running a
recurring, near-sold-out prepaid series.

## Recipe

The new work is **enumerating and parsing the two experience-platform surfaces
into merchant rows**, then resolving each merchant to a canonical row and gating
on ICP. We reuse the `best_wine_shops` httpx+selectolax+Playwright-fallback
pattern for fetching, the `scrape_beli` / `awards/llm_extract.py` Claude pattern
for extraction, Serper Maps for backfill, and the standard postprocessing gate.

1. **Enumerate listings per surface (httpx + selectolax happy path, Playwright
   fallback).** Mirror the `best_wine_shops` fetch shape exactly:

   - **Tock Experiences** — walk `exploretock.com/join/experiences` and its
     city/category facets. Tock renders much of the grid client-side; capture the
     JSON payload from the embedded `__NEXT_DATA__` / XHR where present, fall back
     to Playwright when the static HTML is empty. Each card yields a merchant
     name, city, experience title, price, date(s), and an availability state.
   - **OpenTable Experiences** — walk `opentable.com/experiences` faceted by metro
     (reuse the `config.CITIES` metro list to drive the facet sweep). Same
     static-first / Playwright-fallback policy.

   Bias the city sweep toward `research/trendy_neighborhoods/` metros first
   (~56.5% of partners sit in trendy neighborhoods) so the highest-density
   geography is covered before we widen.

2. **Classify experience type + extract structured fields (Claude).** Send each
   listing's title + blurb to Claude (`claude-haiku-4-5-20251001`, the model
   `scrape_beli` uses; the `awards/llm_extract.py` editorial-extraction scaffold
   applies) to label `experience_type` and pull structured fields. Prefix the
   script with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

   ```
   EXPERIENCE_TYPES = [
     "wine_pairing_dinner", "tasting_menu", "chefs_table", "chef_dinner",
     "guest_chef_collab", "wine_tasting", "wine_class", "cheese_tasting",
     "cheese_class", "butchery_class", "knife_skills_class", "cooking_class",
     "supper_club", "holiday_prix_fixe", "nye_dinner", "festival_dinner",
     "none",   # generic reservation, not a packaged prepaid experience
   ]
   PREPAID_SCARCITY_PHRASES = [   # mined off the listing for the Trigger
     "sold out", "waitlist", "limited", "only N (seats|spots|tickets)",
     "few (seats|spots) left", "prepaid", "non-refundable", "ticketed",
     "seating(s)? at", "series", "monthly", "each month",
   ]
   ```

3. **Resolve listing → canonical row.** Each listing names a merchant + city.
   Fuzzy-join (name + city, phone where the listing exposes it) against the
   existing enriched corpus (`output/2_enriched_*.csv`), the awards master, and
   the niche lanes. Misses go to a thin **Serper Maps** lookup (one query per
   unique name+city — same primitive as `discover.py`, no full crawl) to attach
   `website`, phone, Google rating/review count, and `business_type`. Dedupe with
   `dedupe_existing.py` (phone-first, then name+address).

4. **ICP gate (curation pass).** Run `reclassify.py` for `partner_type` /
   `business_type_v2` (incl. the wine-bar claw-back), then `detect_clubs.py` — an
   existing club/prepaid program is a **positive** switch-the-platform signal, not
   a DQ; carry `has_club` / `club_type` through. Reject anti-ICP before scoring,
   score the trigger after:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  or  wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, ...) or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     experience_type == none  (a plain reservation, not a packaged prepaid SKU)
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}    # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product (a dessert-tasting ticket is real but caps Tier 2)
     static-social-only / thin metrics in a small market (understates brand — never DQ)
     one-off ticketed dinner with no recurrence and not near sold out

   prepaid_strength:
     +3 recurring prepaid series (monthly chef's table / standing pairing dinner / class series)
     +3 listing currently SOLD OUT or waitlisted (hard demand-over-capacity proof)
     +2 limited inventory ("few seats left", named seat cap) on an upcoming date
     +2 high-AGMV partner type (butcher / wine / cheese / destination restaurant)
     +1 single upcoming prepaid experience (capability proof, weaker now-trigger)
     +1 if has_club == True (already monetizing repeat demand)

   QUALIFY if: passes ICP gate AND prepaid_strength >= 3
   ```

5. **Hand off to scoring.** Emit the canonical CSV (below) and run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   experience columns ride as evidence; `prepaid_strength` orders the outbound
   queue inside a tier.

## Output schema

```
output/events_to_subscriptions/events_to_subscriptions_<YYYYMMDD>.csv
source = "events_to_subscriptions"
tier = <1|2|3>   # 1 = high-AGMV type + recurring or sold-out prepaid series; 2 = single/sweets-only/limited; 3 = ICP-soft
business_type = restaurant | wine_store | cheese | butcher | bakery | specialty
distinction = "Sells prepaid {experience_type} on {platform} — already runs scarce, packaged hospitality"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    experience_platform    # tock_experiences | opentable_experiences | both
    experience_type        # wine_pairing_dinner | chefs_table | butchery_class | tasting_menu | ...
    experience_title       # verbatim listing title
    experience_url         # permalink to the Tock/OpenTable listing
    experience_price       # ticket price (parsed)
    next_event_date        # soonest listed date
    availability_state     # sold_out | waitlist | limited | available | unknown
    is_recurring           # bool (series vs one-off)
    prepaid_strength       # int, intra-tier outbound ordering
    trigger_summary        # one-line Claude-written outbound hook
    has_club, club_type    # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

## Volume & cost

- **Listing enumeration:** Tock Experiences + OpenTable Experiences across the
  ~130-metro facet sweep yield, realistically, **~2–4K live experience listings**
  collapsing to **~1–2K unique merchants** (many merchants list multiple
  experiences). Fetching is httpx/Playwright — no per-call API spend, just
  proxy/compute; budget **~$1–3** for Playwright-fallback runs on JS-heavy pages.
- **Claude classify pass** on ~3K short listing prompts (haiku-4-5): **≈ $3–5**.
- **Serper Maps backfill** for unresolved merchants (~600–900 unique names not in
  our corpus, at ~$0.001–0.003/query): **≈ $2–4**.
- Reclassify / detect_clubs / dedupe postprocessing: free (existing scripts).
- **Per-run total: ~$8–15.**
- **Net-new qualified leads per run:** of ~1–2K unique merchants, after the ICP
  gate + `prepaid_strength >= 3` expect **~250–450 qualified rows**. A meaningful
  share — especially destination restaurants — will already be in our corpus;
  that's fine, the value is the **prepaid-SKU trigger**, which re-prioritizes them
  for outbound. The genuinely net-new slice (merchants we never surfaced via Maps
  because their draw is the experience, not review volume) is the prize: estimate
  **~30–40% net-new**, ≈ 80–180 leads.

## Refresh cadence

**Monthly, with heavy pre-holiday runs in late September and late October.**
Experience inventory turns over with the calendar — listings appear, sell out,
and disappear within weeks. A `sold_out` / `waitlist` state is a live trigger only
while the listing is up, so monthly keeps the outbound line current ("saw your
December pairing dinners sold out"). The holiday prix-fixe / NYE-dinner slice is
the highest-intent subset and is live for only ~6–8 weeks — catch it in the open
window. Recurring series (monthly chef's table) are sticky and persist run-to-run;
dedupe against prior outputs so we don't re-pitch the same series.

## Risks

- **`experience_type == none` leakage.** Both platforms list plain reservations
  and generic "book a table" entries alongside true packaged prepaid experiences.
  The Claude pass must distinguish a prepaid, ticketed SKU from an ordinary
  reservation — hard-DQ `none`, and require a price + ticket/seating language
  before assigning `prepaid_strength`.
- **Caterer / event-venue leakage.** A venue whose *only* product is buyout
  dinners or private events is a caterer (anti-ICP). Require a resolved
  retail/restaurant `partner_type` from `reclassify.py`; drop pure event venues.
- **Cocktail-bar / liquor-store leakage via "tasting."** A cocktail bar's "spirits
  flight" or a liquor store's free wine tasting can match. Keep the wine-bar
  exclusion (except geographic-monopoly), the `reclassify.py` wine-bar claw-back,
  and commodity-SKU / ESP red-flag (City Hive, Spot Hopper) checks upstream of
  `prepaid_strength`.
- **Sweets-only demotion.** A dessert-tasting or pastry-class ticket is a real
  prepaid signal but a single-product bakery — cap at Tier 2, don't promote on the
  trigger alone.
- **Sold-out is recency-fragile.** `availability_state` is true only at fetch
  time; record `fetched_at` and don't let a stale "sold out" read as a live
  trigger on a later run. Re-resolve availability on the listing URL before
  outbound.
- **Small-market under-representation.** Tock/OpenTable Experiences skew to big
  metros; a dominant small-market butcher running a monthly whole-animal dinner
  may not list on either platform at all. This engine will miss them — a
  precision/recall tradeoff, not a bug. Don't infer absence-of-listing =
  absence-of-demand; lean on Engines 06/10/12 for small markets, and **never DQ on
  static-only social** (it understates brand).
- **Chain leakage.** Multi-location concepts and hotel-restaurant groups run
  ticketed dinners too. Keep `config.CHAIN_KEYWORDS` + the `reclassify.py` coarse
  pass upstream, or high-AGMV partner-type weight inflates chain scores.
- **Platform fragility / anti-bot.** Tock and OpenTable render listings
  client-side and have anti-bot behavior; the static-first / Playwright-fallback
  policy and a metro-paced sweep (back off on blocks) are required. Accept partial
  recall over aggressive crawling — precision matters more than completeness for a
  trigger list.

## Repo placement

Standalone package mirroring the `best_wine_shops` lane shape (self-contained
fetch + Claude extract + finalize), reusing the httpx/Playwright fetch pattern and
the `scrape_beli` / `awards/llm_extract.py` Claude pattern as libraries.

```
events_to_subscriptions/
  __init__.py                  # engine constants; registers experience-type + scarcity-phrase banks
  signals.py                   # EXPERIENCE_TYPES, PREPAID_SCARCITY_PHRASES, SKU/ESP leak lists
  fetch_tock.py                # exploretock.com/join/experiences enumeration (httpx -> Playwright fallback)
  fetch_opentable.py           # opentable.com/experiences metro-facet sweep (httpx -> Playwright fallback)
  classify.py                  # Claude haiku-4-5: experience_type + price/date/availability + trigger_summary
  resolve.py                   # fuzzy-join to enriched corpus + awards master; Serper Maps backfill for misses
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), prepaid_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_events_to_subscriptions.py  # orchestrator: fetch -> classify -> resolve -> gate -> finalize
```

Refactor target: extract `best_wine_shops`'s httpx-happy-path / Playwright-fallback
fetch helper into a shared `fetch_lib` so this engine and `best_wine_shops` share
one blocked-page fallback policy instead of duplicating it. Reuse `scrape_beli`'s
Claude extraction prompt scaffolding for `classify.py` rather than re-authoring the
extractor, and reuse Engine 12's `EXPERIENCE_TYPES` / scarcity vocabulary if that
engine lands first (the programming-signal banks overlap heavily).

## Open questions

1. **Cross-engine dedupe with Engine 12.** Engine 12 reads programming signals off
   already-crawled businesses; this engine discovers off the experience platforms.
   They will converge on overlapping merchants. Do we merge prepaid-experience and
   on-site-programming triggers onto one partner row (phone-first via
   `dedupe_existing.py`), or keep separate lists with distinct outbound timing?
2. **Availability verification depth.** Do we trust the listing-card
   `availability_state`, or fetch each high-priority listing to confirm sold-out /
   seat-cap before assigning the +3 scarcity bonus? Both platforms have anti-bot
   behavior — worth a spike to size the cost.
3. **Do Tock/OpenTable expose merchant identity cleanly enough** to resolve to a
   canonical row without a Serper Maps round-trip, or is the name+city on the
   listing too ambiguous (multiple locations, DBA vs legal name) to skip backfill?
4. **Is a single recurring prepaid series enough to auto-Tier-1**, or should it
   require corroboration from `detect_clubs.py` (`has_club == True`) before we
   treat it as a hard subscription-readiness signal?
