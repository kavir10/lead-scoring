"""
Wine Enthusiast Wine Star — Retailer of the Year. Reuses the wine-side scraper
and filters to retailer recognition only.
"""
from __future__ import annotations

import pandas as pd

from awards._lib import to_dataframe
from awards.wine.wine_enthusiast_star import scrape as scrape_we


def scrape(**_kwargs) -> pd.DataFrame:
    df = scrape_we()
    if df.empty:
        return df
    mask = df["distinction"].str.lower().str.contains("retailer", na=False)
    out = df[mask].copy()
    out["source"] = "wine_enthusiast_retailer"
    out["business_type"] = "specialty"
    return out
