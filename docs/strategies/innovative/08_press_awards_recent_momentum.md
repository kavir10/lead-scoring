# Lead Engine 08 — Press Momentum Watchlist

**Motion:** Curation
**Vertical fit:** Destination + neighborhood restaurants, bakeries, wine shops, cheesemongers, butchers — any operator that editorial food media and craft-award bodies actively cover
**Suggested list name(s):** `press_awards_recent_momentum`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (mostly Serper Web + Apify Maps geocode/dedupe; LLM extraction on a bounded article set)

## Premise

Press is a SHAP feature in its own right (**Press Mentions** sits mid-table,
above Monthly Traffic and Google Rating), but the real value of *fresh* press
is as a **Trigger**, not an ICP-Fit input. A list landing — Eater's "best new
restaurants," an Infatuation review, a Bon Appétit / Food & Wine feature, a
James Beard semifinalist nod, a Good Food Award, Cheesemonger Invitational
placement — creates a demand spike against a fixed kitchen, counter, or case.
That is the demand-over-capacity thesis stated as a calendar event: recognition
pulls a wave of customers the operator was not staffed to capture, which is the
exact pressure Table22 relieves by converting overflow demand into a recurring
subscription program.

The freshness of the signal is what makes it sellable. A James Beard
*semifinalist* announcement, a brand-new Eater opening, or a just-published
"best of 2026" list gives a BDR a concrete, time-stamped reason to reach out
*this week* — "saw you just made the Eater 16 / JBF semis." Stale awards are
weak triggers; the existing `awards/` package already captures the durable
ICP-Fit credential, so this engine deliberately scopes to **recency**:
recognition dated within the trailing ~120 days.

Pairing matters. High-ICP partner type (butcher / wine / cheese / destination
restaurant) + fresh press = top of the call list. Weak-ICP with a press hit
(a pizza-first spot named in a "best slices" roundup, a cocktail bar in a
nightlife list) is filtered hard before sales — press alone never overrides a
disqualifier.

## Recipe

This engine is a thin **recency overlay on two primitives we already run**:
the `awards/` package (extraction modes + canonical schema + orchestrator) and
`enrich.py` step 4 (press, Serper Web against food-media domains + award
keywords). It is *not* a new scraping stack. Two complementary inputs feed one
finalize step.

1. **Recurring-source lane (structured).** Register the recurring editorial and
   craft-award sources as `awards/<category>/<slug>.py` modules implementing the
   standard `def scrape(**kwargs) -> pandas.DataFrame` contract, returning the
   canonical schema. Use the right extraction mode per source (per `docs/AWARDS.md`):
   - **Mode 2 (httpx + selectolax + regex)** for clean machine-readable lists —
     Good Food Awards winners, James Beard semifinalist/finalist tables.
   - **Mode 1 (Playwright pagination)** for JS-rendered list pages (some Eater
     city map pages, Infatuation guides).
   - **Mode 3 (LLM extraction via `awards/llm_extract.py`)** for prose features
     where no structured list exists — Bon Appétit / Food & Wine articles, local
     mag/paper writeups, Cheesemonger Invitational / Butchers Guild / Good Food
     charcuterie recaps. Remember the `unset ANTHROPIC_API_KEY &&` prefix.

   Seed sources (slugs under the matching `awards/<category>/`):
   `eater`, `the_infatuation`, `bon_appetit`, `food_and_wine`, `jbf_semifinalists`,
   `good_food_awards`, `cheesemonger_invitational`, `butchers_guild`,
   `good_food_charcuterie`, plus a `local_press` aggregator for city mags/papers.

2. **Discovery lane (Serper Web).** Reuse the step-4 press primitive directly to
   sweep recurring queries against the food-media domains already in
   `config.py`, scoped by recency. Seed query templates (run per recent window):

   ```
   "best new restaurants" {city} 2026
   eater {city} "16" OR "best new"
   the infatuation {city} review
   "james beard" semifinalist 2026 {restaurant|bakery|butcher}
   "good food awards" 2026 winner {charcuterie|cheese|preserved}
   "cheesemonger invitational" 2026
   site:eater.com OR site:theinfatuation.com OR site:bonappetit.com {city}
   ```

   Restrict to fresh results with Serper's `tbs=qdr:m` (past month) / a trailing
   `as_qdr` window; pass each surfaced article URL to `awards/llm_extract.py` to
   pull named businesses + city/state into canonical rows.

3. **Normalize + geocode + match to the universe.** Union both lanes through the
   `discover_awards.py` master path (it backfills `source`, `tier`,
   `business_type`). Resolve each extracted name to a real operator: Serper Maps
   lookup (the `discover.py` primitive) to attach phone/address/website and
   confirm it is not closed/relocated. Phone-first dedupe via `dedupe_existing.py`
   against the current scored universe so we know net-new vs. re-surfaced.

4. **Recency gate (the trigger).** Stamp `press_date` per row and keep only
   recent recognition:

   ```
   age_days = scan_date - press_date
   fresh    = age_days <= 120
   if not fresh: drop            # durable credential already lives in awards/
   ```

5. **Tier the trigger** by source weight × recency × ICP partner type. This is a
   *contact-now* overlay, not a change to `config.SCORING_WEIGHTS`:

   ```
   src_tier   = 1  for JBF semis/finalists, Eater "best new", Good Food Awards,
                   Cheesemonger Invitational, marquee BA/F&W feature
              = 2  for Infatuation review, established city-mag best-of
              = 3  for local paper mention, listicle inclusion
   icp_ok     = partner_type in {butcher, wine, cheese, destination_restaurant,
                   neighbourhood_restaurant, bakery, deli, specialty_grocer}
   recency_hot = age_days <= 45

   if   src_tier == 1 and icp_ok and recency_hot:  tier = 1
   elif src_tier <= 2 and icp_ok:                  tier = 2
   elif icp_ok:                                    tier = 3
   else: drop                                      # weak-ICP press = filter, not sell
   ```

6. **Optional demand confirmation.** For Tier-1/2 restaurant rows, opportunistically
   run `enrich.py` step 8 (availability — OpenTable/Apify + Resy) to confirm the
   press hit is translating into reservation scarcity. A fresh feature *plus*
   no-availability is the strongest possible outbound line; skip for retail
   verticals where reservations don't apply.

7. **Stamp the trigger onto the ICP score, don't bury it.** Emit the evidence CSV
   below so `score.py` remains the source of truth for ICP Fit; this engine adds
   the perishable "reason to call now" layer with a citable source URL.

## Output schema

```
output/press_signals/press_awards_recent_momentum_<YYYYMMDD>.csv
source = "press_awards_recent_momentum"
tier = <1|2|3>
business_type = <restaurant|bakery|wine|cheese|butcher|deli|specialty_grocer>
distinction = "Fresh press: {press_source} — {headline} ({press_date}, {age_days}d ago)"
year = <YYYY of press_date>
+ evidence cols:
    name, city, state, partner_type,
    press_source, press_source_tier, headline, source_url,   # cite-the-trigger link
    press_date, age_days, recency_hot,
    extraction_mode,                 # structured|playwright|llm
    matched_phone, matched_website,  # from Serper Maps resolution
    is_net_new,                      # vs current scored universe
    reservation_difficulty, availability_checked,  # optional, restaurants only
    src_tier, scan_date
```

`source_url` + `headline` preserve the exact citation so a BDR opens with
"congrats on the Eater 16 nod last week — here's the link." That verbatim cite
is the whole point of a Curation list.

## Volume & cost

Bounded by article count, not a 130-city Maps crawl:

- Structured/award lanes: ~10 recurring sources, refreshed per run; httpx/Playwright
  cost is negligible (Serper Web calls + a few hundred page fetches).
- Discovery lane: ~150-250 Serper Web queries/run at ~$0.001-0.003 each ≈ **$0.50-1.50**.
- LLM extraction over the prose subset (~150-300 articles) via Haiku ≈ **$3-6**.
- Serper Maps resolution (~400-800 name lookups) ≈ **$2-4**.
- Optional availability check on ~50-100 Tier-1/2 restaurant rows (Apify OpenTable +
  Resy) ≈ **$3-6**.
- **Per-run total: ~$10-18.**
- **Net-new / re-surfaced leads per run: ~150-350**, of which ~40-90 hit Tier 1
  (marquee fresh recognition × strong ICP). A large share will already be in the
  universe — the deliverable is the *dated trigger stamp* that moves a dormant
  high-ICP row to the top of the queue.

## Refresh cadence

**Weekly.** Press recency is the entire mechanism — JBF semifinalist drops,
"best new" lists, and award announcements are calendar events, and the 45-day
`recency_hot` window decays fast. Weekly keeps the trailing-120-day window
current and catches list landings while the demand wave is still cresting.
Tie the cadence to known announcement seasons (JBF semis ~late January, Good
Food Awards ~January, "best of year" lists ~December) and burst the discovery
lane around them.

## Risks

- **LLM extraction is best-effort.** Mode-3 over prose features will miss or
  mis-attribute names, hallucinate cities, or pull non-businesses (chefs, dishes,
  neighborhoods). Always re-resolve via Serper Maps before admitting a row;
  unresolved names get dropped, not guessed.
- **Weak-ICP press leakage.** Listicles mix in pizza-first spots, cocktail bars,
  caterers, ghost kitchens, and chains. Run `reclassify.py` (partner_type +
  wine-bar claw-back) and `config.CHAIN_KEYWORDS` filtering *before* tiering;
  high-trigger / weak-ICP must be filtered, never sold. Press never overrides a
  disqualifier.
- **Wine-bar / liquor-store confusion.** A wine roundup can name a wine *bar*
  (mostly excluded except geographic monopoly) or a liquor store (DQ vs. curated
  shop). Respect upstream reclassification; don't admit on press strength alone.
- **Sweets-only demotion.** A bakery named for a single viral pastry is still
  capped at Tier 2 per ICP rules (single-product heavy demotion). Carry
  `partner_type` and apply the cap.
- **Small-market metrics run low.** A regional best-of in a non-top-30 metro is a
  *stronger* relative signal than its national footprint implies — weight local
  dominance / regional best-of, and don't down-rank for low raw traffic or
  follower volume. Static social understates small-market brand; don't DQ on it.
- **Duplicate / stale-credential noise.** The same operator appears across Eater +
  Infatuation + local paper. Dedupe phone-first and keep the highest `src_tier`
  hit as the canonical row, listing others in evidence. Don't re-mint a Tier-1
  every week for the same unchanged award — gate on `age_days`.
- **Source fragility.** Eater/Infatuation pages are JS-heavy and re-template
  often; JBF/Good Food publish in inconsistent formats year to year. Expect
  per-source breakage; isolate failures (one module down ≠ run down), mirroring
  `discover_awards.py` behavior.
- **Closed/relocated venues.** Press lags reality; a "best new" spot may have
  already closed. The Serper Maps resolution step doubles as a liveness check —
  drop permanently-closed listings.

## Repo placement

```
awards/restaurants/eater.py            # mode 1/3
awards/restaurants/the_infatuation.py  # mode 1/3
awards/restaurants/bon_appetit.py      # mode 3 (llm_extract)
awards/restaurants/food_and_wine.py    # mode 3
awards/restaurants/jbf_semifinalists.py# mode 2
awards/cheese/cheesemonger_invitational.py
awards/butcher/butchers_guild.py
awards/specialty/good_food_awards.py
awards/specialty/good_food_charcuterie.py
awards/_local_press.py                 # city-mag/paper aggregator (mode 3)
        # all registered in awards/__init__.py:ALL_SOURCES

press_signals/
  __init__.py
  fetch_recent_press.py   # Serper Web discovery lane (wraps enrich.py step 4
                          # press primitive) + recency-scoped query templates
  resolve_and_match.py    # Serper Maps resolution + dedupe_existing.py against universe
  finalize.py             # recency gate, src_tier/ICP tiering, emits canonical CSV
discover_press_momentum.py # orchestrator, mirrors discover_awards.py shape;
                          # --window 120 --recent-only --resume; unions the awards
                          # recurring lane + the Serper discovery lane
```

Refactor targets: (1) lift the step-4 press body out of `enrich.py` into a small
`press_lib.py` so both `enrich.py` and `press_signals/fetch_recent_press.py`
share one Serper-Web + food-domain wrapper; (2) expose the step-8 availability
funcs as `_availability_lib.py` (the same lift proposed for Engines 04/05) so the
optional reservation-scarcity confirmation reuses one client instead of importing
`enrich.py` wholesale.

## Open questions

1. Do the recurring editorial sources expose a reliable machine-readable
   **publish date** (for `age_days`), or must we infer it from URL slug / page
   metadata / list edition year? Recency is the whole gate — confirm date
   extraction per source on a probe before committing the 120-day window.
2. Should JBF **semifinalists** (broad, ~20 per category per city) and
   **finalists/winners** (narrow) carry the same `src_tier`, or should semis be
   a higher-volume Tier-2 net and finalists a Tier-1? Semis are the better
   trigger (timely, large pool); winners are the better durable credential.
3. How aggressively do we dedupe against the existing `awards/` master — is a
   row that's already a durable award credential but *also* just got fresh press
   a new lead, or only a priority bump on an existing row?
4. For local mags/papers, is a curated domain seed list (per metro) maintainable,
   or do we lean entirely on Serper site-agnostic recency queries and accept
   noisier extraction?
