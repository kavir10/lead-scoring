# Channel 02 — Food Job Board Employer Extraction

**Motion:** Curation, **time-sensitive** (re-run weekly)
**Vertical fit:** Restaurants (wine programs), wine bars
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $15/week (Serper + light HTTP scraping; no Apify needed)

## Premise

A restaurant currently hiring a **wine director, sommelier, beverage
director, or wine-focused GM** is at peak buying intent for any wine-program
SaaS. Two layered signals fire simultaneously:

1. **Structural signal** — the wine program is big enough to need dedicated
   staff. Restaurants that don't take wine seriously don't post these roles.
2. **Intent signal** — they're actively investing *right now*. Procurement
   cycles for adjacent tools (POS, subscription platform, club software)
   typically follow within 30-90 days of a beverage hire.

Pair this with the Wave 1 #1 channel (competitor / software case studies):
job posting + already-on-competitor-platform = top-of-funnel gold.

## Source boards

| Board | Volume estimate | Listing detail | Access |
|---|---:|---|---|
| **Culinary Agents** | ~3K open wine/bev roles/week US | Restaurant name in title + employer field | Public web, listing pages render server-side |
| **Poached.com** | ~1K open wine/bev roles | Restaurant name prominent | Public web |
| **Sevenrooms Hire** | ~500 wine/bev roles | Native to Sevenrooms hospitality stack | Public web |
| **Indeed** | ~4K wine-director postings | Restaurant name in employer field | Serper Web with `site:indeed.com "wine director"` query |
| **Restaurant Zone** | ~600 wine/bev roles | Restaurant name as employer | Public web |
| **Cool Hunting / Restaurant Hospitality** | <100 (low volume, high quality) | Editorial chef hires | One-off |

Two scraping waterfalls:

- **Direct-fetch** for Culinary Agents, Poached, Sevenrooms Hire, Restaurant
  Zone (httpx + selectolax over listing pages, paginate by city + role
  filter).
- **Serper Web** for Indeed (`site:indeed.com "wine director" OR "sommelier"
  OR "beverage director"` per city). Indeed actively blocks scrapers but
  Serper SERPs surface the listing title + employer in the snippet, which is
  enough.

## Query patterns

```
"wine director"
"sommelier"
"beverage director"
"head sommelier"
"wine buyer" restaurant
"beverage program manager"
"general manager" "wine list"
```

Per-city pagination across the 30-metro panel from `config.py:SEED_METROS`.

## Output schema

`output/jobs/wine_director_postings_<YYYYMMDD>.csv`:

```
source = "job_board_<slug>"
business_type = "restaurant"  # default; refine via name heuristics
distinction = "Hiring: <role> as of <date>"
year = <YYYY>
+ extra cols: role_title, posted_at, listing_url, employer_name,
              employer_city, employer_state, days_open, salary_range_if_present
```

Canonical lead = the **employer**, not the job posting. Dedupe by
(employer_name + city) and keep the most recent posting per employer.

## Aging & decay

Job listings decay fast — a "hiring" signal is most valuable in the first
30 days. Pipeline tags each row with `posted_at`. After 60 days, demote from
A-list to B-list. After 120 days, drop unless re-posted (re-posting itself is
a signal of difficulty filling = even higher intent).

## Pair with competitor case studies

The right product surface is a **join**:

```
(employer_in_job_posting) ∩ (employer_in_competitor_case_study_corpus)
```

That intersection is the strongest single intent stack we can build from
public data. Anything in that intersection should route to senior BDRs same
day.

## Cost estimate

- Serper queries: ~30 metros × 10 query patterns × paginate 3 = 900 queries × $0.30/1K = ~$0.30/week for Indeed
- Direct fetch: free (httpx). Maybe 50K page fetches/week — well within free tier on cloud egress.
- LLM normalization (employer name → canonical form): Sonnet, ~$5/week
- **Per-run total: ~$5-15/week**
- **Net-new venues per run: 200-400 unique employer mentions, ~80 unique restaurants after dedupe across boards**

## Refresh cadence

**Weekly.** This is the only Wave 2 channel where decay actually matters.
Cron via launchd or GitHub Actions Mondays 9am ET.

## Risks

- Indeed will block direct scraping. Serper SERPs are the fallback — confirm
  snippet quality is sufficient before committing.
- Culinary Agents may rate-limit; add 1s delay between page fetches.
- Restaurant names in postings are often misspelled or include franchise
  qualifier ("at Le Bernardin" vs "Le Bernardin"). Normalize via Sonnet or a
  simple regex + manual override list.

## Repo placement

```
jobs/
  __init__.py
  _lib.py                     # SCHEMA, shared helpers
  culinary_agents.py
  poached.py
  sevenrooms_hire.py
  indeed_serper.py            # uses Serper Web, not direct
  restaurant_zone.py
discover_jobs.py              # orchestrator
```

## Open questions

1. Should we expand to general manager / chef de cuisine roles? Probably yes
   for restaurants — chef-hiring is also a buying-cycle signal, just weaker.
   Phase 2.
2. Worth caching results across weeks to compute `days_open` properly?
   Probably yes — `output/jobs/raw/<board>_<YYYYMMDD>.csv` archive, then
   diff.
3. Salary disclosure laws vary by state (CA, NY, CO, WA require). Where
   present, use as a proxy for wine-program tier.
