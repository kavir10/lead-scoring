"""
World's 50 Best Restaurants — global list filtered to US entries.

Uses search-driven LLM extraction; the official site uses heavy JS that
renders cards inconsistently across redesigns.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("world's 50 best restaurants 2024 united states",
     "World's 50 Best Restaurants 2024 — extract ONLY US-based ranked entries. distinction = \"World's 50 Best Restaurants 2024 — #<rank>\"."),
    ("world's 50 best restaurants 2023 united states",
     "World's 50 Best Restaurants 2023 — US entries only. distinction = \"World's 50 Best Restaurants 2023 — #<rank>\"."),
    ("world's 50 best restaurants 51-100 north america",
     "World's 50 Best Restaurants 51-100 list — US entries only. distinction = \"World's 50 Best Restaurants — #<rank>\"."),
    ("north america's 50 best restaurants",
     "North America's 50 Best Restaurants — US-only ranked entries. distinction = \"North America's 50 Best Restaurants — #<rank>\"."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="worlds_50_best",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["theworlds50best.com", "eater.com", "foodandwine.com",
                        "bonappetit.com", "robbreport.com"],
        distinction_default="World's 50 Best Restaurants",
    )
