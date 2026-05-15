"""
NRA FABI Awards — full list (food + beverage innovation).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("fabi awards winners list food beverage innovation",
     "NRA FABI Awards winners across all categories. distinction = 'FABI Award <Year>'."),
    ("national restaurant association fabi award 2024 winners",
     "FABI 2024 winners. distinction = 'FABI Award 2024'."),
    ("national restaurant association fabi award 2023 winners",
     "FABI 2023 winners. distinction = 'FABI Award 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="fabi_general",
        tier=2,
        business_type="specialty",
        search_queries=SEARCH_QUERIES,
        search_domains=["restaurant.org", "fooddive.com", "qsrmagazine.com",
                        "specialtyfood.com"],
        distinction_default="FABI Award",
    )
