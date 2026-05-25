"""
D'Artagnan — premium game, duck, and charcuterie distributor.

The "Where to Dine" / "On the Menu" pages list restaurants serving D'Artagnan
products. Any restaurant on this list is by definition meat-program-serious
and well within ICP.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = [
    "https://www.dartagnan.com/where-to-dine.html",
    "https://www.dartagnan.com/on-the-menu/",
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="dartagnan",
        importer_name="D'Artagnan",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=False,
        business_type_default="restaurant",
        source_prefix="distributor",
        distinction_label="Customer of",
        hint=(
            "This is the D'Artagnan 'Where to Dine' page. It lists US restaurants "
            "that serve D'Artagnan game, duck, foie gras, charcuterie, or specialty "
            "meat products. Every entry should be category='restaurant'. The page "
            "is usually organized by city or state — use those headers as the city "
            "/state hint for individual entries."
        ),
    )
