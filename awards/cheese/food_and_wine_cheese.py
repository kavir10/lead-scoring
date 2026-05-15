"""
Food & Wine — Best Cheese Shops in America.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("food and wine best cheese shops america",
     "F&W best cheese shops in America. distinction = 'F&W Best Cheese Shop in America'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="food_and_wine_cheese",
        tier=1,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["foodandwine.com"],
        distinction_default="F&W Best Cheese Shop",
    )
