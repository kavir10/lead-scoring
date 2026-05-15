"""
Stratified random sample of the final sales list for manual QA review.

Takes min(10, bucket_size) per partner_type so small categories aren't starved
and large categories don't dominate. Deterministic (seed=42). Outputs a
review-friendly subset of columns.

Input:  output/clubs_sales_ready_combined_<date>_final.csv
Output: output/clubs_qa_sample_<date>.csv
"""
import os
import sys
from datetime import date
import pandas as pd


STAMP = date.today().strftime("%Y%m%d")
SOURCE = f"output/clubs_working_sales_list_{STAMP}.csv"
OUT = f"output/clubs_working_sales_list_qa_sample_{STAMP}.csv"
PER_BUCKET = 10
SEED = 42

REVIEW_COLS = [
    "name", "city", "state", "website", "phone",
    "partner_type", "business_type_v2",
    "google_type", "reclass_action",
    "club_type_final", "club_url_final", "club_signals_final",
    "rating", "review_count", "follower_count",
    "instagram_url", "facebook_url",
    "has_ecommerce", "has_email_signup",
    "press_mentions", "awards_count",
    "lead_score", "tier",
]


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(SOURCE, dtype={"cid": str})
    print(f"Loaded {len(df):,} rows from {SOURCE}")
    print()

    cols = [c for c in REVIEW_COLS if c in df.columns]
    samples = []
    print(f"Stratified sample (up to {PER_BUCKET} per partner_type, seed={SEED}):")
    for partner, bucket in df.groupby("partner_type"):
        n_take = min(PER_BUCKET, len(bucket))
        s = bucket.sample(n=n_take, random_state=SEED)
        samples.append(s)
        print(f"  {partner}: {n_take} / {len(bucket):,}")

    sample = pd.concat(samples, ignore_index=True)
    sample = sample[cols + [c for c in sample.columns if c not in cols]]
    sample = sample.sort_values(["partner_type", "lead_score"],
                                ascending=[True, False]).reset_index(drop=True)

    sample.to_csv(OUT, index=False)
    print(f"\nSample: {len(sample):,} rows -> {OUT}")

    print("\nSummary of sample:")
    for k, v in sample["partner_type"].value_counts().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
