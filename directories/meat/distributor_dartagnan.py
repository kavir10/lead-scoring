"""
D'Artagnan — premium game, duck, and charcuterie distributor.

D'Artagnan's `/chefs/` page is a chef-ambassadors marketing wall, not a
customer list. Pivoting to editorial mining for restaurant attributions.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="dartagnan",
        distributor_name="D'Artagnan",
        queries=[
            '"D\'Artagnan" restaurant chef game duck foie gras',
            '"D\'Artagnan" Michelin menu',
            '"supplied by D\'Artagnan" restaurant',
            '"D\'Artagnan" charcuterie chef',
            '"D\'Artagnan duck" OR "D\'Artagnan foie" restaurant New York Chicago',
        ],
    )
