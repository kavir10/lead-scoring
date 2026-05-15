"""
Michelin Grape — wine-program recognition layered on top of starred restaurants.

We don't scrape this independently; the existing Michelin direct scraper
already captures wine-program data. Here we just re-emit any rows where the
cooking_type/blurb suggests a wine focus, retyped as wine_store leads. Until
we extend `discover_michelin_direct.py` to capture Grape directly, this module
is a stub returning an empty frame.
"""
from __future__ import annotations

import pandas as pd

from awards._lib import to_dataframe


def scrape(**_kwargs) -> pd.DataFrame:
    print("  [michelin_grape] stub — extend discover_michelin_direct.py to capture grape distinction", flush=True)
    return to_dataframe([])
