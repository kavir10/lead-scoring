"""
Williams-Sonoma — curated specialty food vendor marketplace.

The W-S marketplace UI is single-page React; vendor brand names are not
extractable from product cards via static HTML. Pivoting to editorial
mining of "Williams-Sonoma" + vendor brand mentions.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="williams_sonoma_marketplace",
        distributor_name="Williams-Sonoma Marketplace",
        business_type="specialty",
        queries=[
            '"Williams-Sonoma" small batch artisan brand',
            '"Williams-Sonoma Marketplace" food vendor',
            '"sold at Williams-Sonoma" food specialty brand',
            '"Williams-Sonoma" food brand owner',
        ],
    )
