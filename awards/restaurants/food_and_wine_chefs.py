"""
Food & Wine — Best New Chefs (annual) and Global Tastemakers.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("food and wine best new chefs 2024",
     "F&W Best New Chefs 2024. For each chef extract their restaurant. distinction = 'F&W Best New Chef 2024'."),
    ("food and wine best new chefs 2023",
     "F&W Best New Chefs 2023. distinction = 'F&W Best New Chef 2023'."),
    ("food and wine global tastemakers restaurants",
     "F&W Global Tastemakers Restaurants — US only. distinction includes 'F&W Global Tastemakers'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="food_and_wine_chefs",
        tier=2,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["foodandwine.com"],
        distinction_default="F&W Best New Chefs",
    )
