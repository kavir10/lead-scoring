"""
Culture Magazine — features on best cheese shops.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("culture magazine best cheese shops america",
     "Culture Magazine best cheese shops. distinction = 'Culture Magazine Best Cheese Shop'."),
    ("culture magazine cheese shop feature",
     "Culture Magazine featured cheese shops. distinction = 'Culture Magazine Featured Cheese Shop'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="culture_magazine",
        tier=1,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["culturecheesemag.com"],
        distinction_default="Culture Magazine Featured Cheese Shop",
    )
