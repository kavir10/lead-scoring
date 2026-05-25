"""
Build recovery-input CSV — error rows from the newsletter scrape that have
a website but failed (403/429/timeout/etc). Skips 404 and non_html_2xx
since those aren't recoverable.

Output: output/newsletter_merchants/inputs/recovery_input.csv
"""
from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS = os.path.join(ROOT, "output/newsletter_merchants/raw/scrape_progress.csv")
SEED = os.path.join(ROOT, "output/newsletter_merchants/inputs/seed_100k.csv")
OUT = os.path.join(ROOT, "output/newsletter_merchants/inputs/recovery_input.csv")


def is_recoverable(status: str) -> bool:
    s = (status or "").strip()
    if not s:
        return False
    # The originals worth recovering: bot-blocks, server errors, TLS/protocol
    # errors, timeouts. Skip 200 (no need), 404 (page genuinely missing),
    # non_html_2* / non_html_4* (intentionally not HTML or missing).
    if s.startswith("200"):
        return False
    if s == "404":
        return False
    if s.startswith("non_html_2") or s.startswith("non_html_4"):
        return False
    return True


def main():
    df = pd.read_csv(PROGRESS, dtype=str).fillna("")
    seed = pd.read_csv(SEED, dtype=str).fillna("")
    print(f"Progress rows: {len(df):,}")
    print(f"Seed rows: {len(seed):,}")

    mask = df["website_status"].apply(is_recoverable)
    err = df[mask].copy()
    print(f"Recoverable error rows: {len(err):,}")

    # Join seed columns (address/phone/rating/review_count) so the output
    # CSV stays self-contained.
    cols = ["cid", "name", "address", "phone", "website",
            "city", "state", "business_type", "rating", "review_count"]
    seed_cols = seed[[c for c in cols if c in seed.columns]].copy()
    out = err[["cid", "website_status"]].merge(seed_cols, on="cid", how="left").fillna("")
    out = out[["cid", "name", "address", "phone", "website", "city", "state",
               "business_type", "rating", "review_count", "website_status"]]
    out = out[out["website"].astype(str).str.strip() != ""]

    print(f"\nBreakdown of recovery candidates:")
    print(out["website_status"].value_counts().head(15).to_string())
    print(f"\nBy vertical:")
    print(out["business_type"].value_counts().to_string())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}  ({len(out):,} rows)")


if __name__ == "__main__":
    main()
