"""
Sample leads with detected club/subscription programs, stratified across business
types, for sales-team sanity checking.

Reads the two v2 CSVs (produced by detect_clubs_v2.py), filters to
has_club_final == True, then draws a random sample per business_type.

Usage:
    python sample_clubs_for_sales.py
    python sample_clubs_for_sales.py --per-vertical 50
    python sample_clubs_for_sales.py --total 200
    python sample_clubs_for_sales.py -o output/sales_sample.csv
    python sample_clubs_for_sales.py --seed 7
"""
import argparse
import os
import sys

import pandas as pd


DEFAULT_INPUTS = [
    "output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all_clubs_v2.csv",
    "output/custom-serper-scoring_kavir_20260402_restaurant_29727_all_clubs_v2.csv",
]

SALES_COLUMNS = [
    "name", "business_type", "city", "state",
    "club_type_final", "club_signals_final", "club_url_final",
    "website", "phone",
    "review_count", "rating", "lead_score", "tier",
]


def _as_true(series: pd.Series) -> pd.Series:
    """Return a boolean mask regardless of whether column is bool or string."""
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower() == "true"


def load_clubs(inputs: list[str]) -> pd.DataFrame:
    frames = []
    for p in inputs:
        if not os.path.exists(p):
            print(f"WARN: missing input {p}", file=sys.stderr)
            continue
        df = pd.read_csv(p, low_memory=False)
        if "has_club_final" not in df.columns:
            print(f"ERROR: {p} missing has_club_final. Did you run detect_clubs_v2 + final-column merge?", file=sys.stderr)
            sys.exit(1)
        df = df[_as_true(df["has_club_final"])].copy()
        frames.append(df)
    if not frames:
        print("ERROR: no input files loaded.", file=sys.stderr)
        sys.exit(1)
    return pd.concat(frames, ignore_index=True)


def sample_stratified(df: pd.DataFrame, per_vertical: int | None, total: int | None, seed: int) -> pd.DataFrame:
    verticals = sorted(df["business_type"].dropna().unique())
    if not verticals:
        print("ERROR: no business_type values found.", file=sys.stderr)
        sys.exit(1)

    if total is not None:
        per_vertical = max(1, total // len(verticals))

    rows = []
    for v in verticals:
        pool = df[df["business_type"] == v]
        take = min(per_vertical, len(pool))
        rows.append(pool.sample(n=take, random_state=seed))
        print(f"  {v}: pool={len(pool):,}  sampled={take}")
    return pd.concat(rows, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Stratified random sample of detected-club leads for sales review.")
    parser.add_argument("-i", "--inputs", nargs="+", default=DEFAULT_INPUTS,
                        help="Input CSV paths (default: both v2 CSVs)")
    parser.add_argument("-o", "--output", default="output/sales_sample_clubs.csv",
                        help="Output CSV path")
    parser.add_argument("--per-vertical", type=int, default=25,
                        help="Rows per business_type (default: 25)")
    parser.add_argument("--total", type=int, default=None,
                        help="Total rows to sample; divides evenly across verticals. Overrides --per-vertical.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"Loading clubs from {len(args.inputs)} file(s)...")
    clubs = load_clubs(args.inputs)
    print(f"Total club-detected leads: {len(clubs):,}\n")

    print("Sampling per vertical:")
    sample = sample_stratified(clubs, args.per_vertical, args.total, args.seed)

    # Keep only columns sales cares about (in a sensible order)
    keep = [c for c in SALES_COLUMNS if c in sample.columns]
    sample = sample[keep].sort_values("business_type").reset_index(drop=True)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    sample.to_csv(args.output, index=False)
    print(f"\nWrote {len(sample):,} rows to {args.output}")
    print("Columns:", ", ".join(keep))


if __name__ == "__main__":
    main()
