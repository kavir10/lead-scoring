"""
Non-award lead discovery — directories and stockist-mining sources.

Awards live in `awards/`. This package handles everything else: curated
directories (Raisin natural wine map) and stockist backlink mining (premium
importer/distributor "where to buy" pages).

Every module exposes:

    def scrape(**kwargs) -> pandas.DataFrame

returning rows in the canonical schema defined in `awards._lib.SCHEMA`.
The orchestrator (`discover_directories.py`) iterates `ALL_SOURCES`, calls
each `scrape()`, writes per-source CSVs to `output/directories/`, then unions
them into the master file `output/directories_all_<YYYYMMDD>.csv`.

Adding a source: drop a module in `directories/<category>/`, register here.
Slug must match the filename (without .py).

Coverage notes (sources investigated but not registered):

  - RAW WINE fair pages: rawwine.com publishes only exhibitor lists (growers
    /makers/wineries), not retail bottle-shop partners. Side-event venue
    lists exist on event-flyer PDFs but aren't scrapeable. Skipped.
  - Most regional natural-wine fairs (Brumaire, Hot Brunette, La Dive
    Bouteille US partners, Vella Terra): same problem — exhibitor pages
    are winemakers, not retailers.
  - Stockist mining for: Louis/Dressner, Kermit Lynch, Selection Massale,
    Vom Boden, Rosenthal, T. Edward, Polaner, Skurnik, VOS, Indie Wineries.
    Traditional importers treat retailer lists as proprietary; no public
    "where to buy" pages exist. Re-probe periodically.
"""
from __future__ import annotations

# (slug, category, tier, module_path, business_type, requires_auth)
ALL_SOURCES: list[tuple[str, str, int, str, str, bool]] = [
    # Wine — curated directories
    ("raisin_app",                "wine", 1, "directories.wine.raisin_app",                "wine_store", False),

    # Wine — stockist backlink mining (importer/distributor "where to buy" pages)
    ("stockist_zev_rovine",       "wine", 1, "directories.wine.stockist_zev_rovine",       "wine_store", False),
    ("stockist_jenny_francois",   "wine", 1, "directories.wine.stockist_jenny_francois",   "wine_store", False),

    # Wine — sommelier credentialing rosters (channel 03)
    ("somm_cms_master",           "wine", 1, "directories.wine.somm_credentialing_cms",    "restaurant", False),
    ("somm_guildsomm",            "wine", 1, "directories.wine.somm_credentialing_guildsomm", "restaurant", False),

    # Restaurants — cookbook author bios (channel 07)
    ("cookbook_authors",          "restaurants", 1, "directories.restaurants.cookbook_authors", "restaurant", False),

    # Meat / charcuterie — specialty distributor customer lists (channel 08)
    ("distributor_dartagnan",     "meat", 1, "directories.meat.distributor_dartagnan",     "restaurant", False),
    ("distributor_niman_ranch",   "meat", 1, "directories.meat.distributor_niman_ranch",   "restaurant", False),
    ("distributor_lafrieda",      "meat", 1, "directories.meat.distributor_lafrieda",      "restaurant", False),
    ("distributor_heritage_foods", "meat", 1, "directories.meat.distributor_heritage_foods", "restaurant", False),

    # Cheese — specialty distributor customer lists (channel 08)
    ("distributor_jasper_hill",   "cheese", 1, "directories.cheese.distributor_jasper_hill", "restaurant", False),
    ("distributor_forever_cheese","cheese", 1, "directories.cheese.distributor_forever_cheese", "restaurant", False),

    # Seafood — specialty distributor customer lists (channel 08)
    ("distributor_greenpoint_fish","seafood", 1, "directories.seafood.distributor_greenpoint_fish", "restaurant", False),
    ("distributor_browne_trading", "seafood", 1, "directories.seafood.distributor_browne_trading", "restaurant", False),

    # Specialty / D2C marketplaces (channel 04)
    ("d2c_goldbelly",             "specialty", 1, "directories.specialty.d2c_goldbelly",       "specialty", False),
    ("d2c_williams_sonoma",       "specialty", 1, "directories.specialty.d2c_williams_sonoma", "specialty", False),
    ("d2c_murrays",               "specialty", 1, "directories.specialty.d2c_murrays",         "cheese",    False),
    ("d2c_zingermans",            "specialty", 1, "directories.specialty.d2c_zingermans",      "specialty", False),

    # Restaurants — Substack / paywalled food-writer recommendation lists (channel 06)
    ("substack_alicia_kennedy",   "restaurants", 1, "directories.restaurants.substack_alicia_kennedy",   "restaurant", False),
    ("substack_vittles",          "restaurants", 1, "directories.restaurants.substack_vittles",          "restaurant", False),
    ("substack_adam_reiner",      "restaurants", 1, "directories.restaurants.substack_adam_reiner",      "restaurant", False),
    ("substack_anna_hezel",       "restaurants", 1, "directories.restaurants.substack_anna_hezel",       "restaurant", False),
    ("eater_newsletter",          "restaurants", 1, "directories.restaurants.eater_newsletter",          "restaurant", False),
]


def by_slug(slug: str):
    for row in ALL_SOURCES:
        if row[0] == slug:
            return row
    return None
