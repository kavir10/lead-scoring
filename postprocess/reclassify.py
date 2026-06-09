"""
Reclassify leads using Google Maps `type` (from output/type_lookup.csv) plus
name + page_title heuristics. Produces two columns:

  partner_type      - fine-grained subvertical (e.g. destination_restaurant,
                      neighbourhood_restaurant, fast_casual, butcher, wine,
                      cheese, bakery, fish, deli, specialty_grocer, books, farm)
  business_type_v2  - coarse bucket (restaurants | wine | retail | other)

Second pass applies NAME_HEURISTIC_RULES to:
  - salvage drops / unclassified / no_type rows when the name clearly identifies
    a specific subvertical
  - "wine bar claw-back": override a restaurant classification to wine when the
    name/page_title explicitly says wine bar / enoteca

Source CSVs are never overwritten. Outputs:
  <source>.reclassified.csv
  <source>.reclassify_report.txt
"""
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    TYPE_TO_PARTNER_TYPE,
    PARTNER_TO_BUSINESS_TYPE,
    NAME_HEURISTIC_RULES,
)


PAIRS = [
    (
        "output/custom-serper-scoring_kavir_20260402_restaurant_14283_top.csv",
        "output/custom-serper-scoring_kavir_20260402_restaurant_29727_all.csv",
    ),
    (
        "output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_16083_top.csv",
        "output/custom-serper-scoring_kavir_20260402_bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_73915_all.csv",
    ),
]
LOOKUP_PATH = "output/type_lookup.csv"

COMPILED_RULES = [
    (pt, [re.compile(p, re.IGNORECASE) for p in patterns])
    for pt, patterns in NAME_HEURISTIC_RULES
]

RESTAURANT_PARTNERS = {"destination_restaurant", "neighbourhood_restaurant", "fast_casual"}


def clean_phone(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"[^\d]", "", regex=True)


def partner_from_type(google_type: str) -> tuple[str, str]:
    """Return (partner_type, reclass_action) from pass-1 Google type mapping."""
    gt = (google_type or "").strip()
    if not gt:
        return "unclassified", "no_type"
    if gt in TYPE_TO_PARTNER_TYPE:
        mapped = TYPE_TO_PARTNER_TYPE[gt]
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
    """Name-based second pass: salvage drops/unclassified and wine claw-back."""
    partner = row["partner_type"]
    action = row["reclass_action"]
    text = f"{row.get('name', '')} {row.get('page_title', '') or ''}".lower()

    # Wine claw-back: if any restaurant partner but name says wine bar/enoteca, flip
    if partner in RESTAURANT_PARTNERS:
        for pt, patterns in COMPILED_RULES:
            if pt != "wine":
                continue
            # Only flip on the wine-BAR-specific patterns, not generic wine_store ones
            for p in patterns:
                pat = p.pattern
                if any(tok in pat for tok in ("wine bar", "enoteca", "wine lounge", "champagne bar")):
                    if p.search(text):
                        return "wine", "override_wine_by_name"
        return partner, action

    # Salvage: drops / unclassified / no_type -> any strong name signal wins
    if action in ("drop_not_icp", "unmapped_type", "no_type"):
        hit = name_hit(text)
        if hit:
            return hit, f"salvaged_by_name:{action}"

    return partner, action


def business_from_partner(partner_type: str) -> str:
    return PARTNER_TO_BUSINESS_TYPE.get(partner_type, "other")


def reclassify_file(top_path: str, all_path: str, lookup: pd.DataFrame) -> None:
    print(f"\n--- {os.path.basename(top_path)} ---")
    top = pd.read_csv(top_path)
    allf = pd.read_csv(all_path, dtype={"cid": str})
    top["phone_clean"] = clean_phone(top["phone"])
    allf["phone_clean"] = clean_phone(allf["phone"])

    allf_keep = (allf[["phone_clean", "cid", "page_title"]]
                 .dropna(subset=["cid"])
                 .drop_duplicates("phone_clean"))
    merged = top.merge(allf_keep, on="phone_clean", how="left")
    merged = merged.merge(
        lookup[["cid", "type", "types", "match_confidence"]].rename(
            columns={"type": "google_type", "types": "google_types"}
        ),
        on="cid", how="left",
    )

    # Pass 1: google type -> partner_type
    pass1 = merged["google_type"].fillna("").apply(partner_from_type)
    merged["partner_type"] = [c[0] for c in pass1]
    merged["reclass_action"] = [c[1] for c in pass1]

    # Pass 2: name heuristic
    pass2 = merged.apply(apply_second_pass, axis=1)
    merged["partner_type"] = [p[0] for p in pass2]
    merged["reclass_action"] = [p[1] for p in pass2]

    # Coarse business_type from partner_type
    merged["business_type_v2"] = merged["partner_type"].apply(business_from_partner)

    merged = merged.drop(columns=["phone_clean"])

    out_path = top_path.replace(".csv", ".reclassified.csv")
    merged.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(merged):,} rows)")

    write_report(top_path, merged)


def write_report(top_path: str, df: pd.DataFrame) -> None:
    report_path = top_path.replace(".csv", ".reclassify_report.txt")
    lines: list[str] = []
    p = lines.append
    n = len(df)

    p(f"Reclassification report for {os.path.basename(top_path)}")
    p(f"Total rows: {n:,}")
    p("")

    p("== reclass_action counts ==")
    for k, v in df["reclass_action"].value_counts(dropna=False).items():
        p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
    p("")

    p("== business_type_v2 distribution ==")
    for k, v in df["business_type_v2"].value_counts(dropna=False).items():
        p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
    p("")

    p("== partner_type distribution ==")
    for k, v in df["partner_type"].value_counts(dropna=False).items():
        p(f"  {k}: {v:,} ({v / n * 100:.1f}%)")
    p("")

    p("== old business_type -> partner_type ==")
    ct = pd.crosstab(df["business_type"], df["partner_type"], margins=True)
    p(ct.to_string())
    p("")

    clawback = df[df["reclass_action"] == "override_wine_by_name"]
    p(f"== wine claw-backs (restaurant -> wine by name): {len(clawback):,} ==")
    if len(clawback):
        p("Sample (up to 15):")
        p(clawback[["name", "business_type", "google_type", "partner_type"]].head(15).to_string(index=False))
        p("")

    salvaged = df[df["reclass_action"].astype(str).str.startswith("salvaged_by_name")]
    p(f"== name-salvaged (rescued from drops/unclassified): {len(salvaged):,} ==")
    if len(salvaged):
        p("Breakdown by new partner_type:")
        p(salvaged["partner_type"].value_counts().to_string())
        p("")
        p("Sample (up to 20):")
        p(salvaged[["name", "business_type", "google_type", "partner_type", "reclass_action"]].head(20).to_string(index=False))
        p("")

    dropped = df[df["partner_type"] == "dropped"]
    p(f"== rows DROPPED as not-ICP: {len(dropped):,} ==")
    if len(dropped):
        p("Top google_type among final drops:")
        p(dropped["google_type"].value_counts().head(20).to_string())
        p("")

    unmapped = df[df["reclass_action"] == "unmapped_type"]
    p(f"== rows with UNMAPPED google_type, no name salvage: {len(unmapped):,} ==")
    if len(unmapped):
        p("Top unmapped google_type values:")
        p(unmapped["google_type"].value_counts().head(25).to_string())
        p("")

    no_type = df[df["reclass_action"] == "no_type"]
    p(f"== rows with NO google_type, no name salvage: {len(no_type):,} ==")
    if len(no_type):
        p("Sample (up to 10):")
        p(no_type[["name", "business_type", "match_confidence"]].head(10).to_string(index=False))
        p("")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {report_path}")


def main() -> None:
    if not os.path.exists(LOOKUP_PATH):
        print(f"Missing lookup at {LOOKUP_PATH}. Run backfill_type.py first.", file=sys.stderr)
        sys.exit(1)
    lookup = pd.read_csv(LOOKUP_PATH, dtype={"cid": str})
    print(f"Loaded lookup: {len(lookup):,} rows")
    for top_path, all_path in PAIRS:
        reclassify_file(top_path, all_path, lookup)


if __name__ == "__main__":
    main()
