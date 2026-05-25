"""
Browne Trading Company — Portland ME-based premium seafood distributor.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.brownetrading.com/our-chefs/",
    "https://www.brownetrading.com/restaurants/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="browne_trading",
        importer_name="Browne Trading Company",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Browne Trading Company chef + restaurant customer list. "
            "Predominantly East Coast fine-dining restaurants serving Browne "
            "Trading seafood. Mark all entries as category='restaurant'."
        ),
    )
