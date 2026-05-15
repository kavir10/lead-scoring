"""
Mondial du Fromage — international cheesemonger competition. We capture
US-based competitors/winners only.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("mondial du fromage american competitor united states",
     "Mondial du Fromage US competitors. The 'name' is the cheese SHOP they work at, not the person. distinction = 'Mondial du Fromage <Placement> <Year>'."),
    ("mondial du fromage usa team finalist",
     "Mondial du Fromage US team / finalists. distinction = 'Mondial du Fromage <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="mondial_du_fromage",
        tier=1,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["culturecheesemag.com", "cheesemongerinvitational.com",
                        "americancheesesociety.org", "eater.com"],
        distinction_default="Mondial du Fromage Competitor",
    )
