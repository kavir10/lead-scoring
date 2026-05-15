"""
James Beard bakery/pastry recognition — Outstanding Bakery, Outstanding Baker,
Outstanding Pastry Chef.

We re-run the JBF scraper but filter the results by category. Cheaper than
maintaining a second source.
"""
from __future__ import annotations

import pandas as pd

from awards._lib import to_dataframe
from awards.restaurants.james_beard import scrape as scrape_jbf

KEEP = ("bakery", "baker", "pastry")


def scrape(**_kwargs) -> pd.DataFrame:
    df = scrape_jbf()
    if df.empty:
        return df
    mask = df["distinction"].str.lower().str.contains("|".join(KEEP), regex=True, na=False)
    out = df[mask].copy()
    out["source"] = "jbf_bakery"
    out["business_type"] = "bakery"
    return out
