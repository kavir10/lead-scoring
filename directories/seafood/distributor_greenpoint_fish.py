"""
Greenpoint Fish & Lobster — NYC-area sustainable seafood wholesaler.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://greenpointfish.com/pages/wholesale",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="greenpoint_fish",
        importer_name="Greenpoint Fish & Lobster",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Greenpoint Fish & Lobster wholesale customer list — NYC-area "
            "restaurants serving their seafood. Mark all as "
            "category='restaurant'."
        ),
    )
