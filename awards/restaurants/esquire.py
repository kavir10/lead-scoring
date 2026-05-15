"""
Esquire — Best New Restaurants in America (annual feature).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("esquire best new restaurants 2024",
     "Esquire Best New Restaurants 2024. distinction = 'Esquire Best New 2024'."),
    ("esquire best new restaurants 2023",
     "Esquire Best New Restaurants 2023. distinction = 'Esquire Best New 2023'."),
    ("esquire best new restaurants 2022",
     "Esquire Best New Restaurants 2022. distinction = 'Esquire Best New 2022'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="esquire",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["esquire.com"],
        distinction_default="Esquire Best New Restaurant",
    )
