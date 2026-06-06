# Lead Engine 12 — Events and Programming List

**Motion:** Curation
**Vertical fit:** Butchers, wine, cheese, bakeries, destination restaurants (the high-AGMV partner types)
**Suggested list name(s):** `events_programming_repeat_commerce`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run

## Premise

A business that already runs a **butchery class, wine tasting, supper club,
chef dinner, pairing dinner, cheese class, bread workshop, holiday preorder,
or CSA pickup** has, by definition, done the three hard things Table22 asks of
a partner before it ever signs: it can **package** a product or experience into
a discrete SKU, it can **communicate** that SKU to a list of customers and fill
seats/boxes, and it has proven there's **repeat interest** worth scheduling
recurring events around. Programming is operational proof of subscription-readiness
— a business that can sell out a monthly bread workshop can sell a monthly bread
club.

This maps cleanly onto the demand-over-capacity thesis. Recurring events are
capacity-constrained by design (a class has N seats, a supper club fills one
table, a CSA share has a cutoff). When those fill, the operator is leaving demand
on the table — exactly the gap a subscription program monetizes. And it lands
on the right partner types: butcher ($75.9k Peak AGMV), wine ($68.2k), cheese
($63.8k), and destination restaurants ($60.5k) are precisely the verticals where
classes, pairing dinners, and tastings are common.

In the two-score model this is mostly an **ICP-Fit** engine with a strong
co-located **Trigger**: the *kind* of programming signals the partner type and
operator sophistication (ICP Fit), while a **currently-listed or upcoming event**
— a holiday preorder window open now, a class with seats on sale — is the
reason-to-contact-now (Trigger). The cleanest rows have both.

## Recipe

No cold discovery. This engine reads programming signals off businesses we've
*already* surfaced and crawled, then layers an events-specific extraction pass.
The website crawl primitive (`enrich.py` step 1) and the Apify IG hooks already
exist; we add a programming-signal parser and a tiny Claude classify pass.

1. **Seed the universe (no Serper Maps sweep).** Feed the existing enriched
   corpus (`output/2_enriched_*.csv`) plus the niche lanes (`butcher/`,
   `best_wine_shops/`, `directories/`, awards master). These rows already cleared
   discovery quality floors and carry `website` + IG/FB handles. For net-new
   geography, seed a small Serper Maps pass (`discover.py` / `scripts/fresh_icp_search.py`)
   biased to `research/trendy_neighborhoods/` (~56.5% of partners sit in trendy
   neighborhoods) for `butcher | wine_store | cheese | bakery | restaurant`.

2. **Crawl for programming signals (extend `enrich.py` step 1).** The step-1
   10-thread crawler already pulls page HTML, anchor `href`s, and CTA text. Add a
   parse layer that scans the homepage plus `/events`, `/classes`, `/calendar`,
   `/tickets`, `/workshops`, `/dinners`, `/preorder`, `/csa` paths for:

   ```
   PROGRAMMING_PHRASES = [
     # classes / workshops
     "butchery class", "knife skills class", "sausage making class",
     "bread workshop", "baking class", "sourdough workshop",
     "cheese making class", "cheesemaking class", "cheese 101",
     "wine class", "wine education", "wine 101", "tasting class",
     # tastings / dinners / clubs
     "wine tasting", "guided tasting", "flight night", "pairing dinner",
     "wine pairing dinner", "chef dinner", "chef's table", "guest chef",
     "supper club", "pop-up dinner", "tasting menu series", "collab dinner",
     # recurring commerce
     "holiday preorder", "thanksgiving preorder", "holiday order form",
     "csa", "csa pickup", "farm share", "meat share", "monthly box",
     "subscription", "standing order", "weekly pickup",
   ]
   EVENT_PLATFORM_HOSTS = [
     "eventbrite.com", "tock.com/...experiences", "resy.com/...events",
     "withfriends.co", "tixr.com", "posh.vip", "*.squarespace.com/...events",
     "exploretock.com", "sevenrooms.com/...events", "calendly.com",
   ]
   ```
   Capture matched phrase + nearest date/price string + the event-platform URL
   (Eventbrite/Tock experience/Resy event link) so the Trigger is citable.

3. **Mine IG for event programming (reuse step-2/7 Apify hooks).** Events are
   often only on Instagram, not the site. Reuse the **instagram-post-scraper**
   (step 7) on each candidate's recent posts and run the `PROGRAMMING_PHRASES`
   regex over captions; flag posts with a date + "tickets"/"RSVP"/"link in bio"
   as live-event evidence. For high-priority rows, the **instagram-profile-scraper**
   (step 2, batches of 30) resolves a link-in-bio (Linktree/Beacons) that often
   points straight at the Eventbrite/Tock listing.

4. **Classify program type + recency (Claude, cheap pass).** Send matched
   snippets to Claude (`claude-haiku-4-5`, same model `scrape_beli` uses) to label
   `program_type ∈ {butchery_class, baking_workshop, cheese_class, wine_tasting,
   wine_class, pairing_dinner, chef_dinner, supper_club, holiday_preorder, csa,
   subscription_box, none}`, extract `next_event_date` where present, and write a
   one-line `trigger_summary` for outbound. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

5. **ICP gate (curation pass).** Run `reclassify.py` for `partner_type` /
   `business_type_v2`, then `detect_clubs.py` (an existing class/club program is
   a **positive** switch-the-platform signal, not a DQ — carry `has_club` through).
   Reject anti-ICP before scoring, score the trigger after:

   ```
   DISQUALIFY if:
     partner_type == liquor_store  or  wine commodity-SKU leak (Tito's, Veuve,
         Barefoot, Yellowtail, BuzzBallz, Cupcake, ...) or ESP red flag (City Hive, Spot Hopper)
     chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
     delivery-only / ghost kitchen / pure caterer / cocktail bar / pizza-first(non-artisanal)
     wine bar -> exclude UNLESS geographic_monopoly flag
     butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}    # butcher lane only

   DEMOTE (cap Tier 2, do not DQ):
     sweets-only / single-product bakery (a cupcake decorating class is real but caps Tier 2)
     static-social-only / thin metrics in a small market (understates brand — never DQ)

   program_strength:
     +3 recurring series (supper club / monthly class / CSA / subscription_box)
     +2 standalone class or pairing/chef dinner with seats on sale
     +2 holiday_preorder window currently open (high-intent seasonal trigger)
     +1 one-off past event only (capability proof, weaker now-trigger)
     +1 if has_club == True (already monetizing repeat demand)
     +1 if next_event_date within 60 days (live trigger)

   QUALIFY if: passes ICP gate AND program_strength >= 2
   ```

6. **Hand off to scoring.** Emit the canonical CSV (below) and run `score.py`
   unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned). The
   programming columns ride as evidence; `program_strength` orders the outbound
   queue inside a tier.

## Output schema

```
output/events_programming/events_programming_repeat_commerce_<YYYYMMDD>.csv
source = "events_programming_repeat_commerce"
tier = <1|2|3>   # 1 = high-AGMV type + recurring series or live preorder; 2 = standalone event / sweets-only; 3 = past-event-only / ICP-soft
business_type = butcher | wine_store | cheese | bakery | restaurant | specialty
distinction = "Runs {program_type} — packages experiences + has a repeat-buying list"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    program_type          # butchery_class | pairing_dinner | supper_club | holiday_preorder | csa | subscription_box | wine_tasting | ...
    program_evidence_url  # Eventbrite/Tock/Resy event link or site /events page
    program_evidence_snippet  # verbatim page/caption text that matched
    found_on              # website | instagram | both
    is_recurring          # bool (series vs one-off)
    next_event_date       # parsed date if a future event is listed
    program_strength      # int, intra-tier outbound ordering
    trigger_summary       # one-line Claude-written outbound hook
    has_club, club_type   # carried from detect_clubs.py (positive signal)
    partner_type          # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped: **~8–12K
  rows**. No discovery spend — these are already-crawled businesses.
- Step-1 crawl extension: free (rides the existing 10-thread crawl; +1 parse
  pass against extra event paths, no new fetch budget).
- IG post mining via Apify post-scraper: only for rows with a handle and *no*
  website-side programming match (~40%, ≈4K). At ~$0.002–0.003/profile in batches
  of 30 ≈ **$8–12**.
- Link-in-bio resolution (profile scraper) on the high-priority subset (~1K):
  **≈ $2–4**.
- Claude Haiku classify pass on matched snippets (~2.5K short prompts): **≈ $2–4**.
- **Per-run total: ~$12–18.**
- **Net-new qualified leads per run:** of ~10K screened, a programming signal
  hits **~15–20%** (≈1.5–2K); after the ICP gate + `program_strength >= 2`, expect
  **~500–800 qualified rows**. Many already exist in our corpus — that's fine; the
  value is the *trigger*, which re-prioritizes them for outbound now.

## Refresh cadence

**Monthly, with heavy pre-holiday runs in late September and late October.** The
holiday-preorder and seasonal-dinner slice (Thanksgiving boxes, holiday workshops,
NYE pairing dinners) is the highest-intent subset and is live on sites/IG for only
~6–8 weeks — catch it while the window is open so the outbound line lands ("saw
your holiday preorder go up"). Off-season, monthly captures newly-launched class
series and supper clubs; recurring programming is sticky and turns over slowly.

## Risks

- **Past-event staleness.** An `/events` page or IG post from 2023 proves
  *capability* but not a *now*-trigger. Parse and weight `next_event_date`; a past-only
  match is `program_strength +1`, not a hard trigger. Record fetch-time so stale
  listings don't read as live.
- **Caterer / event-venue leakage.** A business whose *only* product is private
  events is a caterer (anti-ICP), not a retail/restaurant partner running programming
  on top of a core product. Require a resolved retail/restaurant `partner_type` from
  `reclassify.py`; drop pure event venues and caterers.
- **Cocktail-bar / liquor-store leakage via "tasting."** "Tasting" matches for a
  cocktail bar or a liquor store running a free wine tasting. Keep the wine-bar
  exclusion (except geographic-monopoly), `reclassify.py` wine-bar claw-back, and
  commodity-SKU / ESP red-flag (City Hive, Spot Hopper) checks *upstream* of
  `program_strength`.
- **Sweets-only demotion.** A cupcake-decorating class or cookie workshop is a real
  programming signal but a single-product bakery — cap at Tier 2, don't promote on
  the trigger alone.
- **Small-market metrics run low.** A dominant rural butcher running a monthly
  whole-animal class will have thin social/review volume. Weight relative local
  dominance and the programming trigger over raw follower/review floors; **never DQ
  on static-only social** — it understates brand.
- **Chain leakage.** Williams-Sonoma-style chains and multi-location concepts run
  classes too. Keep `config.CHAIN_KEYWORDS` + the `reclassify.py` coarse pass upstream,
  or high-AGMV partner-type weight inflates chain scores.
- **IG/event-platform fragility.** Apify post/profile scrapers rate-limit and
  Eventbrite/Tock HTML changes; batch at 30, back off, and fall back to website-only
  matches when IG resolution fails (don't block the row).

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler and
the step-2/7 Apify hooks as libraries.

```
events_programming/
  __init__.py                  # engine constants; registers signal banks
  signals.py                   # PROGRAMMING_PHRASES, EVENT_PLATFORM_HOSTS, SKU/ESP leak lists
  crawl_events.py              # parse layer over enrich.py step-1 crawl (extra event paths)
  mine_ig_events.py            # wraps Apify instagram-post-scraper (step 7) + profile/link-in-bio (step 2)
  classify.py                  # Claude haiku-4-5 program_type + next_event_date + trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), program_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_events_programming.py # orchestrator: seed -> crawl -> ig-mine -> classify -> gate -> finalize
```

Refactor target: extract `enrich.py` **step-1** website parsing (HTML, anchors,
CTA text, social links) into a shared `enrich_websites_lib` so `enrich.py` and
`events_programming/crawl_events.py` parse identically without duplicating the crawl
— the same shared-lib argument Engines 02 and 05 raise for the step-1 and step-8
funcs. Reuse Engine 02's `manual_preorder` link-in-bio resolver if it lands first;
holiday-preorder signals overlap heavily.

## Open questions

1. **Cross-engine dedupe with Engine 02.** Holiday preorder is a signal in both
   this engine and `premium_retail_manual_preorder`. Do we merge the programming and
   manual-order triggers onto one partner row (phone-first via `dedupe_existing.py`),
   or keep separate lists with separate outbound timing?
2. **Live-event verification depth.** Do we just HTTP-check the Eventbrite/Tock URL,
   or fetch the listing to confirm seats are on sale (and parse a real `next_event_date`)
   before assigning a live trigger? Eventbrite has anti-bot behavior — worth a spike.
3. **Is a recurring class enough to auto-Tier-1**, or should it require corroboration
   from `detect_clubs.py` (`has_club == True`) before we treat it as a hard
   subscription-readiness signal?
4. **IG-only events at scale.** Mining IG posts for every no-website-match row is the
   cost driver. Do we cap IG mining to the top-N-by-partner-type rows on the first run
   and only widen on refresh?
