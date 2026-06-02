# Lead Engine 35 — Marketplace Avoidance List

**Motion:** Curation
**Vertical fit:** Bakeries, butchers, restaurants, specialty grocers (any operator that could but chooses not to be on third-party marketplaces)
**Suggested list name(s):** `marketplace_avoidance_direct_order`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run (rides the step-1 website crawl; net-new cost is a small Claude classify pass + optional IG-caption pull)

## Premise

When an operator writes "we don't use DoorDash," "pickup only," "order direct
from us," "support local — skip the apps," or "no third-party delivery" on
their site or in an IG caption, they're stating a worldview, not a logistics
note. They've done the margin math on 20–30% marketplace take rates, they care
about owning the customer relationship and the brand experience, and they've
*opted out* of the aggregator model on purpose. That is the exact psychographic
Table22 sells into: we are explicitly **not a marketplace** — we power the
operator's own direct, recurring program and leave the customer relationship
with them. This operator has already pre-qualified themselves on the core
objection.

In the two-score model this is primarily an **ICP-Fit refiner with a soft
Trigger**: marketplace-avoidance language is a durable belief signal (high ICP
Fit — this is the kind of owner who buys Table22), and "order direct from us"
copy is a standing invitation to a better direct channel (a mild, always-on
Trigger). It pairs best with a sharper time-bound trigger from another engine
(sold-out, video spike, ship-intent) — high-ICP / no-acute-trigger rows route
to nurture, not straight to sales.

The fit verticals are deliberately broad here because the *belief* cuts across
partner types: a butcher doing whole-animal shares, a weekend-drop bakery, a
neighborhood restaurant doing pickup-only family meals, a specialty grocer
doing curated boxes — all plausibly publish "order direct" copy. Partner-type
economics still rank the list (butcher $75.9k > wine > cheese > destination
restaurant ...), so the same words score higher under a butcher than under a
fast-casual.

## Recipe

A **curation-overlay** engine, run CSV-in / CSV-out like `detect_clubs.py`. It
scores a known candidate universe for marketplace-avoidance / direct-order
language and stamps the belief signal (with a verbatim quote) onto operators we
already know. The website pass rides the existing crawl; it does not re-discover
businesses.

1. **Seed the candidate set, don't re-discover.** Start from the most recent
   enriched corpus (`output/2_enriched_websites.csv` onward — step-1 already
   ran) and the niche lanes (`butcher/`, `best_wine_shops/`, `directories/`,
   awards master). Require a resolved `website`. For net-new geography, seed
   Serper Maps off `research/trendy_neighborhoods/` for `bakery | butcher |
   restaurant | specialty grocer`, applying the standard quality floors and
   `config.CHAIN_KEYWORDS` filter from `discover.py`.

2. **Mine site copy on the step-1 crawl (no new fetch).** The `enrich.py`
   **step-1 (websites)** 10-thread crawl already pulls page HTML for ecommerce /
   email-signup / social detection. Add a marketplace-language parse pass over
   the same fetched HTML (home, ordering/menu, about, FAQ, footer). Run a regex
   bank first — cheap, no LLM for the gate:

```
AVOID_PATTERNS = (
  r"(we\s*(do\s*not|don'?t|no\s*longer)\s*use\s*)(door\s*dash|doordash|uber\s*eats|grubhub|postmates|seamless|caviar|chowbus|slice|toast\s*takeout)",
  r"no\s*(third[-\s]?party|3rd[-\s]?party)\s*(delivery|apps?)",
  r"not\s*(available|listed)\s*on\s*(delivery\s*apps?|door\s*dash|uber\s*eats|grubhub)",
  r"(pickup|pick[-\s]?up|takeout)\s*(only|exclusively)",
  r"order\s*direct(ly)?(\s*(from\s*us|with\s*us|online|here))?",
  r"(skip|avoid|forget)\s*the\s*(apps?|middle\s*man|third[-\s]?party)",
  r"support\s*(local|small\s*business)\s*[-—,]?\s*(order|buy)\s*direct",
  r"keep(s)?\s*(your\s*)?(dollars?|money)\s*(local|with\s*us)",
  r"(we\s*)?(don'?t|do\s*not)\s*(do|offer)\s*delivery\s*apps?",
  r"call\s*(us|the\s*shop)\s*to\s*order",
  r"(no\s*commission|skip\s*the\s*fees?|avoid\s*the\s*\d{1,2}%)",
)
DELIVERY_BRANDS = (doordash, uber eats, grubhub, postmates, seamless, caviar, chowbus, slice, toast takeout)
```

   Record matched page URL + matched span so sales can cite it.

3. **Corroborate with marketplace ABSENCE (structured negative signal).** The
   strongest version of "marketplace avoidance" is not just words but *actual
   absence* from the apps. Best-effort: probe whether the business appears on
   DoorDash/UberEats/Grubhub. The repo has no marketplace-presence primitive
   today — add a lightweight `marketplace_presence` checker (httpx against each
   platform's public store-search/autocomplete by name+city, behind a flag).
   Treat a clean "stated avoidance + verified absence" as the highest-confidence
   row; treat words-only as still-valid but lower confidence. Gate the probe off
   by default until the lookups prove stable (anti-bot fragile — see Risks).

4. **Optional IG-caption pass (reuse, don't rebuild).** For rows with a resolved
   IG handle, scan recent captions for the same language using the
   `instagram-post-scraper` Apify actor (the same actor `enrich.py` step-7 uses),
   batched in groups of 30. Restrict to the captions already pulled where a
   `2_enriched_posts.csv` exists to avoid a fresh Apify burn; only scrape
   net-new handles. This is additive corroboration, not a requirement.

5. **Compute an avoidance score (distinct surfaces + specificity):**

```
named_app_call_out = matched a "we don't use <DoorDash/UberEats/...>" pattern
pickup_only        = matched pickup/takeout-only
order_direct       = matched "order direct" / "call to order"
support_local      = matched "support local / keep dollars local"
verified_absent    = marketplace_presence probe found NO listing (step 3, when on)
ig_corroborated    = same language found in an IG caption (step 4)

avoidance_score = min(100,
      30*(1 if named_app_call_out else 0)   # explicit, intentional opt-out
    + 20*(1 if order_direct else 0)         # standing invite to a direct channel
    + 15*(1 if pickup_only else 0)
    + 10*(1 if support_local else 0)
    + 15*(1 if verified_absent else 0)      # absence corroborates the words
    + 10*(1 if ig_corroborated else 0))

trigger_tier = 1 if avoidance_score>=55 else 2 if avoidance_score>=35 else 3
```

6. **LLM disambiguation (cheap, targeted).** For ambiguous matches, run an
   `awards/llm_extract.py`-style pass with `claude-haiku-4-5-20251001` (the model
   `scrape_beli` uses) over the matched snippet to (a) reject the inverse case —
   "we're now ON DoorDash!", "order delivery via Grubhub" — which the regex can
   trip on, and (b) emit a one-line `trigger_summary` sales can quote. Prefix any
   SDK-importing script with `unset ANTHROPIC_API_KEY &&` (empty-key shell
   gotcha).

7. **Qualify against ICP before handoff.** Run `reclassify.py` (`partner_type` /
   `business_type_v2` + wine-bar claw-back) and join `detect_clubs.py` (existing
   club = positive platform-switch signal, not a DQ). Hard-filter
   liquor-store / chain / delivery-only / ghost-kitchen / caterer leakage and the
   wine commodity-SKU exclusion list. Feed survivors to `score.py` for the /100
   ICP Fit (do **not** touch `config.SCORING_WEIGHTS` — SHAP-aligned).
   **Final list = high `avoidance_score` AND ICP Fit (A/B tier).**

## Output schema

```
output/marketplace_avoidance/marketplace_avoidance_direct_order_<YYYYMMDD>.csv
source = "marketplace_avoidance_direct_order"
tier = <1|2|3>                       # = trigger_tier from avoidance_score
business_type = butcher | bakery | restaurant | specialty | wine_store | cheese
distinction = "Publicly opts out of delivery apps / 'order direct' — Table22 = the non-marketplace direct channel"
year = <YYYY of the crawl / most-recent matched caption>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    avoidance_score, trigger_tier,
    named_app_call_out,        # bool — explicit "we don't use <app>"
    apps_named,                # which marketplaces called out (pipe-delim)
    pickup_only, order_direct, support_local,   # bools
    verified_absent,           # bool — marketplace-presence probe found no listing
    marketplace_presence_checked,  # which platforms probed (pipe-delim)
    ig_corroborated,           # bool — same language in an IG caption
    matched_terms,             # pipe-delim regex families hit
    avoidance_snippet,         # 1-3 verbatim quotes for outbound
    evidence_url,              # page (or post URL) the quote sits on
    scan_date,
    icp_fit_score, partner_type, has_club   # joined from score.py / detect_clubs
```

## Volume & cost

Overlay on a known set; spend bounded by candidate count, not a fresh crawl.

- Input universe (enriched corpus + niche lanes), deduped: **~8–12K rows** with
  a `website`.
- Website language parse: **free** — rides the step-1 10-thread crawl; +1 parse
  pass over already-fetched HTML.
- Marketplace-presence probe (step 3, when enabled): httpx lookups, no API cost;
  treat as a ~$0 but rate-limit-bounded ~1–2h pass on the subset with a regex
  hit (~600–1,000 rows).
- IG-caption corroboration (step 4): only net-new handles via
  `instagram-post-scraper` ≈ $0.004–0.006/handle; ~1,000 net-new handles ≈
  **$5–6**.
- Haiku disambiguation on regex hits (~600–1,000 short prompts): **≈ $3–5**.
- **Per-run total: ~$10–15** (well under target).
- **Net-new / re-surfaced qualified leads per run:** of ~8–12K rows, explicit
  marketplace-avoidance language hits a **small but high-conviction ~4–8%**
  (~400–900 rows). After ICP gate + `avoidance_score >= 35` and A/B Fit, expect
  **~150–300 qualified rows**; ~30–60 hit Tier 1 (named-app call-out + order-
  direct, ideally verified-absent). Most are already in the universe — the value
  is a quotable belief signal that pre-clears the "you're just another
  marketplace" objection.

## Refresh cadence

**Quarterly.** Marketplace-avoidance copy is a *durable belief*, not a perishable
event — site language rarely changes week to week, so frequent re-scrapes add
little. Re-run when the underlying enriched corpus is refreshed, or quarterly to
catch operators who newly *added* "we left DoorDash" copy (often after a fee
hike or a bad marketplace experience — a fresh emotional trigger worth catching).
The marketplace-presence probe (step 3) drifts faster than copy; re-probe Tier 1
rows before each outbound push.

## Risks

- **Inverse-match false positives.** Regex on `doordash` / `uber eats` will catch
  *positive* mentions ("now on DoorDash!", "order delivery via Grubhub") as well
  as avoidance. The Haiku pass (step 6) is load-bearing — never ship on raw regex
  hit alone; require confirmed *opt-out* sentiment.
- **Stale / aspirational copy.** "Order direct" boilerplate on a templated site
  may not reflect a real margin/brand stance. Weight `named_app_call_out` (an
  intentional, specific opt-out) far above generic "support local" filler.
- **Marketplace-presence probe is unbuilt and fragile.** No existing primitive;
  DoorDash/UberEats/Grubhub search endpoints are anti-bot and change often, and
  name+city matching is noisy (false "absent" when the listing exists under a
  variant name). Ship words-only first; keep `verified_absent` behind a flag and
  treat absence as corroboration, never a sole gate.
- **Anti-ICP leakage.** Liquor stores ("order direct, skip the apps"), chains,
  caterers, ghost kitchens, and pizza-first shops can all publish this copy.
  Enforce `config.CHAIN_KEYWORDS` + the liquor-license filter + the wine
  commodity-SKU exclusion list (and City Hive / Spot Hopper ESP red flags)
  upstream of scoring. A delivery-only ghost kitchen literally cannot publish
  "pickup only" honestly — but caterers will.
- **Wine-bar exclusion.** Wine bars mostly excluded (low Peak AGMV) except
  geographic-monopoly cases — let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake-only bakery doing "pickup only / order
  direct" is still single-product; cap at Tier 2 per the single-product demotion
  rule. Carry the input row's `partner_type` and apply the cap.
- **Small-market metrics run low; static social understates brand.** A rural shop
  may have strong direct-order conviction and thin social — this engine scores
  the *belief*, not engagement, so it's relatively robust here. Do not let an
  absent IG-corroboration signal pull a strong site-language match down; `step 4`
  is additive only.
- **Restaurant ceiling.** Restaurants are a soft-fit vertical here (neighborhood
  restaurant $32.0k, well below butcher/wine/cheese). A pickup-only restaurant is
  valid but should not crowd out high-AGMV verticals — partner-type weighting in
  `score.py` handles this; don't over-index on restaurant volume in the regex.

## Repo placement

```
marketplace_avoidance/
  __init__.py                    # engine constants; registers regex + leak lists
  signals.py                     # AVOID_PATTERNS, DELIVERY_BRANDS, inverse-match guards
  detect_language.py             # parse layer over enrich.py step-1 crawl HTML (site copy match)
  marketplace_presence.py        # NEW: httpx probe of DoorDash/UberEats/Grubhub by name+city (flagged)
  ig_corroborate.py              # optional instagram-post-scraper caption pass (net-new handles only)
  classify.py                    # Claude haiku-4-5: confirm opt-out sentiment, trigger_summary
  aggregate.py                   # avoidance_score, ICP gate (reclassify + detect_clubs join), dedupe
  finalize.py                    # canonical schema writer, date-stamped output
discover_marketplace_avoidance.py # orchestrator (mirrors discover_awards.py shape):
                                   # --input <enriched_or_scored.csv>, --resume,
                                   # --enable-presence-probe, --enable-ig
```

Refactor target: extract the `enrich.py` **step-1** HTML-fetch + parse layer into
a shared `enrich_websites_lib` so `detect_language.py` reads the same fetched
pages without re-crawling (the same shared-lib argument Engines 02, 05, and 19
raise). Reuse `enrich.py` step-7's `instagram-post-scraper` wrapper for the
optional caption pass rather than re-declaring the actor ID / batching. The
**`marketplace_presence` probe** is the only genuinely new infra this engine
needs — no existing lane checks third-party-marketplace listing state; keep it
flagged, throttled, and best-effort until validated.

## Open questions

1. **Is `verified_absent` worth building, or is stated-avoidance enough?** Words
   alone may carry the full signal; the marketplace-presence probe is the most
   fragile, highest-maintenance piece. Run a probe on ~200 stated-avoidance rows
   first — if site copy and verified absence agree >90% of the time, the probe
   adds little and we ship words-only.
2. **Should "we just LEFT DoorDash" be its own higher-priority bucket?** A fresh
   departure (often fee-hike-driven) is an acute emotional trigger, not just a
   standing belief — arguably the highest-converting sub-cohort and worth a
   dedicated `recently_left_marketplace` flag if we can date the copy.
3. **How much does this overlap Engine 09 (tech-ready, no subscription) and the
   `email_list_no_monetization` engine?** Marketplace-avoiders who already run a
   direct-order site + email list are the cleanest Table22 fit — do we cross-
   join into a triple-confirmed cohort, or keep this list standalone?
4. **Restaurant inclusion threshold.** Do we admit neighborhood restaurants at
   all given their lower AGMV, or restrict this engine's restaurant rows to
   destination restaurants (where pickup-only family-meal programs have proven
   recurring demand)?
