"""
Apply subagent verdicts on the 7 edge-case chains to the cleaned sales list.

Input:  output/clubs_sales_ready_combined_<date>_cleaned.csv
Output: output/clubs_sales_ready_combined_<date>_final.csv
        output/clubs_cleaning_removed_<date>_pass2.csv
        output/clubs_verdicts_applied_<date>.txt

Verdicts:
  DROP_ALL:            New York Butcher Shoppe, Von Hanson's Meats
  KEEP_FLAGSHIP_ONLY:  Levain Bakery -> keep NYC row with highest review_count
                       McClain Cellars -> keep Solvang row
  KEEP_ALL (no-op):    Flour Bakery + Cafe, vinodivino, Mermaid Winery & Restaurant
"""
import os
import sys
from datetime import date
import pandas as pd


STAMP = date.today().strftime("%Y%m%d")
SOURCE = f"output/clubs_sales_ready_combined_{STAMP}_cleaned.csv"
OUT_FINAL = f"output/clubs_sales_ready_combined_{STAMP}_final.csv"
OUT_REMOVED = f"output/clubs_cleaning_removed_{STAMP}_pass2.csv"
OUT_REPORT = f"output/clubs_verdicts_applied_{STAMP}.txt"

DROP_ALL = {
    "New York Butcher Shoppe",
    "Von Hanson's Meats",
}


def keep_levain_flagship(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["name"] == "Levain Bakery"
    all_levain = df[mask].copy()
    nyc = all_levain[all_levain["city"].astype(str).str.strip().isin(
        {"New York", "New York City", "NYC", "Manhattan", "Brooklyn"}
    )]
    if len(nyc) == 0:
        nyc = all_levain
    keep = nyc.sort_values("review_count", ascending=False).head(1)
    remove = all_levain[~all_levain.index.isin(keep.index)]
    kept_df = df[~mask].copy()
    kept_df = pd.concat([kept_df, keep], ignore_index=False)
    return kept_df, remove


def keep_mcclain_flagship(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["name"] == "McClain Cellars"
    all_mcc = df[mask].copy()
    solvang = all_mcc[all_mcc["city"].astype(str).str.strip().str.lower() == "solvang"]
    if len(solvang) == 0:
        solvang = all_mcc.sort_values("review_count", ascending=False).head(1)
    else:
        solvang = solvang.sort_values("review_count", ascending=False).head(1)
    remove = all_mcc[~all_mcc.index.isin(solvang.index)]
    kept_df = df[~mask].copy()
    kept_df = pd.concat([kept_df, solvang], ignore_index=False)
    return kept_df, remove


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(SOURCE, dtype={"cid": str})
    n0 = len(df)
    print(f"Loaded {n0:,} rows from {SOURCE}")

    removed_log = []
    lines = [f"Verdict application — {STAMP}", "=" * 60, f"Starting rows: {n0:,}", ""]

    # DROP_ALL
    drop_mask = df["name"].isin(DROP_ALL)
    dropped = df[drop_mask]
    lines += ["[DROP_ALL]"]
    for name, n in dropped["name"].value_counts().items():
        lines += [f"  {n}\t{name}"]
    lines += [f"  Total removed: {len(dropped):,}", ""]
    removed_log.append(dropped.assign(_removed_reason="franchise_drop"))
    df = df[~drop_mask]
    print(f"DROP_ALL: removed {len(dropped)}  -> {len(df):,}")

    # KEEP_FLAGSHIP_ONLY — Levain
    df, levain_removed = keep_levain_flagship(df)
    lines += ["[KEEP_FLAGSHIP_ONLY] Levain Bakery"]
    if len(levain_removed):
        kept_row = df[df["name"] == "Levain Bakery"].iloc[0]
        lines += [f"  Kept: {kept_row['name']} ({kept_row['city']}, review_count={kept_row['review_count']:.0f})"]
        lines += [f"  Removed {len(levain_removed)} satellite rows:"]
        for _, r in levain_removed.iterrows():
            lines += [f"    - {r['city']}, {r.get('state','')}"]
    else:
        lines += ["  No rows found."]
    lines += [""]
    removed_log.append(levain_removed.assign(_removed_reason="levain_satellite"))
    print(f"Levain: kept 1, removed {len(levain_removed)}  -> {len(df):,}")

    # KEEP_FLAGSHIP_ONLY — McClain
    df, mcc_removed = keep_mcclain_flagship(df)
    lines += ["[KEEP_FLAGSHIP_ONLY] McClain Cellars"]
    if len(mcc_removed):
        kept_row = df[df["name"] == "McClain Cellars"].iloc[0]
        lines += [f"  Kept: {kept_row['name']} ({kept_row['city']}, review_count={kept_row['review_count']:.0f})"]
        lines += [f"  Removed {len(mcc_removed)} satellite rows:"]
        for _, r in mcc_removed.iterrows():
            lines += [f"    - {r['city']}, {r.get('state','')}"]
    else:
        lines += ["  No rows found."]
    lines += [""]
    removed_log.append(mcc_removed.assign(_removed_reason="mcclain_satellite"))
    print(f"McClain: kept 1, removed {len(mcc_removed)}  -> {len(df):,}")

    lines += ["[KEEP_ALL no-op]"]
    for name in ["Flour Bakery + Cafe", "vinodivino", "Mermaid Winery & Restaurant"]:
        n = (df["name"] == name).sum()
        lines += [f"  {n}\t{name}"]
    lines += [""]

    df = df.sort_values("lead_score", ascending=False, na_position="last")
    df.to_csv(OUT_FINAL, index=False)
    print(f"\nFinal: {OUT_FINAL}  ({len(df):,} rows)")
    lines += [f"Final rows: {len(df):,}", f"Path: {OUT_FINAL}", ""]

    lines += ["business_type_v2 distribution:"]
    for k, v in df["business_type_v2"].value_counts().items():
        lines += [f"  {k}: {v:,}"]
    lines += ["", "partner_type distribution:"]
    for k, v in df["partner_type"].value_counts().items():
        lines += [f"  {k}: {v:,}"]

    all_removed = pd.concat(removed_log, ignore_index=True) if removed_log else pd.DataFrame()
    if len(all_removed):
        all_removed.to_csv(OUT_REMOVED, index=False)
        print(f"Removed-rows log: {OUT_REMOVED} ({len(all_removed):,} rows)")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"Report: {OUT_REPORT}")


if __name__ == "__main__":
    main()
