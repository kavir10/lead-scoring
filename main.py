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

from butcher import (
    add_why_high_quality,
    load_eligible_butcher_cities,
    save_eligible_cities,
    timestamped_path,
)
from butcher_sources import run_butcher_source_scrape
from config import SERPER_API_KEY
from discover import discover_leads, discover_leads_for_cities
from enrich import (
    enrich_websites, enrich_instagram, enrich_facebook, enrich_press_and_awards,
    enrich_google_reviews, enrich_instagram_reels, enrich_instagram_posts,
    enrich_booking_availability,
)
from score import score_leads, score_butcher_leads


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
BUTCHER_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "butcher")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def ensure_butcher_output_dir():
    os.makedirs(BUTCHER_OUTPUT_DIR, exist_ok=True)


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


def run_butcher_discovery(
    max_searches: int = 0,
    min_population: int = 25_000,
    cities_path: str | None = None,
) -> pd.DataFrame:
    """Butcher-only national discovery into output/butcher."""
    ensure_butcher_output_dir()

    if not SERPER_API_KEY:
        print("\nMissing SERPER_API_KEY. Add it to .env before running live butcher discovery.")
        sys.exit(1)

    cities_df = load_eligible_butcher_cities(
        min_population=min_population,
        cities_path=cities_path,
    )
    cities_csv = save_eligible_cities(cities_df, BUTCHER_OUTPUT_DIR)

    print(f"\n{'='*60}")
    print("BUTCHER NATIONAL CITY COVERAGE")
    print(f"{'='*60}")
    print(f"Eligible cities: {len(cities_df)}")
    print("City source: static top U.S. cities list")
    print("Excluded states: HI, IN, IA, KS, NV, ND, SD")
    print(f"Saved eligible cities to {cities_csv}")

    df = discover_leads_for_cities(
        types=["butcher"],
        cities=cities_df["location"].tolist(),
        max_searches=max_searches,
        source="google_maps",
        niche_min_reviews=5,
        niche_min_rating=3.7,
    )

    if df.empty:
        print("\nNo butcher leads found. Check API key and try again.")
        sys.exit(1)

    df["butcher_source"] = df.get("butcher_source", "google_maps")
    df["source"] = df.get("source", "google_maps")

    path = os.path.join(BUTCHER_OUTPUT_DIR, "1_discovered_butchers.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved butcher discovery results to {path}")

    return df


def run_butcher_source_discovery() -> pd.DataFrame:
    """Run source-only butcher scraping into output/butcher."""
    ensure_butcher_output_dir()

    print(f"\n{'='*60}")
    print("BUTCHER SOURCE SCRAPE")
    print(f"{'='*60}")
    print("Sources: Good Meat Finder, EatWild, Good Food Awards, AGA, stockist pages")
    print("Skipping Google/Serper discovery and all enrichment phases")

    df, status_df = run_butcher_source_scrape(BUTCHER_OUTPUT_DIR)
    print(f"\nSource scrape statuses:")
    if not status_df.empty:
        print(status_df[["source", "status", "rows", "url"]].to_string(index=False))
    print(f"\nSaved {len(df)} deduped source leads to {BUTCHER_OUTPUT_DIR}/1_discovered_butchers.csv")
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


def run_butcher_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    """Run butcher enrichment and save the consolidated butcher CSV."""
    ensure_butcher_output_dir()

    df = enrich_websites(df)
    df = enrich_instagram(df)
    df = enrich_facebook(df)
    df = enrich_press_and_awards(df)
    df = enrich_google_reviews(df)
    df = enrich_instagram_reels(df)
    df = enrich_instagram_posts(df)

    path = os.path.join(BUTCHER_OUTPUT_DIR, "2_enriched_butchers.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved butcher enrichment to {path}")

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


def run_butcher_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """Score butcher leads and save butcher-specific exports."""
    ensure_butcher_output_dir()
    df = score_butcher_leads(df)
    df = add_why_high_quality(df)

    path_full = timestamped_path(BUTCHER_OUTPUT_DIR, "3_scored_butchers")
    df.to_csv(path_full, index=False)
    print(f"\nSaved all scored butcher leads to {path_full}")

    df_top = df[df["tier"].isin(["A - Hot Lead", "B - Warm Lead"])]
    output_cols = [
        "name", "address", "city", "state", "phone", "website", "business_type",
        "butcher_source", "lead_score", "tier", "why_high_quality",
        "has_meat_box", "has_csa_or_share", "has_preorder", "ships_meat",
        "has_pickup", "has_subscription_language", "animal_welfare_signal",
        "whole_animal_signal", "dry_aged_signal", "source_quality_score",
        "review_count", "rating", "follower_count", "avg_video_views",
        "avg_likes", "press_mentions", "press_sources", "awards_count",
        "awards_list", "instagram_url", "ig_followers", "facebook_url",
        "fb_likes", "has_email_signup", "has_ecommerce", "has_online_ordering",
    ]
    available_cols = [c for c in output_cols if c in df_top.columns]

    path_top = timestamped_path(BUTCHER_OUTPUT_DIR, "3_top_butchers")
    df_top[available_cols].to_csv(path_top, index=False)
    print(f"Saved {len(df_top)} top butcher leads (A+B tier) to {path_top}")

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
    parser.add_argument("--butcher-national", action="store_true", help="Run national butcher discovery, enrichment, and scoring")
    parser.add_argument("--butcher-sources", action="store_true", help="Run source-only butcher scraping without enrichment")
    parser.add_argument("--butcher-discover-only", action="store_true", help="Only run national butcher discovery")
    parser.add_argument("--butcher-enrich", type=str, help="Run butcher enrichment + scoring from an existing butcher discovery CSV")
    parser.add_argument("--butcher-score", type=str, help="Run butcher scoring from an existing enriched butcher CSV")
    parser.add_argument("--city-population-min", type=int, default=25_000, help="Minimum population for national butcher city coverage")
    parser.add_argument("--cities-path", type=str, help="Optional local Census Gazetteer-style places file")
    args = parser.parse_args()

    types_filter = [t.strip() for t in args.types.split(",")] if args.types else None

    print(f"\n{'#'*60}")
    print(f"  LEAD SCORING PIPELINE")
    print(f"  Finding subscription-ready independent food businesses")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if types_filter:
        print(f"  Types filter: {', '.join(types_filter)}")
    print(f"{'#'*60}")

    if args.butcher_score:
        df = pd.read_csv(args.butcher_score)
        run_butcher_scoring(df)
        return

    if args.butcher_sources:
        run_butcher_source_discovery()
        return

    if args.butcher_enrich:
        df = pd.read_csv(args.butcher_enrich)
        df = run_butcher_enrichment(df)
        run_butcher_scoring(df)
        return

    if args.butcher_national or args.butcher_discover_only:
        df = run_butcher_discovery(
            max_searches=args.max_searches,
            min_population=args.city_population_min,
            cities_path=args.cities_path,
        )
        if args.butcher_discover_only:
            return
        df = run_butcher_enrichment(df)
        run_butcher_scoring(df)
        return

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
