"""
Zev Rovine Selections — natural wine importer/distributor.

Their `/find-our-wines` page is a long flat list organized by region
("Brooklyn & Queens", etc.) with two subsections per region: "Bars &
Restaurants:" and "Retail:". We extract only the retail subsection (wine
shops/bottle shops); restaurants flow into the existing restaurant pipeline
via other channels.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = ["https://www.zrswines.com/find-our-wines"]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="zev_rovine",
        importer_name="Zev Rovine Selections",
        urls=URLS,
        strategy="playwright",
        tier=1,
        retailers_only=True,
        hint=(
            "This is the Zev Rovine Selections 'Find Our Wines' page. The page "
            "is organized by US region (e.g. 'Brooklyn & Queens', 'New Jersey', "
            "'Pennsylvania'). Within each region, there are TWO subsections: "
            "'Bars & Restaurants:' and 'Retail:'. Entries under 'Retail:' are "
            "wine shops — extract those as category='shop'. Entries under 'Bars "
            "& Restaurants:' are restaurants/bars — extract those as "
            "category='restaurant' or 'bar' so they get filtered out. Use the "
            "region header to infer city/state when individual entries don't "
            "name a city. Names may have stray line-breaks mid-word (e.g. "
            "'Ace Hote\\nl') — normalize them."
        ),
    )
