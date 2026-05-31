"""
Murray's Cheese — affineur + national wholesale brand.

The /makers page is mostly marketing + testimonial quotes. The actual
cheesemaker directory is JS-loaded. Pivoting to editorial mining of
"Murray's Cheese" mentions for restaurant customer attribution.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="murrays_cheesemakers",
        distributor_name="Murray's Cheese",
        business_type="restaurant",
        queries=[
            '"Murray\'s Cheese" restaurant cheese plate',
            '"Murray\'s Cheese" chef restaurant menu',
            '"from Murray\'s" cheese restaurant New York',
            '"Murray\'s Cheese" wholesale customer',
            '"Murray\'s" cheese restaurant Greenwich Village',
        ],
    )
