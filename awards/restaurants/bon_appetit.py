"""
Bon Appétit — Hot 10 + Best New Restaurants annual lists.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("bon appetit hot 10 best new restaurants 2024",
     "Bon Appétit Hot 10 2024. distinction = 'Bon Appétit Hot 10 2024'."),
    ("bon appetit hot 10 best new restaurants 2023",
     "Bon Appétit Hot 10 2023. distinction = 'Bon Appétit Hot 10 2023'."),
    ("bon appetit best new restaurants 2024",
     "Bon Appétit Best New Restaurants 2024 (broader long list). distinction = 'Bon Appétit Best New 2024'."),
    ("bon appetit best new restaurants 2023",
     "Bon Appétit Best New Restaurants 2023. distinction = 'Bon Appétit Best New 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="bon_appetit",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["bonappetit.com"],
        distinction_default="Bon Appétit Best New",
    )
