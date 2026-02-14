"""
Phase 3: Score and rank leads
"""
import numpy as np
import pandas as pd
from config import SCORING_WEIGHTS


def score_reviews(count: int) -> float:
    """Score review count 0-1. More reviews = likely more revenue/traffic."""
    if count >= 1000:
        return 1.0
    elif count >= 500:
        return 0.9
    elif count >= 250:
        return 0.8
    elif count >= 100:
        return 0.6
    elif count >= 50:
        return 0.4
    elif count >= 25:
        return 0.2
    return 0.1


def score_rating(rating) -> float:
    """Score rating 0-1. Higher is better."""
    if rating is None or rating == 0:
        return 0.0
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


def score_ig_followers(count: int) -> float:
    """Score Instagram followers 0-1."""
    if count >= 50000:
        return 1.0
    elif count >= 20000:
        return 0.9
    elif count >= 10000:
        return 0.8
    elif count >= 5000:
        return 0.7
    elif count >= 2000:
        return 0.5
    elif count >= 1000:
        return 0.3
    elif count >= 500:
        return 0.2
    elif count > 0:
        return 0.1
    return 0.0


def score_ig_posts(count: int) -> float:
    """Score Instagram post count 0-1. Active posting = engaged brand."""
    if count >= 500:
        return 1.0
    elif count >= 200:
        return 0.8
    elif count >= 100:
        return 0.6
    elif count >= 50:
        return 0.4
    elif count > 0:
        return 0.2
    return 0.0


def score_fb_likes(count: int) -> float:
    """Score Facebook likes 0-1."""
    if count >= 20000:
        return 1.0
    elif count >= 10000:
        return 0.8
    elif count >= 5000:
        return 0.6
    elif count >= 2000:
        return 0.4
    elif count >= 500:
        return 0.2
    elif count > 0:
        return 0.1
    return 0.0


def compute_lead_score(row: pd.Series) -> float:
    """Compute total lead score for a single row."""
    w = SCORING_WEIGHTS
    score = 0.0

    score += score_reviews(row.get("review_count", 0)) * w["review_count"]
    score += score_rating(row.get("rating")) * w["rating"]
    score += score_ig_followers(row.get("ig_followers", 0)) * w["instagram_followers"]
    score += score_ig_posts(row.get("ig_posts", 0)) * w["instagram_posts"]
    score += score_fb_likes(row.get("fb_likes", 0)) * w["facebook_likes"]
    score += (1.0 if row.get("has_email_signup") else 0.0) * w["has_email_signup"]
    score += (1.0 if row.get("has_ecommerce") else 0.0) * w["has_ecommerce"]
    score += (1.0 if row.get("has_online_ordering") else 0.0) * w["has_online_ordering"]
    score += (1.0 if row.get("website_reachable") else 0.0) * w["website_quality"]

    return round(score, 1)


def score_leads(df: pd.DataFrame) -> pd.DataFrame:
    """Score all leads and sort by score descending."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: SCORING LEADS")
    print(f"{'='*60}")

    df["lead_score"] = df.apply(compute_lead_score, axis=1)

    # Add tier labels
    def get_tier(score):
        if score >= 70:
            return "A - Hot Lead"
        elif score >= 50:
            return "B - Warm Lead"
        elif score >= 30:
            return "C - Worth a Look"
        return "D - Low Priority"

    df["tier"] = df["lead_score"].apply(get_tier)

    df = df.sort_values("lead_score", ascending=False).reset_index(drop=True)

    # Print summary
    tier_counts = df["tier"].value_counts().sort_index()
    print(f"\nLead distribution:")
    for tier, count in tier_counts.items():
        print(f"  {tier}: {count}")

    print(f"\nTop 20 leads:")
    top_cols = ["name", "address", "lead_score", "tier", "review_count", "rating",
                "ig_followers", "has_email_signup", "has_ecommerce"]
    available_cols = [c for c in top_cols if c in df.columns]
    print(df[available_cols].head(20).to_string())

    return df
