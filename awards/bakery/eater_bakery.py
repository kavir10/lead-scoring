"""
Eater — best bakery features (national + city).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("eater best bakeries america",
     "Eater best bakeries in America. distinction = 'Eater Best Bakery'."),
    ("site:ny.eater.com best bakeries",
     "Eater NY best bakeries. distinction = 'Eater Best Bakery NYC'."),
    ("site:la.eater.com best bakeries",
     "Eater LA best bakeries. distinction = 'Eater Best Bakery LA'."),
    ("site:sf.eater.com best bakeries",
     "Eater SF best bakeries. distinction = 'Eater Best Bakery SF'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="eater_bakery",
        tier=1,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        search_domains=["eater.com"],
        distinction_default="Eater Best Bakery",
    )
