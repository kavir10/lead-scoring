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
]


def by_slug(slug: str):
    for row in ALL_SOURCES:
        if row[0] == slug:
            return row
    return None
