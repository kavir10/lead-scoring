"""
Good Food Awards — all categories.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("good food awards winners list",
     "Good Food Awards winners across all categories. distinction = 'Good Food Award <Category> <Year>'."),
    ("good food awards 2024 winners",
     "Good Food Awards 2024 winners. distinction = 'Good Food Award <Category> 2024'."),
    ("good food awards 2023 winners",
     "Good Food Awards 2023 winners. distinction = 'Good Food Award <Category> 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="good_food_general",
        tier=1,
        business_type="specialty",
        search_queries=SEARCH_QUERIES,
        search_domains=["goodfoodfdn.org", "goodfoodawards.org",
                        "specialtyfood.com"],
        distinction_default="Good Food Award",
    )
