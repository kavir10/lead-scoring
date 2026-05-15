"""
sofi Awards — full winners list (specialty food, all categories).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("sofi awards winners list specialty food",
     "sofi Awards winners across all categories. distinction = 'sofi Award <Category> <Year>'."),
    ("sofi awards 2024 winners specialty food association",
     "sofi 2024 winners. distinction = 'sofi Award <Category> 2024'."),
    ("sofi awards 2023 winners specialty food association",
     "sofi 2023 winners. distinction = 'sofi Award <Category> 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="sofi_general",
        tier=1,
        business_type="specialty",
        search_queries=SEARCH_QUERIES,
        search_domains=["specialtyfood.com"],
        distinction_default="sofi Award",
    )
