"""
Food & Wine — best bakery / pastry features.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("food and wine best bakeries in america",
     "F&W best bakeries in America. distinction = 'F&W Best Bakery in America'."),
    ("food and wine best pastry shops in america",
     "F&W best pastry shops. distinction = 'F&W Best Pastry Shop'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="food_and_wine_bakery",
        tier=1,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        search_domains=["foodandwine.com"],
        distinction_default="F&W Best Bakery",
    )
