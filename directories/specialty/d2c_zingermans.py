"""
Zingerman's Mail Order — partner brand catalog. Each catalog entry names the
small producer + city + state.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.zingermans.com/our-partners/",
    "https://www.zingermans.com/about-us/our-friends/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="zingermans",
        importer_name="Zingerman's Mail Order",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="specialty",
        source_prefix="d2c",
        distinction_label="Zingerman's partner brand",
        hint=(
            "Zingerman's partner-producer page. Lists US artisan food makers — "
            "bakeries, charcuterie, cheese, condiments, sweets. Use product or "
            "blurb to set category appropriately ('shop' for retail-style "
            "producers, leave as 'unknown' if unclear)."
        ),
    )
