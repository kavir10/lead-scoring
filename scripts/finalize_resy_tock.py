"""
Post-process scrape_progress.csv into Tock-only, Resy-only, and combined
final CSVs, plus print summary stats and an April-baseline comparison.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS = os.path.join(ROOT, "output/resy_tock_merchants/raw/scrape_progress.csv")
OUT_DIR = os.path.join(ROOT, "output/resy_tock_merchants")
APRIL_NICHE = os.path.join(ROOT, "output/2_enriched_websites.csv")
APRIL_RESTS = os.path.join(ROOT, "output/2_enriched_websites_restaurants.csv")

STAMP = datetime.now().strftime("%Y%m%d")


def nonempty(s):
    return s.fillna("").astype(str).str.strip().ne("")


def main():
    df = pd.read_csv(PROGRESS, dtype=str).fillna("")
    print(f"Loaded progress (raw): {len(df):,} rows")
    df = df.drop_duplicates(subset=["cid"], keep="last").reset_index(drop=True)
    print(f"After dedupe by cid: {len(df):,} rows")

    has_tock = nonempty(df["tock_url"])
    has_resy = nonempty(df["resy_url"])
    has_ot = nonempty(df["opentable_url"])

    print("\n=== Detection summary ===")
    print(f"  Tock:        {has_tock.sum():,} ({has_tock.mean()*100:.1f}%)")
    print(f"  Tock embed-only:  {(df['tock_embed_only']=='1').sum():,}")
    print(f"  Tock with venue slug: {(has_tock & nonempty(df['tock_slug'])).sum():,}")
    print(f"  Resy:        {has_resy.sum():,} ({has_resy.mean()*100:.1f}%)")
    print(f"  Resy embed-only:  {(df['resy_embed_only']=='1').sum():,}")
    print(f"  Resy with venue slug: {(has_resy & nonempty(df['resy_slug'])).sum():,}")
    print(f"  OpenTable:   {has_ot.sum():,} ({has_ot.mean()*100:.1f}%)")
    print(f"  Both T+R:    {(has_tock & has_resy).sum():,}")
    print(f"  Any platform: {(has_tock | has_resy | has_ot).sum():,}")

    print("\n=== By business_type ===")
    tmp = df.copy()
    tmp["has_tock"] = has_tock
    tmp["has_resy"] = has_resy
    tmp["has_ot"] = has_ot
    g = tmp.groupby("business_type").agg(
        n=("cid", "size"),
        tock=("has_tock", "sum"),
        resy=("has_resy", "sum"),
        opentable=("has_ot", "sum"),
    )
    print(g.to_string())

    print("\n=== Error rates ===")
    status = df["website_status"]
    print(status.value_counts().head(10).to_string())

    tock_df = df[has_tock].copy()
    resy_df = df[has_resy].copy()
    combined = df[has_tock | has_resy].copy()

    tock_path = os.path.join(OUT_DIR, f"tock_merchants_{STAMP}.csv")
    resy_path = os.path.join(OUT_DIR, f"resy_merchants_{STAMP}.csv")
    combo_path = os.path.join(OUT_DIR, f"combined_resy_tock_{STAMP}.csv")

    tock_df.to_csv(tock_path, index=False)
    resy_df.to_csv(resy_path, index=False)
    combined.to_csv(combo_path, index=False)
    print(f"\nWrote:\n  {tock_path}  ({len(tock_df):,})\n  {resy_path}  ({len(resy_df):,})\n  {combo_path}  ({len(combined):,})")

    # April baseline comparison
    print("\n=== April baseline comparison ===")
    try:
        april_n = pd.read_csv(APRIL_NICHE, usecols=["cid", "reservation_url"], dtype=str, low_memory=False).fillna("")
        april_r = pd.read_csv(APRIL_RESTS, usecols=["cid", "reservation_url"], dtype=str, low_memory=False).fillna("")
        april = pd.concat([april_n, april_r], ignore_index=True)
        april_tock = set(april[april["reservation_url"].str.contains("tock", case=False, na=False)]["cid"])
        april_resy = set(april[april["reservation_url"].str.contains("resy", case=False, na=False)]["cid"])

        new_tock = set(tock_df["cid"])
        new_resy = set(resy_df["cid"])

        print(f"  April Tock:  {len(april_tock):,}   New Tock:  {len(new_tock):,}")
        print(f"    overlap:   {len(april_tock & new_tock):,}")
        print(f"    new only:  {len(new_tock - april_tock):,}")
        print(f"    lost:      {len(april_tock - new_tock):,}")
        print(f"  April Resy:  {len(april_resy):,}   New Resy:  {len(new_resy):,}")
        print(f"    overlap:   {len(april_resy & new_resy):,}")
        print(f"    new only:  {len(new_resy - april_resy):,}")
        print(f"    lost:      {len(april_resy - new_resy):,}")
    except Exception as e:
        print(f"  comparison failed: {e}")


if __name__ == "__main__":
    main()
