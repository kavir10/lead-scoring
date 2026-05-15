"""
Sommeliers Choice Awards — winners directory.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("sommeliers choice awards winners",
     "Sommeliers Choice Awards winners. US winners only — wine retailers, sommeliers, programs. distinction = 'Sommeliers Choice Award' + medal."),
    ("sommeliers choice awards retailer of the year",
     "Sommeliers Choice Retailer of the Year. distinction = 'Sommeliers Choice Retailer of the Year'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="sommeliers_choice",
        tier=2,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["sommelierschoiceawards.com", "beveragetradenetwork.com"],
        distinction_default="Sommeliers Choice Award",
    )
