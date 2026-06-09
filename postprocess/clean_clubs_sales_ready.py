"""
Data-cleaning pass on output/clubs_sales_ready_combined_<date>.csv:

1. Dedupe by cid (keep the row whose business_type lines up with partner_type;
   tiebreaker = higher lead_score, then first).
2. Drop clear national/franchise chains.
3. Drop bad name-salvages (pet bakery, event venue, grocery chain, caterer).
4. Output a separate edge-case-chains CSV for subagent review.

Everything in new dated files — source file untouched.
"""
import os
import sys
from datetime import date
import pandas as pd


SOURCE = "output/clubs_sales_ready_combined_20260422.csv"
STAMP = date.today().strftime("%Y%m%d")
OUT_CLEANED = f"output/clubs_sales_ready_combined_{STAMP}_cleaned.csv"
OUT_EDGE = f"output/clubs_edge_case_chains_{STAMP}.csv"
OUT_REPORT = f"output/clubs_cleaning_report_{STAMP}.txt"
OUT_DROPPED = f"output/clubs_cleaning_removed_{STAMP}.csv"


CHAINS_TO_DROP = {
    "Cooper\u2019s Hawk Winery & Restaurant",
    "Firebirds Wood Fired Grill",
    "Culinary Dropout",
    "The Henry",
    "Wildfire",
    "Vicious Biscuit",
    "Ruby Sunshine",
    "We Olive & Wine Bar",
    "Lazy Dog Restaurant & Bar",
    "Einstein Bros. Bagels",
    "Rainforest Cafe",
    "Pokeworks",
    "Your Pie Pizza",
    "Maple Street Biscuit Company",
}

BAD_SALVAGES_TO_DROP = {
    "Three Dog Bakery",
    "The Food Emporium",
    "Vino Venue",
    "Cheese and Charcuterie",
    "Mother's Market & Kitchen",
}

EDGE_CASE_CHAINS = {
    "Levain Bakery",
    "Flour Bakery + Cafe",
    "New York Butcher Shoppe",
    "Von Hanson's Meats",
    "vinodivino",
    "McClain Cellars",
    "Mermaid Winery & Restaurant",
}

PARTNER_TO_EXPECTED_BUSINESS = {
    "wine":                      {"wine_store", "wine_bar"},
    "butcher":                   {"butcher"},
    "bakery":                    {"bakery"},
    "fish":                      {"fish_market"},
    "cheese":                    {"cheese_shop"},
    "deli":                      {"deli"},
    "specialty_grocer":          {"specialty_grocer"},
    "farm":                      {"specialty_grocer", "butcher"},
    "books":                     {"specialty_grocer"},
    "destination_restaurant":    {"restaurant"},
    "neighbourhood_restaurant":  {"restaurant"},
    "fast_casual":               {"restaurant"},
}


def dedupe_by_cid(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    def score_row(row):
        expected = PARTNER_TO_EXPECTED_BUSINESS.get(row["partner_type"], set())
        bt_match = 1 if row.get("business_type") in expected else 0
        ls = row.get("lead_score", 0)
        return (bt_match, ls if pd.notna(ls) else 0)

    df = df.copy()
    df["_score_bt"] = df.apply(lambda r: 1 if r.get("business_type") in PARTNER_TO_EXPECTED_BUSINESS.get(r["partner_type"], set()) else 0, axis=1)
    df = df.sort_values(["_score_bt", "lead_score"], ascending=[False, False])
    before = len(df)
    deduped = df.drop_duplicates("cid", keep="first").drop(columns=["_score_bt"])
    return deduped, before - len(deduped)


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(SOURCE, dtype={"cid": str})
    n0 = len(df)
    print(f"Loaded {n0:,} rows from {SOURCE}")

    report = [f"Cleaning report — {STAMP}", "=" * 60, f"Starting rows: {n0:,}", ""]

    # 1. Dedupe
    df, dedup_removed = dedupe_by_cid(df)
    print(f"Dedupe by cid: removed {dedup_removed:,}  -> {len(df):,} rows")
    report += ["[1] Dedupe by cid", f"  Removed: {dedup_removed:,}", f"  Remaining: {len(df):,}", ""]

    # Capture pre-chain state for the removed log
    removed_log = []

    # 2. Chains
    chain_mask = df["name"].isin(CHAINS_TO_DROP)
    chain_rows = df[chain_mask]
    by_name = chain_rows["name"].value_counts()
    report += ["[2] Drop clear chains"]
    report += [f"  {n}\t{name}" for name, n in by_name.items()]
    report += [f"  Removed: {len(chain_rows):,}  -> {(len(df)-len(chain_rows)):,}", ""]
    removed_log.append(chain_rows.assign(_removed_reason="chain"))
    df = df[~chain_mask]
    print(f"Drop chains: removed {len(chain_rows):,}  -> {len(df):,} rows")

    # 3. Bad salvages
    salvage_mask = df["name"].isin(BAD_SALVAGES_TO_DROP)
    salvage_rows = df[salvage_mask]
    by_name_s = salvage_rows["name"].value_counts()
    report += ["[3] Drop bad name-salvages"]
    report += [f"  {n}\t{name}" for name, n in by_name_s.items()]
    report += [f"  Removed: {len(salvage_rows):,}  -> {(len(df)-len(salvage_rows)):,}", ""]
    removed_log.append(salvage_rows.assign(_removed_reason="bad_salvage"))
    df = df[~salvage_mask]
    print(f"Drop bad salvages: removed {len(salvage_rows):,}  -> {len(df):,} rows")

    # 4. Edge case chains -> separate file (keep in cleaned list too, but flag)
    edge_mask = df["name"].isin(EDGE_CASE_CHAINS)
    edge_rows = df[edge_mask].copy()
    edge_rows.to_csv(OUT_EDGE, index=False)
    print(f"\nEdge-case chains written: {len(edge_rows):,} rows -> {OUT_EDGE}")
    report += ["[4] Edge-case chains (for subagent review — still in cleaned file)"]
    for name, n in edge_rows["name"].value_counts().items():
        report += [f"  {n}\t{name}"]
    report += [f"  Total: {len(edge_rows):,}", ""]

    # Write cleaned
    df.to_csv(OUT_CLEANED, index=False)
    print(f"Cleaned file: {OUT_CLEANED}  ({len(df):,} rows)")
    report += [f"Final cleaned rows: {len(df):,}", f"Path: {OUT_CLEANED}"]

    # Distribution after cleaning
    report += ["", "business_type_v2 after cleaning:"]
    for k, v in df["business_type_v2"].value_counts().items():
        report += [f"  {k}: {v:,}"]
    report += ["", "partner_type after cleaning:"]
    for k, v in df["partner_type"].value_counts().items():
        report += [f"  {k}: {v:,}"]

    # Removed log
    if removed_log:
        all_removed = pd.concat(removed_log, ignore_index=True)
        all_removed.to_csv(OUT_DROPPED, index=False)
        print(f"Dropped-rows log: {OUT_DROPPED} ({len(all_removed):,} rows)")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(report))
    print(f"Report: {OUT_REPORT}")


if __name__ == "__main__":
    main()
