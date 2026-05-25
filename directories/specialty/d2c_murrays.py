"""
Murray's Cheese — affineur + retailer with national wholesale partner program.

The Murray's "Cheese 101" / "Our Cheesemakers" pages link to artisan cheese
producers Murray's supports. These are smaller-scale US cheesemakers,
extremely well-aligned ICP for the cheese vertical.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.murrayscheese.com/our-cheesemakers",
    "https://www.murrayscheese.com/cheese-101/cheesemakers",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="murrays_cheesemakers",
        importer_name="Murray's Cheese (cheesemaker partners)",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="cheese",
        source_prefix="d2c",
        distinction_label="Murray's Cheese partner",
        hint=(
            "Murray's Cheese partner-cheesemakers page. Lists US artisan "
            "cheesemakers (producers, not retail). Mark all entries as "
            "category='shop' (will be coerced to business_type='cheese')."
        ),
        keep_categories={"shop", "unknown"},
    )
