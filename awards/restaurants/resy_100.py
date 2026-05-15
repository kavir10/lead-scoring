"""
Resy 100 — annual list. Resy's own page is JS-heavy and often returns minimal
text. We use search-driven LLM extraction over editorial coverage of the list.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("resy 100 list 2024 hardest reservations",
     "The Resy 100 / Resy Best List 2024 — US-only ranked restaurants. distinction = 'Resy 100 2024'."),
    ("resy 100 list 2023 hardest reservations",
     "The Resy 100 2023. distinction = 'Resy 100 2023'."),
    ("resy best list hardest reservations",
     "Resy hardest reservations / best-list features. distinction = 'Resy 100' + year."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="resy_100",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["resy.com", "eater.com", "bonappetit.com",
                        "foodandwine.com", "thrillist.com", "blog.resy.com"],
        distinction_default="Resy 100",
    )
