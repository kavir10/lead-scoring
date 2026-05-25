"""
Niman Ranch — premium pork, beef, lamb distributor. Restaurant partner list
at /restaurant-partners or /find-niman-ranch.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.nimanranch.com/restaurant-partners/",
    "https://www.nimanranch.com/find-niman-ranch/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="niman_ranch",
        importer_name="Niman Ranch",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Niman Ranch restaurant partner page. Lists US restaurants serving "
            "Niman Ranch pork, beef, or lamb. Mark every entry as "
            "category='restaurant'."
        ),
    )
