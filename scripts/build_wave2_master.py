"""
Build the unified Wave 2 master CSV.

Wave 2 = the 8 net-new curation channels added 2026-05-25:

  Channel 01 IG seed-graph        -> output/social_graph/somm_chef_ig_graph_<stamp>.csv
  Channel 02 Job boards           -> output/jobs/job_*_<stamp>.csv
  Channel 03 Sommelier credentialing -> output/directories/somm_*_<stamp>.csv
  Channel 04 D2C marketplaces     -> output/directories/d2c_*_<stamp>.csv
  Channel 05 Reservation-impossible -> output/scarcity/reservation_impossible_<stamp>.csv
  Channel 06 Substack writers     -> output/directories/substack_*_<stamp>.csv + eater_*_<stamp>.csv
  Channel 07 Cookbook authors     -> output/directories/cookbook_authors_<stamp>.csv
  Channel 08 Distributor customers-> output/directories/distributor_*_<stamp>.csv

Unifies into output/wave2_master_<stamp>.csv with `channel` column and dedupe
by (name lower, city lower, state lower). One row per dedup-key with all
contributing sources comma-joined.

Usage:
    python scripts/build_wave2_master.py
    python scripts/build_wave2_master.py --stamp 20260525
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


# (channel_id, channel_name, glob_pattern_under_output)
SOURCES = [
    ("01", "ig_seed_graph",          "social_graph/somm_chef_ig_graph_*.csv"),
    ("02", "job_boards",             "jobs/job_*_*.csv"),
    ("03", "somm_credentialing",     "directories/somm_*_*.csv"),
    ("04", "d2c_marketplaces",       "directories/d2c_*_*.csv"),
    ("05", "reservation_impossible", "scarcity/reservation_impossible_*.csv"),
    ("06", "substack_writers",       "directories/substack_*_*.csv"),
    ("06", "substack_writers",       "directories/eater_*_*.csv"),
    ("07", "cookbook_authors",       "directories/cookbook_authors_*.csv"),
    ("08", "distributor_customers",  "directories/distributor_*_*.csv"),
]


def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _latest_for_pattern(pattern: str, stamp: str | None) -> list[Path]:
    files = sorted(OUT.glob(pattern))
    if not files:
        return []
    if stamp:
        files = [f for f in files if stamp in f.name]
    return files


def _load_source(p: Path, channel_id: str, channel_name: str) -> pd.DataFrame:
    df = pd.read_csv(p, dtype=str).fillna("")
    if df.empty:
        return df
    df["channel"] = channel_name
    df["channel_id"] = channel_id
    df["source_file"] = p.name
    return df


def build(stamp: str | None = None) -> Path:
    rows: list[pd.DataFrame] = []
    for cid, name, pattern in SOURCES:
        files = _latest_for_pattern(pattern, stamp)
        for f in files:
            try:
                df = _load_source(f, cid, name)
            except Exception as e:
                print(f"  [wave2] skip {f.name}: {e}")
                continue
            if df.empty:
                continue
            print(f"  [wave2] {name:24} {f.name:50} +{len(df)}")
            rows.append(df)

    if not rows:
        print("  [wave2] no sources found — did Wave 2 runs complete?")
        return Path()

    big = pd.concat(rows, ignore_index=True)
    big["name_key"] = big["name"].apply(_norm)
    big["city_key"] = big["city"].apply(_norm)
    big["state_key"] = big["state"].apply(_norm)

    big = big[big["name_key"] != ""].copy()
    print(f"  [wave2] union raw: {len(big)} rows")

    # Group by (name, city, state) — stack all sources per venue
    agg = (
        big.groupby(["name_key", "city_key", "state_key"], dropna=False)
        .agg(
            name=("name", "first"),
            city=("city", "first"),
            state=("state", "first"),
            country=("country", "first"),
            business_type=("business_type", "first"),
            tier=("tier", "min"),
            n_sources=("source", "nunique"),
            sources=("source", lambda s: ", ".join(sorted(set(s)))),
            channels=("channel", lambda s: ", ".join(sorted(set(s)))),
            distinctions=("distinction", lambda s: " | ".join(d for d in s if d)),
            blurbs=("blurb", lambda s: " || ".join(b for b in s if b)),
            source_urls=("source_url", lambda s: ", ".join(u for u in s if u)),
        )
        .reset_index(drop=True)
        .sort_values(["n_sources", "business_type"], ascending=[False, True])
    )

    stamp = stamp or datetime.now().strftime("%Y%m%d")
    out_path = OUT / f"wave2_master_{stamp}.csv"
    agg.to_csv(out_path, index=False)

    print(f"  [wave2] unique venues: {len(agg)}")
    print(f"  [wave2] venues w/ 2+ sources: {(agg['n_sources'] >= 2).sum()}")
    print(f"  [wave2] saved -> {out_path}")
    print("\nTop business_type counts:")
    print(agg["business_type"].value_counts().head(10).to_string())
    print("\nTop channel mixes:")
    print(agg["channels"].value_counts().head(10).to_string())
    return out_path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stamp", help="YYYYMMDD filter — only include files matching this stamp")
    args = p.parse_args()
    build(stamp=args.stamp)


if __name__ == "__main__":
    main()
