"""
Forever Cheese — Italian + Spanish cheese importer.

Where-to-buy page lists Forever Cheese's retail customers but layout
defeats the stockist LLM parser. Pivoting to editorial mining for
restaurant attributions in food press.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="forever_cheese",
        distributor_name="Forever Cheese",
        queries=[
            '"Forever Cheese" restaurant chef Italian Spanish',
            '"Forever Cheese" Michelin menu',
            '"Forever Cheese" importer restaurant cheese plate',
            '"Forever Cheese" Manchego OR Pecorino restaurant',
            '"Forever Cheese" Murray\'s OR Eataly OR restaurant',
        ],
    )
