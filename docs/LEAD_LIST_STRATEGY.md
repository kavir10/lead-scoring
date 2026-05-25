# Lead List Creation Strategy

**Drafted:** 2026-05-19
**Author:** Kavir
**Companion code:** [`tam_calc.py`](../tam_calc.py) (TAM build) · [`lead-discovery-plan.html`](../lead-discovery-plan.html) (visual plan)

---

## TL;DR

1. **TAM is finite at ~41,600 US businesses** across three tiers (excluding T4 sub-$10K AGMV). T1+T2 is ~22K, T3 is ~19K.
2. **Lead-list creation should run two parallel motions: Volume + Curation.** They have different inputs, different tools, different cadences, and feed different parts of a BDR's book.
3. **Volume → T3.** Broad Serper/Maps/SBA/Yelp sweeps across categories and metros. Run by automation, refreshed monthly. Goal: comprehensive coverage of the addressable mid-tier universe.
4. **Curation → T1 + upper T2.** Innovative, narrow, high-signal channels — competitor case studies, Beli, lookalikes, awards, chef moves, pop-up scrapes, AI GTM tools. Goal: surface the operators most likely to convert at $30K+ AGMV.
5. **Every BDR's book must contain both.** A book of only T1 curation runs out of volume; a book of only T3 volume burns reps on low-AGMV outcomes. The right mix is ~30% T1+T2 curated, ~70% T3 volume — refreshed weekly.
6. **AI GTM tools (Clay, Instantly, Origami) are force-multipliers**, not channels — they sit on top of either motion to enrich, route, and sequence.

---

## Section 1 — TAM (and how it was calculated)

### Tier definitions (Peak AGMV)

| Tier | AGMV band | Strategic role |
|---|---|---|
| **T1** | ≥ $80K | Anchor accounts — highest LTV, drive case studies, justify field sales effort |
| **T2** | $30K – $80K | Bulk of stable revenue — should be the largest absolute count in pipeline |
| **T3** | $10K – $30K | Volume layer — needed to keep the funnel filled and to feed promotion into T2 over time |
| **T4** | < $10K | **Out of scope.** Unit economics don't support outbound investment. |

### The numbers (triangulated, excluding T4)

| Tier | Top-down | Bottom-up | **Midpoint** | Range |
|---|---:|---:|---:|---:|
| **T1** ≥$80K | 7,450 | 8,586 | **~8,000** | 6,300 – 9,900 |
| **T2** $30–80K | 14,773 | 13,880 | **~14,300** | 11,800 – 17,000 |
| **T3** $10–30K | 27,855 | 10,686 | **~19,300** | 9,100 – 32,000 |
| **TOTAL (T1–T3)** | **50,078** | **33,152** | **~41,600** | **27,000 – 58,000** |

Current penetration: 447 in-scope partners / 41,600 TAM = **~1.1%**.

### How TAM was calculated — three methods, then triangulate

#### Method 1: Top-down (NAICS-anchored)

Source: US Census Economic Census 2022, BLS QCEW, IBISWorld.

For each of 12 verticals:

```
Step 1: US establishment count (e.g., 310K restaurants, NAICS 722511)
Step 2: × % independent (vs chains)         (e.g., 71% of restaurants)
Step 3: × % premium-tier of independents     (e.g., 13% have brand strength)
Step 4: × % concentrated in top-30 metros    (e.g., 50%)
Step 5: + sub-premium pool                   (30% of non-premium × top-30 share)
Step 6: Allocate across T1-T3 via tier mix:
        Premium pool:    20% T1 / 30% T2 / 30% T3
        Sub-prem pool:    3% T1 / 10% T2 / 30% T3
```

Verticals included: full-service restaurants, counter/fast-casual, bars/wine bars, retail bakeries, butcher shops, wine retail, cheese shops, specialty coffee, craft breweries, distilleries, gourmet grocers, confectionery.

**Top-down total (T1–T3, top-30 metros): ~50,000 operators.**

#### Method 2: Bottom-up (from existing 593 partners)

```
For each Partner Type observed in our 593-partner dataset:
  Count partners at each tier (T1, T2, T3) by Peak AGMV
  Assume current market penetration P
    (1.5% baseline, 2.5-4% for verticals sold harder)
  TAM_at_tier = observed_partners_at_tier / P
```

**Bottom-up total (T1–T3): ~33,000 operators.**

#### Method 3: Triangulation

```
Midpoint  = (top-down + bottom-up) / 2
Low band  = min(td, bu) × 0.85
High band = max(td, bu) × 1.15
```

T1 and T2 converge tightly between methods → high confidence at ~22K combined.
T3 diverges → top-down is more aspirational; treat as 9K–32K with ~19K midpoint.

Full reproducible calc in [`tam_calc.py`](../tam_calc.py). Run `python tam_calc.py`.

### Partner Type × Tier matrix (current data)

| Partner Type | Count | T1 % | Read |
|---|---:|---:|---|
| Cheese Shop | 10 | **40.0%** | Tiny universe, exceptional yield. Invest disproportionately. |
| Butcher Shop | 8 | **37.5%** | Same. Niche + high-signal. |
| Wine Shop | 22 | 31.8% | Strongest of the broader-universe verticals. |
| Destination Restaurant | 227 | 26.4% | Largest single segment; healthy T1 rate. |
| Specialty Grocer | 24 | 16.7% | Likely under-penetrated. |
| Neighborhood Restaurant | 201 | 15.4% | Volume engine. Most T2/T3 lives here. |
| Wine Bar | 20 | 10.0% | Lower than expected. |
| Bakery | 15 | **6.7%** | Surprise — clusters in T2, not T1. Worth investigating ceiling. |

**Key insight:** specialty retail (cheese/butcher/wine) is 11% of partner count but converts at 30–40% to T1. Restaurants are 76% of the base but convert at 15–26%. **Reweight curation investment toward specialty retail.**

---

## Section 2 — How TAM informs lead list creation

The 41K TAM splits naturally into two acquisition motions:

| Tier | Count | Best acquisition motion | Why |
|---|---:|---|---|
| T1 | ~8,000 | **Curation** | Brand + scarcity signals matter more than volume. Each lead deserves enrichment investment. |
| T2 | ~14,300 | **Mostly curation** | Upper half of T2 = curated. Lower half = volume. |
| T3 | ~19,300 | **Volume** | Universe is large enough that net-casting beats handpicking. |

**Three implications:**

1. **The funnel is finite — coverage matters more than generation.** At 1.1% current penetration of 41K, you don't have a TAM problem. You have a coverage problem. The question is not "how many leads can we generate" but "what % of the 41K do we know about and have in some BDR's book."

2. **Different tools for different tiers.** Premium curation (Beli, awards, Eater 38, competitor case studies) misses 80%+ of the T2/T3 universe. Volume sweeps (Serper/Maps/SBA) miss the brand-signal-rich operators who don't show up for generic queries.

3. **BDR book composition is not optional.** A book that's 100% T1 curation runs out of names quickly. A book that's 100% T3 volume produces mostly low-AGMV closes. The mix is the strategy.

---

## Section 3 — The Volume + Curation framework

### Volume motion (T3 + lower T2)

**Goal:** comprehensive coverage of the addressable mid-tier universe across top-30 metros. Automated, refreshed monthly.

**Channels:**

| Channel | What it produces | Tool stack |
|---|---|---|
| Serper Maps city × category sweep | Neighborhood restaurants, wine stores, butchers, cheese shops, bakeries, specialty grocers | Serper Maps API + dedup |
| Yelp by category × city pagination | Mid-tier independents Google misses | Yelp Fusion API or scrape |
| SBA loan recipient data | Pre-opening + recently-opened operators | Public CSV download, NAICS filter |
| Liquor / health-inspection rolls | Comprehensive jurisdiction-level coverage | State ABC / city open data |
| Secretary-of-State LLC filings | Pre-opening operators (food NAICS codes) | State business filing portals |
| Restaurant Week directories | Annual rosters per metro (~5–8K venues/cycle) | Per-city scrape, annual cadence |
| Restaurant association rosters | Members of NYC Hospitality Alliance, GSRA, etc. | Web scrape |
| OpenTable + Resy + Tock new-listing feeds | New restaurants added weekly | Apify actors |

**Quality bar at the volume stage:** lower. The point is comprehensive enumeration. Filtering for tier-fit happens downstream via enrichment + scoring.

**Output target:** 15,000–20,000 new+refreshed mid-tier candidates per quarter, with enrichment + dedup against existing pipeline.

### Curation motion (T1 + upper T2)

**Goal:** surface the operators most likely to convert at $30K+ AGMV. Narrow, high-signal, multi-source.

**Channels (already running):**

| Channel | Status | Notes |
|---|---|---|
| Beli app scraping | ✅ Running | Active user-curated lists; refresh weekly |
| Instagram hashtags + keyword discovery | ✅ Running | Direct discovery via captions/hashtags |
| Lookalike v3 (LLM brand-profile + Sonnet judging) | ✅ Running | 100 prospects per source partner, balanced assignment |

**Channels to add (innovative):**

| Channel | Why it surfaces T1 | Tool stack |
|---|---|---|
| **Competitor & adjacent software case studies** | Toast/Square/BentoBox/Resy/Tock publish customer logos — operators who already opted into recurring revenue tools | Serper site: queries + web_fetch |
| **WineSearcher merchant directory** | Most complete wine-retailer enumeration in existence (~5K) | Apify + per-state pagination |
| **Awards / Best-of (deterministic ingest)** | Beard semifinalists, Good Food Awards, Wine Spectator, Resy Class of, Eater 38 per city | Annual scraper per list |
| **Chef-LinkedIn job-change monitoring** | "Chef X just left [restaurant] to open [new venture]" — 6–12 months ahead of SEO | Serper news + LinkedIn Sales Nav |
| **Pop-up / supper-club / ticketed-event operators** | Tock/Resy filtered for ticketed dinners — already monetizing scarce prepaid experiences (most ICP-shaped behavior we can detect) | Apify Tock + Resy actors |
| **Press archive deep-dive (10-year)** | NYT/LA Times/SF Chronicle/regional Eaters — established operators whose press is old | Serper site: with date filters |
| **Reddit city-subreddit recommendation threads** | /r/AskNYC etc. "best [vertical] in [city]" — dense crowdsourced ground-truth | Reddit API + Apify Reddit scraper |
| **Chef collective / association rosters** | JBF members, Slow Food chapters, Cherry Bombe network | Web fetch per directory |
| **Geographic proximity to existing customers** | High-density neighborhoods around current T1 partners cluster peers | Serper Maps with radius |
| **Food-critic / blogger personal lists** | Higher curation than published awards (e.g., Helen Rosner, Pete Wells annotated lists) | Serper + web_fetch |
| **Distributor / specialty purveyor customer logos** | Baldor, Bowery Provisions, regional purveyors brag about customers | Web fetch per supplier |
| **LLM-generated city lists with verification** | Claude/web-search enumerates "30 most respected [vertical] in [city]" with surprising recall | Anthropic API + Serper verify |

**Quality bar at the curation stage:** high. Each row should have at least 2 corroborating signals (e.g., press + reservation difficulty + ICP-aligned cuisine) before entering BDR books.

**Output target:** 800–1,500 net-new curated leads per quarter.

---

## Section 4 — AI GTM tools (force-multipliers, not channels)

These sit *on top of* both motions. They don't generate leads from scratch — they make either motion more effective.

| Tool | Best use in this strategy |
|---|---|
| **Clay** | Strongest fit. Use for: (a) enriching every channel's output with firmographics, social, tech-stack signals; (b) running "find companies like X" off existing T1 partners as a paid lookalike layer parallel to v3; (c) building waterfall enrichment (Apollo → Hunter → Crunchbase) per row. |
| **Instantly** | Outbound sequencing once leads are in BDR books — not lead discovery. Pair with a domain warm-up rotation; use sparingly. |
| **Origami / similar AI prospecting tools** | Test on the curation side — input signal patterns (POS provider, has-club, IG follower band), get back candidate matches. Useful for filling the "competitor case studies" channel quickly without manual scraping. |
| **Apollo / ZoomInfo** | Contact enrichment after company-level discovery. Pair with Clay's waterfalls. |

**Sequencing rule:** never use AI GTM tools as the *primary* discovery layer. Use them to enrich, dedup, route, and contact-find on top of the Volume + Curation outputs. Otherwise you import the same generic firmographic universe every other outbound team in food/bev is also buying.

---

## Section 5 — BDR book composition rule

Every BDR's book at any moment should contain a **calibrated mix**, not a pure tier:

```
Target book mix (per BDR, per week):
  T1 (curated, high-signal):      15-20%  →  ~30-40 accounts
  T2 (curated upper / volume lower): 35-45%  →  ~70-90 accounts
  T3 (volume, mid-signal):        40-50%  →  ~80-100 accounts
```

Why a mix beats a tier-pure book:

| Tier-pure | Failure mode |
|---|---|
| 100% T1 | Reps run out of names in 2-3 weeks. Sit idle waiting for curation. Burn through Beard nominees and stall. |
| 100% T3 | Reps close low-AGMV deals all quarter. Hit logo targets but miss revenue. Demotivating cycle. |
| 100% T2 | Looks balanced but is actually missing both the volume top-up and the anchor-account upside. |

**Refresh cadence:**
- T1 books refreshed every 2 weeks (low volume per refresh, high-effort enrichment per row)
- T2 books refreshed every 2 weeks (mix of curation graduates + volume promotions)
- T3 books refreshed weekly (high volume per refresh, automated enrichment)

**Routing rule:** T1 leads go to senior BDRs; T3 leads to volume-trained BDRs; T2 leads are the proving ground.

---

## Section 6 — What's already done vs what's net-new

### Already running (don't rebuild)

- ✅ Beli app curated lists (curation)
- ✅ Instagram hashtags + keyword discovery (curation, both tiers)
- ✅ Lookalike v3 — LLM brand-profile + Sonnet judging (curation, partner-driven)
- ✅ Awards / Best-of ingest (in flight)
- ✅ Existing clubs scraping
- ✅ Health records / liquor license (partial)
- ✅ Serper / Google Maps city sweeps (volume baseline)
- ✅ Tock + Resy via Apify (curation, pop-up signal)

### Net-new builds (priority order)

| Priority | Channel | Motion | Why now |
|---|---|---|---|
| 1 | Competitor / software case studies | Curation | Highest signal-per-effort; named ICP-shaped operators in public domain |
| 2 | WineSearcher full ingest | Curation (wine) | Near-complete enumeration of wine vertical |
| 3 | Restaurant Week aggregator | Volume | Largest single comprehensive source per metro |
| 4 | SBA loan recipient pipeline | Volume + early-signal | Pre-opening operators no one else catches |
| 5 | Chef-LinkedIn job-change monitoring | Curation | Real-time pre-opening intelligence |
| 6 | Clay enrichment layer on all channels | Force-multiplier | Levels up everything else |
| 7 | Pop-up / supper-club filtered scrape (Tock+Resy ticketed-only) | Curation | Highest behavioral-intent signal |
| 8 | Press archive deep-dive (10-yr horizon) | Curation | Catches established operators v3 misses |
| 9 | Geographic proximity to existing T1s | Curation | Cheap, proven topology of high-AGMV neighborhoods |
| 10 | Reddit city subreddit mining | Curation | Crowdsourced ground-truth, unique recall |

---

## Section 7 — Open questions

1. **Penetration validation.** Bottom-up assumes 1.5% baseline. Worth confirming: of the ~8K T1 universe, do we actually have ~120 partners (i.e., 1.5%)? If actual penetration is 0.5%, true TAM is 3× our bottom-up.
2. **Bakery ceiling.** 15 bakery partners, only 1 at T1. Structural ceiling or wrong profile? 30 minutes with the 14 non-T1 bakery partners would resolve this.
3. **Restaurant Week double-counting.** Restaurant Week directories will overlap heavily with awards + press channels. Need clear dedup logic before volume motion ingests it.
4. **Clay budget cap.** Per-enrichment costs add up fast across volume-tier discovery. Set a hard quarterly ceiling before integrating Clay broadly.
5. **T3 → T2 promotion path.** Once a T3 partner shows growth, who moves the account into a curated book? Pipeline mechanic, not a lead-list question, but the strategy depends on it working.

---

## Appendix — Code & data sources

- TAM build script: [`tam_calc.py`](../tam_calc.py) — reproducible top-down + bottom-up + triangulation
- Partner data input: `Past and Existing Partners - Monthly Website Visits - T22_final_list-Default-view-export-1770858132947 (1).csv` (593 rows, 591 with AGMV)
- Visual plan: [`lead-discovery-plan.html`](../lead-discovery-plan.html)
- Adjacent project: `lookalike-icps/lookalike_v3/` (Kavir's lookalike pipeline)
