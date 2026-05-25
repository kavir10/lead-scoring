"""
Browne Trading Company — premium caviar & seafood distributor (Portland, ME).

Browne Trading lists no public customer roster. Their clientele (Daniel
Boulud, Eric Ripert, Thomas Keller, Jean-Georges Vongerichten, Le Bernardin,
Per Se) is widely cited in editorial coverage.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="browne_trading",
        distributor_name="Browne Trading",
        queries=[
            '"Browne Trading" restaurant chef caviar',
            '"Browne Trading" Michelin seafood',
            '"Rod Mitchell" "Browne Trading" chef',
            '"Browne Trading" purveyor New York',
            '"Browne Trading" supplied OR serves restaurant',
        ],
    )
