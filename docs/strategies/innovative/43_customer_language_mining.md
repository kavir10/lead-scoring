# Lead Engine 43 — Customer Language Mining

**Motion:** Curation
**Vertical fit:** All — strongest on butcher / bakery / wine / cheese (shippable, "I-stock-up" products); restaurants surface through "worth the drive" / "special occasion" language
**Suggested list name(s):** `customer_language_mining`
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $30/run

## Premise

Engines 13 (ship-intent comments) and 16 (angry reviews) mine demand language
on surfaces the operator controls or where the customer is *talking to* the
business. This engine mines the surfaces where customers talk *about* the
business to **each other** — Reddit threads ("best bakery in the East Bay?"),
local Facebook groups, food forums, neighborhood blogs, and the comment walls
under "where to eat in X" listicles. The phrases people use there —
*best bakery in town*, *worth the drive*, *hidden gem*, *always sells out*,
*line out the door*, *I bring this to every party*, *I stock up whenever I'm
in town* — are unprompted, peer-to-peer endorsements. They are the purest
public expression of the demand-over-capacity thesis: a business whose
customers spontaneously evangelize it to strangers has provable, transferable
demand that a Table22 recurring-access program can monetize.

In the two-score model this is a **Trigger harvester that also discovers
net-new names**. Unlike the comment/review overlays it is not bounded to a
known universe — a Reddit thread will name a beloved shop our Serper Maps pass
never surfaced (too few reviews, no website at the time, wrong city query).
So it does double duty: it discovers operators *and* attaches a quotable,
customer-authored trigger to each. The second output is the more unusual one:
because the signal is already in the customer's own words, this engine
produces **outbound copy as a byproduct** — a BDR can open with the exact
sentence a stranger wrote about the prospect.

This is squarely a **Curation** engine. Forum chatter is noisy, anecdotal, and
full of chains, closed spots, and businesses outside our verticals. The gate
that separates a genuine peer endorsement of an in-vertical independent from
"love the Chipotle on 5th" is load-bearing, and net-new names must run the
full discovery quality floor + ICP gate before they reach sales.

## Recipe

A **discovery + trigger** engine modeled on `best_wine_shops/` (Serper-seeded
article/thread discovery → httpx/selectolax fetch → Claude extraction) crossed
with `scrape_beli/`'s multi-phase mine-then-resolve shape. It emits both
net-new candidates and re-surfaced known operators, each carrying verbatim
customer language.

1. **Discover discussion surfaces via Serper Web.** Use the same
   `google.serper.dev/search` primitive the press enrichment step (`enrich.py`
   step 4) drives. Fan out city × phrase queries across `config.CITIES`
   (bias geography with `research/trendy_neighborhoods/` seed CSVs — ~56.5% of
   partners sit in trendy neighborhoods). Restrict to discussion-heavy domains:

```
DISCUSSION_DOMAINS = (
  "reddit.com", "facebook.com/groups", "chowhound",      # forums / groups
  "seriouseats.com", "eater.com", "infatuation.com",     # listicle comment walls
  "tripadvisor.com", "yelp.com",                          # review-thread prose
  "<city>.eater.com", "local food blogs",                 # neighborhood blogs
)
SEED_PHRASES = (
  "best {butcher|bakery|wine shop|cheese shop|deli} in {city}",
  "hidden gem {city} {vertical}", "worth the drive {vertical}",
  "always sells out", "line out the door", "where do you buy {product}",
  "best {sourdough|brisket|natural wine|charcuterie} near me",
)
```

2. **Fetch the threads (httpx + selectolax happy path, Playwright fallback).**
   Reuse the `best_wine_shops/` fetch pattern: httpx + selectolax for static
   HTML, Playwright fallback when blocked. Reddit's public JSON
   (`/<thread>.json`) is a clean fetch and should be the primary Reddit path.
   Facebook groups are mostly login-walled — capture only what surfaces in
   Serper snippets + public group posts; do **not** build a FB-group scraper
   (see Risks). Cache raw thread text to a gitignored JSON per the
   `scrape_beli` convention.

3. **Extract business mentions + the endorsement phrase (Claude).** Run
   `awards/llm_extract.py`-style extraction with `claude-haiku-4-5-20251001`
   (the model `scrape_beli` uses for caption/OCR mining) over each thread.
   For every named business pull: `name`, inferred `city`/`state`, the
   **verbatim endorsement sentence(s)**, and a coarse `vertical` guess. Prefix
   the script with `unset ANTHROPIC_API_KEY &&` (empty-key shell gotcha). A
   cheap regex pre-pass over `LANGUAGE_PATTERNS` gates which threads are worth
   an LLM call — skip threads with no demand language at all:

```
LANGUAGE_PATTERNS = {
  "scarcity":   (r"always sells out", r"line (out the door|around the block)",
                 r"sold out by \d", r"get there early", r"gone by (noon|10)"),
  "loyalty":    (r"i stock up", r"i (always )?bring (this|these) to",
                 r"my go[- ]?to", r"every (week|weekend|party)"),
  "pilgrimage": (r"worth the drive", r"drive .* (just |an hour )?for",
                 r"hidden gem", r"best .* (in town|i'?ve (ever )?had)"),
  "occasion":   (r"special occasion", r"only place (i|we) (go|trust) for"),
}
```

4. **Resolve mentions to a real business (the hard middle step).** A forum
   names "Avedano's" or "that butcher on Cortland" — not a website or phone.
   For each extracted mention, run a `scripts/fresh_icp_search.py`-style Serper
   Maps lookup (`name + city`) to resolve to a Maps `place_id`, website, phone,
   rating, review count, and Google `type`. Drop mentions that don't resolve to
   a single physical food business. This reuses the discovery primitive rather
   than inventing a new resolver.

5. **Apply discovery quality floors + chain filter to net-new names.** Run
   resolved net-new candidates through the same floors `discover.py` enforces:
   restaurants ≥50 reviews / ≥4.2 rating, niche ≥20 / ≥4.0, website required,
   chains filtered via `config.CHAIN_KEYWORDS`. **Do not** DQ a thin-review
   small-market shop the way discovery would by default — a strong peer
   endorsement is exactly the case where static metrics understate brand;
   route sub-floor-but-endorsed rows to a `needs_review` bucket instead of
   dropping them (see Risks).

6. **Score endorsement strength.** Count *distinct threads/authors* per
   resolved business — a name surfaced by one Redditor is weaker than one
   named across three threads:

```
mention_threads = #distinct threads naming this business
mention_authors = #distinct authors naming it (across threads)
scarcity_hits   = authors whose mention matched the "scarcity" family
pilgrimage_hits = authors matching "worth the drive"/"hidden gem"/"best in town"
loyalty_hits    = authors matching "i stock up"/"bring to parties"/"go-to"
recency_days    = days since most-recent matching thread/post

endorsement_score = min(100,
      25*min(mention_threads,2)          # corroboration across threads
    + 15*min(mention_authors,3)          # breadth of evangelists
    + 20*(1 if scarcity_hits>=1 else 0)  # demand-over-capacity language
    + 15*min(pilgrimage_hits,1)          # out-of-market / destination pull
    + 10*min(loyalty_hits,1)             # repeat-purchase intent (club fit)
    + (10 if recency_days<=180 else 0))  # still a live conversation

trigger_tier = 1 if endorsement_score>=55 else 2 if >=35 else 3
```

7. **ICP gate, then hand to scoring.** Run `reclassify.py` (`partner_type` /
   `business_type_v2` + wine-bar claw-back) and join `detect_clubs.py`
   (`has_club`; existing club = positive switch signal, not a DQ). Apply the
   standard disqualifiers below, then `dedupe_existing.py` (phone-first, then
   name+address) against the existing corpus so re-surfaced names merge rather
   than duplicate. Feed survivors to `score.py` **unmodified** — do not touch
   `config.SCORING_WEIGHTS` (SHAP-aligned). `endorsement_score` orders the
   outbound queue inside a tier; the verbatim quote rides as evidence.

```
DISQUALIFY if:
  liquor store (vs curated wine); wine commodity-SKU leak (Tito's, Veuve,
      Barefoot, Yellowtail, Josh, Cupcake, ...) or ESP red flag (City Hive, Spot Hopper)
  chain/franchise (>=10 locations, config.CHAIN_KEYWORDS); caterer; ghost kitchen/delivery-only
  pizza-first (non-artisanal); cocktail bar; wine bar UNLESS geographic_monopoly
  butcher row in BANNED_STATES {HI,IN,IA,KS,NV,ND,SD}   # butcher lane only
DEMOTE (cap Tier 2, do not DQ):
  sweets-only / single-product bakery; static-social-thin small-market (understates brand)
FINAL LIST = passes ICP gate AND endorsement_score >= 35 (A/B tier on score.py)
```

## Output schema

```
output/demand_signals/customer_language_mining_<YYYYMMDD>.csv
source = "customer_language_mining"
tier = <1|2|3>                       # = trigger_tier from endorsement_score
business_type = butcher | bakery | wine | cheese | deli | specialty | restaurant
distinction = "Customers evangelize unprompted: '{best_quote}' — {mention_threads} threads, {mention_authors} voices"
year = <YYYY of most-recent matching thread/post>
+ evidence cols (preserve verbatim so sales can quote the customer in outbound):
    endorsement_score, trigger_tier,
    mention_threads, mention_authors,
    scarcity_hits, pilgrimage_hits, loyalty_hits,
    matched_families (pipe-delim: scarcity|loyalty|pilgrimage|occasion),
    best_quote,             # the single most quotable verbatim sentence
    quote_samples,          # 1-3 verbatim endorsements for outbound copy
    source_urls,            # the threads/posts the quotes came from (Reddit/blog/etc.)
    source_platform,        # reddit | forum | blog | listicle | yelp_prose
    recency_days, scan_date,
    is_net_new,             # True if not previously in the corpus
    needs_review,           # endorsed but below discovery floor (small-market flag)
    icp_fit_score, partner_type, has_club   # joined from score.py / detect_clubs
```

## Volume & cost

- Discovery: ~130 cities × ~6 phrase templates × ~4 verticals, deduped by URL,
  capped at ~3 results/query → **~2,000–3,500 unique threads/articles** per run.
  Serper Web ≈ $0.001–0.003/query; ~3K queries ≈ **$4–8**.
- Fetch: httpx/selectolax is free compute; Playwright fallback on ~10–15% of
  blocked URLs is compute-only. **~$0.**
- Claude Haiku extraction over threads that clear the regex pre-pass (~40% →
  ~1.2K threads, short prompts): **≈ $4–7**.
- Serper Maps resolution of extracted mentions (~3K mentions, dedup to ~1.5K
  unique names) ≈ $0.003/lookup → **≈ $5–8**.
- **Per-run total: ~$15–25.**
- **Net-new + re-surfaced leads per run:** of ~1.5K resolved unique businesses,
  the ICP gate + floors keep **~400–700**; of those, **~120–250** are *net-new*
  (not in the existing corpus). Expect **~40–80 Tier 1** (multi-thread,
  scarcity/pilgrimage language). The recurring value is the customer-authored
  outbound copy attached to every row.

## Refresh cadence

**Monthly.** Forum and blog conversations accumulate slowly and are durable —
a "best bakery in town" Reddit thread keeps surfacing in search for months, so
a tighter cadence re-mines the same threads for diminishing return. Dedup by
thread URL against prior runs and only LLM-extract *new* threads. Run a heavier
pre-holiday pass (Q4): "where do I get a turkey / pie / charcuterie board for
the party" threads spike November–December and carry strong occasion + scarcity
language for exactly the gift-and-stock-up verticals.

## Risks

- **Forum noise is the dominant failure mode.** Threads are full of chains,
  closed businesses, sarcasm ("best bakery if you like cardboard"), and
  out-of-vertical mentions. The Claude extraction (step 3) must confirm a
  *genuine positive endorsement of a real, in-vertical independent*; gate on
  distinct authors with confirmed intent, never raw mention count.
- **Mention-resolution ambiguity.** "That butcher on Cortland" or a misspelled
  name may resolve to the wrong place or none. Require a single confident Maps
  match (name+city); drop multi-match and no-match mentions rather than guess —
  a wrong resolution poisons outbound.
- **Small-market metrics run low → over-filtering.** The discovery floors
  (≥20–50 reviews) will reject exactly the beloved rural shop the forum is
  raving about, where static metrics understate brand. Route endorsed-but-
  sub-floor rows to `needs_review` instead of dropping; weight relative local
  dominance and the endorsement itself over raw review count.
- **Static-social understates brand.** A shop with a thin Instagram but a wall
  of forum love is still high-ICP — this engine exists partly to catch them.
  Do not let downstream social-thin demotion erase the endorsement signal.
- **Liquor-store / chain leakage.** "Best wine shop" threads name liquor stores
  pushing commodity SKUs (Tito's, Veuve, Yellowtail) and regional chains.
  Enforce `config.CHAIN_KEYWORDS` + the liquor-license filter + the wine
  commodity-SKU exclusion list; City Hive / Spot Hopper ESP footprints flag a
  liquor store. Apply *before* the endorsement score.
- **Wine-bar exclusion.** "Best wine spot" conflates retail shops and wine
  bars; wine bars are mostly excluded (low Peak AGMV) except geographic-
  monopoly. Let `reclassify.py`'s claw-back gate them.
- **Sweets-only demotion.** A cupcake/cookie shop drawing "I bring these to
  every party" is a real loyalty signal but single-product — cap at Tier 2 per
  the demotion rule; carry `partner_type` and apply the cap.
- **Facebook-group walls.** Most group content is login-gated. Do not build a
  FB-group scraper (ToS + brittle auth); take only Serper snippets and public
  posts. Reddit + blogs + listicle comment walls carry the bulk of the signal.
- **Recency / dead businesses.** Forum praise can be years old and the shop
  closed. Record `recency_days`, weight it, and confirm the resolved Maps place
  is currently operating ("permanently closed" flag) before handoff.

## Repo placement

Standalone package mirroring the `best_wine_shops/` editorial-scraper shape,
reusing the Serper Web + Maps primitives and the `awards/llm_extract.py`
extraction helper.

```
customer_language/                   # may co-house future text-mining engines
  __init__.py                        # engine constants; registers phrase + domain banks
  patterns.py                        # LANGUAGE_PATTERNS, DISCUSSION_DOMAINS, SEED_PHRASES, SKU/ESP leak lists
  discover_threads.py                # Serper Web fan-out (city x phrase x vertical), URL dedup
  fetch_threads.py                   # httpx+selectolax happy path, Reddit .json, Playwright fallback; caches raw JSON
  extract_mentions.py                # regex pre-gate -> Claude haiku-4-5 extraction of (name, city, quote, vertical)
  resolve_mentions.py                # Serper Maps name+city -> place_id/website/phone/rating (reuses fresh_icp_search shape)
  aggregate.py                       # discovery floors + chain filter, endorsement_score, ICP gate, dedupe_existing join
  finalize.py                        # canonical schema writer, date-stamped output
discover_customer_language.py        # orchestrator: discover -> fetch -> extract -> resolve -> floor+gate -> finalize
```

Refactor targets so we don't duplicate logic:

- Lift the Serper Maps resolution body out of `scripts/fresh_icp_search.py`
  into a shared `serper_resolve_lib` (name+city → place fields) so this engine
  and any future name-resolution lane call one implementation.
- Reuse `awards/llm_extract.py` directly for the Claude extraction step rather
  than re-declaring the SDK client / prompt scaffold.
- Reuse the `best_wine_shops/` httpx→Playwright fetch fallback rather than
  re-implementing it.

`config.py` knobs to add: `LANGUAGE_PATTERNS`, `DISCUSSION_DOMAINS`,
`CUSTOMER_LANGUAGE_SEED_PHRASES`, `ENDORSEMENT_SCORE_THRESHOLDS`, and the
per-query result cap.

## Open questions

1. **Reddit fetch durability.** Reddit's public `.json` endpoints rate-limit
   and increasingly require auth — is the snippet-only path (Serper) enough, or
   does this engine need a Reddit API key / OAuth app registered alongside the
   existing `.env` keys? A probe on 50 threads should settle the floor.
2. **Resolution precision vs recall.** How aggressively do we drop fuzzy
   mentions ("the place near the park")? Dropping them protects outbound
   quality but discards real small-market names — should ambiguous mentions go
   to `needs_review` with their quote, for a human to resolve, rather than be
   discarded?
3. **Net-new vs re-surface split.** Should net-new discoveries (not in the
   corpus) feed back into the main `discover.py` universe as a new seed source,
   or stay isolated to this list until manually promoted?
4. **Quote provenance for outbound.** Can we cite a customer quote in cold
   email without attribution/privacy issues? Likely yes for public forum prose,
   but confirm policy before BDRs paste verbatim Reddit sentences into outreach.
