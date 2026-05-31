"""
Jasper Hill Farm — Vermont artisan cheese maker / cellar; major restaurant
supplier.

No public restaurant client list. Mine editorial mentions: Bayley Hazen Blue
on menus, Harbison and Winnimere placements, etc.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="jasper_hill",
        distributor_name="Jasper Hill",
        business_type="restaurant",
        queries=[
            '"Jasper Hill" restaurant cheese menu',
            '"Bayley Hazen" cheese restaurant menu',
            '"Jasper Hill Farm" chef Michelin restaurant',
            '"Harbison cheese" Jasper Hill restaurant',
            '"Jasper Hill" cheese plate restaurant New York Chicago',
        ],
    )
