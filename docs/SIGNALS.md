# Signal lanes — trigger-based lead discovery

**Created:** 2026-06-10
**Code:** `signals/` + `discover_signals.py`
**Inputs:** `docs/ICP.md` (what makes a good lead) and
`docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md` (the 52-idea backlog these
lanes were selected from).

## The plan

Every existing pipeline in this repo answers *"is this the right kind of
business?"* (category, award, directory membership). None of them answer
*"is there a reason to contact them **now**?"* — the Trigger Score half of
the ideas doc's four-layer model. These lanes fill that gap: each one
produces a list where every row carries a **named, citable trigger** that
sales can reference in the first line of outreach.

Selection criteria for which of the 52 ideas to build first:

1. **Not already covered.** Hiring intent (`jobs/`), reservation pain
   (`scarcity/`), partner adjacency (`social_graph/`), supplier/importer
   graphs (`directories/`), and club detection on existing lists
   (`postprocess/detect_clubs*.py`) all exist.
2. **Buildable on the APIs already in `.env`** — Serper, Anthropic, plain
   HTTP. No new vendors, no new auth.
3. **Strongest ICP alignment per the SHAP/practitioner reads** — transition
   leads and supply-constrained demand beat everything else.

## Lane catalog

| Lane | Category | Engine | Idea # | ICP rationale |
|---|---|---|---|---|
| `club_transition` | transition | Serper phrases | 1, 18 | Existing clubs are the bullseye: switch-the-platform sale, not cold start. Includes "hidden club" vocabulary (allocation, standing order, monthly pickup). |
| `former_club_recovery` | transition | Serper phrases | 52 | "Club paused / not accepting members" = past belief + operational pain. The page itself is the outbound hook. |
| `manual_preorder` | pain | Serper phrases | 2 | Google Form / DM / email ordering = demand plus a concrete pain Table22 systematizes. |
| `sold_out_demand` | demand | Serper phrases | 3 | "More demand than they can serve" is the model's #1 cross-vertical theme; sold-out language is the cleanest public version of it. |
| `seasonal_preorder` | demand | Serper phrases | 22 | Holiday roasts/turkeys/pies/panettone preorders prove prepaid-packaging muscle. Run 60–90 days before each seasonal window. |
| `press_momentum` | press | Serper News + Claude | 8, 38 | Fresh press (≤30 days) creates a demand spike → operational pressure → buying urgency. The `awards/` pipeline covers evergreen lists; this covers *recency*. |
| `reddit_demand` | community | Reddit JSON + Claude | 43, 44, 16 | Customer language ("always sells out", "worth the drive") catches small-market local dominance that raw metrics miss — and doubles as outbound copy. |

## How the phrase lanes work

All five Serper-phrase lanes share one pipeline (`signals/_lib.py:phrase_lane_scrape`):

1. **Search** — `"<trigger phrase>" <vertical keyword>` against Serper Web
   (optionally `--cities N` to add city-scoped variants).
2. **Platform filter** — drop hits on marketplaces/social/press/ordering
   platforms (`PLATFORM_DOMAINS`); we only want the merchant's own domain.
3. **Domain dedupe** — one candidate per registered domain.
4. **Verify (default on)** — fetch the page, require the trigger phrase (or
   a registered synonym) on-page, extract business name (og:site_name →
   cleaned `<title>`) and city/state (`City, ST 12345` scan). `--no-verify`
   skips this: faster and cheaper, but names come from search titles.
5. **Row filters** — chain names (`CHAIN_KEYWORDS`) dropped; liquor names
   dropped from wine rows.

Output schema = the canonical awards/directories schema **plus**
`trigger`, `evidence_url`, `evidence_snippet` — preserve these through any
downstream cleaning so sales can cite the trigger.

## Usage

```bash
python discover_signals.py --list
python discover_signals.py --source club_transition --dry-run   # print queries, no API calls
python discover_signals.py --source club_transition --limit 30  # capped first run
python discover_signals.py --source sold_out_demand --cities 20 # add city-scoped queries
python discover_signals.py --category transition                # both club lanes
python discover_signals.py --all
python discover_signals.py --master-only
```

Outputs: `output/signals/<slug>_<YYYYMMDD>.csv` per lane,
`output/signals_all_<YYYYMMDD>.csv` master. Master keeps one row per
(lane, name, city) — the same business appearing in several lanes is
signal, not duplication.

## Cost notes

| Lane | Default cost profile |
|---|---|
| phrase lanes | ~20–110 Serper web queries each (national); `--cities N` multiplies by N. Verification is plain HTTP. |
| `press_momentum` | ~9 Serper News queries + ≤45 article fetches, **1 Claude call per article** (`--limit` caps). |
| `reddit_demand` | free Reddit JSON (politeness-throttled) + **1 Claude call per thread**, default cap 40 (`--limit`). |

`SERPER_API_KEY` required for all but `reddit_demand`; `ANTHROPIC_API_KEY`
required for `press_momentum` and `reddit_demand`.

## Suggested post-run flow

1. `python discover_signals.py --all`
2. Feed `output/signals_all_<date>.csv` through
   `postprocess/dedupe_existing.py` against your current master lists to
   isolate net-new leads.
3. Optionally push the net-new file through the generic pipeline
   (`python main.py --enrich ...`) to score them — the trigger columns ride
   along untouched.

## Deferred (and why)

- **Tock/OpenTable Experiences mining (#26)** — both surfaces are JS-heavy
  and WAF/login-gated; needs a dedicated Playwright lane. Revisit if
  transition-lane yield is thin.
- **IG/TikTok "do you ship?" comment mining (#13, #14)** — needs paid Apify
  comment actors at meaningful per-business cost; design the sampling
  strategy before spending.
- **Shopify out-of-stock patterns (#19)** — needs a Shopify-storefront
  detector pass over existing lead CSVs first (postprocess), then JSON
  product-feed polling. Different shape than a discovery lane.
- **Permit/buildout watchlists (#23)** — per-city data sources, no uniform
  API; highest effort-to-coverage ratio of the batch.
