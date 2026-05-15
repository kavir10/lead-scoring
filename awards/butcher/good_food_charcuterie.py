"""
Good Food Awards — Charcuterie category. The full winners archive is large;
we focus the LLM on charcuterie/meat winners only.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("good food awards charcuterie winners",
     "Good Food Awards Charcuterie category winners. distinction = 'Good Food Award Charcuterie <Year>'."),
    ("good food awards 2024 charcuterie meat winners",
     "Good Food Awards 2024 charcuterie/meat winners. distinction = 'Good Food Award Charcuterie 2024'."),
    ("good food awards 2023 charcuterie meat winners",
     "Good Food Awards 2023 charcuterie/meat winners. distinction = 'Good Food Award Charcuterie 2023'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="good_food_charcuterie",
        tier=1,
        business_type="butcher",
        search_queries=SEARCH_QUERIES,
        search_domains=["goodfoodfdn.org", "goodfoodawards.org",
                        "specialtyfood.com", "ediblecommunities.com"],
        distinction_default="Good Food Award Charcuterie",
    )
