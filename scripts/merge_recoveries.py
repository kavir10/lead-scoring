"""
Merge waterfall recoveries into the final Tock/Resy merchant CSVs.
Adds a `recovered_via` column on recovered rows; original fresh-scrape hits
get `recovered_via = "fresh"`.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output/resy_tock_merchants")
RAW = os.path.join(OUT_DIR, "raw")
FRESH = os.path.join(RAW, "scrape_progress.csv")
RECOVERY = os.path.join(RAW, "recovery_progress.csv")
STAMP = datetime.now().strftime("%Y%m%d")


def main():
    fresh = pd.read_csv(FRESH, dtype=str).fillna("")
    fresh = fresh.drop_duplicates(subset=["cid"], keep="last")
    fresh["recovered_via"] = "fresh"
    print(f"Fresh: {len(fresh):,}")

    rec = pd.read_csv(RECOVERY, dtype=str).fillna("")
    rec = rec.drop_duplicates(subset=["cid"], keep="last")
    print(f"Recovery: {len(rec):,}")

    # Recovery rows that actually found something
    rec_hits = rec[(rec["tock_url"] != "") | (rec["resy_url"] != "")].copy()
    print(f"Recovered hits: {len(rec_hits):,}")

    rec_cids = set(rec_hits["cid"])
    # Drop any fresh row whose cid was recovered (avoid double-counting); replace with recovery row
    fresh_keep = fresh[~fresh["cid"].isin(rec_cids)]

    # Align columns
    keep_cols = [
        "cid", "name", "website", "business_type", "city", "state",
        "tock_url", "tock_slug", "tock_embed_only",
        "resy_url", "resy_slug", "resy_embed_only",
        "opentable_url",
        "recovered_via",
    ]
    for col in keep_cols:
        if col not in rec_hits.columns:
            rec_hits[col] = ""
        if col not in fresh_keep.columns:
            fresh_keep[col] = ""

    combined_all = pd.concat([fresh_keep[keep_cols], rec_hits[keep_cols]], ignore_index=True)
    print(f"Combined universe: {len(combined_all):,}")

    has_tock = combined_all["tock_url"] != ""
    has_resy = combined_all["resy_url"] != ""
    has_ot = combined_all["opentable_url"] != ""

    tock = combined_all[has_tock].copy()
    resy = combined_all[has_resy].copy()
    combo = combined_all[has_tock | has_resy].copy()

    tock_path = os.path.join(OUT_DIR, f"tock_merchants_{STAMP}.csv")
    resy_path = os.path.join(OUT_DIR, f"resy_merchants_{STAMP}.csv")
    combo_path = os.path.join(OUT_DIR, f"combined_resy_tock_{STAMP}.csv")

    tock.to_csv(tock_path, index=False)
    resy.to_csv(resy_path, index=False)
    combo.to_csv(combo_path, index=False)

    print(f"\nFINAL OUTPUTS")
    print(f"  Tock:        {len(tock):,}   -> {tock_path}")
    print(f"  Resy:        {len(resy):,}   -> {resy_path}")
    print(f"  Combined:    {len(combo):,}   -> {combo_path}")

    print(f"\nBy recovery source:")
    print(combo["recovered_via"].value_counts().to_string())

    print(f"\nBy business_type:")
    g = combo.assign(
        has_tock=combo["tock_url"] != "",
        has_resy=combo["resy_url"] != ""
    ).groupby("business_type").agg(
        n=("cid", "size"),
        tock=("has_tock", "sum"),
        resy=("has_resy", "sum"),
    )
    print(g.to_string())

    print(f"\nSlug-vs-embed-only:")
    print(f"  Tock with slug: {(combo['tock_slug'] != '').sum():,}")
    print(f"  Tock embed-only: {(combo['tock_embed_only'] == '1').sum():,}")
    print(f"  Resy with slug: {(combo['resy_slug'] != '').sum():,}")
    print(f"  Resy embed-only: {(combo['resy_embed_only'] == '1').sum():,}")


if __name__ == "__main__":
    main()
