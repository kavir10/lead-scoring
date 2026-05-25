# Channel 05 — Reservation-Impossible Permanent Venues

**Motion:** Curation
**Vertical fit:** Destination restaurants, wine bars, neighborhood
restaurants (upper-tier)
**Status:** Not yet built (extends existing infrastructure)
**Owner:** TBD
**Cost target:** ≤ $30/run

## Premise

Strategy doc Wave 1 #7 covers **ticketed pop-up / supper-club** scraping —
that's the *novelty / unique-experience* cohort.

This channel is its **permanent-restaurant counterpart**: established
restaurants where reservations have **zero availability across all common
party sizes for 30+ days forward**. These are demand-saturated brand-rich
operators. Different cohort, different conversation, different motion.

Why this is a strong signal for Table22:

- The venue can't grow on-prem revenue (full).
- Customer demand exceeds capacity → they have a captive base actively
  willing to pay for access.
- A subscription program is the obvious unlock — recurring access for
  superfans without diluting walk-in availability.

## Recipe

Reuse existing Apify hooks from `enrich.py` step 8 (availability) and the
Resy API client. The new logic is the **scan, not the lookup**.

For each booking platform:

1. **Enumerate venues** — start from the existing `output/2_enriched_*.csv`
   universe (we already know which venues are on Resy / Tock / OpenTable
   with platform_id). For venues without platform_id, run Serper Maps with
   `"book" OR "reservations" site:resy.com OR site:exploretock.com OR
   site:opentable.com` to discover.
2. **Probe availability matrix** — for each venue, fetch availability for:
   - Party sizes: 2, 4
   - Date range: next 30 days
   - Time windows: peak (6:30-8:30pm), off-peak (5:30pm, 9:30pm)
3. **Score scarcity**:

```
scarcity_score = 1 - (open_slots / total_slots_in_grid)
zero_avail_days = count of days with 0 slots at any party size
peak_only_zero_days = count of days where peak is full but off-peak is open
```

4. **Flag venues** where `zero_avail_days >= 21` (of 30) AND `scarcity_score
   >= 0.85`. These are the reservation-impossible cohort.

## Output schema

`output/scarcity/reservation_impossible_<YYYYMMDD>.csv`:

```
source = "reservation_impossible"
tier = 1
business_type = "restaurant"
distinction = "Reservation-impossible (zero avail {N}/30 days, scarcity {S})"
year = <YYYY>
+ extra cols: platform, platform_venue_id, zero_avail_days, scarcity_score,
              peak_only_zero_days, scan_date, party_size_grid
```

## Volume & cost

Enumeration of universe is cheap because we **already have** the venues —
this rides our existing enrichment output.

- Estimated US universe of restaurants on Resy/Tock/OpenTable from our
  pipeline: ~20K
- Apify availability scrape per venue: ~$0.005-0.01
- 20K × $0.008 ≈ **$160 for full universe scan**
- Or limit to "candidates with reservation difficulty > 0.6 already" — drops
  to ~3K venues × $0.008 = **$24**

Recommendation: start with the **already-flagged-difficulty-> 0.6 subset**
to validate signal, then expand if conversion rate justifies.

- **Net-new venues per run (filtered): ~150-300 truly reservation-impossible**
- A meaningful chunk will already be T22 partners. That's fine — flagging
  them as *re-investment opportunities* (upsell to higher tier) is itself
  valuable.

## Refresh cadence

**Monthly.** Demand patterns shift seasonally; an October scarcity venue
may have open Tuesday tables in February.

## Risks

- Resy's reverse-engineered API is fragile (per CLAUDE.md design notes).
  Monitor for breakage; have OpenTable + Tock as fallbacks.
- Some venues block all 30-day-forward reservations as a policy (release
  weekly) — those will look "reservation-impossible" but are actually just
  closed booking windows. **Counter-check**: if `slots_released_per_week` is
  visible, treat that as a separate signal.
- Walk-in-only venues won't be on any platform → invisible to this channel.
  That's fine, they're invisible to our scarcity signal anyway.
- Holiday windows (Nov-Dec) will inflate scarcity broadly. Either run
  outside Nov-Dec, or normalize against same-month-prior-year baseline.

## Repo placement

```
scarcity/
  __init__.py
  reservation_impossible.py    # main scanner
  _availability_lib.py         # wraps existing Resy/Tock/OpenTable hooks
                               # already in enrich.py — refactor target
discover_reservation_impossible.py  # orchestrator
```

Worth refactoring `enrich.py` step 8 to expose the availability functions
as a shared library callable from both `enrich.py` and `scarcity/`. Avoid
duplicating the Resy/Tock auth logic.

## Open questions

1. Should we also flag the **inverse** signal — venues with chronically
   *available* prime tables despite good Google ratings? That's a different
   pitch (we can help you sell out off-peak) but a real signal too.
2. Party size 4 is the canonical "weekend dinner" size. Worth also probing
   party size 6 for big-name destination venues? Diminishing returns
   probably.
3. Cross-check against Google review text mining — venues where reviewers
   complain about reservation difficulty should match the scarcity scan
   independently. Triple-corroboration play.
