"""
Cellars at Jasper Hill — Vermont cheesemaker + national affineur. Their
'Find Our Cheese' or 'Restaurant Partners' page lists US restaurants serving
Jasper Hill cheeses.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.jasperhillfarm.com/find-our-cheese/",
    "https://www.jasperhillfarm.com/restaurants/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="jasper_hill",
        importer_name="Cellars at Jasper Hill",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "Jasper Hill 'where to find our cheese' list. Mix of cheese shops "
            "(category='shop') and restaurants (category='restaurant') — split "
            "them as you go. The page is usually organized by state."
        ),
    )
