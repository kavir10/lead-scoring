"""
Reclassify the *clubs_v2* files (full universe with club detection flags)
using the existing Google type lookup + name heuristics.

Mirrors reclassify.py logic but operates on:
  output/custom-serper-scoring_kavir_20260402_restaurant_29727_all_clubs_v2.csv
  output/custom-serper-scoring_kavir_20260402_bakery-...-wine-store_73915_all_clubs_v2.csv

Uses output/type_lookup.csv (25k cids) as-is — no new Serper calls. Rows whose
cid is not in the lookup fall through to name heuristics; if those also miss,
they land in reclass_action='no_type'.

Outputs (new files, sources untouched):
  <input>.reclassified.csv                            (per clubs file)
  output/clubs_sales_ready_combined.csv               (has_club_final=True + ICP partner_type)
  output/clubs_needs_type_backfill.csv                (has_club_final=True + no_type/unmapped_type)
  output/clubs_reclassify_report.txt                  (distributions + coverage)
"""
import os
import re
import sys
from datetime import date
import pandas as pd

from config import (
    TYPE_TO_PARTNER_TYPE,
    PARTNER_TO_BUSINESS_TYPE,
    NAME_HEURISTIC_RULES,
)


INPUTS = [
    "output/custom-serper-scoring_kavir_20260402_restaurant_29727_all_clubs_v2.csv",
    "output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all_clubs_v2.csv",
]
LOOKUP_PATHS = ["output/type_lookup.csv", "output/type_lookup_clubs.csv"]
STAMP = date.today().strftime("%Y%m%d")
COMBINED_SALES_PATH = f"output/clubs_sales_ready_combined_{STAMP}.csv"
NEEDS_BACKFILL_PATH = f"output/clubs_needs_type_backfill_{STAMP}.csv"
REPORT_PATH = f"output/clubs_reclassify_report_{STAMP}.txt"

EXTRA_TYPE_TO_PARTNER_TYPE: dict[str, str | None] = {
    "Cattle farm": "farm",
    "Seafood wholesaler": "fish",
    "Agricultural service": "farm",
    "North African restaurant": "neighbourhood_restaurant",
    "Kosher grocery store": "specialty_grocer",
    "Russian grocery store": "specialty_grocer",
    "Oyster supplier": "fish",
    "Livestock breeder": "farm",
    "Chocolate artisan": "bakery",
    "Po\u2019 boys restaurant": "neighbourhood_restaurant",
    "Agricultural production": "farm",
    "Livestock producer": "farm",
    "Olive oil bottling company": "specialty_grocer",
    "Orchard": "farm",
    "Poultry farm": "farm",
    "African goods store": "specialty_grocer",
    "Organic shop": "specialty_grocer",
    "Winemaking supply store": "wine",
    "Greenhouse": "farm",
    "\uc544\uc2dc\uc544 \uc2dd\ub8cc\ud488\uc810": "specialty_grocer",

    "Popcorn store": None,
    "Herb shop": None,
    "Coffee store": None,
    "Frozen yogurt shop": None,
    "Pretzel store": None,
    "Cooking school": None,
    "Shared-use commercial kitchen": None,
    "Food processing company": None,

    "Golf club": None, "Golf course": None, "Tennis club": None, "Boat club": None,
    "Gym": None, "Sports club": None, "Fitness center": None,
    "Candle store": None, "Lumber store": None, "Cutlery store": None,
    "Scrapbooking store": None, "Craft store": None,
    "Delivery service": None, "Shipping service": None, "Self-storage facility": None,
    "Warehouse": None, "Warehouse club": None,
    "Adult education school": None, "Trade school": None, "Handicraft school": None,
    "Education center": None,
    "Movie theater": None, "Museum": None, "Community center": None,
    "Arts organization": None,
    "Fraternal organization": None, "Singles organization": None,
    "Unitarian Universalist Church": None,
    "Men's clothing store": None, "Toy store": None, "Record store": None,
    "Comic book store": None,
    "Acupuncture clinic": None, "Physical fitness program": None,
    "Wellness center": None, "Health spa": None,
    "Stained glass studio": None, "Water mill": None, "Dog park": None,
    "Indoor playground": None, "Miniature golf course": None,
    "Metaphysical supply store": None, "Aromatherapy supply store": None,
    "Packaging supply store": None,
    "Tour operator": None, "Tourist information center": None,
    "Event planner": None, "Mailing service": None,
    "Heating contractor": None, "Makerspace": None, "Internet shop": None,
    "Animal feed store": None,
}

MERGED_TYPE_TO_PARTNER_TYPE: dict[str, str | None] = {**TYPE_TO_PARTNER_TYPE, **EXTRA_TYPE_TO_PARTNER_TYPE}

COMPILED_RULES = [
    (pt, [re.compile(p, re.IGNORECASE) for p in patterns])
    for pt, patterns in NAME_HEURISTIC_RULES
]

RESTAURANT_PARTNERS = {"destination_restaurant", "neighbourhood_restaurant", "fast_casual"}
ICP_PARTNERS = set(PARTNER_TO_BUSINESS_TYPE.keys())


def partner_from_type(google_type: str) -> tuple[str, str]:
    gt = (google_type or "").strip()
    if not gt:
        return "unclassified", "no_type"
    if gt in MERGED_TYPE_TO_PARTNER_TYPE:
        mapped = MERGED_TYPE_TO_PARTNER_TYPE[gt]
        if mapped is None:
            return "dropped", "drop_not_icp"
        return mapped, "mapped"
    return "unclassified", "unmapped_type"


def name_hit(text: str) -> str | None:
    for pt, patterns in COMPILED_RULES:
        for p in patterns:
            if p.search(text):
                return pt
    return None


def apply_second_pass(row: pd.Series) -> tuple[str, str]:
    partner = row["partner_type"]
    action = row["reclass_action"]
    text = f"{row.get('name', '')} {row.get('page_title', '') or ''}".lower()

    if partner in RESTAURANT_PARTNERS:
        for pt, patterns in COMPILED_RULES:
            if pt != "wine":
                continue
            for p in patterns:
                pat = p.pattern
                if any(tok in pat for tok in ("wine bar", "enoteca", "wine lounge", "champagne bar")):
                    if p.search(text):
                        return "wine", "override_wine_by_name"
        return partner, action

    if action in ("drop_not_icp", "unmapped_type", "no_type"):
        hit = name_hit(text)
        if hit:
            return hit, f"salvaged_by_name:{action}"

    return partner, action


def business_from_partner(partner_type: str) -> str:
    return PARTNER_TO_BUSINESS_TYPE.get(partner_type, "other")


def reclassify_clubs(path: str, lookup: pd.DataFrame) -> pd.DataFrame:
    print(f"\n--- {os.path.basename(path)} ---")
    df = pd.read_csv(path, dtype={"cid": str})
    n = len(df)
    print(f"Loaded {n:,} rows")

    before_cols = list(df.columns)

    df = df.merge(
        lookup[["cid", "type", "types", "match_confidence"]].rename(
            columns={"type": "google_type", "types": "google_types"}
        ),
        on="cid", how="left",
    )

    pass1 = df["google_type"].fillna("").apply(partner_from_type)
    df["partner_type"] = [c[0] for c in pass1]
    df["reclass_action"] = [c[1] for c in pass1]

    pass2 = df.apply(apply_second_pass, axis=1)
    df["partner_type"] = [p[0] for p in pass2]
    df["reclass_action"] = [p[1] for p in pass2]

    df["business_type_v2"] = df["partner_type"].apply(business_from_partner)

    new_cols = ["google_type", "google_types", "match_confidence",
                "partner_type", "reclass_action", "business_type_v2"]
    df = df[before_cols + new_cols]

    out_path = path.replace(".csv", f".reclassified_{STAMP}.csv")
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df):,} rows)")
    return df


def build_sales_ready(frames: list[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True, sort=False)
    clubs_only = combined[combined["has_club_final"] == True].copy()
    sales = clubs_only[clubs_only["partner_type"].isin(ICP_PARTNERS)].copy()
    if "lead_score" in sales.columns:
        sales = sales.sort_values("lead_score", ascending=False, na_position="last")
    return sales


def build_needs_backfill(frames: list[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True, sort=False)
    clubs_only = combined[combined["has_club_final"] == True]
    mask = clubs_only["reclass_action"].isin(["no_type", "unmapped_type"])
    needs = clubs_only[mask].copy()
    keep_cols = [c for c in ["cid", "name", "address", "city", "state", "phone",
                             "website", "business_type", "google_type",
                             "reclass_action", "has_club_final", "club_type_final",
                             "club_url_final", "lead_score", "tier"]
                 if c in needs.columns]
    return needs[keep_cols]


def write_report(frames: list[pd.DataFrame], paths: list[str],
                 sales: pd.DataFrame, needs: pd.DataFrame) -> None:
    lines: list[str] = []
    p = lines.append

    p("Clubs reclassification report")
    p("=" * 60)
    p("")

    for df, path in zip(frames, paths):
        n = len(df)
        p(f"### {os.path.basename(path)}  ({n:,} rows)")
        p("")
        p("reclass_action:")
        for k, v in df["reclass_action"].value_counts(dropna=False).items():
            p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
        p("")
        p("business_type_v2:")
        for k, v in df["business_type_v2"].value_counts(dropna=False).items():
            p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
        p("")
        p("partner_type:")
        for k, v in df["partner_type"].value_counts(dropna=False).items():
            p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
        p("")

        clubs = df[df["has_club_final"] == True]
        p(f"has_club_final=True rows: {len(clubs):,}")
        p("  partner_type among clubs:")
        for k, v in clubs["partner_type"].value_counts(dropna=False).items():
            p(f"    {k}: {v:,}")
        p("")
        p("-" * 60)
        p("")

    p("### Combined sales-ready list")
    p(f"Path: {COMBINED_SALES_PATH}")
    p(f"Rows: {len(sales):,}")
    if len(sales):
        p("  business_type_v2:")
        for k, v in sales["business_type_v2"].value_counts(dropna=False).items():
            p(f"    {k}: {v:,}")
        p("  partner_type:")
        for k, v in sales["partner_type"].value_counts(dropna=False).items():
            p(f"    {k}: {v:,}")
    p("")

    p("### Needs Google-type backfill (step 2 — Serper calls)")
    p(f"Path: {NEEDS_BACKFILL_PATH}")
    p(f"Rows: {len(needs):,}  (has_club_final=True AND reclass_action in [no_type, unmapped_type])")
    if len(needs):
        p("  reclass_action:")
        for k, v in needs["reclass_action"].value_counts(dropna=False).items():
            p(f"    {k}: {v:,}")
    p("")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {REPORT_PATH}")


def main() -> None:
    frames_lookup = []
    for path in LOOKUP_PATHS:
        if os.path.exists(path):
            frames_lookup.append(pd.read_csv(path, dtype={"cid": str}))
            print(f"Loaded {path}: {len(frames_lookup[-1]):,} rows")
        else:
            print(f"Skipping missing lookup: {path}")
    if not frames_lookup:
        print("No lookup files found.", file=sys.stderr)
        sys.exit(1)
    lookup = pd.concat(frames_lookup, ignore_index=True).drop_duplicates("cid", keep="last")
    print(f"Combined lookup: {len(lookup):,} unique cids")

    frames = [reclassify_clubs(path, lookup) for path in INPUTS]

    sales = build_sales_ready(frames)
    sales.to_csv(COMBINED_SALES_PATH, index=False)
    print(f"\nWrote {COMBINED_SALES_PATH} ({len(sales):,} rows)")

    needs = build_needs_backfill(frames)
    needs.to_csv(NEEDS_BACKFILL_PATH, index=False)
    print(f"Wrote {NEEDS_BACKFILL_PATH} ({len(needs):,} rows)")

    write_report(frames, INPUTS, sales, needs)


if __name__ == "__main__":
    main()
