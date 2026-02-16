"""
Lead Scoring Pipeline for Independent Food Businesses
Find, enrich, and score leads for Table22 subscription program outreach.

Usage:
    python main.py              # Run full pipeline
    python main.py --discover   # Only run discovery phase
    python main.py --enrich     # Enrich from existing discovery CSV
    python main.py --score      # Score from existing enriched CSV
"""
import os
import sys
import argparse
from datetime import datetime

import pandas as pd

from discover import discover_leads
from enrich import (
    enrich_websites, enrich_instagram, enrich_facebook, enrich_press_and_awards,
    enrich_google_reviews, enrich_instagram_reels, enrich_instagram_posts,
    enrich_booking_availability,
)
from score import score_leads


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_discovery(types: list[str] | None = None, max_searches: int = 0) -> pd.DataFrame:
    """Phase 1: Find leads."""
    df = discover_leads(types=types, max_searches=max_searches)

    if df.empty:
        print("\nNo leads found. Check API key and try again.")
        sys.exit(1)

    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, "1_discovered.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved discovery results to {path}")

    return df


def run_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    """Phase 2: Enrich with website + social data."""
    df = enrich_websites(df)

    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, "2_enriched_websites.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved website enrichment to {path}")

    df = enrich_instagram(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_instagram.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved Instagram enrichment to {path}")

    df = enrich_facebook(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_social.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved social enrichment to {path}")

    df = enrich_press_and_awards(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_full.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved full enrichment to {path}")

    df = enrich_google_reviews(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_reviews.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved Google Reviews enrichment to {path}")

    df = enrich_instagram_reels(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_reels.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved Instagram Reels enrichment to {path}")

    df = enrich_instagram_posts(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_posts.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved Instagram Posts enrichment to {path}")

    df = enrich_booking_availability(df)

    path = os.path.join(OUTPUT_DIR, "2_enriched_availability.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved booking availability enrichment to {path}")

    return df


def run_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """Phase 3: Score and rank."""
    df = score_leads(df)

    ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Full results
    path_full = os.path.join(OUTPUT_DIR, f"3_scored_all_{timestamp}.csv")
    df.to_csv(path_full, index=False)
    print(f"\nSaved all scored leads to {path_full}")

    # Top leads only (A + B tier)
    df_top = df[df["tier"].isin(["A - Hot Lead", "B - Warm Lead"])]

    # Clean output columns for the final list
    output_cols = [
        "name", "address", "city", "state", "phone", "website", "business_type",
        "lead_score", "tier",
        "reservation_difficulty", "reservation_url",
        "review_difficulty_sentiment", "booking_availability_score",
        "follower_count", "avg_video_views",
        "review_count",
        "press_mentions", "press_sources", "awards_count", "awards_list",
        "rating", "avg_likes", "price_tier",
        "instagram_url", "ig_followers",
        "facebook_url", "fb_likes",
        "has_email_signup", "has_ecommerce",
    ]
    available_cols = [c for c in output_cols if c in df_top.columns]

    path_top = os.path.join(OUTPUT_DIR, f"3_top_leads_{timestamp}.csv")
    df_top[available_cols].to_csv(path_top, index=False)
    print(f"Saved {len(df_top)} top leads (A+B tier) to {path_top}")

    return df


def merge_discovery(existing_path: str, new_df: pd.DataFrame) -> pd.DataFrame:
    """Merge new discovery results with an existing discovery CSV, deduplicating."""
    existing = pd.read_csv(existing_path)
    print(f"\nMerging {len(new_df)} new leads with {len(existing)} existing leads...")

    combined = pd.concat([existing, new_df], ignore_index=True)

    # Dedup by phone
    combined["phone_clean"] = combined["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
    df_deduped = combined.drop_duplicates(subset=["phone_clean"], keep="first")
    mask_no_phone = df_deduped["phone_clean"] == ""
    df_with_phone = df_deduped[~mask_no_phone]
    df_no_phone = df_deduped[mask_no_phone].drop_duplicates(
        subset=["name", "address"], keep="first"
    )
    merged = pd.concat([df_with_phone, df_no_phone], ignore_index=True)
    merged = merged.drop(columns=["phone_clean"])

    dupes_removed = len(combined) - len(merged)
    print(f"  Combined: {len(merged)} unique leads ({dupes_removed} duplicates removed)")

    for bt in merged["business_type"].unique():
        n = (merged["business_type"] == bt).sum()
        print(f"  {bt}: {n}")

    return merged


def main():
    parser = argparse.ArgumentParser(description="Lead Scorer")
    parser.add_argument("--discover", action="store_true", help="Only run discovery")
    parser.add_argument("--types", type=str, help="Comma-separated business types to discover (e.g. butcher,wine_store)")
    parser.add_argument("--max-searches", type=int, default=0, help="Max Serper API calls (0 = unlimited)")
    parser.add_argument("--merge", type=str, help="Merge new discovery with existing CSV (path to existing)")
    parser.add_argument("--enrich", type=str, help="Enrich from existing CSV path")
    parser.add_argument("--enrich-remaining", type=str, help="Run only remaining enrichment phases (reels, posts, availability) + scoring")
    parser.add_argument("--score", type=str, help="Score from existing CSV path")
    args = parser.parse_args()

    types_filter = [t.strip() for t in args.types.split(",")] if args.types else None

    print(f"\n{'#'*60}")
    print(f"  LEAD SCORING PIPELINE")
    print(f"  Finding subscription-ready independent food businesses")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if types_filter:
        print(f"  Types filter: {', '.join(types_filter)}")
    print(f"{'#'*60}")

    if args.score:
        # Just score existing enriched data
        df = pd.read_csv(args.score)
        run_scoring(df)
        return

    if args.enrich_remaining:
        # Run only the remaining enrichment phases (reels, posts, availability) + scoring
        df = pd.read_csv(args.enrich_remaining)
        ensure_output_dir()

        df = enrich_instagram_reels(df)
        path = os.path.join(OUTPUT_DIR, "2_enriched_reels.csv")
        df.to_csv(path, index=False)
        print(f"\nSaved Instagram Reels enrichment to {path}")

        df = enrich_instagram_posts(df)
        path = os.path.join(OUTPUT_DIR, "2_enriched_posts.csv")
        df.to_csv(path, index=False)
        print(f"\nSaved Instagram Posts enrichment to {path}")

        df = enrich_booking_availability(df)
        path = os.path.join(OUTPUT_DIR, "2_enriched_availability.csv")
        df.to_csv(path, index=False)
        print(f"\nSaved booking availability enrichment to {path}")

        run_scoring(df)
        return

    if args.enrich:
        # Enrich existing discovery data
        df = pd.read_csv(args.enrich)
        df = run_enrichment(df)
        run_scoring(df)
        return

    if args.discover:
        df = run_discovery(types=types_filter, max_searches=args.max_searches)
        if args.merge and not df.empty:
            df = merge_discovery(args.merge, df)
            path = os.path.join(OUTPUT_DIR, "1_discovered_merged.csv")
            df.to_csv(path, index=False)
            print(f"\nSaved merged discovery to {path}")
        return

    # Full pipeline
    df = run_discovery(types=types_filter, max_searches=args.max_searches)
    if args.merge and not df.empty:
        df = merge_discovery(args.merge, df)
    df = run_enrichment(df)
    df = run_scoring(df)

    print(f"\n{'#'*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'#'*60}")
    print(f"\nTotal leads found: {len(df)}")
    a_count = len(df[df["tier"] == "A - Hot Lead"])
    b_count = len(df[df["tier"] == "B - Warm Lead"])
    print(f"Hot leads (A tier): {a_count}")
    print(f"Warm leads (B tier): {b_count}")
    print(f"\nResults saved to: {OUTPUT_DIR}/")
    print(f"Open 3_top_leads_*.csv for your outreach list")


if __name__ == "__main__":
    main()
