"""
Niman Ranch — premium heritage pork, beef, lamb distributor. No public
restaurant client list resolves (URLs timeout). Pivoting to editorial
mention mining.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="niman_ranch",
        distributor_name="Niman Ranch",
        queries=[
            '"Niman Ranch" restaurant chef pork beef',
            '"Niman Ranch" Michelin menu',
            '"Niman Ranch" supplied OR serves restaurant',
            '"Niman Ranch pork" restaurant',
            '"Niman Ranch lamb" restaurant',
        ],
    )
