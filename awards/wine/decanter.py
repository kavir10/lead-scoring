"""
Decanter — World Wine Awards retailer categories.

Decanter results pages are gated for full detail but the retailer-of-the-year
announcements are public.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

ARTICLES: list[tuple[str, str]] = [
    ("https://www.decanter.com/decanter-retailer-awards/",
     "Decanter Retailer Awards. Filter to US winners. distinction = 'Decanter Retailer Award' + category."),
]


def scrape(*, cookies=None, **_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="decanter",
        tier=3,
        business_type="wine_store",
        article_urls=ARTICLES,
        distinction_default="Decanter Retailer Award",
    )
