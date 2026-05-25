"""
Build the seed CSV for the newsletter/email-list scrape.

Combines the niche-vertical universe (bakeries, butchers, cheese shops,
delis, fish markets, specialty grocers, wine bars, wine stores) and the
restaurant universe into one ~100K-row seed with canonical columns the
async scraper expects.

Output: output/newsletter_merchants/inputs/seed_100k.csv
"""
from __future__ import annotations

import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NICHE = os.path.join(
    ROOT,
    "output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all.csv",
)
RESTS = os.path.join(
    ROOT,
    "output/custom-serper-scoring_kavir_20260402_restaurant_29727_all.csv",
)
OUT = os.path.join(ROOT, "output/newsletter_merchants/inputs/seed_100k.csv")

COLS = ["cid", "name", "address", "phone", "website",
        "city", "state", "business_type", "rating", "review_count"]


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, low_memory=False).fillna("")
    keep = [c for c in COLS if c in df.columns]
    return df[keep].copy()


def main():
    niche = load(NICHE)
    rests = load(RESTS)
    print(f"Niche rows: {len(niche):,}")
    print(f"Restaurant rows: {len(rests):,}")

    df = pd.concat([niche, rests], ignore_index=True)
    print(f"Combined: {len(df):,}")

    df["website"] = df["website"].astype(str).str.strip()
    df = df[df["website"] != ""].copy()
    print(f"With website: {len(df):,}")

    df = df.drop_duplicates(subset=["cid"], keep="first").reset_index(drop=True)
    print(f"After dedupe by cid: {len(df):,}")

    print("\nBusiness-type breakdown:")
    print(df["business_type"].value_counts().to_string())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}  ({len(df):,} rows)")


if __name__ == "__main__":
    main()
