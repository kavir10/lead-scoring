"""
Heritage Foods USA — heritage-breed meat distributor (Niman alumni founders).
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://heritagefoods.com/pages/restaurants",
    "https://heritagefoods.com/pages/restaurants-and-artisans",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="heritage_foods",
        importer_name="Heritage Foods USA",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Heritage Foods USA restaurant partner list. US restaurants serving "
            "heritage-breed pork, beef, poultry. Mark every entry as "
            "category='restaurant'."
        ),
    )
