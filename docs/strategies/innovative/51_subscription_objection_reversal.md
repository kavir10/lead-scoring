# Lead Engine 51 — Subscription Objection Reversal List

**Motion:** Curation (with a Trigger overlay — the complaint *is* the trigger, and it pre-loads the rebuttal)
**Vertical fit:** All — strongest on butcher / bakery / restaurant (delivery-fee + staffing pain) and wine / cheese / specialty grocer (wholesale-margin + marketplace-commoditization pain)
**Suggested list name(s):** `subscription_objection_reversal`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $25/run (rides existing Serper Web + step-1 crawl; net-new cost is a Claude classify pass + a small Apify caption pull)

## Premise

The hardest part of selling Table22 isn't finding businesses with demand — it's
getting past the reflexive "I don't want another platform / another fee / another
thing to manage" objection. This engine inverts that. It finds operators who have
**publicly complained** about the exact pains Table22 solves — 20–30% delivery-app
commissions, collapsing wholesale margins, unpredictable week-to-week demand, the
staffing churn of running a counter, and being commoditized inside a marketplace
where they compete on price next to chains. An operator who has already said "the
apps are killing us" out loud has *pre-articulated the objection and the wedge in
the same breath*: the right pitch isn't "add a platform," it's **margin control,
direct customer ownership, and predictable preorder volume** — which is precisely
the rebuttal to what they're angry about.

In the two-score model this is a **Trigger harvester layered on an ICP refiner**.
The complaint is a live, dated, emotionally-charged Trigger ("you just told the
world the apps take 30% — here's how to take that back"), and the *kind* of
complaint correlates with ICP Fit: operators who think in unit-margin and
customer-ownership terms are exactly the owner-operators who buy Table22 and run a
program well. It maps directly onto the demand-over-capacity thesis from the other
angle — these operators *have* the demand; what they're publicly mourning is that
the channel eating it is the wrong one. The unusual byproduct, like Engines 16 and
43, is **outbound copy**: a BDR opens by quoting the operator's own words back to
them, then reframes.

This is a **Curation** engine. Operator-complaint language is genuinely
ICP-correlated, but the surfaces it lives on (press quotes, Reddit, IG captions,
local news) are dense with noise — generic "small business is hard" venting,
chains, closed shops, and complaints that have nothing to do with the
direct-channel thesis. The gate that separates "delivery-app / margin / demand-
predictability pain Table22 reverses" from "my landlord raised rent" is
load-bearing, and net-new names must clear the full discovery floor + ICP gate.

## Recipe

A **discovery + trigger** engine modeled on `best_wine_shops/` (Serper-seeded
article discovery → httpx/selectolax fetch → Claude extraction) for the press/
forum surface, crossed with a `detect_clubs.py`-style overlay pass for known
operators' own sites and IG captions. It both re-surfaces known operators with a
fresh trigger and discovers net-new names that pain-press has named.

1. **Run two lanes in parallel — known-operator overlay + net-new discovery.**
   - *Overlay lane:* start from the enriched/scored corpus
     (`output/2_enriched_*.csv`, `custom-serper-scoring_*_all.csv`) and the niche
     lanes (`butcher/`, `best_wine_shops/`, awards/directories masters). These
     already cleared discovery floors and carry `website` / IG handle / `place_id`.
   - *Discovery lane:* fan out Serper Web (`google.serper.dev/search`, the same
     primitive `enrich.py` step-4 press drives) over complaint phrases × geography,
     biased toward `research/trendy_neighborhoods/` seeds. Pull from press,
     local-news, and forum surfaces.

2. **Seed the complaint lexicon (regex pre-gate, no LLM).** Cheap regex decides
   which pages/captions/reviews are worth a Claude call. Group by pain family so
   the family maps to the rebuttal:

```
COMPLAINT_PATTERNS = {
  "delivery_fees":   (r"(door\s*dash|doordash|uber\s*eats|grubhub|seamless|postmates|caviar)\s*(takes?|charges?|fees?|commission)",
                      r"\b(20|25|28|30|35)\s*%?\s*(commission|fee|cut|take[-\s]?rate)",
                      r"the\s*apps?\s*(are\s*)?(killing|crushing|eating|gouging|bleeding)",
                      r"third[-\s]?party\s*(fees?|commission|delivery)\s*(too\s*high|insane|brutal|unsustainable)"),
  "wholesale_margin":(r"wholesale\s*(margins?|prices?)\s*(too\s*low|don'?t\s*(work|pencil)|aren'?t\s*(worth|sustainable))",
                      r"(can'?t|barely)\s*make\s*(money|a\s*margin)\s*(on\s*)?wholesale",
                      r"selling\s*to\s*(retailers?|distributors?)\s*at\s*a\s*loss",
                      r"margins?\s*(are\s*)?(razor[-\s]?thin|getting\s*squeezed|disappearing)"),
  "demand_unpredict":(r"(never\s*know|can'?t\s*predict|impossible\s*to\s*forecast)\s*how\s*(much|many|busy)",
                      r"(slow|dead)\s*(weeks?|days?)\s*then\s*slammed",
                      r"(throw|toss|waste)\s*(out|away)\s*(so\s*much|unsold|product)",
                      r"feast\s*or\s*famine|boom\s*(and|or)\s*bust"),
  "staffing":        (r"(can'?t|hard\s*to)\s*(find|keep|afford)\s*(staff|labor|cooks?|counter\s*help)",
                      r"(staffing|labor)\s*(is\s*)?(a\s*nightmare|killing\s*us|our\s*biggest)",
                      r"(short[-\s]?staffed|understaffed)\s*(every|again|constantly)"),
  "commoditized":    (r"(race\s*to\s*the\s*bottom|competing\s*on\s*price)\s*(with|against)\s*(chains?|big)",
                      r"(marketplace|platform)\s*(buried|drowned|lost)\s*(us|our\s*brand)",
                      r"(just\s*another\s*(listing|logo)|invisible)\s*on\s*(the\s*app|doordash)"),
}
PAIN_TO_WEDGE = {                                   # the rebuttal each family pre-loads
  "delivery_fees":    "margin control + customer ownership (no 30% take)",
  "wholesale_margin": "direct retail margin via your own preorder channel",
  "demand_unpredict": "predictable, prepaid preorder volume you can plan around",
  "staffing":         "preorder smooths the rush; you staff to a known number",
  "commoditized":     "your brand + your customer, not a listing in a marketplace",
}
```

3. **Fetch the discovery-lane surfaces (httpx + selectolax, Playwright fallback).**
   Reuse the `best_wine_shops/` fetch pattern. Reddit public `/<thread>.json` is
   the primary Reddit path. Press / local-news articles are mostly static HTML.
   **Do not** build a Facebook-group scraper (login-walled, brittle) — take only
   Serper snippets there. Cache raw text to gitignored JSON per the `scrape_beli`
   convention.

4. **Overlay-lane surfaces (reuse, don't re-fetch).** For known operators, run the
   complaint regex over (a) site copy already pulled by `enrich.py` **step-1**
   (about / FAQ / blog pages — owners vent in "our story" and blog posts), (b) IG
   captions via the `instagram-post-scraper` Apify actor (the one step-7 uses,
   batches of 30; restrict to existing `2_enriched_posts.csv` captions where
   present, only scrape net-new handles), and (c) the step-5 Google-Maps-Reviews
   text — owner *responses* to reviews frequently contain "we left the apps
   because…" complaints.

5. **Classify pain + confirm it's a Table22-reversible objection (Claude, load-
   bearing).** Send regex-matched snippets to Claude (`claude-haiku-4-5-20251001`,
   the model `scrape_beli` uses) to (a) confirm the speaker is the **operator /
   owner**, not a customer venting (a customer complaint about fees is a different,
   weaker signal); (b) confirm the pain is one of the five reversible families, not
   generic "rent / supply chain / it's hard out here"; (c) label `pain_family`;
   and (d) emit a one-line `trigger_summary` plus the matched `wedge`. Prefix the
   script with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

6. **Resolve net-new names to a real business.** For discovery-lane mentions,
   run a `scripts/fresh_icp_search.py`-style Serper Maps lookup (`name + city`) →
   `place_id`, website, phone, rating, review count, Google `type`. Drop mentions
   that don't resolve to a single physical food business. Apply `discover.py`
   quality floors (restaurants ≥50 reviews / ≥4.2; niche ≥20 / ≥4.0; website
   required) and the `config.CHAIN_KEYWORDS` chain filter — but route endorsed-but-
   sub-floor small-market shops to `needs_review` rather than dropping (static
   metrics understate brand; see Risks).

7. **Score objection-reversal strength + recency.**

```
operator_confirmed = Claude confirmed speaker is owner/operator (hard requirement)
pain_families      = #distinct reversible families the operator hit
fee_or_margin_hit  = matched delivery_fees OR wholesale_margin (the sharpest wedges)
recency_days       = days since the complaint was published/posted
recurrence         = #distinct sources/posts where this operator complained

reversal_strength = min(100,
      40*(1 if operator_confirmed else 0)          # gate: customer venting != signal
    + 25*(1 if fee_or_margin_hit else 0)           # fee/margin = cleanest rebuttal
    + 15*min(pain_families, 3)/3                    # breadth of pain
    + 10*(1 if recency_days <= 180 else 0)         # live, still-raw trigger
    +  5*min(recurrence, 2)                         # repeated, not a one-off vent
    +  5*(1 if has_club else 0))                    # already runs a program = warmest

trigger_tier = 1 if reversal_strength>=55 else 2 if reversal_strength>=35 else 3
```

8. **ICP gate, then hand to scoring.** Run `reclassify.py` (`partner_type` /
   `business_type_v2` + wine-bar claw-back), join `detect_clubs.py` (`has_club`;
   existing club = positive switch signal, not a DQ), `dedupe_existing.py`
   (phone-first, then name+address) so re-surfaced names merge. Feed survivors to
   `score.py` **unmodified** — do not touch `config.SCORING_WEIGHTS` (SHAP-
   aligned). `reversal_strength` orders the outbound queue inside a tier.

```
DISQUALIFY if:
  liquor store (vs curated wine); wine commodity-SKU leak (Tito's, Veuve, Barefoot,
      Yellowtail, Josh, Cupcake, ...) or ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS); caterer; delivery-only/ghost kitchen
  pizza-first (non-artisanal); cocktail bar; wine bar UNLESS geographic_monopoly
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery; static-social-thin small-market (understates brand)
FINAL LIST = operator_confirmed AND passes ICP gate AND reversal_strength >= 35 (A/B on score.py)
```

## Output schema

```
output/demand_signals/subscription_objection_reversal_<YYYYMMDD>.csv
source = "subscription_objection_reversal"
tier = <1|2|3>                       # = trigger_tier from reversal_strength
business_type = butcher | bakery | restaurant | wine | cheese | deli | specialty
distinction = "Operator publicly complained about {pain_family}: '{best_quote}' — Table22 reverses it via {wedge}"
year = <YYYY of most-recent complaint>
+ evidence cols (preserve verbatim so sales can quote the operator + lead with the rebuttal):
    reversal_strength, trigger_tier,
    pain_family,            # delivery_fees | wholesale_margin | demand_unpredict | staffing | commoditized
    pain_families_all,      # pipe-delim if multiple
    wedge,                  # the PAIN_TO_WEDGE rebuttal for the dominant family
    operator_confirmed,     # bool — Claude confirmed owner/operator, not customer
    fee_or_margin_hit,      # bool — matched the sharpest wedge families
    best_quote,             # single most quotable operator sentence
    quote_samples,          # 1-3 verbatim operator complaints for outbound
    source_urls,            # press article / Reddit thread / IG post / review-response URL
    source_platform,        # press | local_news | reddit | ig_caption | site_copy | review_response
    recency_days, recurrence, scan_date,
    is_net_new,             # True if not previously in the corpus
    needs_review,           # complained but below discovery floor (small-market flag)
    icp_fit_score, partner_type, has_club   # joined from score.py / detect_clubs
```

## Volume & cost

- *Overlay lane:* runs over the existing corpus (~8–12K rows) reusing already-
  fetched step-1 HTML and step-5 review text — **free** parse pass. Net-new IG
  caption pulls via `instagram-post-scraper` ≈ $0.004–0.006/handle on ~800 net-new
  handles ≈ **$4–5**.
- *Discovery lane:* ~130 cities × ~5 pain phrases × ~4 verticals, URL-deduped,
  capped ~3 results/query → **~1,500–2,500 unique articles/threads**. Serper Web
  ≈ $0.001–0.003/query; ~2.5K queries ≈ **$3–7**.
- Fetch: httpx/selectolax free; Playwright fallback on ~10–15% blocked URLs is
  compute-only. **~$0.**
- Claude Haiku classify over regex-passing snippets (~1.5–2K short prompts,
  operator-confirmation is the heavy lift): **≈ $3–6**.
- Serper Maps resolution of net-new mentions (~1.5K, dedup to ~800 unique) ≈
  $0.003/lookup → **≈ $2–4**.
- **Per-run total: ~$12–22.**
- **Net-new + re-surfaced qualified leads per run:** operator-authored complaint
  language is *rare and high-conviction* — of ~10K screened + ~800 resolved
  net-new, expect the operator-confirmed gate + ICP gate + `reversal_strength>=35`
  to keep **~120–250 qualified rows**, of which **~30–70 are net-new** and
  **~25–50 hit Tier 1** (fee/margin pain, recent, owner-confirmed). The recurring
  value is the objection-pre-loaded outbound copy attached to each row.

## Refresh cadence

**Monthly, with event-driven spikes.** Most complaint language is a perishable
emotional trigger — a fee-hike rant or a "we're done with DoorDash" post is hottest
in the weeks after it's published. A monthly pass keeps `recency_days` fresh and
catches new press/forum chatter; dedup by source URL against prior runs and only
LLM-classify net-new snippets. Run an opportunistic spike whenever a sector-wide
trigger lands (a marketplace commission hike, a viral "restaurants vs delivery
apps" news cycle, a minimum-wage change) — those events produce a burst of
operator complaints across many cities at once, and the trigger is freshest then.

## Risks

- **Customer-vs-operator confusion is the dominant failure mode.** Most "DoorDash
  takes 30%" complaints online are written by *customers* about *their* fees, not
  operators about commission. A customer venting is a weak/irrelevant signal; the
  whole engine hinges on the Claude operator-confirmation gate (step 5). Never ship
  on raw regex hit — `operator_confirmed` is a hard requirement, not a score input.
- **Generic "small business is hard" noise.** Rent, insurance, supply-chain, and
  permitting complaints are real but **not Table22-reversible** — including them
  produces outbound where the rebuttal doesn't land. Gate strictly on the five
  reversible pain families; weight `fee_or_margin_hit` highest because it maps to
  the cleanest, most-credible wedge.
- **Inverse / sarcastic matches.** Regex on app names catches positive mentions
  ("now on DoorDash!") and sarcasm. The Claude pass must confirm genuine *negative*
  operator sentiment about the named pain.
- **Anti-ICP leakage through the complaint.** A liquor store, a 12-location chain,
  or a ghost kitchen can all complain about marketplace fees. Enforce
  `config.CHAIN_KEYWORDS` + the liquor-license filter + wine commodity-SKU exclusion
  + City Hive / Spot Hopper ESP red flags *upstream* of the strength score.
- **Wine-bar exclusion.** Wine bars mostly excluded (low Peak AGMV) except
  geographic-monopoly — let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake shop complaining about delivery fees is a
  valid trigger but single-product — cap at Tier 2; carry `partner_type` and apply
  the cap.
- **Small-market metrics run low; static social understates brand.** A rural
  butcher who posts one angry "the apps don't make sense out here" caption may have
  thin reviews/social. This engine scores the *complaint*, not engagement — route
  sub-floor-but-complained rows to `needs_review`, never hard-DQ on thin volume.
- **Press-quote recency drift.** An operator's fee complaint from a 2019 article is
  stale and may no longer reflect their stance (they may have since solved it).
  Always record `recency_days`; treat >12 months as low-confidence and prefer
  recent posts/articles.
- **Privacy/attribution for outbound.** Public press quotes and forum prose are
  fair to cite, but confirm policy before BDRs paste verbatim operator sentences;
  for IG-caption / review-response quotes, attribute to the operator's own channel.
- **Reddit / press fetch fragility.** Reddit `.json` rate-limits and increasingly
  needs auth; press sites vary in anti-bot. Checkpoint per batch, support
  `--resume`, and fall back to Serper snippets when a fetch fails.

## Repo placement

Standalone package mirroring the `best_wine_shops/` editorial-scraper shape for the
discovery lane and the `detect_clubs.py` overlay shape for the known-operator lane,
reusing Serper Web + Maps, the step-1 crawl, the step-5/7 Apify wrappers, and the
`awards/llm_extract.py` extraction helper.

```
demand_signals/                      # co-houses Engines 03/16/43 if built
  __init__.py                        # engine constants; registers pain lexicon + wedge map
  patterns.py                        # COMPLAINT_PATTERNS, PAIN_TO_WEDGE, COMPLAINT_SEED_PHRASES, SKU/ESP leak lists
  discover_pain_articles.py          # Serper Web fan-out (city x pain-phrase x vertical), URL dedup
  fetch_sources.py                   # httpx+selectolax happy path, Reddit .json, Playwright fallback; caches raw JSON
  overlay_known.py                   # complaint regex over step-1 site HTML + step-5 review responses + IG captions
  classify.py                        # Claude haiku-4-5: operator-vs-customer gate, pain_family, wedge, trigger_summary
  resolve_mentions.py                # Serper Maps name+city -> place fields for net-new (reuses fresh_icp_search shape)
  aggregate.py                       # discovery floors + chain filter, reversal_strength, ICP gate, dedupe_existing join
  finalize.py                        # canonical schema writer, date-stamped output
discover_subscription_objection_reversal.py  # orchestrator:
                                     # --input <enriched_or_scored.csv> (overlay lane),
                                     # --discover (net-new lane), --resume, --enable-ig
```

Refactor targets so we don't duplicate logic:

- Reuse `awards/llm_extract.py` directly for the Claude classify/extract step
  rather than re-declaring the SDK client / prompt scaffold.
- Reuse the `best_wine_shops/` httpx→Playwright fetch fallback rather than
  re-implementing it.
- Lift the Serper Maps name+city resolution body out of
  `scripts/fresh_icp_search.py` into a shared `serper_resolve_lib` (the same
  shared-resolver argument Engine 43 raises).
- Lift `enrich.py` **step-1** HTML fetch+parse into a shared `enrich_websites_lib`
  and reuse the step-7 `instagram-post-scraper` wrapper, so the overlay lane reads
  already-fetched pages/captions without re-burning crawls or Apify jobs (the same
  shared-lib argument Engines 16, 35, and 43 raise).

`config.py` knobs to add: `COMPLAINT_PATTERNS`, `PAIN_TO_WEDGE`,
`COMPLAINT_SEED_PHRASES`, `REVERSAL_STRENGTH_THRESHOLDS`, and the per-query result
cap. No genuinely new external infra is required — the only net-new logic is the
operator-vs-customer classification, which is a prompt, not a tool.

## Open questions

1. **Operator-confirmation precision.** Can Haiku reliably tell "owner complaining
   about commission" from "customer complaining about delivery fees" on short press
   quotes and Reddit snippets without author metadata? A labeled probe set should
   set the precision floor before launch — this gate is the entire engine.
2. **Press vs forum vs caption yield.** Which surface produces the highest density
   of *operator-authored, reversible* complaints? If press quotes dominate and
   Reddit/IG are mostly customers, the discovery lane should weight food-media +
   local-news domains and treat forums as secondary.
3. **Should "recently left a marketplace" be its own top-priority sub-bucket?** A
   dated "we just pulled off DoorDash" event overlaps Engine 35's
   `recently_left_marketplace` idea and is arguably the warmest cut here — do we
   cross-join, or keep a dedicated flag?
4. **Trigger half-life for outbound.** How fresh must a complaint be to lead with
   it? A fee rant loses punch fast once the operator adapts — should Tier 1 require
   `recency_days <= 90` rather than 180?
