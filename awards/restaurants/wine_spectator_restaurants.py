"""
Wine Spectator Restaurant Awards — Award of Excellence / Best of Award /
Grand Award.

The full database (restaurants.winespectator.com) is subscription-walled.
Without cookies we still get the public Grand Award honor roll which lists
the ~100 highest-tier US restaurants for wine programs.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles
from awards._lib import to_dataframe

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("wine spectator grand award restaurants list",
     "Wine Spectator Grand Award restaurants — US restaurants with the most ambitious wine programs. distinction = 'Wine Spectator Grand Award' + year."),
    ("wine spectator best of award of excellence restaurants",
     "Wine Spectator Best of Award of Excellence restaurants. distinction = 'Wine Spectator Best of Award of Excellence' + year."),
]


def scrape(*, cookies=None, **_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="wine_spectator_restaurants",
        tier=3,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["winespectator.com", "robbreport.com"],
        distinction_default="Wine Spectator Restaurant Award",
    )
