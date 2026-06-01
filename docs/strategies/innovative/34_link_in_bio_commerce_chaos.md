# Lead Engine 34 — Link-in-Bio Commerce Chaos

**Motion:** Curation (a Trigger-rich overlay that reads the link-in-bio page of already-discovered, in-vertical rows for a fragmented commerce stack)
**Vertical fit:** All — but sharpest on butcher, wine, cheese, bakery and specialty grocer (recurring-product-native types where a manual stack is actively losing money), with destination restaurants on the events/preorder edge
**Suggested list name(s):** `link_in_bio_commerce_chaos`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ~$8–20 per run (one `detect_clubs`-style page fetch over resolved bio links + a small Claude classification pass; no Apify post/reel scrape, optional Serper Web)

## Premise

When a food business runs a Google Form *and* a Square store *and* a Venmo handle *and* an Eventbrite *and* a Toast page *and* a "DM us to order" line *and* a newsletter signup — all stacked on one Linktree / Beacons / Campsite bio page — that is a business with **multiple live revenue motions and no unified system to run them**. Each destination is a separate operator on a separate tool, none of them recurring, none of them talking to each other. The link-in-bio page is a public confession that the operator has outgrown ad-hoc tooling: they are taking pre-orders by form, payment by Venmo, events by Eventbrite, and retail by Square, manually reconciling all of it. That fragmentation is exactly the pain Table22 collapses into one recurring-commerce platform.

In the two-score model this is a clean **Trigger** overlay on the ICP Fit the pipeline already scores. The signal is not "do they sell online" (a single clean Shopify store is *less* interesting here) — it's the **number and heterogeneity of disconnected commerce destinations**. A messy stack means the operator has already manufactured demand across several channels and is paying for it in manual labor; the demand-over-capacity thesis applies to *operational* capacity, not just seating. The richer overlay is when the stack also contains a recurring tell — a "monthly box" Google Form, an Eventbrite series, a Square subscription product — because that's a proto-Table22 program running on the wrong rails.

It is **Curation**, not Volume: output is small, hand-citable, and each row carries the literal list of platforms found on the page so a BDR can open with "you're running a Google Form, Venmo and an Eventbrite — we put all of that on one system." Precision on platform classification (a real Square *store* vs. a generic link; an Eventbrite *event series* vs. a one-off) is the engine's whole job.

## Recipe

A **postprocessing overlay**, run CSV-in / CSV-out like `detect_clubs.py`. It consumes an already-discovered + `websites`+`instagram`-enriched CSV (so IG handles and bio URLs are present) and emits a small, evidence-tagged CSV. It does **not** run Serper discovery and does **not** re-scrape posts/reels.

1. **Input.** Take an `instagram`-enriched or scored CSV (`output/2_enriched_instagram.csv` or `output/2_enriched_social.csv`, or any `custom-serper-scoring_*_all.csv`). Every row already cleared quality floors and `CHAIN_KEYWORDS`. Do not re-discover. The `instagram` step (`enrich.py` step 2, `instagram-profile-scraper`) already returns the bio's external URL — that's the bio link this engine resolves.

2. **Resolve the link-in-bio page.** For each row, take the IG bio external URL (and the website's own "links" page as a fallback). Identify aggregator hosts:

   ```
   AGGREGATOR_HOSTS = (
     linktr.ee, lnk.bio, beacons.ai, campsite.bio, linkin.bio,
     linkpop.com, tap.bio, milkshake.app, withkoji.com, snipfeed.co,
     msha.ke, allmylinks.com, hoo.be, bio.link, stan.store, flowpage,
     komi.io, later.com/linkinbio, shorby, taplink.cc
   )
   ```

   Rows whose bio link points at one of these are in-scope. Rows that point straight at a single own-domain store (one clean Shopify/Squarespace) are **out** — they have a unified system already; flag `single_unified_store=True` and drop from this engine (they may belong to Engine 09 / 19).

3. **Fetch + parse the aggregator page (`detect_clubs.py` crawl path).** Reuse the `detect_clubs.py` / `detect_clubs_v2.py` concurrent crawler (50 threads, `--resume`) to fetch each bio page's HTML and extract the outbound destination links. Linktree/Beacons/Campsite render link lists in markup or a JSON blob — parse both; fall back to the existing Playwright path (the `best_wine_shops` fallback pattern) for JS-only renderers. Emit the full resolved destination URL list per row.

4. **Classify each destination into a commerce motion (the core of this engine).** Map each outbound link to a platform/motion bucket by host + path regex. Count distinct motions and distinct platforms:

   ```
   ordering/retail:   square.site, squareup.com, shop.app, shopify, bigcartel.com,
                      ecwid, squarespace (commerce), toasttab.com, popmenu,
                      goldbelly.com, faire.com
   preorder/form:     forms.gle, docs.google.com/forms, typeform.com, jotform,
                      airtable.com/shr, formstack, "pre-order"/"preorder" anchor text
   payment/p2p:       venmo.com, cash.app/$, paypal.me, zelle (text), buymeacoffee
   events/ticketing:  eventbrite.com, posh.vip, withfriends, dice.fm, resy/opentable
                      (event), tock (event), partiful, luma (lu.ma)
   reservations:      resy.com, opentable.com, exploretock.com, sevenrooms
   newsletter/esp:    mailchi.mp, substack.com, /subscribe, klaviyo, beehiiv,
                      flodesk, mailerlite, "join our list"/"newsletter"
   social/dm:         instagram dm anchor, "DM to order", wa.me (whatsapp),
                      m.me (messenger), text/sms: links
   gift/other:        gift card host, tip jar, patreon, kickstarter
   ```

   Emit `platforms_found` (pipe-joined host list), `motion_buckets` (distinct buckets that fired), `n_destinations`, `n_motions`, and per-bucket booleans (`has_form`, `has_venmo`, `has_square`, `has_eventbrite`, `has_toast`, `has_newsletter`, `has_dm_order`, …).

5. **Score the chaos.** Fragmentation = several heterogeneous payment/ordering motions with no unifying platform. Reward heterogeneity and the presence of a *recurring* tell; penalize a single clean store.

   ```
   chaos_score = min(100,
        18*min(n_motions, 4)               # breadth of disconnected motions
      + 20*(1 if (has_form and (has_venmo or has_dm_order)) else 0)  # form+manual-pay = no real cart
      + 15*(1 if has_eventbrite else 0)    # repeat-commerce / events motion (-> Engine 12/26)
      + 15*(1 if has_newsletter else 0)    # a list to migrate, no monetization layer
      + 12*(1 if recurring_tell else 0)    # "monthly box"/"weekly"/"subscription" anchor text
      - 30*(1 if single_unified_store else 0))   # one clean store = NOT chaos

   # recurring_tell = anchor/url text matches monthly|weekly|box|share|subscription|club|standing order
   trigger_tier = 1 if chaos_score>=55 else 2 if chaos_score>=35 else 3
   ```

   A row scoring high on `n_motions` with a form + Venmo + newsletter and no real cart is the canonical catch: live demand, zero infrastructure.

6. **LLM adjudication (`awards/llm_extract.py` pattern, Claude Haiku).** Host-matching is noisy — a `linktr.ee` may just hold an IG link + a website link (not chaos), and anchor text disambiguates a Square *store* from a Square *appointment* page or an Eventbrite *series* from a one-off. For any row with `chaos_score >= 35`, pass the parsed link list + anchor text to a Claude classifier (reuse `awards/llm_extract.py` plumbing; `claude-haiku-4-5-20251001` as in `scrape_beli`):

   ```
   is_fragmented_commerce: bool      # multiple live, disconnected revenue motions?
   live_ordering_motions: [str]      # which buckets are genuine purchase paths
   has_recurring_motion: bool        # any subscription/box/standing-order tell?
   unifiable: bool                   # would a single platform plausibly collapse these?
   evidence: str                     # the verbatim platform/anchor list proving chaos
   confidence: 0.0-1.0
   ```

   Keep rows where `is_fragmented_commerce == True` AND `len(live_ordering_motions) >= 2` AND `confidence >= 0.6`. Prefix the run with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha).

7. **Qualify against ICP before handoff.** Run `reclassify.py` (`partner_type` / `business_type_v2` + wine-bar claw-back), `detect_clubs.py` (an existing labeled club is a *positive* platform-switch signal, not a DQ — but note it so we don't double-touch with Engine 01), then `dedupe_existing.py` (phone-first, then name+address). Apply the butcher-lane `BANNED_STATES = {HI, IN, IA, KS, NV, ND, SD}` to `partner_type == butcher` rows only. Hard-filter chain / liquor-store / delivery-only leakage. Final list = high `chaos_score` AND ICP A/B; high-chaos / weak-ICP routes to nurture.

8. **(Optional) Score for ranking.** If the input was only `instagram`-enriched, hand survivors to the remaining `enrich.py` steps + `score.py` so the chaos trigger rides on top of the SHAP-aligned score. The chaos fields are overlay evidence — do **not** touch `SCORING_WEIGHTS`.

## Output schema

```
output/social_signals/link_in_bio_commerce_chaos_<YYYYMMDD>.csv
source = "link_in_bio_commerce_chaos"
tier = <1|2|3>                       # = trigger_tier from chaos_score
business_type = restaurant | butcher | wine | cheese | bakery | specialty_grocer | ...
distinction = "Fragmented commerce: {n_motions} disconnected motions on {bio_host} ({platforms_found})"
year = <YYYY of scan>
+ canonical: name, city, state, country, source_url (= bio page URL), blurb
+ evidence cols (preserve so sales can name the exact platform mess in outbound):
    bio_url                  # the resolved Linktree/Beacons/Campsite page
    bio_host                 # which aggregator (linktr.ee, beacons.ai, ...)
    platforms_found          # pipe-joined destination hosts
    motion_buckets           # distinct motion buckets that fired
    n_destinations           # total outbound links on the page
    n_motions                # distinct commerce motions
    has_form, has_venmo, has_square, has_eventbrite, has_toast,
    has_newsletter, has_dm_order, has_giftcard            # per-bucket booleans
    recurring_tell           # bool: monthly/weekly/box/subscription anchor text
    chaos_score              # 0-100 from step 5
    is_fragmented_commerce   # LLM verdict
    live_ordering_motions    # LLM: genuine purchase paths
    unifiable                # LLM: collapsible into one platform
    evidence                 # verbatim platform/anchor proof string
    confidence               # LLM 0.0-1.0
    single_unified_store     # must be False (clean single-store rows excluded)
    has_club                 # joined from detect_clubs (note, don't DQ)
    icp_fit_score, partner_type   # joined from score.py / reclassify
    scan_date
```

## Volume & cost

Overlay on a known set; spend bounded by candidate count, not a fresh crawl.

- Candidate pool from one `instagram`-enriched run with a resolved bio URL: ~3,000–5,000 rows across verticals.
- Share whose bio link is an aggregator (Linktree/Beacons/Campsite/etc.) rather than a direct domain: realistically **25–40%** → ~900–2,000 in-scope pages to fetch.
- Page fetch + link parse folds into the `detect_clubs` 50-thread crawl over ~1,500 pages (near-free compute, bandwidth only); Playwright fallback on the JS-only ~10–15% adds a little time, not API spend.
- LLM adjudication runs only on rows with `chaos_score >= 35` (~20–35% of in-scope → ~250–500 Haiku calls of a small link-list snippet each) ≈ **$4–10**.
- Optional Serper Web to resolve a bio link for rows missing one from IG (≤ a few hundred queries) ≈ **$1–3**.
- **Per-run: ~$8–20.** No Apify post/reel scrape, no Resy calls.
- **Net-new / re-surfaced triggered leads per run:** ~120–280 operators clearing `chaos_score >= 35` AND ICP A/B; ~40–80 hit Tier 1 (≥3 heterogeneous motions, form+manual-pay, no real cart). Most are already in the universe — the value is a sharp, quotable operational-pain trigger.

## Refresh cadence

**Quarterly, with an opportunistic diff.** A link-in-bio stack is fairly stable — operators add a Venmo or an Eventbrite over months, not days. The high-value event is the *diff*: a previously-clean operator who just added a Google Form pre-order plus a Square page (they're scaling a manual program right now), or a stack that grew from 2 to 5 motions since last run. That delta is itself the "now's the moment" trigger. Run off the back of large `instagram`-enriched discovery batches rather than on a fixed clock; tighten ahead of holiday pre-order season when forms proliferate.

## Risks

- **Aggregator with only social links isn't chaos.** Many Linktrees hold just "Website / Instagram / Menu" — three links, zero commerce. The `n_motions >= 2` gate plus the Haiku `live_ordering_motions` check is load-bearing; never tier on raw `n_destinations`.
- **Single clean store false-negative inversion.** A unified Shopify/Square store is good operating hygiene and *low* chaos — correctly excluded here, but don't let the `single_unified_store` penalty leak into the main ICP score; it's an engine-local demotion only.
- **Liquor-store / chain leakage.** A liquor store's Linktree (Drizly, a City Hive / Spot Hopper storefront, commodity-SKU links: Tito's, Veuve, Josh, Barefoot, Kendall Jackson, Yellowtail, Apothic…) can light up motion buckets. Enforce `CHAIN_KEYWORDS` + the liquor-license filter + the wine commodity-SKU exclusion before scoring; an importer-trust hit (Skurnik, Louis/Dressner, Jenny & Francois, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, Jose Pastor) pushes the other way for `wine` rows.
- **Wine-bar exclusion.** A wine bar with a Tock event link + Resy + a newsletter can score high; wine bars are mostly out (avg AGMV $36.2k) except geographic monopolies — let the `reclassify.py` claw-back gate them before scoring.
- **Sweets-only / single-product demotion.** A cupcake-only bakery with a busy Linktree is still single-product; cap at Tier 2 per the demotion rule — the chaos signal must not override it. Carry the input row's `partner_type`.
- **Static-social understates brand.** A respected butcher who keeps one clean phone-order line and no aggregator scores zero here — that is **not** a DQ. This engine only *adds* a trigger; absence of a messy stack ≠ absence of demand or operational pain.
- **Small-market metrics run low.** Rural operators often run the messiest manual stacks (Facebook + Venmo + a Google Form) but on Facebook rather than IG/Linktree, so a bio-only resolve misses them. Add a Facebook-page links pass (Engine reuses `enrich.py` step 3 surface) for `partner_type in {butcher, deli, specialty_grocer}` and weight relative local dominance over raw motion count.
- **Aggregator anti-bot / rate-limit fragility.** Linktree and Beacons throttle and increasingly render link lists client-side; checkpoint per batch, support `--resume`, and probe parse-yield before locking thresholds. Some hosts cloak destination URLs behind a redirect — resolve one hop where cheap, otherwise classify on anchor text.
- **LLM cost/latency creep.** If the `chaos_score >= 35` pre-gate is too loose the Haiku pass balloons; keep the gate tight and re-validate the classifier against a labeled chaotic/clean sample periodically.

## Repo placement

An overlay package plus a thin orchestrator, reusing the `detect_clubs` crawler and the `awards/llm_extract.py` classifier. Mirrors the `social_signals/` shape proposed by Engines 04/13.

```
social_signals/                          # shared with Engines 04 / 13 if built first
  __init__.py
  resolve_bio_links.py                   # NEW: read IG bio URL from instagram-enriched CSV;
                                         #      detect AGGREGATOR_HOSTS; flag single_unified_store
  fetch_bio_pages.py                     # NEW: detect_clubs 50-thread crawl + Playwright fallback;
                                         #      parse Linktree/Beacons/Campsite link lists (+ JSON blob)
  classify_commerce_motions.py           # NEW: host+path regex -> motion buckets; chaos_score;
                                         #      Claude Haiku adjudication via awards/llm_extract.py
  finalize.py                            # reclassify -> detect_clubs note -> dedupe ->
                                         #      BANNED_STATES (butcher) -> canonical schema

discover_link_in_bio_chaos.py            # NEW orchestrator (mirrors discover_butchers.py)
  python discover_link_in_bio_chaos.py --input output/2_enriched_instagram.csv
  python discover_link_in_bio_chaos.py --input output/custom-serper-scoring_*_all.csv --resume
  python discover_link_in_bio_chaos.py --master-only

config.py
  + AGGREGATOR_HOSTS (step 2 list)
  + COMMERCE_MOTION_MAP (host/path -> motion bucket, step 4)
  + CHAOS_SCORE_THRESHOLDS
  + reuse commodity-wine exclusion SKUs + City Hive/Spot Hopper red-flag + importer trust list
```

Refactor target so we don't duplicate the crawler: expose `detect_clubs.py`'s concurrent fetch (the 50-thread `--resume` body) as a small `crawl_lib.fetch_pages(urls)` helper that both `detect_clubs.py` and `fetch_bio_pages.py` call, instead of re-declaring threading/retry. No genuinely new external tool is required — the only new infrastructure is the aggregator-link parser and the motion-classification map; everything else (crawl, Playwright fallback, Haiku extract, reclassify, dedupe) already exists.

## Open questions

1. What fraction of in-vertical operators actually use an aggregator bio vs. a direct domain link? A quick probe over one `instagram`-enriched batch (count rows whose bio URL host ∈ `AGGREGATOR_HOSTS`) settles the volume estimate before committing the build.
2. Do Linktree/Beacons/Campsite reliably expose destination URLs in server-rendered HTML or a parseable JSON blob, or is Playwright required for most? This drives whether step 3 is a cheap crawl or a slower browser pass, and the cost line.
3. Should `has_eventbrite` / events-heavy stacks route to Engine 12 (events → repeat commerce) / Engine 26 instead of (or in addition to) here, to avoid double-touching the same operator with two motions' worth of outbound?
4. Is the Facebook-links pass (for butcher/deli/grocer, where the messy stack lives on FB not IG) a launch dependency or a follow-on? It catches the small-market operators this engine otherwise misses, but adds the `enrich.py` step-3 surface as a second fetch path.
