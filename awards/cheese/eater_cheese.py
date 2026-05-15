"""
Eater / Serious Eats — national cheese shop lists.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ('"best cheese shops" eater map',
     "Eater best cheese shops MAP article (multiple shops listed in one article). distinction = 'Eater Best Cheese Shop'."),
    ('eater "best cheese shops" new york OR los angeles OR chicago',
     "Eater city best-cheese-shops articles. distinction = 'Eater Best Cheese Shop <City>'."),
    ('"essential cheese shops" eater',
     "Eater essential cheese shop articles. distinction = 'Eater Essential Cheese Shop'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="eater_cheese",
        tier=1,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["eater.com"],
        distinction_default="Eater Best Cheese Shop",
    )
