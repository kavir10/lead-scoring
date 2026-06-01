# Lead Engine 36 — Founder Story Density Score

**Motion:** Curation (a pure ICP-Fit overlay that re-reads already-crawled About/Story pages for founder-led, craft-heavy narrative density)
**Vertical fit:** All high-fit verticals — butcher, wine, cheese, bakery, specialty grocer, destination/neighborhood restaurant
**Suggested list name(s):** `founder_story_density`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$5–10 per run (folds into the existing `websites` crawl + a single Claude Haiku pass; no Apify, no Serper Maps, no Resy)

## Premise

The most predictive feature we have is **Partner Type** (SHAP-dominant), and the partner types that print the highest Peak AGMV — butcher ($75.9k), wine ($68.2k), cheese ($63.8k), destination restaurant ($60.5k) — share a quality that volume metrics chronically under-measure: they are **founder-led, craft-obsessed operators** whose whole brand is a person and a point of view. A shop that writes "we work with three family farms within 40 miles, butcher whole animals nose-to-tail, and cure everything in-house" is telling you it has a captive superfan base and a story worth subscribing to — the demand-over-capacity thesis in narrative form. Those same shops frequently run thin on the numeric signals our pipeline leans on: low review counts in small markets, sparse static social, modest follower counts. They get buried.

This engine captures the **language of craft and founder identity** directly off the About / Story / Our Farmers / Philosophy pages we already crawl in `enrich.py` step 1, and turns it into a single **founder-story density score**. It is a pure **ICP-Fit harvester** — it does not assert a time-bound trigger, so on the two-score model it produces high-ICP / no-trigger rows that route to nurture or, better, *boost* the ICP side of leads that another engine has already flagged with a trigger. Its highest value is as a corrective: a low-review, low-follower butcher in a small market that scores 85/100 on founder-story density is exactly the kind of high-AGMV operator the numeric floors would otherwise demote.

It pairs naturally with Engine 06 (premium butcher craft language), Engine 07 (wine street-cred), and Engine 10 (small-market local dominance) — where those engines key on a vertical-specific signal, this one is the cross-vertical narrative spine, scored uniformly so a bakery and a wine shop can be compared on "how founder-led and craft-heavy is the story they tell."

## Recipe

A **postprocessing overlay**. It consumes an already-discovered, `websites`-enriched CSV, fetches the About/Story page text (which the step-1 crawl already reaches for), runs a lexical pre-score and then a Claude adjudication, and emits a small evidence-tagged CSV. It does **not** run Serper discovery.

1. **Input.** Take a `websites`-enriched or scored CSV (`output/2_enriched_websites.csv` or a `custom-serper-scoring_*_all.csv`). Every row already has a `website`, cleared `config.CHAIN_KEYWORDS`, and passed quality floors. This engine runs across all high-fit verticals — do not restrict by `business_type` (the score is cross-vertical by design), but carry `business_type` through for the vertical-weighting in step 4.

2. **Reach the founder/story page text.** Reuse the step-1 website crawler (`enrich.py`, 10-thread concurrent crawl). Today it captures homepage + social/reservation/ecommerce signals; extend it to also fetch and retain text from the narrative pages via a link probe over: `/about`, `/about-us`, `/our-story`, `/story`, `/philosophy`, `/our-farmers`, `/sourcing`, `/team`, `/who-we-are`, `/mission`, `/the-shop`. Concatenate the matched pages' visible text (selectolax) into a `story_text` blob per row. If no narrative page resolves, fall back to homepage body text and set `story_page_found=False`.

3. **Lexical density pre-score (cheap gate before the LLM).** Count weighted matches of craft/founder-narrative families over `story_text`. This is a pre-filter and an evidence trail, not the final score — the LLM (step 5) adjudicates. Grouped so the matched family becomes citable evidence:

   ```
   SOURCING      = family farm, small grower(s), single-origin, named farm/ranch,
                   pasture[- ]raised, grass[- ]fed, regenerative, biodynamic,
                   day-boat, line-caught, foraged, "within \d+ miles", local farmers
   CRAFT         = whole animal, nose to tail, naturally leavened, long fermentation,
                   hand[- ]selected, hand[- ]made, small[- ]batch, in-house (cure|smoke|age|mill),
                   dry[- ]aged, house[- ]made, stone[- ]ground, slow proof, artisan(al)
   FOUNDER       = "I/we started", "our family", founder, "my grandmother",
                   "third[- ]generation", owner[- ]operated, "left my job",
                   chef[- ]owner, "learned to (bake|butcher|...)", first[- ]person voice
   RELATIONSHIP  = producer relationship(s), "we know our (farmers|growers|fishermen)",
                   "direct from", "by hand from", partner(ship) with (farm|grower|vineyard)
   VALUES        = seasonal, community, heritage (breed|variety|grain), traditional method,
                   terroir, provenance, "the right way", stewardship
   ```

   Compute a raw lexical density and family coverage:

   ```
   matches        = weighted count of family hits in story_text
   density_raw    = 100 * matches / max(words_in_story_text, 1) * SCALE      # normalize for page length
   families_hit   = number of the 5 families with >=1 match
   lexical_score  = min(100, round(density_raw))                            # length-normalized so a long boilerplate
                                                                            #   "About" doesn't beat a tight craft story
   ```

   Length-normalization is load-bearing: density (signal per word), not raw hit count, so a verbose corporate "about" page does not outrank a dense two-paragraph founder story.

4. **Vertical weighting (optional, applied to the final score, never to `SCORING_WEIGHTS`).** Founder-story language matters in every vertical, but it is most diagnostic where AGMV headroom is highest. Apply a light multiplier so a dense narrative in a top-AGMV vertical ranks above an equally dense one in a low-AGMV vertical:

   ```
   vertical_boost = 1.15 if business_type in {butcher, wine, cheese}
                    1.05 if business_type in {destination_restaurant, market_deli}
                    1.00 otherwise (bakery, neighborhood_restaurant, specialty_grocer)
   ```

5. **Claude adjudication (`awards/llm_extract.py` pattern, Haiku).** Regex over "family," "community," "seasonal" is noisy — every marketing page uses those words. For any row with `lexical_score >= a low floor` OR `families_hit >= 2`, pass `story_text` (truncated to a few KB) to a `claude-haiku-4-5-20251001` classifier reusing the `awards/llm_extract.py` plumbing. Tight schema:

   ```
   is_founder_led: bool              # a real person/family operating the business, not faceless brand copy
   craft_depth: 0-3                  # 0 none, 1 buzzwords only, 2 specific practices, 3 deep + sourcing named
   sourcing_specificity: 0-3         # 0 vague, 3 names farms/growers/breeds/regions
   first_person_voice: bool          # written in the operator's own voice
   story_summary: str                # 1-2 sentence human-readable narrative summary
   pull_quote: str                   # the single most compelling verbatim line for outbound
   confidence: 0.0-1.0
   ```

   Prefix the run with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

6. **Combine into the founder-story density score + tier.** Blend the length-normalized lexical signal with the LLM's depth judgments; the LLM dominates because it disambiguates buzzwords from genuine craft.

   ```
   story_density = round( vertical_boost * (
                     0.35 * lexical_score
                   + 0.25 * (craft_depth/3 * 100)
                   + 0.20 * (sourcing_specificity/3 * 100)
                   + 0.10 * (100 if is_founder_led else 0)
                   + 0.10 * (100 if first_person_voice else 0)
                 ) )
   tier 1  if story_density >= 70 and is_founder_led and craft_depth >= 2
   tier 2  if story_density >= 45 and (is_founder_led or craft_depth >= 2)
   tier 3  if story_density >= 25
   drop    otherwise (faceless brand copy, no craft narrative)
   ```

7. **Reclassify, dedupe, state filter before handoff.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, wine-bar claw-back), then `dedupe_existing.py` (phone-first, then name+address). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter to `partner_type == butcher` rows only.

8. **(Optional) Feed the ICP boost into scoring/ranking.** The founder-story fields are **overlay evidence** — do not touch `config.SCORING_WEIGHTS`. The intended use is to *rescue* high-density rows that the numeric floors demoted: surface any row with `tier <= 2` here whose pipeline ICP score sat in C/D tier as a manual-review "under-measured founder operator" queue. Preserve `pull_quote` verbatim so sales can open outbound with the operator's own line.

## Output schema

```
output/founder_story/founder_story_density_<YYYYMMDD>.csv
source = "founder_story_density"
tier = <1|2|3>                       # story-density tier from recipe step 6
business_type = butcher | wine | cheese | bakery | specialty_grocer | restaurant | market_deli
distinction = "Founder-led craft story (density {story_density}/100): {story_summary}"
year = 2026
+ canonical: name, city, state, country, source_url (= about/story page or website), blurb
+ evidence cols (preserve so sales can quote the founder's own words in outbound):
    story_density            # final 0-100 score from step 6
    lexical_score            # length-normalized regex pre-score
    families_hit             # count of the 5 lexicon families that fired (0-5)
    matched_signals          # pipe-joined verbatim regex matches
    matched_families         # which lexicon buckets fired (sourcing|craft|founder|relationship|values)
    is_founder_led           # LLM bool
    craft_depth              # LLM 0-3
    sourcing_specificity     # LLM 0-3
    first_person_voice       # LLM bool
    story_summary            # LLM 1-2 sentence narrative summary
    pull_quote               # verbatim outbound-ready line
    confidence               # LLM 0.0-1.0
    story_page_found         # False => scored off homepage fallback (lower trust)
    story_page_url           # the /about|/our-story|... page if resolved
```

## Volume & cost

Bounded by input size, not fresh discovery. Over a ~2,500-row mixed-vertical batch:

- The narrative-page crawl folds into the existing step-1 `websites` crawl (10 threads) — near-free, bandwidth only; the marginal cost is the extra link probes per row.
- Lexical pre-score is pure-Python and free; it gates the LLM. Expect the regex/`families_hit>=2` gate to pass a wide ~55–70% of rows (craft language is common in our verticals) → ~1,400–1,750 rows to the LLM pass.
- LLM adjudication is ~1,400–1,750 Haiku calls of a few-KB `story_text` each ≈ **$5–10** (truncate aggressively; About pages are short).
- No Apify, no Serper, no Resy.
- **Per-run: ~$5–10.**
- **Net-new qualified leads per run:** of the adjudicated rows, roughly **15–25% clear tier 1+2** → **~250–400 high-density founder-story leads per 2,500-row batch**, skewed toward butcher/wine/cheese/bakery. The real payoff is narrower: the **~40–80 rows that scored C/D on numeric ICP but tier 1–2 here** — the under-measured founder operators this engine exists to rescue.

## Refresh cadence

**Run off the back of each large discovery batch, not on a fixed clock.** About/Story pages are among the most stable content a small business has — a founder narrative written in 2021 reads the same in 2026 — so re-scanning the same rows monthly mostly re-surfaces identical scores and re-burns LLM calls. The score is essentially a property of the row, computed once. The events worth a re-run are (a) a fresh discovery batch (new rows never scored) and (b) a website redesign that adds or removes a story page — caught opportunistically via a `story_page_found` / `story_text`-hash diff against the prior run rather than a blanket re-scan. Practically: invoke whenever a new `2_enriched_websites.csv` lands.

## Risks

- **Buzzword copy without substance (primary false-positive trap).** Marketing agencies salt "family," "community," "seasonal," "hand-crafted," "artisan" across faceless brand sites with zero founder behind them. The lexical score alone over-produces these; the Haiku `is_founder_led` + `craft_depth >= 2` gate is the load-bearing guard. Never tier-1 on lexical score alone.
- **Long-page dilution / verbose-about inflation.** A rambling corporate "About" can rack up raw hits. Length-normalization (density per word, step 3) is mandatory — without it, the longest page wins, not the most founder-led.
- **Chains and franchise copy.** Multi-location and franchise brands write polished founder-origin myths ("it all started in our founder's kitchen…") that score high but are anti-ICP. `config.CHAIN_KEYWORDS` must have run upstream; additionally treat 10+ locations as a hard drop regardless of story density.
- **Liquor-store leakage (wine).** A liquor store can publish a warm founder story while stocking commodity SKUs. Cross-check `business_type == wine` rows against the commodity/exclusion SKU list (Tito's, Veuve, Josh, Barefoot, Kendall Jackson, Meiomi, Yellowtail, Apothic, etc.) and liquor-ESP red flags (City Hive, Spot Hopper) from `config.py`; demote to tier 3 and flag if they fire. A respected-importer logo (Skurnik, Louis/Dressner, Jenny & Francois, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor) confirms curated wine.
- **Wine-bar exclusion.** A wine bar with a lovingly written owner story is still mostly out (avg AGMV $36.2k) except geographic monopolies — run the `reclassify.py` wine-bar claw-back before scoring.
- **Sweets-only / single-product demotion.** A bakery with a gorgeous naturally-leavened founder story is great, but a single-SKU cookie or candy shop caps at tier 2 on ICP grounds — the founder-story score must not override the sweets-only demotion.
- **Static-social / thin-web shops understate.** A genuinely founder-led small-market operator may have a one-paragraph About page or none at all (`story_page_found=False`). Absence of a rich story page is **not** absence of a founder-led business — do not subtract from a row's ICP standing; flag low-confidence/homepage-fallback rows for manual review rather than dropping them. This is the same caveat as static social understating brand.
- **Small-market metrics run low.** The whole point of the engine is to rescue these; do not let any numeric floor silently exclude a high-density small-market row before it reaches this overlay.
- **LLM cost/latency creep & prompt rot.** If the lexical gate is too loose the Haiku pass balloons toward every row. Keep the gate tight and re-validate the classifier against a labeled founder-led / faceless-brand sample periodically.

## Repo placement

An overlay package plus a thin orchestrator, with one extension to the `enrich.py` step-1 crawler so the story-page text is captured once and shared.

```
enrich.py
  + extend the step-1 website crawl to probe + retain narrative-page text       # MODIFY
    (/about, /our-story, /philosophy, /our-farmers, /sourcing, ...)
  + expose crawl_story_text(url) -> {story_text, story_page_url, story_page_found}  # NEW, exported
    (shared with Engines 03/06 which also want richer About-page text than the
     current crawl captures)

founder_story/                           # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                            # lexicon families, weights, vertical_boost, tier thresholds
  fetch.py                               # crawl_story_text over input CSV + lexical density pre-score
  classify.py                            # Claude Haiku adjudication via awards/llm_extract.py plumbing
  aggregate.py                           # blend lexical + LLM into story_density, tier, liquor/chain guards
  finalize.py                            # reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical schema

discover_founder_story.py                # NEW orchestrator (mirrors discover_hidden_clubs.py / discover_butchers.py)
  python discover_founder_story.py --input output/2_enriched_websites.csv
  python discover_founder_story.py --input output/custom-serper-scoring_*_all.csv
  python discover_founder_story.py --master-only

config.py
  + FOUNDER_STORY_FAMILIES (the 5 lexicon groups), FOUNDER_STORY_WEIGHTS,
    FOUNDER_STORY_TIER_THRESHOLDS, vertical_boost map                            # NEW
  + reuse existing commodity-wine exclusion SKUs + City Hive/Spot Hopper red-flags
    + importer trust list (already present for other engines)
```

The only genuinely new infrastructure is the narrative-page text capture in the step-1 crawl (a link-probe + text-concat extension, not a new fetcher) and the small classify/aggregate overlay. Every other primitive — `awards/llm_extract.py`, `reclassify.py`, `dedupe_existing.py`, the Haiku model, the config exclusion lists — already exists.

## Open questions

1. Should the LLM adjudicate on `story_text` alone, or should the homepage hero/tagline be included? Some operators put their entire founder identity in a one-line tagline ("Whole-animal butchery since 2014, three farms, no shortcuts") and have no About page — including the hero would catch them but adds noise.
2. What `story_density` and `confidence` thresholds actually separate a sales-meaningful founder operator from competent marketing copy? Needs a labeled backtest against onboarded high-AGMV partners — do their pre-Table22 About pages score high here?
3. Should this run as a standalone list at all, or only as an **ICP-boost column** merged into other engines' outputs (its true value is rescuing under-measured rows, not producing a fresh list)? If the latter, the "list" is really the C/D-numeric ∩ tier-1/2-density rescue queue.
4. Many founder stories live only on Instagram bios / pinned posts, not the website. Is a `scrape_beli`-style IG-bio pass over in-vertical rows worth adding here, or is that a separate engine?
