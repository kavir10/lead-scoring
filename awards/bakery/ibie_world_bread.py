"""
IBIE World Bread Awards USA — annual results page.

The site historically lists Bronze/Silver/Gold/Platinum winners by category,
identified by bakery name and city. We try to scrape the results page directly
via Playwright and fall back to LLM extraction.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("world bread awards usa winners results",
     "IBIE World Bread Awards USA winners. distinction = 'World Bread Award <Level>: <Category> <Year>'. Bakery name + city + state."),
    ("ibie world bread awards usa gold silver",
     "IBIE World Bread Awards USA medal recipients. distinction = 'World Bread Award <Level> <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="ibie_world_bread",
        tier=2,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        search_domains=["worldbreadawards.com", "ibie.com", "bakemag.com",
                        "kingarthurbaking.com"],
        distinction_default="World Bread Award (USA)",
    )
