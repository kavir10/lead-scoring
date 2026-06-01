# Lead Engine 02 — Manual Workflow Pain List

**Motion:** Hybrid (Curation-grade ICP gate + a hard operational Trigger overlay)
**Vertical fit:** Bakeries, butchers, wine, cheese, specialty grocers, holiday-preorder restaurants
**Suggested list name(s):** `premium_retail_manual_preorder`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run (riding existing `enrich.py` step-1 crawl; net-new cost is link-in-bio resolution + a small Claude classify pass)

## Premise

A business that takes orders through a Google Form, a Typeform, "email to
order," "DM to reserve," a downloadable PDF order sheet, a Square checkout
link, or "Venmo us to hold your box" is broadcasting two things at once:
**proven recurring demand** (you don't build a manual preorder flow for
products nobody asks for repeatedly) and **acute operational pain** (they're
hand-managing what a platform exists to systematize). That is the cleanest
possible Trigger in the two-score model — the outbound line writes itself:
"you're doing manually what Table22 automates."

The demand-over-capacity thesis maps directly. A butcher running a Google
Form for Thanksgiving turkeys, a bakery taking holiday pie preorders by
email, a cheese shop DMing to reserve a raclette night, a wine shop
collecting allocation requests over Venmo — these are operators whose
fulfilment ceiling is set by a spreadsheet, not by the product. They are
exactly the high-AGMV partner types (butcher $75.9k, wine $68.2k, cheese
$63.8k) where Table22 has both performance and headroom.

This engine is a **Hybrid**: the manual-order signal is a strong Trigger but
a *weak* ICP gate on its own (a chain or a liquor store can run a Google
Form too). So we curate hard — the Trigger only counts once the row clears
the ICP-fit floor. High-trigger / weak-ICP rows get filtered before sales,
not nurtured.

## Recipe

The detection primitive already exists. `enrich.py` **step 1 (websites)** is
a concurrent 10-thread crawl that already pulls ecommerce flags, email-signup
forms, social links, and reservation-platform detection. We extend that
crawler's parse layer with a **manual-order signal extractor**, then run a
link-in-bio resolver for the social handles we already collect.

1. **Seed the universe.** Don't cold-discover. Feed this engine the existing
   enriched corpus (`output/2_enriched_*.csv`) plus the niche-vertical lanes
   (`butcher/`, `best_wine_shops/`, `directories/`, awards master). These rows
   already cleared discovery quality floors and carry `website` + social
   handles. For net-new geography, seed Serper Maps off
   `research/trendy_neighborhoods/` (≈56.5% of partners sit in trendy
   neighborhoods) for `butcher | bakery | cheese | wine_store | specialty`.

2. **Crawl the site for order-mechanism signals.** Extend the step-1 crawler
   to scan page HTML, anchor `href`s, and visible button/CTA text for:

   - **Form/link hosts:** `docs.google.com/forms`, `forms.gle`,
     `*.typeform.com`, `*.jotform.com`, `airtable.com/shr`, `square.link`,
     `squareup.com/...checkout`, `checkout.square.site`, `*.formstack.com`,
     `wufoo.com`, `cognitoforms.com`
   - **Order-by-channel phrases (regex, case-insensitive):**
     `email (us )?to order`, `to order,? (please )?(email|call|text|dm)`,
     `pre-?order by (email|phone|dm)`, `call (the shop )?to reserve`,
     `dm to (order|reserve|hold)`, `message us to order`,
     `venmo`, `zelle`, `place your order by`, `order form` (PDF link),
     `download (the )?order (form|sheet)`, `holiday (pre-?order|order) form`,
     `reserve your (turkey|ham|box|wheel|pie|allocation)`
   - **PDF order sheets:** any `.pdf` link whose anchor text or filename
     matches `order|preorder|holiday|thanksgiving|easter|catering`.

3. **Resolve link-in-bio.** We already collect IG/FB handles in step 1. The
   real order link is often only in the bio, not the website. Resolve the
   `link in bio` target (Linktree, Beacons, Stan.store, Milkshake, raw
   bio URL) by fetching the public bio via the **Apify
   instagram-profile-scraper** (already wired, run in batches of 30 — reuse
   the step-2 hook) and re-running the regex/host match from step 2 against
   the resolved destination(s). This is where butchers and bakeries actually
   hide the Google Form.

4. **Classify the mechanism (Claude, cheap pass).** For ambiguous matches,
   send the surrounding snippet to Claude (`claude-haiku-4-5`, same model
   `scrape_beli` uses) to label `order_mechanism ∈ {google_form, typeform,
   jotform, airtable, square_link, email_to_order, dm_to_order,
   call_to_reserve, pdf_order_form, venmo_zelle, none}` and emit a one-line
   `trigger_summary` sales can quote. Prefix the script with
   `unset ANTHROPIC_API_KEY &&` (shell empty-key gotcha).

5. **Apply the ICP gate (curation half of the hybrid).** Run `reclassify.py`
   to get `partner_type` / `business_type_v2`, then `detect_clubs.py` (a
   business already running a Squarespace/Shopify subscription is a *better*
   lead — existing club is a positive switch-the-platform signal, not a DQ;
   carry `has_club` through). Reject anti-ICP before scoring:

```
DISQUALIFY if:
  partner_type in {liquor_store} or wine commodity-SKU leak (Tito's, Veuve,
      Barefoot, Yellowtail, BuzzBallz, ...) or ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS)
  delivery-only / ghost kitchen / caterer / cocktail bar / pizza-first(non-artisanal)
  wine bar  -> exclude UNLESS geographic_monopoly flag
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # enforce only in butcher lane

DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery
  static-social-only (understates brand in small markets — never DQ on this)

trigger_strength:
  +3 google_form|typeform|jotform|airtable|pdf_order_form   # hardest pain
  +2 email_to_order|venmo_zelle|square_link
  +1 dm_to_order|call_to_reserve
  +1 if mechanism is seasonal/holiday preorder (recurring spike pattern)
  +1 if has_club==True (proven recurring demand, platform-switch motion)

QUALIFY (engine output) if: passes ICP gate AND trigger_strength >= 2
```

6. **Hand off to scoring.** Emit the canonical CSV (below) and let `score.py`
   run unmodified — do **not** touch `config.SCORING_WEIGHTS` (SHAP-aligned).
   The manual-order columns ride as evidence; `trigger_strength` orders the
   outbound queue inside a tier.

## Output schema

```
output/manual_preorder/premium_retail_manual_preorder_<YYYYMMDD>.csv
source = "premium_retail_manual_preorder"
tier = <1|2|3>     # 1 = butcher/wine/cheese + hard-form trigger; 2 = bakery/specialty or seasonal-only; 3 = ICP-soft
business_type = butcher | wine_store | cheese | bakery | specialty | restaurant
distinction = "Takes orders manually via {mechanism} — systematize w/ Table22"
year = <discovery_year>
+ evidence cols (preserve so sales can cite the trigger in outbound):
    order_mechanism            # google_form | typeform | email_to_order | dm_to_order | pdf_order_form | venmo_zelle | square_link | call_to_reserve
    order_evidence_url         # the actual form/PDF/link-in-bio destination
    order_evidence_snippet     # verbatim page/bio text that matched
    found_on                   # website | link_in_bio | both
    is_seasonal_preorder       # bool (holiday/turkey/pie/allocation pattern)
    trigger_strength           # int, intra-tier outbound ordering
    trigger_summary            # one-line Claude-written outbound hook
    has_club                   # carried from detect_clubs.py (positive signal)
    partner_type               # from reclassify.py
```

## Volume & cost

- Input universe (existing enriched corpus + niche lanes), deduped: **~8–12K
  rows**. No discovery spend — these are already-crawled businesses.
- Step-1 crawl extension: free (rides the existing 10-thread crawl; +1 parse
  pass, no new fetch).
- Link-in-bio resolution via Apify profile scraper: only for rows with a
  social handle and *no* website-side match (~30–40%, ≈3.5K). At batches of
  30 and ~$0.002–0.004/profile ≈ **$10–14**.
- Claude Haiku classify pass on ambiguous snippets (~2K rows, short prompts):
  **≈ $2–4**.
- **Per-run total: ~$15–18.**
- **Net-new qualified leads per run:** of ~10K screened, manual-order signal
  hits **~12–18%** (≈1.2–1.8K); after ICP gate + `trigger_strength >= 2`,
  expect **~400–700 qualified rows**, the strongest of which are net-new only
  on the *trigger* (many businesses already in our corpus — that's fine, the
  trigger re-prioritizes them for outbound now).

## Refresh cadence

**Monthly, with a heavy pre-holiday run in late September and late October.**
The seasonal-preorder slice (Thanksgiving turkeys, holiday pies, charcuterie
boxes, Easter hams) is the highest-conversion subset and appears on sites for
only ~6–8 weeks. Catching the form *while it's live* makes the outbound line
land ("saw your holiday preorder form go up"). Off-season, monthly is enough —
manual-order setups are sticky and turn over slowly.

## Risks

- **ICP leakage through the trigger.** A liquor store or 12-location chain
  runs a Google Form too. The trigger is loud; the ICP gate must do the
  filtering. Keep `config.CHAIN_KEYWORDS`, commodity-SKU, and ESP-red-flag
  (City Hive, Spot Hopper) checks *upstream* of `trigger_strength`.
- **Wine-bar and liquor-store false positives.** Enforce the wine-bar
  exclusion (except geographic-monopoly) and `reclassify.py` wine-bar
  claw-back; a bottle-shop-with-Venmo that's really a liquor store must drop.
- **Small-market metrics run low.** A great rural butcher with a paper order
  form may have thin social/review volume. Weight relative local dominance
  and the trigger itself; **never DQ on static-only social** — it understates
  brand.
- **Sweets-only demotion.** A cupcake shop with a holiday order form is a real
  trigger but a single-product bakery — cap at Tier 2, don't promote on
  trigger alone.
- **Stale forms.** Google Forms close after the season; a dead `forms.gle`
  link reads as a signal but the pain is over. Record `found_on` +
  fetch-time HTTP status; treat a closed form as `is_seasonal_preorder` +
  lower confidence, not a hard hit.
- **Link-in-bio fragility.** Apify IG profile scraper rate-limits and Linktree
  HTML changes; batch at 30, back off, and fall back to website-only matches
  when bio resolution fails (don't block the row).
- **False "manual" reads on real ecommerce.** A site with full Shopify
  checkout *and* a legacy "email to special-order" line is not in pain. Require
  the manual mechanism to be the *primary* order path; if `has_ecommerce` from
  step 1 is true AND it's the main CTA, demote unless the manual flow is a
  distinct high-value SKU (allocations, whole-animal shares).

## Repo placement

Standalone package mirroring the niche-lane shape, reusing the step-1 crawler
and the step-2 Apify hook as libraries.

```
manual_preorder/
  __init__.py                  # registers signal hosts/regex; engine constants
  signals.py                   # FORM_HOSTS, ORDER_PHRASE_REGEX, PDF_ORDER_RULES, SKU/ESP leak lists
  crawl_signals.py             # parse layer over enrich.py step-1 crawl output
  resolve_link_in_bio.py       # wraps Apify instagram-profile-scraper (reuse step-2 batching)
  classify.py                  # Claude haiku-4-5 mechanism + trigger_summary
  aggregate.py                 # ICP gate (reclassify + detect_clubs join), trigger_strength, dedupe
  finalize.py                  # canonical schema writer, date-stamped output
discover_manual_preorder.py    # orchestrator: seed -> crawl -> bio-resolve -> classify -> gate -> finalize
```

Refactor target: extract `enrich.py` **step-1** order-mechanism-relevant
parsing (forms, social links, ecommerce flag) into a shared
`enrich_websites_lib` so both `enrich.py` and `manual_preorder/crawl_signals.py`
parse identically without duplicating the crawl. Same shared-lib argument as
the step-8 availability refactor noted in Engine 05.

## Open questions

1. **Live-form verification depth.** Do we just HTTP-check the form URL, or
   actually fetch the Google Form / Typeform to confirm it's accepting
   responses (open vs closed) before assigning a hard trigger? Cheap to check,
   but Typeform/Forms have anti-bot behavior — worth a spike.
2. **Square-link ambiguity.** `square.link` / `checkout.square.site` can mean
   either "manual workaround" or "real lightweight store." Is Square presence
   a *pain* signal or a *tech-stack-fit* signal (Square is a compatible POS in
   the ICP)? It may belong in both columns with different meaning.
3. **Should the seasonal slice be its own list?** A late-September
   `holiday_preorder_<YYYYMMDD>` cut with its own outbound timing may convert
   better than folding seasonal rows into the evergreen master.
4. **Cross-engine dedupe key.** Many of these rows already exist in awards /
   directories / butcher lanes. Phone-first dedupe via `dedupe_existing.py`,
   but how do we *merge* the trigger onto an existing partner row rather than
   emit a duplicate?
