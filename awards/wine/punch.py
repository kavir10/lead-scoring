"""
Punch Magazine — features on wine shops, lists, and notable retailers.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("punch best wine shops america",
     "Punch best wine shops in America. distinction = 'Punch Best Wine Shop'."),
    ("punch natural wine shops new york",
     "Punch NYC natural wine shops. distinction = 'Punch Best Wine Shop NYC'."),
    ("punch best wine shops los angeles",
     "Punch LA wine shops. distinction = 'Punch Best Wine Shop LA'."),
    ("punch best wine shops san francisco",
     "Punch Bay Area wine shops. distinction = 'Punch Best Wine Shop SF'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="punch",
        tier=1,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["punchdrink.com"],
        distinction_default="Punch Best Wine Shop",
    )
