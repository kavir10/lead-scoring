# Lead Engine 20 — Email List But No Monetization List

**Motion:** Hybrid (a Trigger overlay over discovered/enriched leads; the email-list signal also lifts ICP Fit)
**Vertical fit:** All — restaurants (destination + neighborhood), wine, butcher, cheese, bakery, specialty grocer, deli/market
**Suggested list name(s):** `email_list_no_monetization`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$6–12 per run (no new Apify spend; folds into the websites crawl + a detect_clubs site fetch)

## Premise

A business that runs Mailchimp/Klaviyo/an embedded newsletter form or a homepage pop-up has already done the hardest, least-fun part of building a subscription program: **it owns an audience and chose to invest in capturing it.** Email-list presence is itself a strong ICP signal — it separates operators who think in terms of "my customers, my list, repeat contact" from those running a transactional storefront and nothing else. The list is the asset Table22 monetizes; an operator who has built one has pre-qualified themselves on intent and digital literacy.

The trigger is the gap: they have the audience-capture layer but **no monetization layer for recurring demand** — no club, subscription, membership, preorder, monthly box, meat share, CSA, or standing order. They are collecting addresses and (at best) blasting one-off promos. In the two-score model this engine raises **ICP Fit** (list = audience-building maturity, an ESP signal SHAP ranks meaningfully) and supplies a **sharp, citable Trigger**: "You've already built a list of [N]+ subscribers on Klaviyo — you've done the audience work, you just haven't turned it into recurring revenue." This is demand-over-capacity in its cleanest form: the demand (an engaged owned audience) provably exists and is sitting unmonetized.

It is explicitly **Hybrid**, and the close sibling of Engine 09 (tech-ready/no-subscription) and the inverse of Engine 01 (existing-club transition). Where 09 keys on the whole stack and 01 keeps club-positive rows, this engine keys specifically on **ESP/list-capture present AND every monetization signal absent**. Email-positive + club-positive rows are not this engine's leads — they belong to Engine 01's transition motion and route to nurture.

## Recipe

A **postprocessing overlay**. It consumes an already-discovered + `websites`-enriched CSV and emits a filtered, list-tagged CSV. No fresh Serper discovery; it reuses the websites crawler and `detect_clubs.py`.

1. **Input.** Take a scored or at-least-`websites`-enriched CSV (`output/2_enriched_websites.csv`, a vertical lane master, or a `custom-serper-scoring_*_all.csv`). Every row already has a `website`, passed quality floors, and survived `CHAIN_KEYWORDS`. Do not re-discover.

2. **Detect list-capture (extend `enrich.py` step 1 `websites`).** The websites crawl already detects an email-signup form. Tighten it into a `detect_list_capture(html, headers, scripts)` pass on the same fetch (no extra request) that fingerprints the ESP/form vendor and the capture *mechanism* from HTML, script `src`, `<form action>`, and `<meta name="generator">`:

   ```
   ESP / list vendor:  klaviyo (klaviyo.js, _learnq, a.klaviyo.com),
                       mailchimp (list-manage.com, mc.us*.list-manage, mc-validate),
                       constant contact (ctctcdn, constantcontact.com),
                       flodesk (flodesk.com, getflodesk), omnisend, sendinblue/brevo,
                       activecampaign, mailerlite, beehiiv, substack (embed),
                       convertkit/kit, drip, hubspot forms (hsforms.net),
                       shopify email/forms (shopify_form, /contact#newsletter)
   capture mechanism:  embedded inline form, footer signup, modal/pop-up
                       (klaviyo onsite, privy, sumo, optinmonster, justuno),
                       "join our list / newsletter / VIP / mailing list" CTA text
   ```

   Emit `esp_vendor` (the detected ESP), `list_capture_type` (`inline|footer|popup|none`), and `has_email_list` (bool). Refactor: expose `detect_list_capture()` from `enrich.py` so this overlay and `detect_clubs.py` share one crawl rather than re-fetching.

3. **Negative monetization check (reuse `detect_clubs.py`).** Run `detect_clubs.py` (50-thread site scrape) over the same input to populate `has_club`, `club_type`, `club_url`, `club_signals`. Its `CLUB_KEYWORDS` / `CLUB_URL_PATHS` / `CLUB_TYPE_PATTERNS` already cover wine club, meat/fish share, CSA, monthly box, bread club, cheese club, allocation, subscription, membership, autoship. This engine keeps **only `has_club == False`** rows. The standing repo principle — existing club is a *positive* signal — holds: club-positive rows are not discarded, they are tagged `route=nurture_transition` and handed to Engine 01.

4. **Belt-and-suspenders monetization-absence scan.** Add a lightweight regex pass over the crawled homepage plus a `/subscribe`, `/membership`, `/club`, `/box`, `/preorder`, `/gift-subscription` link probe to catch preorder/box wording `detect_clubs.py` may miss:

   ```
   MUST_BE_ABSENT (zero matches to qualify):
     subscription, subscribe & save, membership, member(s) club, wine club,
     meat share, CSA, monthly box, box of the month, bottle club, cheese club,
     bread club, mystery box, preorder, pre-order, standing order,
     recurring (order|delivery), gift subscription, allocation, autoship
   ```

   A row qualifies only if `has_club == False` (step 3) AND zero matches here.

5. **Grade list strength** (trigger strength, not ICP). A first-party ESP with a real capture surface is a hot trigger; a bare `mailto:` link is cold:

   ```
   list_strength:
     hot   = esp_vendor in {klaviyo, mailchimp, flodesk, omnisend, beehiiv,
                            convertkit, hubspot} AND list_capture_type in {inline, popup}
     warm  = esp_vendor detected AND list_capture_type == footer
     cold  = only a mailto: signup or generic "contact us" form, no ESP fingerprint
   drop list_strength == cold AND no other strong ICP signal   # not really a list
   ```

   Klaviyo specifically over-indexes on commerce-minded operators (it ties to a storefront) — treat a Klaviyo fingerprint as the strongest single tell.

6. **Vertical-aware ESP nuance (wine + liquor-store leakage).** For `business_type == wine`, reuse the liquor-store-ESP red flags from `config.py` — `City Hive` and `Spot Hopper` as the ESP/site vendor are a strong liquor-store (anti-ICP) tell, not curated-wine list maturity. Demote any wine row whose only detected list vendor is City Hive or Spot Hopper, set `liquor_store_esp_suspect=True`, and let `reclassify.py` adjudicate. Conversely, a curated-wine operator running Klaviyo/Flodesk with importer street-cred (Skurnik, Louis/Dressner, Jenny & Francois, Zev Rovine, Rosenthal) is the wine "new club" sweet spot — flag `wine_new_club_candidate=True`.

7. **Reclassify + dedupe before handoff.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, wine-bar claw-back) then `dedupe_existing.py` (phone-first). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` filter only to `partner_type == butcher` rows.

8. **(Optional) Score for ranking.** If the input was only websites-enriched, hand qualifying rows back through the remaining `enrich.py` steps + `score.py` so the list trigger rides on the SHAP-aligned score. Do not alter `SCORING_WEIGHTS`; `has_email_list` already informs the ESP feature, and `list_strength` is an overlay attribute, not a new scoring weight.

## Output schema

```
output/email_list/email_list_no_monetization_<YYYYMMDD>.csv
source = "email_list_no_monetization"
tier = <1|2|3>                       # list-strength tier from recipe step 5 (1=hot,2=warm,3=thin)
business_type = restaurant | wine | butcher | cheese | bakery | specialty_grocer | deli
distinction = "Owns a list (<esp_vendor>), no club/subscription detected"
year = 2026
+ canonical: name, city, state, country, source_url (= website), blurb
+ evidence cols (preserve verbatim so sales can cite the trigger in outbound):
    esp_vendor              # e.g. "klaviyo" — opens with "saw you run Klaviyo"
    list_capture_type       # inline | footer | popup
    has_email_list          # must be True
    list_strength           # hot | warm | cold
    has_club                # must be False
    club_signals            # raw detect_clubs output (should be empty)
    monetization_scan       # MUST_BE_ABSENT matches found (should be empty)
    liquor_store_esp_suspect   # wine-only flag
    wine_new_club_candidate    # wine-only flag (importer/somm street-cred + list)
    route                   # sales | nurture_transition (club-present spillover)
```

Master union: `output/email_list/email_list_all_<YYYYMMDD>.csv`.

## Volume & cost

Bounded by input list size, not fresh discovery. Over a typical ~2,500-row vertical-mix discovery batch:

- ESP/list-capture penetration in independent food businesses is high — empirically **~45–60%** show a detectable ESP or embedded form → ~1,150–1,500 list-positive rows.
- Of those, recurring-program (club/subscription) penetration in the independent long tail is low — ~15–25% — so **~75–85%** survive the negative-monetization filter.
- After dropping `list_strength == cold` (bare mailto / no ESP): roughly **700–1,000 net-new tier-1+2 leads per 2,500-row batch**, ~300–450 of them tier-1 (hot ESP + inline/popup capture).

Cost arithmetic: list detection folds into the existing `websites` crawl (zero marginal request). `detect_clubs.py` is a second site fetch over ~2,500 rows at 50 threads ≈ free compute, bandwidth only. No Apify, no Serper Web, no Resy calls are added. If the input needs fresh discovery first, that Serper Maps cost (~$5–10) belongs to the discovery run, not this overlay. **Overlay-only marginal cost: ~$6–12** (mostly the detect_clubs crawl; near-zero if `has_club` is already populated upstream).

## Refresh cadence

**Quarterly per vertical**, run opportunistically off the back of any large discovery batch. ESP adoption and club launches move slowly at independent shops, so monthly re-runs mostly re-surface the same rows. The high-value diff is a previously-qualified list-positive lead that *launches a club* between runs — that intersection (this run's `has_club==True` ∩ last run's `email_list_no_monetization` set) is itself a fresh "they finally started monetizing the list — switch them to Table22" trigger that feeds Engine 01.

## Risks

- **List-capture false negatives.** Server-rendered or heavily CDN-cached footers and JS-injected pop-ups can hide ESP fingerprints; absence of a signal ≠ absence of a list. Treat `has_email_list` as a floor. Static-only social already understates brand — same caution here: do not DQ on a missing list alone, demote to tier 3.
- **Club-detection false positives kill good leads.** `detect_clubs.py` flags "wine club" in a blog post or a "membership" loyalty punch-card as a club, wrongly disqualifying a genuine no-monetization lead. Keep `club_signals` in the output and sample via `sample_clubs_for_qa.py` before handoff; prefer precision on the negative filter.
- **Liquor-store leakage (wine).** Liquor stores commonly run Square + Squarespace + City Hive and capture emails — list-positive, zero curated-wine ICP. The City Hive / Spot Hopper demote (step 6) plus `reclassify.py` wine-bar/liquor adjudication and the commodity-SKU exclusion list (Tito's, Smirnoff, Veuve, Yellowtail, Josh, Barefoot, etc.) are mandatory.
- **Chain / franchise leakage.** ESPs are *more* common at small local chains. `CHAIN_KEYWORDS` runs at discovery, but a 3–9-location group can slip through; reconfirm independence on tier-1 rows before outreach.
- **Wine-bar exclusion.** A list + reservation tech is a wine-bar tell; wine bars are mostly out (avg AGMV $36.2k) except geographic monopolies. The reclassify claw-back must run before scoring.
- **Sweets-only / single-product demotion.** A bakery with a great Klaviyo list selling only cookies is list-ready but caps at Tier 2 on ICP grounds — `list_strength` must not override the sweets-only demotion baked into scoring.
- **Small-market metrics run low.** A dominant rural butcher with a real Mailchimp list will under-index on raw reviews/followers and may present a thin web footprint. Weight relative local dominance + reservation difficulty over raw social/list-capture sophistication for non-metro rows. Butcher/deli/specialty-grocer audiences also skew to Facebook over IG — `follower_count` (IG + FB) already accounts for this; don't DQ on thin IG.
- **Fingerprint rot.** ESP signatures (Klaviyo `_learnq`, Mailchimp `list-manage.com`, Flodesk `getflodesk`) change. The signature table needs periodic re-validation against known-stack reference sites or it silently degrades.

## Repo placement

An overlay package plus a thin orchestrator, with one shared-lib refactor in `enrich.py`.

```
enrich.py
  + detect_list_capture(html, headers, scripts) -> dict   # NEW, called inside step-1 websites crawl
  +   (export so detect_clubs.py and the overlay import it; no second crawl)

email_list/                              # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                           # ESP_SIGNATURES table, MUST_BE_ABSENT regex, list_strength thresholds
  fetch.py                              # reuses detect_list_capture + detect_clubs.detect() over input CSV
  aggregate.py                          # negative-monetization filter, scan, list_strength grading, tiering
  finalize.py                           # reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical schema

discover_email_list.py                  # NEW orchestrator (mirrors discover_butchers.py)
  python discover_email_list.py --input output/2_enriched_websites.csv
  python discover_email_list.py --input output/custom-serper-scoring_*_all.csv --verticals wine,butcher
  python discover_email_list.py --master-only

config.py
  + ESP_SIGNATURES dict (or keep in email_list/__init__.py if vendor-specific)
  + reuse existing City Hive / Spot Hopper liquor-ESP red-flag list + importer street-cred list
```

No new external tool is required — every primitive (websites crawl, `detect_clubs.py`, `reclassify.py`, `dedupe_existing.py`) exists. The only genuinely new code is the `detect_list_capture` fingerprinter (small, lives in `enrich.py` so the cost folds into an existing fetch) and the overlay package that joins, filters, and tiers. This shares the `detect_list_capture` refactor with Engine 09 — both want a shared `enrich.py` step-1 fingerprint lib; build it once.

## Open questions

1. Should `has_email_list` be sourced from the existing step-1 email-signup boolean (cheap, already computed) or always re-run the richer `detect_list_capture` fingerprint (gives `esp_vendor`, which is the outbound hook)? The vendor name is what makes the trigger citable — leaning toward always fingerprinting.
2. Can we estimate list *size* at all from public signals (e.g. social-follower-to-list-proxy, "join 10,000+ subscribers" copy on the form)? A size proxy would sharpen tier-1, but may be too sparse to rely on.
3. Where does the wine "new club" candidate (`wine_new_club_candidate=True`, list + importer/somm street-cred, club-negative) flow — its own sibling engine, or stay in this CSV with a flag and let scoring rank it? Affects whether `finalize.py` emits one file or two.
4. For the club-present spillover (`route=nurture_transition`), do we physically hand those rows to Engine 01's `clubs_transition` pipeline, or just tag-and-keep here? Determines whether the two engines share an input-assembly step.
