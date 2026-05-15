"""
World of Fine Wine — Best Wine Lists awards. Most recipients are restaurants;
relevant as a wine-program signal. We tag rows business_type='restaurant'
because that's what they actually are, but file the source under wine/.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("world of fine wine best wine lists awards us",
     "World of Fine Wine Best Wine Lists awards — US winners only. distinction = 'WoFW Best Wine List' + year."),
    ("world of fine wine awards 2024 united states",
     "WoFW awards 2024 US restaurants. distinction = 'WoFW Best Wine List 2024'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="world_of_fine_wine",
        tier=2,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["worldoffinewine.com"],
        distinction_default="World of Fine Wine Best Wine List",
    )
