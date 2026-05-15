"""
VinePair 50 Best Wine Shops (annual).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("vinepair 50 best wine shops in america",
     "VinePair 50 Best Wine Shops in America. distinction = 'VinePair 50 Best Wine Shop' + year if visible."),
    ("vinepair next wave wine shops",
     "VinePair Next Wave Wine Shops. distinction = 'VinePair Next Wave Wine Shop'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="vinepair_50",
        tier=1,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["vinepair.com"],
        distinction_default="VinePair Best Wine Shops",
    )
