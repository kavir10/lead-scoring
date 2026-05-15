"""
NRA FABI Awards — meat / charcuterie subset.

FABI awards recognize products, often supplied by butchers/charcuteries to
restaurants. We keep meat-related winners only.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("fabi awards winners meat charcuterie",
     "NRA FABI Award meat / charcuterie / sausage winners. distinction = 'FABI Award <Year>'."),
    ("national restaurant association fabi award winners list",
     "NRA FABI award winners — keep meat-related products. distinction = 'FABI Award <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="fabi_butcher",
        tier=2,
        business_type="butcher",
        search_queries=SEARCH_QUERIES,
        search_domains=["restaurant.org", "specialtyfood.com",
                        "fooddive.com", "qsrmagazine.com"],
        distinction_default="FABI Award (Meat)",
    )
