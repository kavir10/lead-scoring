"""
Forever Cheese — Italian + Spanish cheese importer. Restaurant + retail
customer list.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.forevercheese.com/where-to-find-us/",
    "https://www.forevercheese.com/partners/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="forever_cheese",
        importer_name="Forever Cheese",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Forever Cheese importer customer list. Split cheese shops "
            "(category='shop') from restaurants (category='restaurant'). "
            "Italian/Spanish cheese-focused venues skew toward restaurants and "
            "wine bars."
        ),
    )
