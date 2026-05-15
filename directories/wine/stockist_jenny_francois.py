"""
Jenny & François Selections (From the Tank) — natural wine importer.

Their `/fromthetank/retailers/` page is a flat list grouped by US state
("ALABAMA", "CALIFORNIA", "NEW YORK", ...). All US, all wine retailers.
"""
from __future__ import annotations

import pandas as pd

from directories._stockists import scrape_stockist_page


URLS = ["https://www.jennyandfrancois.com/fromthetank/retailers/"]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_stockist_page(
        importer_slug="jenny_francois",
        importer_name="Jenny & François Selections",
        urls=URLS,
        strategy="llm",
        tier=1,
        retailers_only=True,
        hint=(
            "This is the Jenny & François 'From the Tank Retailers' page. "
            "Entries are wine shops grouped by US state header (uppercase, e.g. "
            "'ALABAMA', 'NEW YORK', 'CHICAGO'). Treat 'CHICAGO' as Illinois. "
            "All entries are retail wine shops — category='shop'. Use the state "
            "header as the state for every entry beneath it until the next "
            "state header. No city is given; leave city blank."
        ),
    )
