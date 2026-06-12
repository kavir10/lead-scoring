# Agent brief — innovative ICP lead discovery (2026-06-12 run)

Goal: 1,000 qualified US leads per vertical (restaurants, butchers, cheese, bakeries, wine),
built from web research (WebSearch + WebFetch), qualified against `docs/ICP.md`, with the
trigger-based lanes from `docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md`.

## Output contract

Write a CSV (UTF-8, header row, comma-separated, quote fields containing commas) to the
exact path given in your task prompt. Columns, in order:

```
name,city,state,website,vertical,source_strategy,source_url,evidence,date_added
```

- `name` — business name as published.
- `city`, `state` — US city and 2-letter state. US businesses only.
- `website` — if known; else empty. Never fabricate.
- `vertical` — one of `restaurants|butchers|cheese|bakeries|wine`.
- `source_strategy` — the lane that surfaced the lead (e.g. `press_awards_recent_momentum`,
  `existing_club_transition`, `sold_out_demand_signals`, `best_of_city_list`,
  `small_market_local_dominance`, `events_programming`, `natural_wine_map`).
- `source_url` — the URL where you found the business.
- `evidence` — one short sentence quoting/paraphrasing why it qualifies (the award, the
  club, the sold-out language, the press mention). Sales will reference this in outreach.
- `date_added` — `2026-06-12`.

One row per business. Do not duplicate a business you already wrote. Do not invent
businesses — every row must come from a fetched page or search result you actually saw.

## Cross-vertical qualification (from ICP.md)

KEEP: independent or small group (1–3 locations), premium/artisanal positioning,
US-based, currently open.

REJECT always: chains/franchises (10+ locations, or recognizable national brands),
supermarkets/big-box, caterers, ghost kitchens/delivery-only, cocktail bars,
liquor stores, food trucks, "coming soon"/closed businesses, online-only brands with no
physical retail (ButcherBox, Crowd Cow etc.).

## Per-vertical rules

**restaurants** — destination + strong neighborhood full-service only. Positive: Michelin/
Bib Gourmand, James Beard (incl. semifinalists), Eater/Infatuation/Bon Appétit/Resy lists,
hard-to-book language, tasting menu, chef-driven, wine program. Cuisine core fit: Italian,
French, Mediterranean, Middle Eastern/Israeli, farm-to-table American, Thai, steakhouse,
European; emerging: Korean, Japanese, Chinese, Mexican, Vietnamese, Filipino, BBQ, Spanish.
Reject: fast casual/QSR/counter-service, pizza-first, burgers, breakfast/brunch-first,
sweets-only.

**butchers** — whole-animal / nose-to-tail, pasture-raised/heritage sourcing, dry-aging,
in-house charcuterie, butchery classes, supper clubs, and the bullseye: meat share / meat
CSA / butcher subscription. Chef-led or master-butcher-led is Tier 1 language. Reject:
supermarket meat counters, generic meat markets with no curation story, BBQ-first
restaurants, online-only meat delivery. Farms with a real butcher-shop/retail storefront
count; pure farms/ranches with only on-farm pickup are weaker — include only with a real
retail or share program, and say so in evidence. Skip states HI, IN, IA, KS, NV, ND, SD.

**cheese** — independent cut-to-order cheese shops/cheesemongers; curated import+domestic
sourcing, named producers/affineurs, CCP-credentialed mongers, cheese clubs, classes,
wine+cheese bundling. Reject: chains, wholesalers, producers with no retail shop,
commodity sourcing.

**bakeries** — bread-first artisanal (sourdough/naturally leavened, laminated pastry as
complement). Bullseye: bread club / bread share / CSB (community-supported bread) /
subscription, "sells out daily", recent capacity expansion, seasonal preorders
(Thanksgiving pies, holiday, king cake, panettone). Reject: sweets-only (cupcakes/
cookies/cakes-only), breakfast/brunch cafés with incidental baking, donut chains.

**wine** — wine SHOPS, not wine bars. Positive: natural/low-intervention/biodynamic
focus, curated small-grower inventory, respected importers (Skurnik, Louis/Dressner,
Jenny & François, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden,
T. Edward, José Pastor), existing wine club, sommelier/owner prominence, press
(VinePair, Wine Enthusiast, Punch, Food & Wine, local best-of). Reject: liquor stores,
Total Wine/BevMo/Binny's/Spec's-type chains, wineries/vineyards, online-only retail,
wine bars (unless explicit retail-shop hybrid — say so in evidence).

## Method notes

- WebSearch works well. **WebFetch is fully blocked in this environment (403 on
  everything)** — do not waste calls on it. Harvest names from WebSearch result content:
  run several query variations per target list (e.g. `"<list name>" full list`,
  `site-name <city> best <vertical>` , `"<business>" <city>` follow-ups) to pull more
  entries out of snippets.
- High-yield patterns: city "best of" listicles (Eater, Infatuation, local press),
  award lists (James Beard semifinalists by year, Good Food Awards winners), club/share
  language searches (`"wine club" shop <city>`, `"meat CSA" butcher <state>`,
  `"bread subscription" bakery`), directory-style roundups.
- Small markets count: a dominant shop in a small affluent town qualifies even with
  modest metrics (note `small_market_local_dominance`).
- Don't stop at the first page of a listicle — many have 20–40 entries; extract all
  qualifying ones.
