"""
Academy of Cheese — Young Cheesemonger of the Year (UK-led; we extract any
US-based competitors).
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("academy of cheese young cheesemonger of the year united states",
     "Academy of Cheese Young Cheesemonger of the Year — US-based winners/finalists and the cheese shop they work at. distinction = 'Academy of Cheese Young Cheesemonger <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="academy_of_cheese",
        tier=2,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["academyofcheese.org", "culturecheesemag.com",
                        "americancheesesociety.org"],
        distinction_default="Academy of Cheese Young Cheesemonger",
    )
