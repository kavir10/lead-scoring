"""
Pat LaFrieda — NYC-area premium beef distributor (steakhouses, burgers).
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.lafrieda.com/restaurants/",
    "https://www.lafrieda.com/where-to-find-us/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="lafrieda",
        importer_name="Pat LaFrieda Meat Purveyors",
        urls=URLS,
        strategy="playwright",  # LaFrieda site is JS-heavy
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Pat LaFrieda restaurant list. Northeast + national steakhouses, "
            "burger spots, fine-dining venues serving LaFrieda beef. Mark every "
            "entry as category='restaurant'."
        ),
    )
