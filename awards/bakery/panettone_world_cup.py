"""
Panettone World Cup — extract US-based finalists and their bakeries.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("panettone world cup united states finalist bakery",
     "Panettone World Cup / World Championship — US finalists / competitors and their bakeries. distinction = 'Panettone World Cup <Placement> <Year>'."),
    ("panettone world championship american baker",
     "Panettone World Championship US bakers and their bakeries. distinction = 'Panettone World Cup <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="panettone_world_cup",
        tier=2,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        distinction_default="Panettone World Cup Finalist",
    )
