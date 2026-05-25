# Channel 03 — Sommelier Credentialing Pass Lists

**Motion:** Curation
**Vertical fit:** Restaurants (wine programs), wine shops, wine bars
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $10/run

## Premise

Every major sommelier credentialing body publishes its passers. The pass
listing names the **person + their employer at time of certification**.
The employer is the lead.

A restaurant employing a CMS Advanced Sommelier, a Master Sommelier, a WSET
Diploma graduate, or an American Sommelier alum has, by definition, a wine
program serious enough to subsidize multi-year credentialing. ~99% will be
T1 or upper-T2.

Almost zero overlap with the awards corpus — credential lists are
person-indexed, awards are venue-indexed.

## Source rosters

| Source | Public list? | Volume (cumulative US) | Format |
|---|---|---:|---|
| **Court of Master Sommeliers Americas** — Master Sommelier directory | Yes (full names + city) | ~170 Master Sommeliers | HTML list, employer NOT included → enrich separately |
| **Court of Master Sommeliers — Advanced Sommelier passers (most recent 5 yrs)** | Yes (year-end pass announcements) | ~80 new/year, ~400 cumulative | Press release PDFs + blog posts |
| **GuildSomm member directory (Advanced + Master tier)** | Yes (opt-in member profile) | ~250 with public profiles | HTML profiles list name + employer |
| **WSET Diploma graduates** — published in WSET annual reports + LinkedIn announcements | Partial | ~150 US grads/year | Press, LinkedIn |
| **American Sommelier alumni** — graduate spotlights, course completion announcements | Yes | ~50/year, ~500 cumulative | Blog posts + alumni page |
| **Wine Scholar Guild — French Wine / Italian Wine / Spanish Wine Scholars** | Partial | ~300 US/year | Annual graduate lists |

## Recipe

For each source:

1. **Direct fetch the roster page** (httpx + selectolax).
2. If only `name + city` (CMS Master list), **enrich employer** via Serper
   Web: `"{name}" sommelier site:linkedin.com OR site:resy.com OR
   site:eater.com`. Pull first match.
3. If full profile available (GuildSomm), parse `employer` field directly.
4. Normalize employer name → canonical venue → dedupe against existing
   T22 partner list.

## Output schema

`output/awards/somm_credentialing_<YYYYMMDD>.csv` (yes, lands in `awards/`
because it shares the same canonical schema and reads cleanly in awards
master union):

```
source = "credentialing_<body>"
tier = 1   # all credentialing bodies are T1 quality signal
business_type = "restaurant" | "wine_store" (heuristic from venue name)
distinction = "<credential> @ <employer> (<year>)"
year = <pass_year>
+ extra cols: person_name, credential_body, credential_level, employer_id_clay
```

## Volume & cost

- ~6 source rosters × 1-time scrape = trivial
- ~1,200 enrichment calls (Serper Web for employer lookup where missing) × $0.30/1K = ~$0.40
- LLM employer normalization: Haiku 4.5 (this is name-mapping, doesn't need Sonnet), ~$2-3
- **Per-run total: ~$3-5**
- **Net-new venues per run (first run): 700-1,000 unique employers**
- **Subsequent runs: incremental ~150 new/year**

## Refresh cadence

Quarterly is plenty. Most credential bodies announce annually; quarterly
catches mid-year individual announcements.

## Risks

- CMS roster doesn't ship employer field → fully dependent on Serper enrich
  succeeding. Expect ~70% match rate. Tag unmatched rows for manual review
  rather than dropping them.
- People change employers. Roster snapshot is point-in-time. Cross-reference
  against LinkedIn for current employer when stakes are high (Master Somm
  level rarely changes; Advanced does within 2-3 years).
- Some Diploma grads work in wholesale / distribution, not retail / on-prem.
  Filter `business_type` heuristically and tag wholesale-only as out-of-scope.

## Repo placement

`directories/wine/somm_credentialing.py` — single module emitting one
canonical DataFrame. Registered in `directories/__init__.py:ALL_SOURCES`.

Alternative placement: under `awards/wine/somm_credentialing.py` if the
scrape volume + signal quality warrants treating it as an award. Default to
`directories/` since it's roster scraping, not editorial.

## Open questions

1. Should we treat CMS Introductory + Certified-level passers? Volume is ~10x
   higher (~5K cumulative) but signal quality drops fast — Intro is a
   weekend course. Recommend: stop at Advanced + Master only.
2. Worth scraping the **classmate graph** — same intro course cohort often
   ends up in same restaurant group ecosystem? Probably v2 of this channel,
   not v1.
3. Wine Scholar Guild graduates skew academic / education, not on-prem.
   Consider deprioritizing.
