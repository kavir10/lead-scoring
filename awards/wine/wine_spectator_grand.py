"""
Wine Spectator Grand Awards — applies to *retail* wine programs at restaurants
in our restaurants module, but Wine Spectator also publishes a separate public
"Top Wine Retailers" piece. This module captures the retailer-side recognition.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("wine spectator grand award winners list",
     "Wine Spectator Grand Award winners — US restaurants/retailers with the most ambitious wine programs. distinction = 'Wine Spectator Grand Award' + year."),
    ("wine spectator grand award retailer wine merchant",
     "Wine Spectator Grand Award retail recipients. distinction = 'Wine Spectator Grand Award (Retailer)'."),
]


def scrape(*, cookies=None, **_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="wine_spectator_grand",
        tier=1,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["winespectator.com", "robbreport.com", "winemag.com"],
        distinction_default="Wine Spectator Grand Award",
    )
