# Lead Engine 17 — Reservation Refresh Pain List

**Motion:** Curation (with a hard Trigger overlay — customer-effort language IS the trigger)
**Vertical fit:** Destination restaurants (primary); upper-tier neighborhood restaurants, wine bars only where geographic-monopoly
**Suggested list name(s):** `reservation_refresh_pain`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run (Serper Web/social search + Claude classify; rides existing availability lane for verification)

## Premise

`reservation_difficulty` is the #2 SHAP feature behind Partner Type, and the
phase-8 composite measures it three ways — platform signal (40%), review-text
sentiment (35%), real-time availability (25%). All three are operator- or
platform-side proxies. **This engine captures the demand side directly: the
customer's own broadcast of irrational effort to get in.** When a diner posts
"been refreshing Resy for three weeks," "set alerts and still couldn't get a
table," or "booked for months out — gave up," they are publicly pricing their
own willingness to pay for guaranteed access. That is the exact unmet demand a
Table22 membership / prepaid-access / drop program monetizes.

This is a cleaner trigger than a supply-side scan (Engine 05) because it proves
demand *exceeds capacity from the buyer's perspective* — people are exerting
effort, not just finding tables full. It maps to the two-score model as a strong
**Trigger** ("your superfans are fighting for tables and losing — let them pay
for access") that co-occurs with **ICP Fit**: only demand-saturated,
brand-rich destination restaurants ($60.5k avg Peak AGMV) generate this kind of
public lament. Volume is concentrated in restaurants because the
reservation-refresh behavior is a restaurant phenomenon — this is a focused,
high-precision destination-restaurant engine, not a cross-vertical one.

It is a **Curation** engine: the signal is strongly ICP-correlated (you don't
refresh Resy for a chain), so the gate is lighter than a pure volume play — but
hype-cycle one-offs, permanently-closed venues, and out-of-market mentions can
fake it, so we curate and verify before sales.

## Recipe

The new work is **harvesting and classifying customer-generated effort
language across public social/review surfaces**, then verifying against the
real-time availability lane we already run. We reuse Serper Web, the step-8
availability hooks, the step-5 review-text miner, and the `scrape_beli` Claude
extraction pattern.

1. **Build the effort-language query set.** Run **Serper Web**
   (`google.serper.dev/search`, the same client the press step uses) against
   the surfaces where diners vent, site-scoped where it helps precision:

   - Reddit: `site:reddit.com (r/FoodNYC OR r/AskNYC OR r/LosAngeles OR
     r/ChicagoFood OR r/foodie) "<phrase>"`
   - X/Twitter: `site:twitter.com OR site:x.com "<phrase>"`
   - TikTok captions/titles: `site:tiktok.com "<phrase>" reservation`
   - General web (blogs, eater/infatuation comment threads): `"<phrase>"
     restaurant <city>`

   Effort-language phrase seeds (case-insensitive; quote for exact match):

   - **Refresh grind:** `keep refreshing Resy`, `refreshing (Resy|OpenTable|
     Tock|the app)`, `refresh at 9am`, `drops at midnight`, `set an alarm for`,
     `camping on Resy`
   - **Alert tooling:** `(Resy|reservation) (alerts?|notifications?)`,
     `(using|set up) (Appointment Trader|ResNotify|notify)`, `bots? for
     reservations`, `paid for a reservation`
   - **Impossible / sold-out:** `impossible to get (a table|in|a reservation)`,
     `(reservations?|tables?) (sold out|gone) in (seconds|minutes)`, `can'?t
     get (a table|in|a reservation)`, `no availability for (weeks|months)`
   - **Months-out / waitlist:** `booked (for|out|solid for) months`, `booked
     up (weeks|months) out`, `(month|6 weeks)-long waitlist`, `still on the
     waitlist`, `gave up trying`

2. **Resolve mention → venue.** Each hit names (or implies) a restaurant +
   city. Pass the snippet to **Claude** (`claude-haiku-4-5-20251001`, the model
   `scrape_beli` uses) to extract `restaurant_name`, `city`, `state`, and a
   normalized `effort_type`. Reuse the `scrape_beli` caption-extraction approach
   (it already turns messy IG captions into restaurant mentions). Prefix the
   script with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

3. **Resolve venue → canonical row.** Join extracted names against the existing
   enriched corpus (`output/2_enriched_*.csv`) and awards master by fuzzy
   name+city. Misses go to a thin **Serper Maps** lookup (one query per unique
   name+city) to attach `website`, phone, Google rating/review count, and
   `business_type` — same discovery primitive as `discover.py`, no full crawl.

4. **Verify with real-time availability (corroboration, not gate).** For
   resolved restaurants, run the **step-8 availability** probe (OpenTable via
   Apify + Resy API): a venue diners complain about that *also* shows zero
   real-time availability across party size 2/4 for the next 14–30 days is a
   hard, triple-corroborated hit (customer effort + platform scarcity). Treat a
   failed/blocked availability check as missing-bonus, not disqualifying — the
   Resy client is fragile.

5. **Cross-check the step-5 review-text miner.** Where the venue carries
   step-5 `reviews` enrichment, pull its existing reservation-difficulty
   sentiment score; agreement across independent surfaces (review text + social
   effort + real-time zero) is the strongest possible signal and orders the
   outbound queue.

6. **Apply the ICP gate + score effort strength.** Run `reclassify.py`
   (`partner_type` / `business_type_v2`, wine-bar claw-back) and carry
   `has_club` from `detect_clubs.py` (existing club = positive switch signal).

```
DISQUALIFY if:
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar -> exclude UNLESS geographic_monopoly flag
  venue permanently closed / relocated (Maps "permanently closed")
  mention is out-of-market / not a US venue (country != US)

DEMOTE (cap Tier 2, do not DQ):
  neighborhood restaurant (real but lower headroom than destination)
  thin corroboration: single social mention, no review-text or real-time backup
  static-social-only / small-market venue (never DQ — understates brand)

effort_strength:
  +3 verified real-time zero-avail (Resy/OT empty 14-30d) AND >=1 effort mention
  +3 active alert/bot tooling or paid-reseller mention (Appointment Trader)
  +2 multiple distinct effort mentions across >=2 surfaces (Reddit + X, etc.)
  +2 "refreshing / set alarm / drops at midnight" recurrence language
  +1 single "booked for months" / "impossible to get in" mention
  +1 if step-5 review-text reservation-difficulty sentiment is high
  +1 if has_club == True (proven recurring demand)

QUALIFY (engine output) if: passes ICP gate AND effort_strength >= 2
```

7. **Hand off to scoring.** Emit the canonical CSV (below); run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). Effort
   columns ride as evidence; `effort_strength` orders outbound inside a tier.
   The verified real-time slice can feed the phase-8 `reservation_difficulty`
   composite where the row reaches enrichment (see Open questions on
   double-counting).

## Output schema

```
output/reservation_refresh_pain/reservation_refresh_pain_<YYYYMMDD>.csv
source = "reservation_refresh_pain"
tier = <1|2|3>   # 1 = destination + verified/triple-corroborated; 2 = neighborhood or single-surface; 3 = ICP-soft
business_type = restaurant
distinction = "Diners fight to book: {effort_summary} — sell access via Table22"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    effort_type            # refresh_grind | alert_tooling | reseller | impossible | months_out | waitlist
    effort_strength        # int, intra-tier outbound ordering
    found_on               # reddit | twitter_x | tiktok | web | multiple
    effort_evidence_url    # permalink to the post/thread that matched
    effort_snippet         # verbatim matched quote ("been refreshing Resy for 3 weeks")
    effort_recency_days    # days since most recent mention
    effort_surface_count   # distinct surfaces the venue appeared on
    rt_availability_zero   # bool — Resy/OpenTable showed no availability 14-30d
    review_resdiff_sentiment # carried from step-5 review-text miner (if enriched)
    trigger_summary        # one-line Claude-written outbound hook
    has_club               # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

## Volume & cost

- Effort-language harvest: ~8 phrase clusters × ~4 surface scopes × ~30 top US
  metros ≈ a few hundred Serper Web queries; Serper is cheap (~$0.001–0.003 /
  query) → **≈ $1–3**.
- Claude Haiku extraction (mention → venue) on ~2–4K raw snippets, short
  prompts: **≈ $3–5**.
- Serper Maps backfill for unresolved venues (~300–600 unique names): **≈ $2–4**.
- Real-time availability probe (step-8 actors) on resolved restaurants only
  (~400–800): reuses existing Apify/Resy hooks, **≈ $6–12**.
- **Per-run total: ~$15–25.**
- **Net-new qualified leads per run:** raw snippets ~2–4K collapse to ~400–800
  unique venues after resolution+dedupe; after ICP gate + `effort_strength >=
  2`, expect **~120–250 qualified rows**. A meaningful share will already sit
  in our corpus or be T22 partners — the value is the *trigger* (and the
  re-investment / upsell flag on existing partners), which re-prioritizes them
  for outbound now.

## Refresh cadence

**Monthly.** Reservation-effort chatter is recency-sensitive — "refreshing for
three weeks" is a live trigger; the same post six months later is stale and the
venue may have shifted its release policy. Monthly keeps the outbound line
current without re-burning Serper/Claude on a thin incremental delta. Run a
heavier pass around restaurant-week, awards season (James Beard), and major
openings, when effort chatter spikes for the exact demand-saturated venues we
want.

## Risks

- **Hype-cycle one-offs vs durable saturation.** A brand-new opening generates a
  burst of "impossible to book" chatter that fades in weeks. Require recurrence
  or real-time/review-text corroboration before a Tier-1 trigger; record
  `effort_recency_days` and weight it.
- **Mention → venue ambiguity.** Customers misname venues, use nicknames, or
  omit the city. The Claude pass plus fuzzy Maps resolution will mis-attribute
  some; keep `effort_evidence_url` + `effort_snippet` so a human can verify the
  named venue before outbound.
- **Sentiment/negation traps.** "Finally got off the waitlist" or "you don't
  need to refresh, walk-ins are easy" are anti-signals that regex flags as
  hits. The Claude pass must read polarity, not just keyword presence.
- **Permanently-closed / relocated venues.** Old threads point at venues that
  no longer exist. Counter-check Google Maps "permanently closed" in the Maps
  backfill and DQ.
- **Wine-bar / cocktail-bar leakage.** "Impossible to get into" applies to
  buzzy bars too. Enforce wine-bar exclusion (except geographic-monopoly), the
  `reclassify.py` wine-bar claw-back, and the cocktail-bar disqualifier.
- **Small-market under-representation.** Reservation-refresh culture skews to
  big metros (NYC/LA/SF/Chicago) — a demand-saturated rural destination
  restaurant may produce zero social chatter. This engine will miss them;
  that's a precision/recall tradeoff, not a bug. Don't infer absence-of-chatter
  = absence-of-demand; lean on Engines 05/10 for small markets and **never DQ
  on static-only social** (it understates brand).
- **Reseller signal is double-edged.** Appointment-Trader / bot mentions are a
  strong demand proof, but also surface venues so saturated they may resist any
  access program; treat as high-priority but flag for a tailored pitch.
- **Resy/OpenTable fragility.** The Resy client is reverse-engineered and
  rate-limits; treat real-time zero-availability as a *bonus* hard signal, not a
  gate.
- **Platform rate-limits / blocking on social search.** Serper Web indexes a
  subset of Reddit/X/TikTok; deep comment threads may be missed. Accept partial
  recall — precision matters more than completeness for a trigger list.

## Repo placement

Standalone package mirroring the niche-lane shape (Engine 03 / Engine 05
shape), reusing the step-8 availability hooks and the `scrape_beli` extraction
pattern as libraries.

```
reservation_refresh_pain/
  __init__.py                  # engine constants; registers effort-language query set
  signals.py                   # EFFORT_PHRASES, SURFACE_SCOPES, RESELLER_TOOLS, negation/anti-signal rules
  harvest.py                   # Serper Web across surfaces (reuse press-step client); raw-snippet collection
  resolve.py                   # Claude haiku-4-5: snippet -> {name, city, state, effort_type, trigger_summary}
  match.py                     # fuzzy join to enriched corpus + awards master; Serper Maps backfill for misses
  check_availability.py        # wraps step-8 Resy/OpenTable for resolved-restaurant subset
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), effort_strength, recency/recurrence, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_reservation_refresh_pain.py  # orchestrator: harvest -> resolve -> match -> avail-check -> gate -> finalize
```

Refactor target: extract the `enrich.py` **step-8** availability functions
(OpenTable Apify call + Resy lookup) into a shared `enrich_availability_lib` so
`enrich.py`, `reservation_refresh_pain/check_availability.py`, and the Engine-05
scarcity scanner all use one implementation (the shared-lib argument Engines 03
and 05 both raise). Likewise reuse `scrape_beli`'s caption-extraction prompt
scaffolding for `resolve.py` rather than re-authoring the mention extractor.

## Open questions

1. **Overlap with Engine 05 (supply-side scan).** This engine and the
   reservation-impossible scanner should converge on the same venues from
   opposite directions. Do we merge them into one reservation-scarcity master
   (demand + supply corroboration as a single confidence score), or keep two
   lists with distinct outbound timing?
2. **Feeding `reservation_difficulty`.** Should verified real-time scarcity from
   this engine write back into the phase-8 composite (40/35/25), or stay
   evidence-only to avoid double-counting against SHAP-aligned weights?
3. **Surface weighting.** Reddit threads, X posts, and TikTok captions differ in
   signal quality and recency. Should `effort_strength` weight surfaces
   differently (e.g. Reddit thread depth > a single tweet), and is TikTok worth
   the lower text-extractability?
4. **Reseller-market data as a direct source.** Appointment Trader publishes
   resale prices/volume per venue. Is scraping it (a fourth surface) worth a
   dedicated module — resale liquidity is arguably the purest "people pay for
   access" proof we could find?
