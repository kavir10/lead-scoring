# Lead Engine 52 — Churned or Former Club Recovery List

**Motion:** Curation (a Trigger-rich overlay that re-reads in-vertical rows for a *dead* recurring program — a club that once existed and went dark)
**Vertical fit:** Wine, butcher, cheese, bakery (the recurring-product-native, high-AGMV partner types where a paused program leaves the loudest residue)
**Suggested list name(s):** `former_club_recovery`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$15–30 per run (one `detect_clubs`-style crawl + a Wayback CDX/snapshot diff + a small Claude adjudication pass; no Apify, no Serper Maps discovery)

## Premise

Engine 01 catches operators who *currently* run a club; Engine 18 catches operators running one *without naming it*. This engine catches the third state, the one nobody else surfaces: operators who **used to run a club and stopped**. The tells are a "membership paused," "not accepting new members," "club is currently closed," or "join the waitlist" banner; an `/wine-club` or `/meat-share` page that 404s now but resolved last year; archived Instagram posts hawking a "monthly box" with no recent follow-through; a stale "next pickup" date that's months in the past; an email-list signup still promising a club that no longer ships.

A former club is a *stronger* lead than a cold new-club pitch because two of Table22's hardest objections are already answered. **They believed in the model** — somebody at that business decided recurring prepaid demand was worth building, designed it, and sold memberships. And **they hit operational pain** — they almost never stop because demand vanished; they stop because the manual tooling (a spreadsheet, a Google Form, billing chaos, fulfillment overhead) broke under the weight. That is the demand-over-capacity thesis in its purest form: proven belief plus demonstrated administrative failure. Table22's pitch writes itself — "you ran a club, it got too painful to administer; that pain is the exact thing we remove." It is a *re-launch* sale, not a concept sale, and closer to the platform-switch economics of Engine 01 than to cold outbound.

It is **Curation**, not Volume: each row must carry the verbatim residue that proves a club *once existed and is now dark* — a closed-membership banner, an archived snapshot URL, a 404'd club path that Wayback confirms used to resolve. Precision is everything; a false "former club" claim in outbound ("I see you used to run a wine club") that the operator never ran is worse than silence. The engine targets the four recurring-product-native verticals (butcher $75.9k, wine $68.2k, cheese $63.8k, bakery $34.7k) where a dead club leaves the most legible footprint.

## Recipe

A **postprocessing + archive-diff overlay**. It consumes an already-discovered, ideally `websites`-enriched CSV and emits a small, evidence-tagged CSV. It does not run Serper Maps discovery. The novel piece is a Wayback Machine diff layer — the one genuinely new dependency (see Repo placement).

1. **Input.** Take a `websites`-enriched or scored CSV (`output/2_enriched_websites.csv` or a `custom-serper-scoring_*_all.csv`). Every row already has a `website`, cleared the quality floors, and passed `CHAIN_KEYWORDS`. Restrict to `business_type in {wine, butcher, cheese, bakery}`. Do not re-discover.

2. **Run live club detection first (`detect_clubs.py`).** Run `detect_clubs.py` / `detect_clubs_v2.py` (50-thread crawl, `--resume`) to populate `has_club`, `club_type`, `club_url`, `club_signals`. This engine wants rows where a club existed historically but the **live** state is *dark*, so two row populations feed it:
   - **Currently-closed clubs:** `has_club == True` but the page content carries dormancy language (next step). The club page resolves, but it is *paused / closed / waitlist-only*.
   - **Vanished clubs:** `has_club == False` *now*, but Wayback shows a club page that used to resolve (step 4). The page is gone — a 404 or a redirect to the homepage.

3. **Dormancy-language scan (live HTML).** Add a `DORMANT_CLUB_SIGNALS` lexicon to `detect_clubs.py` (sibling to the existing `CLUB_KEYWORDS`) and scan the crawled HTML + the probed club paths (`/wine-club`, `/meat-share`, `/bread-club`, `/cheese-club`, `/membership`, `/subscribe`, `/box`). These are the "we ran one, it's off right now" tells:

   ```
   paused:        "membership is paused", "club is currently closed",
                  "temporarily closed", "on hold", "taking a break",
                  "club is on hiatus", "paused for the season"
   not-accepting: "not accepting new members", "membership is full",
                  "closed to new members", "waitlist only", "join the waitlist",
                  "sign up to be notified", "notify me when memberships reopen"
   stale-date:    "next pickup: <date in past>", "<month/season> club" w/ past year,
                  "2023 club", "spring 2024 box", "last shipment"
   past-tense:    "we used to", "our former", "the club has ended",
                  "we've discontinued", "no longer offering", "club has wound down"
   ```

   Emit `dormant_hits` (pipe-joined matched phrases) and `dormant_class` (paused | not_accepting | stale_date | past_tense). A **stale-date** match requires the date parser to confirm the referenced date/season is in the past relative to the run date — a future "next pickup" is a *live* club, not a former one, and must route to Engine 01 instead.

4. **Wayback / archive diff (the core new layer).** For each in-scope row, query the Internet Archive **CDX API** (`web.archive.org/cdx/search/cdx`) for the domain + likely club paths to answer one question: *did a club page that no longer resolves used to resolve?*

   ```
   for each candidate club path p in {/wine-club, /meat-share, /bread-club,
                                      /cheese-club, /club, /membership, /subscribe, /box}:
     past_snaps  = CDX(domain + p, from=2019, to=last_year, statuscode=200)
     live_status = HEAD(domain + p)            # from the detect_clubs crawl
     if past_snaps and live_status in {404, 301->home, 410}:
         vanished_club = True
         archive_url   = newest 200-snapshot URL          # the proof link sales cites
         archive_last_live = newest 200-snapshot timestamp
   ```

   For **currently-closed** rows (step 2), also pull the newest pre-dormancy snapshot so we can show the club was *actively selling* before it went to waitlist — `archive_url` then points at the live-selling version, which is the strongest outbound artifact ("here's your club when it was open"). Cache CDX responses by domain; rate-limit politely (Wayback is unauthenticated and throttles aggressively — see Risks).

5. **LLM adjudication (`awards/llm_extract.py` pattern, Claude Haiku).** Dormancy regex is noisy — "waitlist" can mean a busy live club, "paused" can be a one-off event, a 404 can be a site redesign rather than a killed program. For any row with a dormancy hit OR a `vanished_club` flag, pass the live HTML snippet + the newest archived snapshot text to a Claude classifier (reuse `awards/llm_extract.py` plumbing; `claude-haiku-4-5-20251001` as in `scrape_beli`). Tight schema:

   ```
   ran_a_club_before:   bool      # archive/text confirms a real recurring program once existed
   currently_dark:      bool      # paused, closed, waitlist-only, or vanished — NOT actively selling now
   former_state:        paused|not_accepting|vanished|stale|unclear
   club_type:           wine|meat|cheese|bread|box|membership|unclear
   recurrence_evidence: str       # verbatim phrase OR archived snippet proving the past program
   restartable_signal:  bool      # any "reopening soon" / "notify me" intent suggesting they want it back
   confidence:          0.0-1.0
   ```

   Keep rows where `ran_a_club_before == True` AND `currently_dark == True` AND `confidence >= 0.6`. Prefix the run with `unset ANTHROPIC_API_KEY &&` (the empty-key shell gotcha).

6. **Tier by recovery readiness × vertical economics.** A club that's *paused with a "notify me" form* is hotter than one that vanished two years ago with no trace of intent to return — the former has a warm list and stated intent; the latter needs reviving from scratch.

   ```
   strength = confidence
            + 0.30 if former_state in {paused, not_accepting}      # warm, recent, list intact
            + 0.20 if restartable_signal                           # they want it back
            + 0.20 if business_type in {butcher, wine, cheese}     # top-3 AGMV headroom
            + 0.15 if has_esp (from websites crawl)                # a list to re-activate
            - 0.20 if archive_last_live older than ~24 months      # cold, list likely decayed
   tier 1  if currently_dark and former_state in {paused, not_accepting} and strength >= 1.2
   tier 2  if currently_dark and strength >= 0.9
   tier 3  if currently_dark (vanished/stale, weak intent)
   drop    otherwise
   ```

7. **Liquor-store / commodity-wine guard.** A "wine club currently closed" on a liquor site is anti-ICP. For `business_type == wine`, demote to tier 3 and flag `liquor_store_suspect=True` if the page surfaces commodity/exclusion SKUs (Tito's, Smirnoff, Veuve, Josh, Cupcake, Barefoot, Kendall Jackson, Meiomi, Duckhorn, Yellowtail, Apothic, etc.) or a liquor-store ESP (City Hive, Spot Hopper). A respected-importer logo (Skurnik, Louis/Dressner, Jenny & Francois, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor) pushes the other way — record `importer_trust_hit`.

8. **Reclassify + dedupe + state filter, then optional score.** Run `reclassify.py` (Maps `type` + name heuristics → `partner_type` / `business_type_v2`, wine-bar claw-back), then `dedupe_existing.py` (phone-first, then name+address). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` to `partner_type == butcher` rows only. If the input was only `websites`-enriched, hand survivors to the remaining `enrich.py` steps + `score.py` so the recovery trigger rides on top of the SHAP score. The recovery fields are overlay evidence — do **not** touch `SCORING_WEIGHTS`.

## Output schema

```
output/clubs/former_club_recovery_<YYYYMMDD>.csv
source = "former_club_recovery"
tier = <1|2|3>                       # recovery-readiness tier from recipe step 6
business_type = wine | butcher | cheese | bakery
distinction = "Former club: ran a <club_type> club, now <former_state> ('<recurrence_evidence>')"
year = 2026
+ canonical: name, city, state, country, source_url (= live website or club page), blurb
+ evidence cols (preserve so sales can cite the dead-club trigger verbatim in outbound):
    former_state          # paused | not_accepting | vanished | stale
    club_type             # wine | meat | cheese | bread | box | membership
    recurrence_evidence   # verbatim live phrase OR archived snippet proving the past program
    dormant_hits          # pipe-joined live-HTML matches (closed/paused/waitlist language)
    dormant_class         # paused | not_accepting | stale_date | past_tense
    archive_url           # newest Wayback snapshot of the club WHEN LIVE — the proof link
    archive_last_live     # timestamp of that snapshot (how long ago it was selling)
    vanished_club         # True if a once-200 club path now 404s/redirects
    restartable_signal    # "notify me" / "reopening" intent present
    confidence            # LLM 0.0-1.0
    strength              # tiering score from step 6
    has_esp               # list-to-reactivate signal from websites crawl
    importer_trust_hit    # wine: respected-importer confirmation
    liquor_store_suspect  # wine-only demote flag
```

Master union: `output/clubs/clubs_recovery_all_<YYYYMMDD>.csv`. Keep `archive_url`, `recurrence_evidence`, and `dormant_hits` verbatim — they are the entire outbound proof; never normalize them away in cleanup.

## Volume & cost

Bounded by input size, not fresh discovery. Over a ~2,500-row vertical-mix batch, after restricting to the four recurring-product-native verticals (~35–50% of a mixed batch → ~900–1,250 in-scope rows):

- `detect_clubs` + dormancy scan: ~10–18% of in-scope rows carry *some* dormancy/closed-language or a vanished club path → ~120–220 rows go to the Wayback + LLM passes.
- Wayback CDX confirms a real past-club footprint on roughly 40–60% of those (the rest are redesigns, event one-offs, or false "waitlist" on a live club) → ~50–130 candidates.
- LLM adjudication confirms `ran_a_club_before & currently_dark` on ~50–65% → **~30–80 net-new tier-1+2 former-club leads per 2,500-row batch**, skewed toward wine (paused allocation/club lists) and butcher (killed meat shares).

Cost arithmetic: the dormancy re-scan folds into a `detect_clubs`-style crawl over ~1,000 rows at 50 threads (bandwidth only, near-free). Wayback CDX is free but rate-limited — ~1,000 domain lookups + ~150 snapshot fetches, throttled, is compute-time not dollars. The LLM pass is ~120–220 Haiku calls of a few-KB live+archive snippet each ≈ **$5–12**. No Apify, no Serper Web, no Resy. Total marginal: **~$15–30**, the upper end if Wayback throttling forces slower serial fetching or a paid archive fallback.

## Refresh cadence

**Quarterly, with a high-value reactivation diff.** A club's *dormancy* is itself a moving target: a "paused for the season" wine club reopens in fall; a vanished meat share might quietly come back; a "waitlist only" bakery club might fully kill the program. The sharpest sub-signal is the **state transition** — a row that was tier-1 *paused* last quarter and is still dark this quarter is a confirmed, persistent pain ("you've been closed two seasons running — that's not seasonality, that's tooling"). Run off the back of large discovery batches rather than a fixed clock, and diff each run's recovery set against the prior to catch (a) clubs that just went dark (freshest, hottest trigger) and (b) clubs that came back (route to Engine 01, drop from this list).

## Risks

- **Dormancy false positives.** "Waitlist" and "join the list" frequently mark a *thriving* live club, not a dead one; "paused" can be a one-week holiday notice; a 404 can be a site redesign that moved the club to a new path. The Wayback confirmation (step 4) + LLM adjudication (step 5) are the primary guards — never ship a "former club" row on a regex hit alone. Keep `recurrence_evidence` + `archive_url` in output and QA-sample with `sample_clubs_for_qa.py` before handoff. A wrong "you used to run a club" in outbound is more damaging than a missed lead.
- **Overlap with Engines 01 and 18.** A live, currently-selling club belongs to Engine 01; an unlabeled live program belongs to Engine 18. This engine must hard-require `currently_dark == True` (and route any reopened/now-live row back to Engine 01) or the three lists collide and double-touch the prospect. A future "next pickup" date or active checkout flow is the disqualifier from *this* list.
- **Wayback fragility / rate limits.** The Internet Archive CDX + snapshot endpoints are unauthenticated, frequently slow, and throttle aggressively; a large serial run can stall or get soft-blocked. Cache per domain, back off on 429/503, cap concurrency low, and degrade gracefully — a row with strong live dormancy language can still tier on the live signal alone if Wayback is unavailable (`archive_url` empty, lower `confidence`).
- **Liquor-store / commodity-wine leakage.** A "wine club closed" on a Tito's/Josh/Barefoot liquor site is anti-ICP; the commodity-SKU + City Hive/Spot Hopper demote (step 7) is mandatory or the wine slice over-produces liquor stores.
- **Static-social / thin-web shops understate.** Many real former clubs lived entirely on Instagram (a 2023 "monthly box" post highlight, DM-to-join) or a Google Form that's simply been unpublished — invisible to a homepage crawl *and* to Wayback. Absence of a web footprint is **not** absence of a dead club; do not DQ in-vertical rows on a clean crawl. An archived-IG / `scrape_beli`-style highlight pass is a future extension (see Open questions).
- **Small-market metrics run low.** Rural butchers/farms that ran the strongest shares (whole-animal, CSA) often have the thinnest digital trail and the sparsest Wayback coverage. Weight relative local dominance and the recovery trigger over raw web/social volume for non-metro rows.
- **Wine-bar exclusion.** A wine bar with a discontinued "members' table" can trip the lexicon; wine bars are mostly out (avg AGMV $36.2k) except geographic monopolies — run the `reclassify.py` wine-bar claw-back before scoring.
- **Sweets-only / single-product demotion.** A bakery whose dead "club" was a cookie-of-the-month is single-product → caps at Tier 2 on ICP grounds; the recovery signal must not override the sweets-only demotion.
- **Cold/decayed lists.** A club that vanished 3+ years ago has likely lost its member list and the operator's appetite. The `archive_last_live > ~24 months` penalty (step 6) demotes these; treat very-cold vanished clubs as nurture, not sales-ready.

## Repo placement

An overlay package plus a thin orchestrator, with one vocabulary extension to `detect_clubs.py` and one genuinely new archive-client module.

```
detect_clubs.py
  + DORMANT_CLUB_SIGNALS lexicon (paused/not-accepting/stale/past-tense groups)   # NEW
  + scan_dormant_signals(html, links) -> {hits, dormant_class}                    # NEW, exported
  +   (reuses the existing 50-thread crawl + --resume; emits HEAD status per club path)

former_club/                             # NEW top-level package, mirrors best_wine_shops/ shape
  __init__.py                            # DORMANT_CLUB_SIGNALS thresholds, tiering weights, club-path list
  wayback.py                             # NEW: Internet Archive CDX + snapshot client (cache, backoff)
  fetch.py                               # detect_clubs crawl + dormancy scan + wayback diff over input CSV
  classify.py                            # Claude Haiku adjudication via awards/llm_extract.py plumbing
  aggregate.py                           # require currently_dark, score strength, tier, liquor-guard
  finalize.py                            # reclassify -> dedupe -> BANNED_STATES (butcher) -> canonical schema

discover_former_clubs.py                 # NEW orchestrator (mirrors discover_butchers.py)
  python discover_former_clubs.py --input output/2_enriched_websites.csv
  python discover_former_clubs.py --input output/custom-serper-scoring_*_all.csv --verticals wine,butcher,cheese
  python discover_former_clubs.py --master-only

config.py
  + reuse commodity-wine exclusion SKUs + City Hive/Spot Hopper red-flag + importer trust list
    (all already present); add WAYBACK_CDX_BASE + polite-rate knobs
```

The only genuinely new dependency is `former_club/wayback.py` — a small unauthenticated Internet Archive CDX/snapshot client (httpx + caching + backoff). Everything else reuses existing primitives: the `detect_clubs` crawl, `awards/llm_extract.py`, `reclassify.py`, `dedupe_existing.py`. As flagged for Engines 01 and 18, expose `enrich.py` step functions as an importable lib rather than forking them if survivors need scoring.

## Open questions

1. Is the Wayback CDX API reliable and fast enough at ~1,000-domain scale, or do we need a cached/paid archive fallback (e.g. a one-time bulk CDX pull per domain stored in `output/`)? The diff is the engine's edge — if Wayback is too flaky, does the live dormancy-language signal alone carry enough precision for a v1?
2. How do we reach former clubs that lived only on Instagram (a 2023 "box" highlight, a now-deleted link-in-bio)? An archived-IG / `scrape_beli` highlight pass would catch them but is a meaningfully larger build — separate engine, or a flagged sub-mode here?
3. What `archive_last_live` recency cutoff actually separates a warm, recoverable list from a cold-restart? Needs a backtest against onboarded partners who *did* relaunch a previously-dead club, if that history exists.
4. Should a "currently closed / waitlist" club (page resolves, actively gating signups) be tiered higher than a fully *vanished* one — the former has an intact list and live intent, the latter proves the operator gave up entirely? Confirm which converts better before fixing the step-6 weights.
