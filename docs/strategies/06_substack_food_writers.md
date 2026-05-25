# Channel 06 — Paywalled Substack Food-Writer Recommendation Lists

**Motion:** Curation
**Vertical fit:** Restaurants, wine bars, specialty retail (writer-dependent)
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $20/run

## Premise

Food substacks and adjacent newsletter-only outlets (Air Mail, New Yorker
columns) publish curated venue lists that are **invisible to press-archive
deep-dive** because the content sits behind paywalls or in newsletter
archives that don't get fully indexed by Serper.

The audience for these newsletters is **highly ICP-shaped for Table22** —
food-obsessed urban professionals who already subscribe to one premium food
publication, would happily subscribe to another (a restaurant club).

## Source writers

| Writer / Outlet | Platform | Cadence | Lists or single-venue | Public access |
|---|---|---|---|---|
| **Helen Rosner** (New Yorker — "Food Scene" column + newsletter) | newyorker.com | Weekly-ish | Single-venue + roundups | Public archive, some paywalled |
| **Alicia Kennedy** (alicia-kennedy.com / Substack — *From the Desk of Alicia Kennedy*) | Substack | Weekly | Single-venue + thematic | Free-tier sample, premium paywalled |
| **Vittles** (Jonathan Nunn, UK-led but US coverage growing) | Substack | Weekly | Heavy on venue lists, neighborhood guides | Free + paid |
| **Air Mail — Look** (Graydon Carter) | airmail.news | Weekly | Single-venue mentions inside Look section | Subscription |
| **Anna Hezel** (*The Sticky Note* — IIRC, plus Bon Appétit + Lucky Peach archive) | Substack | Monthly | Single-venue | Mostly free |
| **Adam Reiner** (*The Restaurant Manifesto*) | Substack | Weekly | Single-venue + industry essays | Free + paid |
| **Pete Wells** (post-NYT, where he's writing — verify) | varies | varies | Venue reviews | varies |
| **Eater Upsell / Eater Inside** (newsletter editions of Eater) | Eater | Weekly | Venue features | Free |
| **The Infatuation — Sunday Slate** (paid tier) | The Infatuation | Weekly | Venue picks | Free + paid |
| **Tejal Rao** (NYT but worth tracking) | NYT | Weekly | Venue features | NYT paywall |
| **Soleil Ho** (SF Chronicle — venue criticism) | SF Chronicle | Weekly | Venue features | Paywall |

## Recipe

For each writer:

1. **Subscribe** (under team email) to get authenticated paywall access where
   needed. Persist auth cookies in `cookies/substack_*.json` mirroring the
   awards-pipeline pattern (`--cookies-from`).
2. **Pull archive** — Substack exposes a paginated archive at
   `{publication}.substack.com/archive`. Direct fetch with httpx +
   selectolax for free posts; authenticated fetch with cookies for paywalled.
3. **LLM extraction** — feed each post body to Claude Haiku 4.5 with prompt:

   > Extract every restaurant, bar, wine shop, bakery, butcher, or specialty
   > food retailer named in this post. For each, return: venue_name, city,
   > state, country, context (one-sentence reason the writer mentioned it),
   > sentiment (positive | neutral | negative).

4. **Filter** to US, sentiment != negative. Drop venues already on T22
   partner list (re-mention is fine for re-engagement but not for net-new
   discovery).

## Output schema

`output/directories/substack_food_writers_<YYYYMMDD>.csv`:

```
source = "substack_<writer>"
tier = 1   # any named mention in this corpus is signal
business_type = inferred
distinction = "Mentioned by {writer} on {date} — '{context}'"
year = <post_year>
+ extra cols: writer, post_url, post_date, context_snippet, sentiment,
              mention_count_lifetime
```

## Aggregation across writers

A venue named by ≥2 writers is **A-list** automatically. The food-writer
audience overlap is high enough that cross-writer mention = strong consensus.

## Volume & cost

- 10 writers × ~50 archive posts each = 500 posts on first run
- Haiku extraction: 500 × ~3K input + 1K output × $1/$5 per Mtok ≈ ~$2
- Incremental runs: ~50 new posts/week × small cost = trivial
- **Per-run total: ~$5-15 (first), ~$1-2 (incremental)**
- **Net-new venues per run (first): ~600-1,200 unique mentions, ~300 unique venues post-dedupe**

## Refresh cadence

**Weekly.** Newsletter content is fresh weekly; recency is part of the
signal value.

## Risks

- **Paywalls.** Some publications (Air Mail, NYT, SF Chronicle) require a
  paid subscription. Use team subscription only — never share cookies via
  source control. Store under `cookies/` (gitignored).
- **Substack rate limits** — Substack actively blocks scraping at high
  volume. Throttle to ~1 req/sec per publication and rotate User-Agent.
- **Writer churn** — substacks die. Maintain a `WRITERS.md` registry with
  `last_seen_at` and prune dead feeds.
- **Negative sentiment** — Pete Wells will pan a restaurant. The LLM must
  classify sentiment so we don't pitch a venue the writer hated.
- **International venues** — Vittles is UK-centric. Default US-only filter
  in the LLM prompt is critical.

## Repo placement

Mirror the existing `awards/_editorial.py` pattern — these are editorial
sources that need LLM extraction. Cleanest fit:

```
awards/                                # OR directories/, see below
  editorial/                           # new subdir for newsletter-archive sources
    substack_alicia_kennedy.py
    substack_vittles.py
    substack_adam_reiner.py
    new_yorker_helen_rosner.py
    air_mail_look.py
    eater_newsletter.py
    infatuation_sunday_slate.py
  llm_extract_newsletter.py            # specialized prompt for newsletter post text
```

Default to `awards/editorial/` because these are editorial mentions on par
with press archive deep-dive — they belong in the same downstream pipeline
that awards rows flow through. The orchestrator (`discover_awards.py`)
already handles `requires_auth` cookies via `--cookies-from`.

## Open questions

1. Worth scraping the **Eater Upsell** newsletter beyond Eater 38? Eater
   already has structured pages, so this might be redundant.
2. Should we LLM-extract from **the comments section** too? Reader comments
   on food substacks often crowd-source competing restaurant recs. Phase 2.
3. **Tejal Rao / Pete Wells / Soleil Ho** are NYT/SF Chronicle staff, not
   substackers. Treat as press archive deep-dive (Wave 1 #8) rather than
   here? Probably yes — but their newsletter editions (NYT Cooking, etc.)
   live in archive-only form that this lane is built for.
