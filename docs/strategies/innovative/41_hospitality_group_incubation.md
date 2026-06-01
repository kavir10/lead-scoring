# Lead Engine 41 — Hospitality Group Incubation List

**Motion:** Curation
**Vertical fit:** Restaurant groups launching a retail arm — in-house butcher counters, wine shops, bakeries, pantries/provisions shops, prepared-foods/market concepts spun out of a known restaurant brand
**Suggested list name(s):** `hospitality_group_incubation`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $15/run (Serper-heavy discovery + bounded Claude relationship extraction; no per-lead Apify unless an arm resolves to a real ICP business)

## Premise

Restaurant groups that launch a retail arm are the best-prepared D2C
prospects in the whole universe: they already have a demand engine (the
restaurant brand), operational sophistication (purchasing, cold chain,
labor), and a reason to extend revenue past the four walls — but they almost
never have a real commerce layer behind the new butcher counter / wine shop /
bakery. They are building exactly the *capacity* that Table22 monetizes, and
they're building it on top of *proven demand*. That is the demand-over-capacity
thesis in its cleanest form.

The retail arm also lands directly in the high-AGMV partner types. A group's
in-house **butcher counter** ($75.9k avg Peak AGMV), **wine shop** ($68.2k),
**cheese/provisions** ($63.8k), or **bakery** ($34.7k) inherits the parent's
audience, press, and chef credibility on day one — so the arm punches above
its standalone reviews/followers. The restaurant brand is the trust signal the
retail arm hasn't earned yet, which is why a standalone-scored newborn counter
looks weak but the *group-attached* one is strong.

In the two-score model this is a **Trigger** engine with an unusually strong
ICP backstop: the trigger is "group is launching / just launched a retail
concept," and ICP Fit is inherited from a parent brand we can usually verify
(press, awards, multiple acclaimed locations). The hard ICP nuance, from the
cheat sheet: a restaurant-group **butcher** arm qualifies *only if a public
retail counter exists* — back-of-house whole-animal programs that sell to the
kitchen, not to walk-in customers, are not ICP and must be filtered out.

## Recipe

No genuinely new external infrastructure is required — this is a Serper Web +
Claude relationship-extraction lane that resolves discovered retail arms back
through the existing discover → enrich → score loop. The one new concept is a
**group → arm graph**: we discover the parent restaurant group, then expand to
its retail children and treat each child as a candidate lead.

1. **Seed the parent-group universe.** Three converging sources:
   - **Press lane (Serper Web).** Reuse the press enrichment primitive
     (`enrich.py` step 4: Serper Web against the food-media domain list in
     `config.py`) with launch-intent query templates rather than award
     keywords. Seeds:

     ```
     "<group/restaurant> opens butcher shop"
     "<group/restaurant> opens wine shop" | "bottle shop" | "wine store"
     "<group/restaurant> launches market" | "provisions" | "pantry" | "general store"
     "<group/restaurant> bakery opens" | "to-go" | "prepared foods" | "shop"
     "restaurant group" + ("retail arm" | "marketplace" | "butcher counter" | "wine shop")
     "from the team behind <restaurant>" + ("shop" | "market" | "butcher" | "bakery")
     ```

   - **Known-group seed list.** Hand-seed a starter list of multi-concept
     hospitality groups already on our radar (the kind that spin out retail:
     Italian/market groups, steakhouse groups with a butcher case, wine-bar
     groups with a retail license). Store under `research/` as a seed CSV,
     mirroring `research/trendy_neighborhoods/`.

   - **Maps adjacency.** Reuse the `discover.py` Serper Maps primitive: for
     each parent address, query nearby same-name / shared-brand listings
     ("<group name> butcher", "<group name> market") to catch arms that share
     the brand but sit a few doors down.

2. **Extract the group → arm relationship (Claude).** Run press snippets +
   parent/child site copy through `awards/llm_extract.py`-style extraction
   (prefix `unset ANTHROPIC_API_KEY &&`). For each candidate, return:
   `parent_group`, `arm_name`, `arm_type` (butcher | wine | bakery | cheese |
   market/provisions | prepared_foods), `relationship` (owned-arm |
   collab/popup | franchise), `launch_date_or_status`, and a
   `public_retail_counter` boolean with the evidence sentence.

3. **Enforce the butcher public-counter gate (load-bearing).** Drop any
   `arm_type == butcher` row where `public_retail_counter` is false or
   unverifiable — a back-of-house dry-aging / kitchen-only program is not ICP.
   Require at least one of: retail hours, "shop"/"counter"/"market" page on the
   site, an ecommerce/order page, or a Maps listing with a storefront. Apply
   the same walk-in test, more loosely, to bakery/prepared-foods arms.

4. **Resolve each arm to a real business — Serper Maps + enrich.** For arms
   that look live, run the standard pipeline on the *arm itself* (not the
   parent):
   - `discover.py` Maps lookup to get the arm's phone/website/reviews and to
     apply the quality-floor + `config.CHAIN_KEYWORDS` checks (niche floor:
     ≥20 reviews / ≥4.0).
   - `enrich.py` step 1 (websites, 10-thread crawl): ecommerce flag,
     email-signup form, social links, reservation-platform detection — the
     "has a commerce layer yet?" read that decides build-vs-transition.
   - `detect_clubs.py` on the arm's site to flag any club the group already
     runs (existing club = positive platform-switch signal, not a DQ).
   - Standard `instagram`/`facebook` enrichment so `follower_count` exists; for
     butcher/deli/provisions arms, weight FB engagement (often beats IG here).

5. **Carry parent equity onto the arm.** A newborn retail arm scores thin on
   its own social/reviews, so attach the parent's evidence as inherited ICP
   support: parent press mentions, parent awards, parent follower base, number
   of parent locations. Store these in evidence columns; use them to lift the
   *qualification* read without re-tuning `config.SCORING_WEIGHTS`.

6. **Score the trigger.** Group launch × arm partner-type economics × recency ×
   public-counter verification. Live arms flow through `score.py` /100 on their
   own data; pre-/just-launched arms get a trigger score and an `icp_inferred`
   flag where social/reviews are too thin to score.

   ```
   ARM_TYPE_WEIGHT = {            # tracks partner-type avg Peak AGMV
       "butcher": 1.0, "wine": 0.95, "cheese": 0.9,
       "market_provisions": 0.8, "prepared_foods": 0.7, "bakery": 0.6,
   }
   recency = max(0, 1 - months_since_launch / 12)   # launch trigger perishes
   parent_equity = min(0.2, 0.05*parent_locations + 0.1*has_parent_press
                              + 0.05*has_parent_award)
   trigger = ARM_TYPE_WEIGHT[arm_type] * recency

   # butcher with no verified public counter is dropped, not demoted
   if arm_type == "butcher" and not public_retail_counter:
       drop()

   tier = 1 if (trigger + parent_equity >= 0.85 and counter_ok and not no_ecom_blocker) else \
          2 if (trigger + parent_equity >= 0.55) else 3
   # sweets-only / single-product bakery arms cap at Tier 2 per cheat-sheet
   ```

7. **Diff + emit.** Archive raw discovered arms per run; diff against the prior
   run and against the current scored universe (phone-first via
   `dedupe_existing.py`) so the master only flags arms that are newly launched
   or newly net-new to our list.

## Output schema

```
output/hospitality_group_incubation/hospitality_group_incubation_<YYYYMMDD>.csv
source = "hospitality_group_incubation"
tier = <1|2|3>
business_type = <butcher | wine | cheese | bakery | specialty_grocer | restaurant>
distinction = "<human-readable trigger, e.g. 'Butcher counter launched Feb 2026 by <group> (3-location steakhouse group)'>"
year = <YYYY of launch/announcement>
+ evidence cols:
    parent_group              # the hospitality group / flagship restaurant
    parent_locations          # count of parent concepts (group sophistication proxy)
    parent_press_url          # cite-the-trigger link (launch coverage)
    parent_awards             # inherited award/press equity, if any
    parent_follower_count     # inherited audience size
    arm_name                  # the retail arm itself
    arm_type                  # butcher | wine | bakery | cheese | market_provisions | prepared_foods
    relationship              # owned-arm | collab/popup | franchise
    public_retail_counter     # bool — load-bearing for butcher rows
    counter_evidence          # the sentence/URL proving a walk-in counter exists
    launch_status             # announced | pre_open | live
    has_ecommerce, has_email_signup   # from enrich.py step 1 (commerce-layer read)
    has_club, club_url        # from detect_clubs.py (transition vs build)
    arm_followers, arm_reviews        # arm's own (thin) metrics
    icp_inferred              # true when arm too new to score on own data
    icp_score                 # /100 from score.py (live, enrichable arms only)
    trigger_score, parent_equity, recency
    is_net_new                # vs current scored universe (phone-first)
    scan_date
```

Preserve `parent_press_url` and `counter_evidence` on every row — the outbound
line writes itself ("saw you opened the butcher counter at <arm> from the
<group> team — want the club live before the holidays?").

## Volume & cost

Bounded by press/launch discovery, not a full Maps crawl.

- Serper Web launch-intent search across the seed groups + media domains:
  assume ~40 query templates × a few media-domain passes ≈ a few hundred Serper
  Web calls/run at ~$0.003 each ≈ **$1–2**.
- Maps resolution on candidate arms (~150–300 after filtering) ≈ **$0.50–1**.
- Claude relationship extraction over discovered snippets/pages (~300 rows,
  Haiku) ≈ **$3–5**.
- `enrich.py` step 1 website crawl + `detect_clubs.py` on the live-arm subset:
  negligible API $, mostly compute.
- IG/FB enrichment only on arms that resolve to live ICP businesses (batched
  Apify, ≤ a few dozen profiles): **$2–4**.
- **Per-run total: ~$7–12.**

Expected yield: of a few hundred discovered group/arm candidates, perhaps
**40–80 carry a verifiable retail-arm launch**, of which **~15–30 reach
Tier 1** (live or recent arm, verified public counter where butcher, strong
parent equity). A meaningful share are net-new — group arms often haven't
accreted enough standalone reviews/social to surface in the generic Serper
discovery pass yet, so this engine front-runs the standard lane.

## Refresh cadence

**Bi-weekly.** Launches cluster around press cycles and seasonal openings
(holiday markets, spring provisions shops), and the 12-month recency decay
means a launch stays a live trigger for a while — but a just-announced arm is
worth catching inside its first weeks, when the group is actively standing up
the concept and hasn't picked a commerce platform. Re-resolve `announced` /
`pre_open` rows each run; an arm flips to `live` once Maps + a working site
appear, at which point it gets full enrichment + `score.py`.

## Risks

- **Back-of-house butcher leakage (primary trap).** Many group "butcher
  programs" are kitchen-only whole-animal operations with no walk-in counter —
  not ICP. The `public_retail_counter` gate is load-bearing and *drops*, not
  demotes, unverifiable butcher rows. Do not infer a counter from "house-made
  charcuterie" copy alone; require retail hours / shop page / Maps storefront.
- **Collab and popup false positives.** "From the team behind X" can be a
  one-off popup, a licensing deal, or a vendor stall, not an owned retail arm
  the group controls. The `relationship` field exists to demote
  collab/popup/franchise; only `owned-arm` should reach Tier 1.
- **Chain / franchise leakage.** Larger groups shade into franchise/chain
  territory. Run `config.CHAIN_KEYWORDS` after Maps resolution; a group with
  10+ identical locations is a chain disqualifier even if the food is good.
- **Liquor-store / commodity wine leakage.** A group's "wine shop" can be a
  full-liquor / commodity bottle shop, not curated wine. Apply the
  cheat-sheet commodity SKU and liquor-store-ESP exclusions (City Hive / Spot
  Hopper, Tito's/Veuve/Barefoot inventory); keep curated/owner-somm arms only.
  Wine-bar arms stay excluded except a clear geographic monopoly.
- **Thin-arm metrics + inherited-brand understatement.** A newborn arm scores
  low on its own social/reviews, and static social understates the brand it
  inherited from the parent. Do **not** down-rank for absence of arm-level
  signal — that's what `parent_equity` and `icp_inferred` are for. Lean on
  reservation-difficulty/press of the parent and relative local dominance,
  especially in small markets.
- **Sweets-only / single-product demotion.** A group bakery arm that's
  cupcakes-only / single-pastry caps at Tier 2 per the cheat-sheet even with a
  strong fresh launch; carry the single-product flag from Claude classification.
- **Banned states.** Enforce the butcher-lane
  `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` for butcher-typed arms before
  output.
- **Serper/Claude fragility.** Press discovery depends on media coverage
  existing and on Serper not rate-limiting; isolate per-group failures (one
  group's extraction failing ≠ run failing), mirroring `discover_awards.py`.

## Repo placement

```
hospitality_groups/
  __init__.py                 # registers fetchers + known-group seed loader
  _lib.py                     # raw SCHEMA, ARM_TYPE_WEIGHT, launch-intent query seeds
  discover_groups.py          # Serper Web launch-intent search vs food-media domains
  expand_arms.py              # Maps adjacency + parent→arm candidate expansion
  extract_relationship.py     # Claude (llm_extract-style): parent/arm/counter/relationship
  resolve_and_enrich.py       # Serper Maps + enrich.py step 1 + detect_clubs.py on live arms
  finalize.py                 # ARM_TYPE_WEIGHT + parent_equity scoring, counter gate, tiering, CSV
discover_hospitality_groups.py  # orchestrator (mirrors discover_awards.py shape):
                              #   --group <slug>  --seeds-only  --no-search
                              #   --all  --since 90d  --master-only  --resume
research/hospitality_groups_seed.csv   # hand-seeded multi-concept groups
output/hospitality_group_incubation/raw/   # per-run raw archive for the newly-launched diff
```

Shared-code refactors this engine wants:
- Expose the `enrich.py` step-1 website crawl (ecommerce / email-signup /
  social-link detection) as an importable function so `resolve_and_enrich.py`
  can run the commerce-layer read on a single arm without invoking the full
  sequential `main.py` enrichment chain.
- Reuse the `discover.py` Serper Maps lookup as an importable resolver (the
  same lift several trigger engines want) rather than re-implementing Maps auth.
- Add `ARM_TYPE_WEIGHT`, the launch-intent query templates, and the
  retail-counter keyword list to `config.py` alongside the existing
  keyword/chain blocks so non-engineers can extend coverage.
- `detect_clubs.py` and `dedupe_existing.py` are reused as-is.

## Open questions

1. Where's the cleanest line between an **owned retail arm** and a
   **collab/licensing/popup**? Do we require shared ownership evidence (same
   LLC/principal) for Tier 1, or is shared brand + a permanent storefront
   enough?
2. For the **butcher public-counter** test, what's the minimum verifiable
   evidence we'll accept — retail hours on the site, a Maps storefront, an
   order page — and how do we avoid false negatives when a real counter just
   has a thin web presence?
3. How do we weight **parent equity vs. arm metrics** without touching the
   SHAP-aligned `SCORING_WEIGHTS`? Is `parent_equity` a qualification overlay
   only, or should it feed a documented, separate group-arm scoring path?
4. Is the **known-group seed list** worth maintaining by hand, or can press
   launch-intent discovery alone surface enough groups that the seed CSV is
   just a warm-start convenience?
