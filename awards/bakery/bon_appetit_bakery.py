"""
Bon Appétit — best bakery / pastry features.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("bon appetit best bakeries in america",
     "Bon Appétit best bakeries in America. distinction = 'Bon Appétit Best Bakery'."),
    ("bon appetit best new bakeries",
     "Bon Appétit best new bakeries. distinction = 'Bon Appétit Best New Bakery'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="bon_appetit_bakery",
        tier=1,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        search_domains=["bonappetit.com"],
        distinction_default="Bon Appétit Best Bakery",
    )
