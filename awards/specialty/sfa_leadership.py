"""
Specialty Food Association Leadership Awards.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("specialty food association leadership awards winners",
     "SFA Leadership Awards winners — specialty retailers, producers, makers. distinction = 'SFA Leadership Award <Category> <Year>'."),
    ("specialty food association leadership awards 2024",
     "SFA Leadership Awards 2024. distinction = 'SFA Leadership Award 2024'."),
    ("specialty food association leadership awards 2023",
     "SFA Leadership Awards 2023. distinction = 'SFA Leadership Award 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="sfa_leadership",
        tier=2,
        business_type="specialty",
        search_queries=SEARCH_QUERIES,
        search_domains=["specialtyfood.com"],
        distinction_default="SFA Leadership Award",
    )
