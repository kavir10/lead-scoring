# Docs index

Everything in this folder is **background reading** — strategy, qualification
rules, run history, and reference material. To actually *run* the tools, start
with the top-level [`README.md`](../README.md).

## Start here

| If you want to… | Read |
|-----------------|------|
| Understand who counts as a good lead (the ICP) | [`ICP.md`](ICP.md) — Table22 ICP & lead-qualification guide |
| See the overall lead-sourcing strategy | [`LEAD_LIST_STRATEGY.md`](LEAD_LIST_STRATEGY.md), or the visual [`lead-discovery-plan.html`](lead-discovery-plan.html) (open in a browser) |
| Know what's broken / fragile before trusting output | [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) |
| Browse the awards source catalog | [`AWARDS.md`](AWARDS.md) |

## Reference

- **[`ICP.md`](ICP.md)** — the definitive ideal-customer-profile and
  qualification rules used across pipelines. The longest and most important
  strategy doc.
- **[`AWARDS.md`](AWARDS.md)** — catalog of award/editorial sources, their
  tiers, and extraction modes. *(Note: its per-source "Strategy" column is
  partly stale — see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md); the code registry
  `awards/__init__.py:ALL_SOURCES` is authoritative.)*
- **[`INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md`](INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md)**
  — brainstorm of lead-signal ideas. Expanded, one-per-file, under
  [`strategies/innovative/`](strategies/innovative/) (52 ideas, e.g. "existing
  club transition", "sold-out demand signals", "worth-the-drive").
- **[`lead-discovery-plan.html`](lead-discovery-plan.html)** — a designed,
  browser-viewable strategy briefing.

## "Wave 2" curation channels

Eight alternative discovery channels, each with a one-page strategy doc. Some
are implemented as experimental scrapers (see the matching code area and
[`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)):

| Doc | Channel | Code |
|-----|---------|------|
| [`strategies/01_somm_chef_ig_graph.md`](strategies/01_somm_chef_ig_graph.md) | Sommelier/chef IG graph | `social_graph/`, `discover_ig_graph.py` |
| [`strategies/02_food_job_boards.md`](strategies/02_food_job_boards.md) | Food job-board employers | `jobs/`, `discover_jobs.py` |
| [`strategies/03_somm_credentialing.md`](strategies/03_somm_credentialing.md) | Sommelier credential lists | `directories/` (`somm_*`) |
| [`strategies/04_d2c_marketplaces.md`](strategies/04_d2c_marketplaces.md) | D2C food marketplaces | `directories/` (`d2c_*`) |
| [`strategies/05_reservation_impossible.md`](strategies/05_reservation_impossible.md) | Reservation-impossible venues | `scarcity/` |
| [`strategies/06_substack_food_writers.md`](strategies/06_substack_food_writers.md) | Substack food writers | `directories/` (`substack_*`) |
| [`strategies/07_cookbook_author_restaurants.md`](strategies/07_cookbook_author_restaurants.md) | Cookbook authors → restaurants | `directories/` (`cookbook_authors`) |
| [`strategies/08_specialty_distributor_logos.md`](strategies/08_specialty_distributor_logos.md) | Distributor customer logos | `directories/` (`distributor_*`) |

## Run logs (history, not instructions)

Records of specific past lead-generation runs — useful for reproducing volumes
or understanding a delivered list, not for day-to-day operation.

- [`RESTAURANT_5K_RUN_LOG.md`](RESTAURANT_5K_RUN_LOG.md) — the 5,000-lead
  restaurant run.
- [`WINE_5K_RUN_LOG.md`](WINE_5K_RUN_LOG.md) — the 5,000-lead wine run.
- [`strategies/RUN_LOG_20260525.md`](strategies/RUN_LOG_20260525.md) — the
  "Wave 2" channels run (2026-05-25).
