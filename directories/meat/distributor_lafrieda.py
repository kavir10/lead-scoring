"""
Pat LaFrieda — NYC-area premium beef distributor (steakhouses, burgers).

LaFrieda does not publish a restaurant client list on their public site.
Their clients (Eleven Madison Park, Minetta Tavern, Marea, Shake Shack, etc.)
are surfaced in editorial coverage. We mine those mentions instead.
"""
from __future__ import annotations

import pandas as pd

from directories._editorial_mining import mine_distributor_mentions


def scrape(**_kwargs) -> pd.DataFrame:
    return mine_distributor_mentions(
        distributor_slug="lafrieda",
        distributor_name="Pat LaFrieda",
        queries=[
            '"Pat LaFrieda" restaurant chef beef',
            '"LaFrieda" steakhouse New York burger',
            '"supplied by Pat LaFrieda" restaurant',
            '"LaFrieda" purveyor chef Michelin',
            '"LaFrieda beef" restaurant menu',
        ],
    )
