"""
Phase 3: Score and rank leads using SHAP-aligned weights
"""
import numpy as np
import pandas as pd
from config import SCORING_WEIGHTS


def _to_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def score_reservation_difficulty_composite(row: pd.Series) -> float:
    """Composite reservation difficulty score combining three sub-signals.

    - Platform signal (40%): Tock=1.0, Resy=0.7, OpenTable=0.4, none=0.0
    - Review sentiment (35%): from Google Reviews keyword analysis
    - Availability (25%): inverted — fewer slots = harder to get in
    """
    platform_value = int(row.get("reservation_difficulty", 0) or 0)
    platform_map = {3: 1.0, 2: 0.7, 1: 0.4, 0: 0.0}
    platform_score = platform_map.get(platform_value, 0.0)

    review_sentiment = float(row.get("review_difficulty_sentiment", 0) or 0)

    availability = float(row.get("booking_availability_score", 1.0) or 1.0)
    availability_difficulty = 1.0 - availability  # invert: fewer slots = harder

    composite = (
        0.40 * platform_score +
        0.35 * review_sentiment +
        0.25 * availability_difficulty
    )
    return round(composite, 3)


def score_avg_video_views(count: int) -> float:
    """Score average Instagram Reels / TikTok views 0-1."""
    count = _to_float(count)
    if count >= 100_000:
        return 1.0
    elif count >= 50_000:
        return 0.9
    elif count >= 20_000:
        return 0.8
    elif count >= 10_000:
        return 0.6
    elif count >= 5_000:
        return 0.4
    elif count >= 1_000:
        return 0.2
    elif count > 0:
        return 0.1
    return 0.0


def score_follower_count(count: int) -> float:
    """Score combined social followers 0-1."""
    count = _to_float(count)
    if count >= 100_000:
        return 1.0
    elif count >= 50_000:
        return 0.9
    elif count >= 20_000:
        return 0.8
    elif count >= 10_000:
        return 0.7
    elif count >= 5_000:
        return 0.5
    elif count >= 2_000:
        return 0.3
    elif count >= 500:
        return 0.1
    return 0.0


def score_press_mentions(count: int) -> float:
    """Score number of press / food-media mentions 0-1."""
    count = _to_float(count)
    if count >= 10:
        return 1.0
    elif count >= 7:
        return 0.8
    elif count >= 5:
        return 0.6
    elif count >= 3:
        return 0.4
    elif count >= 1:
        return 0.2
    return 0.0


def score_awards_count(count: int) -> float:
    """Score James Beard, Michelin, and similar awards 0-1."""
    count = _to_float(count)
    if count >= 3:
        return 1.0
    elif count == 2:
        return 0.8
    elif count == 1:
        return 0.5
    return 0.0


def score_domain_age(years: float) -> float:
    """Score domain age in years 0-1. Older domains = more established."""
    years = _to_float(years)
    if years >= 10:
        return 1.0
    elif years >= 7:
        return 0.8
    elif years >= 5:
        return 0.6
    elif years >= 3:
        return 0.4
    elif years >= 1:
        return 0.2
    return 0.1


def score_google_rating(rating) -> float:
    """Score Google rating 0-1. Higher is better."""
    if rating is None or rating == 0:
        return 0.0
    rating = _to_float(rating)
    if rating >= 4.7:
        return 1.0
    elif rating >= 4.5:
        return 0.9
    elif rating >= 4.3:
        return 0.7
    elif rating >= 4.0:
        return 0.5
    elif rating >= 3.5:
        return 0.3
    return 0.1


def score_review_count(count: int) -> float:
    """Score Google review volume 0-1. More reviews = stronger signal."""
    count = _to_float(count)
    if count >= 5000:
        return 1.0
    elif count >= 2000:
        return 0.9
    elif count >= 1000:
        return 0.8
    elif count >= 500:
        return 0.6
    elif count >= 200:
        return 0.4
    elif count >= 100:
        return 0.2
    elif count >= 50:
        return 0.1
    return 0.0


def score_avg_likes(count: int) -> float:
    """Score average likes per post 0-1."""
    count = _to_float(count)
    if count >= 5_000:
        return 1.0
    elif count >= 2_000:
        return 0.8
    elif count >= 1_000:
        return 0.6
    elif count >= 500:
        return 0.4
    elif count >= 200:
        return 0.2
    elif count > 0:
        return 0.1
    return 0.0


def score_price_tier(tier: int) -> float:
    """Score price tier ($ count) 0-1. Higher price = stronger lead signal."""
    tier = int(_to_float(tier))
    mapping = {4: 1.0, 3: 0.7, 2: 0.4, 1: 0.2}
    return mapping.get(tier, 0.0)


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def score_source_quality(value) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Map each weight key -> (scoring function, DataFrame column name)
# ---------------------------------------------------------------------------
_SCORE_DISPATCH = {
    "avg_video_views":        (score_avg_video_views,        "avg_video_views"),
    "follower_count":         (score_follower_count,         "follower_count"),
    "review_count":           (score_review_count,           "review_count"),
    "press_mentions":         (score_press_mentions,         "press_mentions"),
    "awards_count":           (score_awards_count,           "awards_count"),
    "google_rating":          (score_google_rating,          "rating"),
    "avg_likes":              (score_avg_likes,              "avg_likes"),
    "price_tier":             (score_price_tier,             "price_tier"),
}


def compute_lead_score(row: pd.Series) -> float:
    """Compute total lead score for a single row."""
    w = SCORING_WEIGHTS
    score = 0.0

    # Composite reservation difficulty (uses full row for sub-signals)
    score += score_reservation_difficulty_composite(row) * w["reservation_difficulty"]

    # Numeric / tiered signals
    for weight_key, (fn, col) in _SCORE_DISPATCH.items():
        default = None if col == "rating" else 0
        score += fn(row.get(col, default)) * w[weight_key]

    # Boolean signals
    score += (1.0 if row.get("has_email_signup") else 0.0) * w["has_email_signup"]
    score += (1.0 if row.get("has_ecommerce") else 0.0) * w["has_ecommerce"]

    return round(score, 1)


BUTCHER_SCORING_WEIGHTS = {
    "has_ecommerce": 10,
    "has_email_signup": 5,
    "has_meat_box": 12,
    "has_csa_or_share": 10,
    "has_preorder": 8,
    "ships_meat": 7,
    "has_pickup": 4,
    "has_subscription_language": 10,
    "animal_welfare_signal": 5,
    "whole_animal_signal": 5,
    "dry_aged_signal": 4,
    "google_rating": 8,
    "review_count": 5,
    "follower_count": 5,
    "avg_video_views": 3,
    "avg_likes": 2,
    "press_mentions": 5,
    "awards_count": 2,
    "source_quality_score": 5,
}


def compute_butcher_lead_score(row: pd.Series) -> float:
    """Compute butcher-specific score without reservation difficulty."""
    w = BUTCHER_SCORING_WEIGHTS
    score = 0.0

    for col in [
        "has_ecommerce", "has_email_signup", "has_meat_box", "has_csa_or_share",
        "has_preorder", "ships_meat", "has_pickup", "has_subscription_language",
        "animal_welfare_signal", "whole_animal_signal", "dry_aged_signal",
    ]:
        score += (1.0 if _truthy(row.get(col, False)) else 0.0) * w[col]

    score += score_google_rating(row.get("rating")) * w["google_rating"]
    score += score_review_count(row.get("review_count", 0)) * w["review_count"]
    score += score_follower_count(row.get("follower_count", 0)) * w["follower_count"]
    score += score_avg_video_views(row.get("avg_video_views", 0)) * w["avg_video_views"]
    score += score_avg_likes(row.get("avg_likes", 0)) * w["avg_likes"]
    score += score_press_mentions(row.get("press_mentions", 0)) * w["press_mentions"]
    score += score_awards_count(row.get("awards_count", 0)) * w["awards_count"]
    score += score_source_quality(row.get("source_quality_score", 0)) * w["source_quality_score"]

    return round(score, 1)


def _add_tiers(df: pd.DataFrame) -> pd.DataFrame:
    def get_tier(score):
        if score >= 55:
            return "A - Hot Lead"
        elif score >= 35:
            return "B - Warm Lead"
        elif score >= 20:
            return "C - Worth a Look"
        return "D - Low Priority"

    df["tier"] = df["lead_score"].apply(get_tier)
    return df


def _add_butcher_tiers(df: pd.DataFrame) -> pd.DataFrame:
    def get_tier(score):
        if score >= 40:
            return "A - Hot Lead"
        elif score >= 20:
            return "B - Warm Lead"
        elif score >= 10:
            return "C - Worth a Look"
        return "D - Low Priority"

    df["tier"] = df["lead_score"].apply(get_tier)
    return df


def score_leads(df: pd.DataFrame) -> pd.DataFrame:
    """Score all leads and sort by score descending."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: SCORING LEADS")
    print(f"{'='*60}")

    df["lead_score"] = df.apply(compute_lead_score, axis=1)

    # Add tier labels
    df = _add_tiers(df)

    df = df.sort_values("lead_score", ascending=False).reset_index(drop=True)

    # Print summary
    tier_counts = df["tier"].value_counts().sort_index()
    print(f"\nLead distribution:")
    for tier, count in tier_counts.items():
        print(f"  {tier}: {count}")

    print(f"\nTop 20 leads:")
    top_cols = [
        "name", "address", "business_type", "lead_score", "tier",
        "reservation_difficulty", "follower_count", "press_mentions",
        "awards_count",
    ]
    available_cols = [c for c in top_cols if c in df.columns]
    print(df[available_cols].head(20).to_string())

    return df


def score_butcher_leads(df: pd.DataFrame) -> pd.DataFrame:
    """Score butcher leads with butcher-specific purchase-readiness weights."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: SCORING BUTCHER LEADS")
    print(f"{'='*60}")

    df = df.copy()
    df["lead_score"] = df.apply(compute_butcher_lead_score, axis=1)
    df = _add_butcher_tiers(df)
    df = df.sort_values("lead_score", ascending=False).reset_index(drop=True)

    tier_counts = df["tier"].value_counts().sort_index()
    print(f"\nButcher lead distribution:")
    for tier, count in tier_counts.items():
        print(f"  {tier}: {count}")

    print(f"\nTop 20 butcher leads:")
    top_cols = [
        "name", "address", "lead_score", "tier", "has_meat_box",
        "has_csa_or_share", "has_preorder", "ships_meat",
        "has_subscription_language", "has_ecommerce", "review_count",
    ]
    available_cols = [c for c in top_cols if c in df.columns]
    print(df[available_cols].head(20).to_string())

    return df
