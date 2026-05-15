"""
Food & Wine Visionaries / Global Tastemakers — wine-side recognition.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("food and wine global tastemakers wine 2024",
     "F&W Global Tastemakers Wine 2024 — US wine retailers/programs/sommeliers only. distinction = 'F&W Global Tastemakers Wine 2024'."),
    ("food and wine global tastemakers wine 2023",
     "F&W Global Tastemakers Wine 2023. distinction = 'F&W Global Tastemakers Wine 2023'."),
    ("food and wine visionaries award wine",
     "F&W Visionaries / Tastemakers Wine awards. distinction = 'F&W Visionaries Wine'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="food_and_wine_visionaries",
        tier=2,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["foodandwine.com"],
        distinction_default="F&W Global Tastemakers Wine",
    )
