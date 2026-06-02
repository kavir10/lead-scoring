# Lead Engine 01 — Existing Club Transition List

**Motion:** Curation
**Vertical fit:** Wine, butcher, cheese, bakery (specialty grocer as overflow)
**Suggested list name(s):** `wine_existing_club_transition`, `butcher_meat_share_transition`, `cheese_club_transition`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run

## Premise

An operator who already runs a wine club, meat share, CSA, bread club, or
"box of the month" has done the only thing Table22 cannot do for them: they
have **proven recurring demand exists in their book of business**. They
believe in the model, they have a list of paying members, and they are
fighting their fulfillment/billing tooling every month to keep it running.
That makes this a **platform-switch sale, not a concept sale** — the cheapest,
fastest-closing motion in the whole repo. We are not pitching subscriptions;
we are pitching a better operating system for the subscription they already
have.

This is a near-pure **Trigger** engine bolted onto strong **ICP Fit**
verticals. In the two-score model, an existing club is the loudest public
buying signal we can observe short of a checkout flow — it directly evidences
the demand-over-capacity thesis (they are converting loyal regulars into
prepaid recurring revenue). It also maps cleanly onto the highest-AGMV
partner types: butcher ($75.9k), wine ($68.2k), cheese ($63.8k), with bakery
($34.7k) as the cap-Tier-2 tail. The wine vertical's "transition path"
(existing club → move to Table22) is exactly this engine; the "new club"
path is everything this engine deliberately leaves out.

## Recipe

This engine is a **curation overlay**, not a fresh discovery crawl. It runs
`detect_clubs.py` (the existing primitive) over already-discovered, already-
qualified leads and keeps only the club-positive rows, then re-scores them
for the transition motion.

1. **Assemble the input universe.** Concatenate the freshest qualified rows
   for the four target verticals from existing outputs — `output/butcher/
   1_discovered_butchers.csv`, the latest `best_wine_shops/` master, any
   `directories_all_*` cheese/bakery rows, and the latest generic-pipeline
   `2_enriched_*` rows filtered to `business_type in {wine_store, butcher,
   cheese, bakery, specialty}`. Dedupe with `dedupe_existing.py` (phone-first,
   then name+address) into one stamped input CSV.

2. **Run club detection.** `python detect_clubs.py <input>.csv --threads 50`.
   This adds `has_club`, `club_type`, `club_url`, `club_signals`. The
   `CLUB_KEYWORDS` / `CLUB_URL_PATHS` / `CLUB_TYPE_PATTERNS` lists in
   `detect_clubs.py` already cover the source idea's vocabulary — wine club,
   meat/fish share, CSA, monthly box, bread/sourdough club, cheese club,
   allocation, recurring delivery, supper club, autoship. No new keyword work
   is required for v1; if recall is weak on `--resume`, extend `CLUB_KEYWORDS`
   in place (it is shared with `detect_clubs_v2.py`).

3. **Filter to club-positive, target-vertical rows.** Keep
   `has_club == True` AND `club_type` in the vertical-relevant set:

   ```
   wine_existing_club_transition  → club_type in {wine_club}
   butcher_meat_share_transition  → club_type in {meat_club, csa}        # CSA only if business_type==butcher/farm
   cheese_club_transition         → club_type in {cheese_club}
   bakery (folded into above run) → club_type in {bread_club}
   # generic transition-positive but unclassified:
   #   club_type in {subscription_box, of_the_month, subscription, membership}
   #   → keep ONLY if business_type is target vertical (drops loyalty-points retail noise)
   ```

4. **Grade the trigger strength** (transition-readiness, not ICP — ICP comes
   from scoring). A specific perishable club on a target vertical is a hot
   trigger; a generic "rewards program" is a cold one:

   ```
   trigger_strength:
     hot   = club_type in {wine_club, meat_club, cheese_club, bread_club, seafood_club, csa}
     warm  = club_type in {subscription_box, of_the_month, supper_club}
     cold  = club_type in {membership, subscription}        # loyalty/points, weak transition signal
   drop if trigger_strength == cold AND price/ICP signals also weak
   ```

5. **Enrich the survivors for ICP fit + outbound proof.** Run only the cheap,
   high-SHAP `enrich.py` steps on the filtered set — `websites` (step 1:
   confirms ecommerce + email-signup, the platform they'd be migrating off),
   `instagram` (step 2) and `facebook` (step 3) for `follower_count`, and
   `reviews` (step 5) for `reservation_difficulty` text mining on wine bars/
   destinations. Skip the expensive reels/posts/availability steps unless a
   row scores A on the cheap features — this engine's edge is the trigger, not
   exhaustive social.

6. **Detect the incumbent platform** during the website crawl (small add to
   step 1, or a post-pass over `club_url`). Note the ESP/commerce stack on the
   club page (Shopify subscriptions, Squarespace, WooCommerce, City Hive, Spot
   Hopper, Cellar/Commerce7, custom). This is gold for outbound — sales can
   open with "saw you run your wine club on Commerce7." Flag `City Hive` /
   `Spot Hopper` as **liquor-store-ESP red flags** for downstream QA, not auto-
   drop.

7. **Score & tier.** Run `score.py` with `config.SCORING_WEIGHTS` unchanged
   (SHAP-aligned — Partner Type dominant), then emit `_all` and A+B `_top`.
   Because every row here carries a live trigger, expect the tier distribution
   to skew higher than cold discovery; the club signal itself is not a
   scoring weight, so carry it as an evidence column, not a score bump.

## Output schema

```
output/clubs/<slug>_<YYYYMMDD>.csv          # e.g. wine_existing_club_transition_20260601.csv
source = "<slug>"                            # wine_existing_club_transition | butcher_meat_share_transition | cheese_club_transition
tier = 1                                     # trigger-engine rows; final A/B/C/D set by score.py
business_type = wine_store | butcher | cheese | bakery | specialty
distinction = "Runs an existing {club_type} ({incumbent_platform})"   # human-readable trigger summary
year = <discovery_year>
+ evidence cols:
    has_club            = True
    club_type           = wine_club | meat_club | cheese_club | bread_club | csa | subscription_box | ...
    club_url            = <the live club/subscription page — sales clicks this>
    club_signals        = "<top matched phrases, verbatim, so sales can cite the trigger>"
    incumbent_platform  = shopify_subs | commerce7 | squarespace | woocommerce | city_hive | spot_hopper | custom | unknown
    trigger_strength    = hot | warm | cold
    esp_red_flag        = True|False         # City Hive / Spot Hopper → liquor-store leakage QA flag
```

Preserve `club_url` and `club_signals` verbatim — these are the outbound
proof points; never normalize them away in cleanup. Master union:
`output/clubs/clubs_transition_all_<YYYYMMDD>.csv`.

## Volume & cost

- Input universe (deduped, four verticals from existing outputs): **~5-8K rows**.
- Empirically (`detect_clubs.py` runs to date) roughly **15-25% of qualified
  niche-retail rows trip `has_club`**; after filtering to target verticals +
  dropping cold loyalty-only hits: **~700-1,400 club-positive leads**, of which
  hot-trigger ≈ 400-700.
- `detect_clubs.py`: pure requests + BeautifulSoup, **free**.
- `dedupe_existing.py`: free.
- Enrichment on survivors only — websites (free), IG+FB Apify on ~1,000 rows
  (profiles batched 30s) ≈ **$8-12**, reviews on the ~400 A-candidates ≈ **$3-5**.
- **Per-run total: ~$12-18.**
- **Net-new leads per run:** mostly a *re-tier*, not net-new venues — these
  rows already exist in our universe. The value is converting C/D cold rows
  into A/B trigger-flagged rows. First run promotes ~400-700 hot-trigger leads;
  subsequent runs surface ~5-10% new clubs as operators launch them.

## Refresh cadence

**Quarterly**, or on-demand right after any large discovery run (butcher/wine/
cheese) lands new rows. Clubs are launched and quietly killed on a seasonal
cadence (holiday gift boxes, summer CSAs), so a quarterly re-crawl catches
both new launches and dead pages. `--resume` makes incremental re-runs cheap.

## Risks

- **Loyalty-points leakage.** `club_type in {membership, subscription}` catches
  generic "rewards"/"VIP points" programs that are *not* recurring-product
  clubs. These dilute the list and waste BDR time — gate them behind
  `trigger_strength != cold` unless ICP is otherwise strong.
- **Liquor-store / chain leakage.** A "wine club" on a Tito's/Josh/Barefoot-
  heavy liquor store is anti-ICP. `esp_red_flag` (City Hive, Spot Hopper) plus
  the existing `CHAIN_KEYWORDS` filter and commodity-SKU exclusion list
  (Tito's, Smirnoff, Veuve, Yellowtail, etc.) must run before sales handoff.
  Pipe survivors through `reclassify.py` for the wine-bar claw-back and
  liquor-vs-curated split.
- **Sweets-only demotion.** A pure cookie/cake "club" is single-product → caps
  at Tier 2 by ICP rules. Keep but demote; don't let bread/pastry clubs inflate
  the bakery count.
- **Dead/stale club pages.** A `club_url` that 404s or shows "coming soon" is a
  false trigger. The crawl confirms the page resolves; QA-sample with
  `sample_clubs_for_qa.py` to catch zombie pages before outbound.
- **Static-social understatement.** Butcher/deli/specialty-grocer clubs often
  live on Facebook, not IG, and present thin static social — do **not** DQ on
  follower count; `follower_count` = IG + FB already, and trigger strength
  carries these rows.
- **Small-market metrics run low.** A dominant rural butcher with a meat share
  will under-index on raw reviews/followers. Lean on `reservation_difficulty`
  and relative local dominance, not absolute volume.
- **Existing club is a POSITIVE signal** — never filter these out as
  "already solved." The whole engine inverts that instinct.

## Repo placement

This is a **postprocessing overlay** over `detect_clubs.py`, not a new scraper
package — it reuses the existing primitive and adds a thin orchestrator +
filter/grade module.

```
clubs_transition/
  __init__.py              # registers the three slugs + vertical→club_type maps
  assemble.py              # build deduped input universe from existing outputs
  grade.py                 # filter to target verticals, classify trigger_strength,
                           #   detect incumbent_platform + esp_red_flag from club_url
  finalize.py              # write per-slug + master CSV in canonical schema
discover_clubs_transition.py   # orchestrator: assemble → detect_clubs → grade → enrich → finalize
                               #   mirrors discover_directories.py shape
```

Refactors to share:
- Expose `_fetch_page` and `CLUB_TYPE_PATTERNS` from `detect_clubs.py` as
  importable helpers (already module-level) so `grade.py` can detect
  `incumbent_platform` without re-fetching — pass through the soup/HTML the
  detector already pulled, or add an `--emit-platform` flag to `detect_clubs.py`
  that records the commerce/ESP fingerprint alongside `club_signals`.
- Reuse `enrich.py` steps 1/2/3/5 by importing the step functions; do **not**
  fork the enrichment logic. If those funcs aren't currently importable
  standalone, expose them as a thin lib (the same refactor flagged for the
  reservation engine).

## Open questions

1. Is `incumbent_platform` reliably fingerprintable from the public club page
   (Commerce7/Cellar/City Hive leave JS/CSS tells), or does it need a
   Wappalyzer-style pass? If the latter, is it worth the added crawl cost vs.
   leaving it `unknown` and letting BDRs find it manually?
2. Should CSA-only farms (no retail storefront, `business_type == farm`) flow
   into `butcher_meat_share_transition` or get their own slug? They're proven
   recurring operators but sit at the edge of ICP and may trip BANNED_STATES.
3. What's the right handling of the wine "transition vs new" split here — do we
   want a sibling `wine_new_club` engine that takes the *club-negative* wine
   rows with strong owner-somm/importer street-cred, or keep that out of scope?
4. Do we trust `detect_clubs.py`'s ~15-25% hit rate as the volume basis, or run
   a 500-row calibration pass per vertical first to size the list before
   committing the full enrichment spend?
