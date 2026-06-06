# Lead Engine 25 — Hiring Intent List

**Motion:** Curation (a Trigger-led overlay; the *kind* of role posted also lifts ICP Fit)
**Vertical fit:** All — restaurants (destination + neighborhood), wine, butcher, cheese, bakery, specialty grocer, deli/market
**Suggested list name(s):** `hiring_intent_growth_roles`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$10–18 per run (Serper Web/Maps job-board mining + a Claude classify pass; no new Apify spend)

## Premise

A business that is actively hiring a **fulfillment lead, ecommerce manager, events manager, marketing manager, wine club manager, production baker, butcher apprentice, operations manager, or "special projects" role** is broadcasting two things at once. First, **growth intent** — you don't post an ecommerce or events role unless you've decided to scale a channel beyond what the owner can run alone. Second, **operational pain** — the role exists because demand is outrunning the current team's capacity. Both surface in a job post weeks or months before they show up on the website, the social feed, or a "we're now shipping nationwide" announcement.

This maps directly onto the demand-over-capacity thesis: a hire is a capacity expansion the operator is *paying for*, which is the strongest possible admission that demand exists and is currently under-served. It also keys on the dominant SHAP feature — **Partner Type** — because the *role title* is a proxy for partner sophistication and for the exact economic lane we want (a "wine club manager" req is a butcher/wine/cheese-grade signal; a "production baker" places a real bakery; a "fulfillment/ecommerce" hire proves shippable product + intent to ship at volume). ICP Appendix D names the corroborating roles outright: Catering Manager, Events Manager, Director of Operations, Marketing Director/Manager, Special Projects Lead correlate with willingness to test new growth channels.

In the two-score model this is a **Trigger-first** engine with a co-located ICP lift. The open req is the reason-to-contact-now ("saw you're hiring an events manager — that's exactly the program Table22 runs for you"); the role *category* nudges ICP Fit (a wine-club-manager or ecommerce-fulfillment posting is high-fit, a generic line-cook posting is not). The cleanest rows pair a growth-channel role with an already-high-ICP partner type.

## Recipe

Build out `scripts/discover_jobs.py` (referenced in the repo but not yet implemented) as the source-scrape lane, then run discovered employers through the standard ICP gate. This is a **discovery → match-to-known → enrich → score** loop, not a pure overlay, because the job board surfaces businesses we may not have in the corpus yet.

1. **Harvest job posts (Serper Web, `scripts/discover_jobs.py`).** Serper has no jobs endpoint, so mine job-board result pages with `google.serper.dev/search` using `site:` + role queries. No new external tool needed — this is the existing press-step Serper Web primitive (`enrich.py` step 4) pointed at job hosts instead of food-media domains.

   ```
   JOB_HOSTS = [
     "boards.greenhouse.io", "jobs.lever.co", "apply.workable.com",
     "indeed.com", "ziprecruiter.com", "culinaryagents.com",   # restaurant/food-specific
     "poachedjobs.com", "goodfoodjobs.com",                    # specialty-food specific
     "linkedin.com/jobs", "snagajob.com",
   ]
   ROLE_QUERIES = [
     # growth-channel / high-signal
     "ecommerce manager", "fulfillment lead", "fulfillment manager",
     "events manager", "events coordinator", "marketing manager",
     "wine club manager", "club manager", "membership manager",
     "subscription manager", "special projects", "director of operations",
     "operations manager", "retail operations",
     # vertical craft roles (place the partner type + prove product depth)
     "production baker", "head baker", "lead baker",
     "butcher apprentice", "lead butcher", "charcuterie",
     "cheesemonger", "wine buyer", "sommelier",
   ]
   ```

   For each `(JOB_HOST, ROLE_QUERY)` issue `"<role>" "<food-business keyword>" site:<host>` (food keyword from `config.py` business-type query banks so we don't pull tech/healthcare hits). Capture the employer name, posting URL, posting title, location, and snippet. Bias geography toward `research/trendy_neighborhoods/` for the city-restricted passes.

2. **Resolve poster → business (Serper Maps + dedupe).** A job post gives an employer name + city but not a website/phone. Run each unique employer through `discover.py` / `scripts/fresh_icp_search.py` Serper Maps ("`<employer name>` `<city>`") to attach the canonical Maps record (website, phone, rating, review count, Google type). Then `dedupe_existing.py` (phone-first, then name+address) against the existing corpus so we tag rows as **already-known** vs **net-new** and never double-count.

3. **Classify role intent (Claude, cheap pass).** Send each posting title+snippet to Claude (`claude-haiku-4-5-20251001`, the model `scrape_beli` uses) to label `role_category ∈ {ecommerce_fulfillment, events, marketing, club_subscription, operations, special_projects, craft_baker, craft_butcher, craft_cheese, wine_buyer_somm, other}` and write a one-line `trigger_summary` for outbound. Prefix the script with `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha). Drop `other` (line cook, dishwasher, server, cashier — no growth signal).

4. **Enrich matched employers (standard `enrich.py` steps).** For net-new businesses (and stale known rows), run the normal sequence — `websites` (step 1: ecommerce flag, email-signup, social, reservation platform), `instagram`/`facebook` (steps 2–3: `follower_count`), `reviews` (step 5), and for restaurants `availability` (step 8). The role signal rides alongside; scoring stays standard.

5. **ICP gate (curation pass).** Run `reclassify.py` (`partner_type` / `business_type_v2`, wine-bar claw-back) and `detect_clubs.py` (existing club is a **positive** switch-the-platform signal, carry `has_club` through, do not DQ). Reject anti-ICP before scoring; rank the trigger after:

   ```
   DISQUALIFY if:
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)   # restaurant GROUPS post the most reqs — biggest leak here
     posting is a staffing agency / restaurant-group corporate / PEO (not the operator)
     partner_type == liquor_store OR wine commodity-SKU leak (Tito's, Veuve, Barefoot,
         Yellowtail, BuzzBallz, Cupcake, ...) OR ESP red flag (City Hive, Spot Hopper)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first (non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}        # butcher lane only
     role_category == other (no growth signal)

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery (a production-baker req is real but caps Tier 2)
     static-social-only / thin metrics in a small market (understates brand — never DQ)

   intent_strength:
     +3 club_subscription role (wine club / membership / subscription manager) — buys exactly our program
     +3 ecommerce_fulfillment role — proves shippable product + intent to ship at volume
     +2 events role (Appendix D: packages experiences, repeat-buy muscle)
     +2 marketing | special_projects | operations (Appendix D growth-channel correlates)
     +2 craft role (production_baker / lead_butcher / cheesemonger / wine_buyer) on a high-ICP type
     +1 if posting age <= 45 days (live, hot trigger)
     +1 if has_club == True (already monetizing repeat demand — transition motion)
     +1 if multiple distinct growth reqs open at once (scaling hard right now)

   QUALIFY if: passes ICP gate AND intent_strength >= 3
   ```

6. **Hand off to scoring.** Emit the canonical CSV (below) and run `score.py` unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). `role_category` + `intent_strength` ride as evidence and order the outbound queue inside a tier.

## Output schema

```
output/hiring_intent/hiring_intent_growth_roles_<YYYYMMDD>.csv
source = "hiring_intent_growth_roles"
tier = <1|2|3>   # 1 = high-AGMV type + club/ecommerce/events req live now; 2 = craft/ops role or sweets-only; 3 = stale posting / ICP-soft
business_type = restaurant | wine | butcher | cheese | bakery | specialty_grocer | deli
distinction = "Hiring {role_category} — actively expanding capacity on a growth channel"
year = <discovery_year>
+ canonical: name, city, state, country, source_url (= job posting URL), blurb
+ evidence cols (preserve so sales can cite the trigger in outbound):
    role_category          # club_subscription | ecommerce_fulfillment | events | marketing | operations | special_projects | craft_baker | craft_butcher | craft_cheese | wine_buyer_somm
    posting_title          # verbatim req title
    posting_url            # canonical job-board link
    posting_host           # greenhouse | lever | culinaryagents | poached | indeed | ...
    posting_snippet        # verbatim text that matched
    posting_age_days       # parsed from listing date (drives live-trigger bonus)
    open_reqs_count        # distinct growth reqs open at this employer (scaling-hard tell)
    intent_strength        # int, intra-tier outbound ordering
    trigger_summary        # one-line Claude-written outbound hook
    match_status           # net_new | already_in_corpus
    has_club, club_type    # carried from detect_clubs.py (positive signal)
    partner_type           # from reclassify.py
```

Master union: `output/hiring_intent/hiring_intent_all_<YYYYMMDD>.csv`.

## Volume & cost

- Serper Web harvest: ~10 job hosts × ~22 role queries × city-bias passes ≈ **400–700 search credits**. At Serper's ~$0.001/credit ≈ **$0.50–1**. Many results are duplicate employers or non-food noise.
- After dedupe to unique employers and dropping non-food/`other`: expect **~600–1,200 distinct hiring food businesses** per national run.
- Serper Maps poster→business resolution on uniques (~1 credit each): **≈ $1**.
- `enrich.py` on net-new only (~40–60% are not in corpus, ≈300–700): websites crawl is free compute; IG/FB Apify at ~$0.002–0.003/profile in batches of 30 ≈ **$3–6**; reviews/availability for the restaurant subset ≈ **$3–6**.
- Claude Haiku classify pass (~1.5–2K short prompts): **≈ $2–3**.
- **Per-run total: ~$10–18.**
- **Net-new qualified leads per run:** of ~600–1,200 hiring businesses, the ICP gate + `intent_strength >= 3` keeps the growth-channel and high-ICP-craft reqs — expect **~250–450 qualified rows**, with **~80–150 Tier-1** (high-AGMV partner type + a live club/ecommerce/events req). A meaningful share already exist in our corpus — that's fine; the value is the *trigger*, which re-prioritizes them for outbound now.

## Refresh cadence

**Bi-weekly.** Job-post freshness is the entire value here — a req that's been open 90 days is either filled or stale, and the outbound line ("saw you're hiring…") dies on a closed posting. A 2-week cadence keeps `posting_age_days` low enough that most rows are genuinely live, while not re-burning Serper credits on the same long-open reqs every few days. Run an extra pass in **January and late summer** when food businesses staff up for the year and for Q4 fulfillment respectively.

## Risks

- **Restaurant-group / chain leakage — the biggest trap.** Multi-location groups and franchises post the *most* reqs (centralized HR, Greenhouse/Lever accounts) and will dominate raw harvest. Keep `config.CHAIN_KEYWORDS` + the `reclassify.py` coarse pass upstream of scoring, and explicitly drop corporate/PEO/staffing-agency posters — a "Director of Operations, 14 locations" req is anti-ICP no matter how growth-y the title.
- **Staffing-agency / aggregator noise.** Indeed/ZipRecruiter republish the same req under agency names and scrape-farms. Dedupe on employer (phone-first via `dedupe_existing.py`) and prefer the operator-direct hosts (Greenhouse/Lever/Poached/Good Food Jobs/Culinary Agents) as the canonical `source_url`.
- **Stale / closed postings read as live triggers.** Listing dates are inconsistent across boards and some never expire. Parse `posting_age_days`, weight it (+1 only if ≤45 days), and HTTP-check the posting still resolves before assigning Tier 1. A stale post is capability proof, not a now-trigger.
- **Liquor-store / wine-bar leakage.** A liquor store hiring a "wine buyer" is not curated wine. Keep the commodity-SKU exclusion (Tito's, Veuve, Yellowtail, Barefoot…), the City Hive / Spot Hopper ESP red flag, the wine-bar exclusion (except geographic monopoly), and the `reclassify.py` wine-bar claw-back upstream of `intent_strength`.
- **Sweets-only demotion.** A single-product bakery hiring a production baker is a real signal but caps at Tier 2 — don't let the craft-role bonus promote it on the trigger alone.
- **Small-market metrics run low.** A dominant rural butcher posting a "butcher apprentice" on Indeed will have thin social/review volume and may not be on the polished job boards at all. Weight relative local dominance + the hiring trigger over raw follower/review floors; **never DQ on static-only social** — it understates brand. Butcher/deli/specialty-grocer audiences also skew Facebook over IG; `follower_count` (IG + FB) already accounts for this.
- **Serper-as-jobs-board fragility.** There is no jobs API; we're scraping board result pages, which change layout and rate-limit. Back off, cache employer→business resolution between runs, and treat any single host going dark as degraded-not-broken (fall back to the remaining hosts).
- **Title ambiguity.** "Special projects" and "operations manager" appear in non-food and corporate contexts; the food-keyword query constraint + Claude `role_category` classify pass + `reclassify.py` partner-type gate are all required to keep these clean.

## Repo placement

Build `scripts/discover_jobs.py` from a stub into a real source-scrape lane, plus a small package for the multi-stage logic, mirroring the niche-lane shape and reusing the Serper Web (press-step) and `enrich.py` primitives as libraries.

```
scripts/discover_jobs.py            # orchestrator (referenced in repo, currently absent — implement here)
  python scripts/discover_jobs.py --all
  python scripts/discover_jobs.py --hosts greenhouse,lever,poached --roles club,ecommerce,events
  python scripts/discover_jobs.py --verticals wine,butcher,cheese
  python scripts/discover_jobs.py --master-only

hiring_intent/                      # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                       # JOB_HOSTS, ROLE_QUERIES, role->intent_strength weights
  harvest.py                        # Serper Web site:-query harvest -> raw postings
  resolve.py                        # Serper Maps poster->business + dedupe_existing join (net_new vs known)
  classify.py                       # Claude haiku-4-5 role_category + trigger_summary (unset ANTHROPIC_API_KEY)
  aggregate.py                      # ICP gate (reclassify + detect_clubs join), intent_strength, posting_age, tiering
  finalize.py                       # canonical schema writer, date-stamped output + master union

config.py
  + JOB_HOSTS / ROLE_QUERIES (or keep in hiring_intent/__init__.py)
  + reuse business-type query banks (food keywords), CHAIN_KEYWORDS, City Hive/Spot Hopper red flags
```

Refactor target: extract the **Serper Web search call** in `enrich.py` step 4 (press) into a shared `serper_web_lib` so `harvest.py` and the press step issue identical queries without duplicating auth/paging/back-off. Also reuse Engine 05's capacity-expansion logic if it lands first — a hiring req and a buildout permit are two reads of the same "expanding capacity now" trigger and should share a partner row (phone-first dedupe).

## Open questions

1. **People-data fallback for poster resolution.** When Serper Maps can't resolve an employer (no Maps presence, or name collision), do we accept the LinkedIn Jobs employer page as the canonical record, or drop the row? Appendix D names People Data Labs as a verification source — is bringing in a PDL/LinkedIn enrichment for the unresolved tail worth the new dependency?
2. **Per-board listing-date parsing.** Greenhouse/Lever expose post dates cleanly; Indeed/ZipRecruiter fuzz them ("30+ days ago"). How accurately can we compute `posting_age_days` per host, and should we HTTP-fetch each posting to confirm it's still open before Tier 1?
3. **Cross-engine dedupe with Engine 05 (capacity expansion) and Engine 12 (events).** A "events manager" req overlaps Engine 12's programming signal and Engine 05's expansion trigger. Do we merge triggers onto one partner row, or keep separate lists with separate outbound timing/copy?
4. **Do we mine the role title for seniority/scale?** "Director of fulfillment" vs "fulfillment associate" implies very different operation sizes — worth extracting a seniority axis to sharpen Tier 1, or too noisy across boards?
