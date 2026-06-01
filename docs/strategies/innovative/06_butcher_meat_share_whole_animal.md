# Lead Engine 06 — Premium Butcher Universe

**Motion:** Curation
**Vertical fit:** Butchers (whole-animal / nose-to-tail / dry-aging / charcuterie)
**Suggested list name(s):** `butcher_meat_share_whole_animal`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $15/run

## Premise

Butchers have the highest average Peak AGMV of any partner type ($75.9k) and
Partner Type is the single most predictive SHAP feature we have. The catch is
universe size: the *premium* butcher universe — chef/master-butcher-led shops
doing whole-animal sourcing — is tiny, roughly 1,000–1,200 US shops. A broad
"butcher shop" Serper sweep buries those 1,000 under supermarket counters,
generic meat markets, halal/carniceria volume shops, and BBQ joints. The ICP
signal we want is not the word "butcher"; it's the *language of the craft*.

This engine is a **pure ICP-Fit harvester** built around that language:
`whole animal`, `nose to tail`, `pasture raised`, `heritage breed`, `dry aged`,
`in-house charcuterie`, `butchery class`, `meat share`, `ranch to butcher`. A
shop that runs a monthly meat share or sells out a whole-pig charcuterie batch
is already operating a proto-subscription with a captive base — the closest
behavioral analog to a Table22 program in any vertical. That makes the meat-
share / whole-animal signal not just ICP fit but a soft trigger: demand-over-
capacity productized by the operator themselves.

It pairs with Engine 03 (sold-out demand) and existing-club detection: a high-
ICP butcher already running a share that periodically closes is the highest-
conviction butcher target we can surface.

## Recipe

This is a **curation overlay** on the existing butcher lane. It reuses
`butcher.py` / `butcher_sources.py` alt-source lanes (Good Meat Finder,
EatWild, AGA, Good Food Awards charcuterie, stockist pages) which already skip
Serper/Google and carry the premium-signal vocabulary — then layers an ICP
language filter, a tight Serper Maps pass keyed on craft terms, and a
classification gate. `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` is enforced
throughout this lane (already wired in both modules).

1. **Pull the alt-source universe.** Run `run_butcher_source_scrape()` (via
   `discover_butchers.py`) to harvest Good Meat Finder, EatWild, AGA producer
   members, Good Food Awards charcuterie winners, and curated stockist pages.
   These sources are *already* skewed toward pasture-raised / grass-fed /
   whole-animal vendors, so they form the high-precision core. Dedupe with the
   existing `dedupe_source_rows()` (phone-first, then name+address).

2. **Add a craft-keyword Serper Maps pass for net-new shops.** The alt sources
   miss urban chef-butcher shops that aren't farm-affiliated. Run a *narrow*
   `discover.py` / `scripts/fresh_icp_search.py` Serper Maps sweep across
   `config.CITIES` (bias to `research/trendy_neighborhoods/` seeds), but replace
   the generic butcher query with ICP-language queries:

   ```
   BUTCHER_CRAFT_QUERIES = [
     "whole animal butcher", "nose to tail butcher shop",
     "dry aged butcher", "in-house charcuterie butcher",
     "heritage breed butcher", "pasture raised butcher shop",
     "meat share butcher", "ranch to butcher", "butchery class",
     "house-made sausage charcuterie shop",
   ]
   ```

   Apply niche quality floors (≥20 reviews / ≥4.0 rating), require a website,
   and run `config.CHAIN_KEYWORDS` to strip Whole Foods / Costco / chain
   counters. Drop `BANNED_STATES`.

3. **Score the premium-signal vocabulary over each shop's website text.** Reuse
   `butcher_sources.PREMIUM_SIGNAL_PATTERNS` (it already encodes
   `pasture_raised`, `heritage_breed`, `dry_aged`, `whole_animal`, `grass_fed`,
   `csa_meat_share`, `charcuterie`, `holiday_preorder`, `email_capture`) and
   `verify_vendor_websites()` / `_extract_vendor_signals()` to crawl homepages
   and emit `subscription_signals`. Compute an ICP-craft score:

   ```
   POSITIVE = {whole_animal:30, dry_aged:20, charcuterie:20, heritage_breed:15,
               csa_meat_share:25, pasture_raised:10, grass_fed:10,
               butchery_class:15, named_local_farm:15}   # new regex families
   NEGATIVE = {supermarket/grocery counter, "carniceria", BBQ-first menu,
               "we ship nationwide"-only/no storefront, chain match} -> hard drop

   craft_score   = min(100, sum(POSITIVE[f] for f in matched_families))
   icp_tier      = 1 if craft_score>=55 else 2 if craft_score>=35 else 3
   meat_share    = 1 if csa_meat_share OR butchery_class matched
   ```

   Add two regex families not yet in the module: `butchery_class`
   (`butchery class|knife skills|whole[- ]hog (?:class|demo)|supper club`) and
   `named_local_farm` (proper-noun "… Farm/Ranch/Farms" adjacency to
   sourcing language) — `named_local_farm` is best confirmed by the Haiku pass.

4. **Exclusion gate (anti-ICP leakage).** Hard-drop before scoring:
   supermarket/grocery counters, generic/ethnic-volume meat markets, **BBQ-
   first** (smoked-meat restaurant, not a butcher), **online-only meat brands**
   (DTC ship-only with no local storefront — fails the brick-and-mortar ICP),
   and chains (10+ locations). The "ship nationwide with no storefront" trap is
   the biggest false positive in this vertical — require a physical retail
   address from Maps or the alt-source row.

5. **LLM confirmation on borderline rows.** For rows in `icp_tier` 2–3 or where
   storefront/BBQ status is ambiguous, run an `awards/llm_extract.py`-style
   `claude-haiku-4-5-20251001` pass over the homepage/about-page text to confirm
   (a) chef/master-butcher-led, (b) whole-animal sourcing, (c) physical
   storefront, (d) not BBQ-first / not ship-only. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

6. **Enrich engagement — Facebook-weighted.** Butcher/deli/specialty-grocer
   engagement skews to Facebook, so run `enrich.py` step 3 (`facebook`) before
   IG. Run step 2 (`instagram` profile scraper, batches of 30) for handle +
   follower_count, and step 1 (`websites`) for ecommerce / email-signup flags.
   Skip the expensive reservation lanes (steps 5/8) — butchers have no
   reservation grid.

7. **Classify, dedupe against existing club detection, score.** Run
   `reclassify.py` to set `partner_type = butcher` / `business_type_v2 = retail`
   and `detect_clubs.py` to flag `has_club` (existing meat-share / club =
   positive platform-switch signal, **not** a DQ). Feed survivors to `score.py`.
   Final list = `craft_score` ≥ 35 **AND** ICP A/B tier, with `meat_share=1`
   rows promoted to the top of the sales queue.

Premium-signal hits and the matched homepage snippet are preserved verbatim so
sales can cite the exact "whole-animal share" / "dry-aging program" line in
outbound.

## Output schema

```
output/butcher/butcher_meat_share_whole_animal_<YYYYMMDD>.csv
source = "butcher_meat_share_whole_animal"
tier = <1|2|3>                       # = icp_tier from craft_score
business_type = butcher
distinction = "Premium butcher — {top craft signals} ({craft_score}/100, meat-share={Y/N})"
year = <YYYY>
+ evidence cols:
    craft_score, icp_tier, meat_share_bool, matched_signals (pipe-delim),
    subscription_signals, has_subscription_offering,    # from _extract_vendor_signals
    named_local_farms (pipe-delim), chef_butcher_led_bool,
    storefront_confirmed_bool, bbq_first_bool, ship_only_bool,   # exclusion audit
    web_snippet,                         # verbatim quote for outbound
    source_lane (good_meat_finder|eatwild|aga|good_food_awards|stockist|serper_craft),
    fb_likes, ig_handle, follower_count, has_ecommerce, has_email_signup,
    partner_type, business_type_v2, has_club, icp_fit_score, scan_date
```

## Volume & cost

Universe is intentionally small — this is precision, not volume.

- Alt-source scrape (`butcher_sources`): free (httpx + selectolax), ~600–900
  raw rows pre-dedupe, ~400–600 after dedupe.
- Serper Maps craft pass: ~10 queries × ~130 cities, but craft terms return
  thin result sets → ~3–5K Maps calls ≈ **$3–5**. Nets ~150–300 net-new urban
  chef-butcher shops not in the alt sources.
- Website crawl + premium-signal scoring: free (reuses `verify_vendor_websites`,
  12 threads).
- Haiku confirmation on ~250 borderline rows at a few hundred tokens each:
  ≈ **$2–3**.
- Facebook + IG enrichment via Apify on the survivor set: scope to ICP A/B
  survivors (~300 handles) × ~$0.015 ≈ **$5**.
- **Per-run: ~$12–15.**
- **Net-new qualified leads per run:** ~**150–300** premium butchers clearing
  `craft_score` ≥ 35 AND ICP A/B; of those ~**60–120** with `meat_share=1` are
  the priority cohort. Because the true universe is ~1,000–1,200, the engine
  saturates fast — expect the first run to capture the bulk and later runs to
  trickle.

## Refresh cadence

**Quarterly.** The premium butcher universe is small and slow-moving — new
whole-animal shops open at a trickle, not a flood. A quarterly re-run catches
new openings and shops that *add* a meat-share / dry-aging program (an ICP-
strengthening event worth re-scoring). Run an extra pass in **September–
October** to catch Thanksgiving/holiday whole-bird and whole-animal preorder
language (the `holiday_preorder` signal spikes seasonally).

## Risks

- **Online-only meat brands (biggest trap).** Crowd Cow / Porter Road–style DTC
  brands hit every craft keyword but have no storefront and fail the brick-and-
  mortar ICP. The `storefront_confirmed_bool` gate (Maps address or alt-source
  physical address) is load-bearing — `ship_only_bool` must hard-drop.
- **BBQ-first leakage.** Smoked-meat restaurants match `charcuterie`/`smoked`
  and "whole hog" but are restaurants, not butchers. The Haiku pass classifies
  BBQ-first; don't rely on regex alone.
- **Supermarket / volume-counter leakage.** Whole Foods butcher counters and
  high-volume carnicerias surface in Maps; enforce `config.CHAIN_KEYWORDS` and
  the supermarket/generic-market negative families before scoring.
- **Small-market metrics run low.** A genuine whole-animal butcher in a small
  town will have low review counts and a thin social presence. Weight relative
  local dominance and the craft-language signal over raw review/follower volume;
  do not let the niche quality floor (≥20 reviews) silently drop them — flag
  sub-floor rows for manual review rather than discarding.
- **Static-social understates brand.** Butcher Facebook/IG is often sparse even
  for respected shops. Static social must never subtract ICP fit — this engine
  scores on craft language and source provenance first, engagement second.
- **Named-farm false positives.** `named_local_farm` regex can match farm-to-
  table *restaurant* copy or supplier logos that aren't the shop's own
  sourcing. Confirm via Haiku before treating it as a positive signal.
- **Alt-source fragility.** Good Meat Finder / EatWild / AGA pages change markup
  and rate-limit; checkpoint per source (the lane already emits a per-source
  status CSV) and degrade gracefully when one lane returns zero rows.
- **Single-product demotion.** The sweets-only rule doesn't apply, but a
  jerky-only or single-SKU shop should cap at tier 2 by analogy — single-product
  narrows the subscription thesis.

## Repo placement

Extend the existing butcher lane rather than spawning a new package — the
alt-source scraping and `BANNED_STATES` logic already live there.

```
butcher_sources.py                 # extend: add butchery_class + named_local_farm
                                   #   regex to PREMIUM_SIGNAL_PATTERNS; expose
                                   #   craft_score() helper
butcher_craft.py                   # new: ICP-language overlay
                                   #   - serper craft-query Maps pass
                                   #   - craft scoring + exclusion gate
                                   #   - haiku confirmation pass
discover_butchers.py               # extend: add --premium / --craft flag that
                                   #   runs alt-sources -> butcher_craft overlay
                                   #   -> reclassify -> detect_clubs -> score
```

Refactor targets to avoid duplication:

- Expose `enrich.py` step-1 website crawl as an importable
  `crawl_site_text(url) -> dict[path -> text]` (shared with Engine 03) so the
  craft scorer reads richer text than `verify_vendor_websites` currently
  captures.
- Reuse the Apify Facebook/IG actor wrappers from `enrich.py` steps 2–3 instead
  of re-implementing actor calls in the butcher lane.

`config.py` knobs to add: `BUTCHER_CRAFT_QUERIES`, `BUTCHER_CRAFT_WEIGHTS`
(the POSITIVE/NEGATIVE map), and `BUTCHER_CRAFT_TIER_THRESHOLDS`.

## Open questions

1. Is the ~1,000–1,200 premium-universe estimate right, and how much of it do
   the alt sources already cover? Worth a one-time reconciliation run to measure
   alt-source vs. Serper-craft net-new overlap before committing to quarterly.
2. Should `meat_share=1` (operator already runs a share/club) split into its own
   higher-priority list, mirroring Engine 01's existing-club-transition motion —
   since it's both ICP fit *and* a platform-switch trigger?
3. How aggressively do we treat `ship_only_bool`? Some otherwise-ICP shops have a
   storefront *and* a national ship business — keep them (storefront wins) or
   demote them (ship revenue dilutes the local-superfan thesis)?
4. Do we trust regex `named_local_farm` enough to score on it, or always gate it
   behind the Haiku confirmation pass given the restaurant/supplier-logo
   false-positive rate?
