"""
Eater — Restaurant of the Year + national/city "best" lists.

Curated list of article URLs. Add to ARTICLES below as new lists publish.
LLM extracts the named restaurants from each.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("eater best new restaurants america 2024",
     "Eater Best New Restaurants in America 2024. distinction = 'Eater Best New Restaurant 2024'."),
    ("eater best new restaurants america 2023",
     "Eater Best New Restaurants in America 2023. distinction = 'Eater Best New Restaurant 2023'."),
    ("eater restaurant of the year",
     "Eater Restaurant of the Year (national). distinction = 'Eater Restaurant of the Year' plus year."),
    ("site:ny.eater.com best new restaurants",
     "Eater NY Best New Restaurants. distinction includes 'Eater NY Best New' and the year if shown."),
    ("site:la.eater.com best new restaurants",
     "Eater LA Best New Restaurants. distinction = 'Eater LA Best New'."),
    ("site:chicago.eater.com best new restaurants",
     "Eater Chicago Best New Restaurants. distinction = 'Eater Chicago Best New'."),
    ("site:sf.eater.com best new restaurants",
     "Eater SF Bay Area Best New Restaurants. distinction = 'Eater SF Best New'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="eater",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["eater.com"],
        search_keyword_block=["michelin", "stars-of"],
        distinction_default="Eater Best New Restaurant",
    )
