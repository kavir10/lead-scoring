# Awards & Recognitions Catalog

Reference for the `awards/` discovery package. Every award we pull lead candidates
from is listed here with its tier, business type, source URL, extraction strategy,
auth requirements, and current status.

This file is the source of truth — when adding a new award, append a row here AND
a module under `awards/<category>/<source>.py`.

The Michelin Guide pipeline (`discover_michelin_direct.py`) is kept entirely separate
from this catalog. `awards/restaurants/michelin.py` is a thin wrapper that loads the
most recent `output/michelin_direct_us_*.csv` so Michelin rows show up in the master
union without re-scraping.

---

## Common schema

Every source emits a CSV with these columns:

```
source              # short slug, e.g. "james_beard", "eater_chicago_2024"
tier                # 1 = highest prestige, 2 = strong, 3 = regional/specialised
business_type       # restaurant | wine_store | bakery | cheesemonger | butcher | specialty
name                # business name
city                # city
state               # 2-letter US state when known, else full
country             # us | other
distinction         # e.g. "Outstanding Bakery 2024", "Hot 10 2023", "Bib Gourmand"
year                # award year, when known
source_url          # link to the listing or the business page
blurb               # optional context (review excerpt, citation reason)
```

Per-source CSVs live at `output/awards/<source>_<YYYYMMDD>.csv`.
The combined union lives at `output/awards_all_<YYYYMMDD>.csv`.

## Status legend

- ✅ Working scraper, last run produced rows
- 🟡 Module exists but is best-effort (LLM-driven, may need human QA)
- 🔒 Auth/cookies required — module skeleton only, needs `--cookies-from`
- ⚠️ Source has no clean machine-readable list; LLM extraction over editorial article(s)
- 📌 Stub only — known to exist but not yet implemented

## Extraction modes

Three patterns are used across modules:

1. **Structured Playwright** — paginate a real listing page (Michelin pattern).
2. **Static URL list + LLM** — pass known stable article URLs through Claude.
3. **Serper search + LLM** — for editorial sources where article URLs change
   yearly (Eater best-of, Bon Appétit Hot 10, VinePair 50): the module declares
   search queries + an allowed-domain list, the orchestrator resolves URLs via
   the Serper Web Search API, then LLM-extracts each. Robust to URL churn.

Modules choose mode 2 or 3 (or both) based on which is more durable for that
publication.

---

## Restaurants

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | Michelin Stars 1/2/3 + Bib + Green | `restaurants/michelin.py` | Wraps existing scraper output | `discover_michelin_direct.py` | ✅ | Already shipped — module just loads its CSV |
| 1 | James Beard Awards (restaurant/chef/hospitality) | `restaurants/james_beard.py` | Playwright over `/awards/search` filtered to relevant subcategories | https://www.jamesbeard.org/awards/search | ✅ | Cover semifinalists/finalists/winners back to ~2018 |
| 1 | Eater Restaurant of the Year + city lists | `restaurants/eater.py` | Serper search + LLM | https://www.eater.com/ | ✅ | URLs auto-discovered each run; current run produced 165 rows |
| 1 | Resy 100 | `restaurants/resy_100.py` | HTTP fetch of `/specials/resy-best-list` then HTML parse | https://resy.com/specials/resy-best-list | 🔒 | May 403 — falls back to LLM over snapshot if blocked |
| 1 | Esquire "Best" lists | `restaurants/esquire.py` | LLM extraction of yearly Best New / Best Bars lists | https://www.esquire.com/food-drink/restaurants/ | ⚠️ | |
| 1 | New York Times reviews / lists | `restaurants/nyt.py` | LLM over The Best Restaurants in NYC + critic 4-star reviews | https://www.nytimes.com/ | 🔒 | Paywall — needs cookies |
| 1 | Bon Appétit Best New / Hot 10 | `restaurants/bon_appetit.py` | LLM extraction of yearly Hot 10 + Best New articles | https://www.bonappetit.com/restaurants | ⚠️ | |
| 1 | World's 50 Best Restaurants | `restaurants/worlds_50_best.py` | Playwright scrape of list page, filter `country = United States` | https://www.theworlds50best.com/list/1-50 | ✅ | Also pulls 51-100 extended list |
| 2 | Food & Wine Best New Chefs / Global Tastemakers | `restaurants/food_and_wine_chefs.py` | LLM extraction over yearly archives | https://www.foodandwine.com/ | ⚠️ | |
| 3 | Wine Spectator Restaurant Awards (wine program) | `restaurants/wine_spectator_restaurants.py` | List of award levels (Award of Excellence / Best of Award of Excellence / Grand Award) | https://restaurants.winespectator.com/ | 🔒 | Subscription-walled — currently fetches Grand-Award-only public summary |

## Wine Stores / Retailers

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | Wine Spectator Grand Awards (retail) | `wine/wine_spectator_grand.py` | LLM extraction over public Grand Award announcement | https://www.winespectator.com/articles/grand-award-winners | 🔒 | |
| 1 | Wine Enthusiast Wine Star Awards | `wine/wine_enthusiast_star.py` | Playwright pulls `/awards/wine-star-awards/` retailer category | https://www.wineenthusiast.com/awards/wine-star-awards/ | ✅ | Pull Retailer of the Year + Importer / Distributor where retail-relevant |
| 1 | Wine Enthusiast Best Wine Shops in America | `wine/wine_enthusiast_shops.py` | LLM extraction of yearly listicle | https://www.wineenthusiast.com/culture/wine-shops/ | ⚠️ | |
| 1 | James Beard wine-program recognition | `wine/jbf_wine.py` | Subset of `restaurants/james_beard.py` filter for "Outstanding Wine Program" | (same) | ✅ | Restaurant-typed rows; we re-emit them as wine_store for consideration |
| 1 | Michelin Grape program | `wine/michelin_grape.py` | Reuses `discover_michelin_direct.py` filter (grape distinction) | https://guide.michelin.com/us/en/restaurants/grape | 🟡 | Light extension of existing scraper |
| 1 | VinePair 50 Best Wine Shops | `wine/vinepair_50.py` | LLM extraction over annual feature | https://vinepair.com/ | ⚠️ | |
| 1 | Punch Magazine features | `wine/punch.py` | LLM extraction over relevant feature URLs | https://punchdrink.com/ | ⚠️ | Curated article list per year |
| 2 | World of Fine Wine Best Wine Lists | `wine/world_of_fine_wine.py` | LLM extraction | https://www.worldoffinewine.com/awards/best-of-list/best-wine-lists | ⚠️ | Often restaurant lists — flagged as wine-program signal |
| 2 | Sommeliers Choice Awards | `wine/sommeliers_choice.py` | Playwright over winners directory | https://sommelierschoiceawards.com/winners/ | ✅ | Categories include retailers + importers + sommeliers |
| 2 | Food & Wine Visionaries / Global Tastemakers | `wine/food_and_wine_visionaries.py` | LLM extraction | https://www.foodandwine.com/ | ⚠️ | |
| 3 | Decanter World Wine Awards (retailer) | `wine/decanter.py` | LLM over annual retailer awards page | https://www.decanter.com/ | 🔒 | |
| 3 | "Best of [local area]" recognition | `wine/regional_best_of.py` | LLM over per-city "best wine shop" round-ups | (varies) | 📌 | Generic regional helper — TODO |

## Bakeries

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | James Beard (Outstanding Bakery, Pastry Chef, Outstanding Baker) | `bakery/jbf_bakery.py` | Subset of `restaurants/james_beard.py` filter | (same) | ✅ | |
| 1 | Bon Appétit best bakery lists | `bakery/bon_appetit_bakery.py` | LLM extraction | https://www.bonappetit.com/ | ⚠️ | |
| 1 | Eater best bakery lists | `bakery/eater_bakery.py` | LLM extraction | https://www.eater.com/ | ⚠️ | |
| 1 | Food & Wine best bakery lists | `bakery/food_and_wine_bakery.py` | LLM extraction | https://www.foodandwine.com/ | ⚠️ | |
| 2 | Coupe du Monde de la Boulangerie (US team) | `bakery/coupe_du_monde.py` | LLM over Wikipedia + official site to extract US-team bakers and their bakeries | https://www.coupedumondedelaboulangerie.com/ | 🟡 | Few entries per cycle; high prestige |
| 2 | IBIE World Bread Awards USA | `bakery/ibie_world_bread.py` | Playwright over `/usa-results` | https://www.worldbreadawards.com/usa-results | ✅ | Bronze/Silver/Gold per category |
| 2 | Panettone World Cup (US-based finalists) | `bakery/panettone_world_cup.py` | LLM extraction | https://panettoneworldchampionship.com/ | 📌 | Tiny cohort |
| 3 | Regional bakery recognition | `bakery/regional_best_of.py` | Generic LLM helper | (varies) | 📌 | TODO |

## Cheesemongers / Cheese Retailers

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | Cheesemonger Invitational (CMI) | `cheese/cheesemonger_invitational.py` | Playwright/HTML over winners archive | https://www.cheesemongerinvitational.com/winners | ✅ | Cross-reference to mongers' employer shops |
| 1 | Mondial du Fromage (US competitors) | `cheese/mondial_du_fromage.py` | LLM over Wikipedia + competition reports | https://mondialdufromage.com/ | 🟡 | |
| 1 | Culture Magazine features | `cheese/culture_magazine.py` | LLM extraction over best-cheese-shop articles | https://culturecheesemag.com/ | ⚠️ | |
| 1 | Eater / Serious Eats national cheese lists | `cheese/eater_cheese.py` | LLM extraction | https://www.eater.com/ + seriouseats.com | ⚠️ | |
| 1 | Food & Wine Best Cheese Shops in America | `cheese/food_and_wine_cheese.py` | LLM extraction | https://www.foodandwine.com/ | ⚠️ | |
| 2 | American Cheesemonger Invitational | `cheese/american_cmi.py` | If distinct from CMI; otherwise alias | (TBD) | 📌 | Confirm whether this is the same as CMI under different name |
| 2 | Academy of Cheese — Young Cheesemonger of the Year | `cheese/academy_of_cheese.py` | LLM over award-year announcements | https://academyofcheese.org/ | 📌 | Mostly UK — flag US winners only |
| 3 | Regional cheese shop recognition | `cheese/regional_best_of.py` | Generic LLM helper | (varies) | 📌 | TODO |

## Butchers / Charcuterie

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | American Association of Meat Processors (AAMP) Awards | `butcher/aamp.py` | Playwright over `/cured-meats-championships/results` | https://www.aamp.com/ | ✅ | Annual Cured Meats Championship + Outstanding Specialty Meat Retailer |
| 1 | Good Food Awards (Charcuterie) | `butcher/good_food_charcuterie.py` | Playwright over `/winners/?category=charcuterie` | https://goodfoodfdn.org/awards/winners/ | ✅ | Multi-year archive |
| 2 | sofi Awards (Charcuterie Meats) | `butcher/sofi_charcuterie.py` | Playwright over `/awards/sofi/winners` filtered to meat categories | https://www.specialtyfood.com/sofi/winners/ | ✅ | |
| 2 | FABI Awards (NRA) | `butcher/fabi.py` | LLM extraction over annual FABI list filtered to meat products | https://restaurant.org/events/show/fabi-awards/ | ⚠️ | |
| 3 | Regional butcher / charcuterie recognition | `butcher/regional_best_of.py` | Generic LLM helper | (varies) | 📌 | TODO |

## Specialty Food Retail (general)

| Tier | Source | Module | Strategy | URL | Status | Notes |
|---|---|---|---|---|---|---|
| 1 | sofi Awards | `specialty/sofi.py` | Playwright over `/awards/sofi/winners` (full unfiltered) | https://www.specialtyfood.com/sofi/winners/ | ✅ | Producers > retailers; we keep producer rows because retailers often share owners |
| 1 | Good Food Awards | `specialty/good_food.py` | Playwright over `/winners/` (full unfiltered) | https://goodfoodfdn.org/awards/winners/ | ✅ | |
| 2 | FABI Awards | `specialty/fabi.py` | LLM extraction | https://restaurant.org/events/show/fabi-awards/ | ⚠️ | |
| 2 | Specialty Food Association Leadership Awards | `specialty/sfa_leadership.py` | LLM over annual press release | https://www.specialtyfood.com/news/awards/leadership-awards/ | ⚠️ | |
| 2 | Wine Enthusiast Wine Star — Retailer of the Year | `specialty/wine_enthusiast_retailer.py` | Reuses `wine/wine_enthusiast_star.py` filter | (same) | ✅ | |
| 3 | Regional specialty-food recognition | `specialty/regional_best_of.py` | Generic LLM helper | (varies) | 📌 | TODO |

---

## Running

```bash
source .venv/bin/activate
python discover_awards.py --source james_beard           # one source
python discover_awards.py --category restaurants         # everything in a category
python discover_awards.py --tier 1                       # everything Tier 1
python discover_awards.py --all                          # everything; rebuilds master at end
python discover_awards.py --source nyt --cookies-from cookies/nyt.json   # auth-walled source
```

Outputs:

- `output/awards/<source>_<YYYYMMDD>.csv` — one per source
- `output/awards_all_<YYYYMMDD>.csv` — union with `source` and `tier` columns

## Adding a new award

1. Add a row to the table above with your URL and strategy.
2. Drop a module under `awards/<category>/<source>.py` exposing `def scrape() -> pd.DataFrame`.
3. Register it in `awards/__init__.py::ALL_SOURCES` so the orchestrator picks it up.
4. Run `python discover_awards.py --source <slug>` to verify.

## Known limitations

- Sources marked 🔒 require you to log in once with `--headed` and dump cookies via
  the helper, then pass `--cookies-from <path>`. NYT, Wine Spectator, Decanter all
  use this.
- LLM extraction (⚠️) is best-effort. It can hallucinate, miss businesses, or
  conflate related entries. Spot-check any rows that don't have a `source_url`
  pointing to a specific business.
- Awards from outside the US are filtered to US entries only; international fields
  default to `country = "other"` and are dropped before writing.
- Regional 📌 stubs need URL inputs from a human curator; the generic helper exists
  but the source list doesn't.
