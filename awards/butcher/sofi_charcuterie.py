"""
sofi Awards — Charcuterie / Meat categories.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("sofi awards winners charcuterie meat",
     "sofi Awards charcuterie / cured meat / sausage winners. distinction = 'sofi Award <Category> <Year>'."),
    ("specialty food association sofi charcuterie meat winner",
     "SFA sofi awards meat-product category winners. distinction = 'sofi Award <Category> <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="sofi_charcuterie",
        tier=2,
        business_type="butcher",
        search_queries=SEARCH_QUERIES,
        search_domains=["specialtyfood.com"],
        distinction_default="sofi Award Charcuterie",
    )
