"""
Build a focused bakery lead list from the scored corpus.

The default workflow:
1. Load the previously scored/reclassified Serper corpus.
2. Keep independent bakery rows that already show email-signup and Instagram signals.
3. Optionally enrich those Instagram profiles with Apify follower data.
4. Re-score and export the top N bakery leads into a dedicated run folder.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CHAIN_KEYWORDS
from enrich import enrich_instagram
import enrich as enrich_module
from score import score_leads


DEFAULT_SOURCE = Path(
    "output/"
    "custom-serper-scoring_kavir_20260402_"
    "bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_"
    "73915_all_clubs_v2.reclassified_20260422.csv"
)
DEFAULT_RUN_DIR = Path("output/bakery_leads_20260525")


def truthy(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y"})


def present(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def normalize_bool_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["has_email_signup", "has_ecommerce", "has_online_ordering"]:
        if col in df.columns:
            df[col] = truthy(df[col])
    return df


def looks_like_chain(name: str) -> bool:
    text = str(name or "").lower()
    return any(keyword in text for keyword in CHAIN_KEYWORDS)


def load_bakery_candidates(source: Path) -> pd.DataFrame:
    df = pd.read_csv(source)
    df = normalize_bool_columns(df)

    if "business_type" not in df.columns:
        raise ValueError(f"{source} does not include a business_type column")

    bakery = df[df["business_type"].fillna("").astype(str).eq("bakery")].copy()
    bakery = bakery[~bakery["name"].apply(looks_like_chain)].copy()

    if "website" in bakery.columns:
        bakery = bakery[present(bakery["website"])].copy()

    if "phone" in bakery.columns:
        phone_clean = bakery["phone"].fillna("").astype(str).str.replace(r"[^\d]", "", regex=True)
        bakery["_phone_clean"] = phone_clean
    else:
        bakery["_phone_clean"] = ""

    bakery["_has_instagram"] = present(bakery.get("instagram_url", pd.Series(index=bakery.index)))
    bakery["_has_email_signup"] = truthy(bakery.get("has_email_signup", pd.Series(index=bakery.index)))
    bakery["_base_lead_score"] = numeric(bakery.get("lead_score", pd.Series(index=bakery.index)))
    bakery["_review_count_num"] = numeric(bakery.get("review_count", pd.Series(index=bakery.index)))
    bakery["_rating_num"] = numeric(bakery.get("rating", pd.Series(index=bakery.index)))

    # Preferred pool: the user's requested traits, with an existing warm/hot score.
    preferred = bakery[
        bakery["_has_email_signup"]
        & bakery["_has_instagram"]
        & bakery.get("tier", "").isin(["A - Hot Lead", "B - Warm Lead"])
    ].copy()

    # If a future source file is thinner, fall back gracefully while preserving preference order.
    if len(preferred) < 2000:
        preferred = bakery[bakery["_has_email_signup"] & bakery["_has_instagram"]].copy()
    if len(preferred) < 2000:
        preferred = bakery[bakery["_has_email_signup"] | bakery["_has_instagram"]].copy()
    if len(preferred) < 2000:
        preferred = bakery.copy()

    dedupe_cols = ["_phone_clean"] if preferred["_phone_clean"].ne("").any() else ["name", "address"]
    preferred = preferred.sort_values(
        ["_base_lead_score", "_has_email_signup", "_has_instagram", "_review_count_num", "_rating_num"],
        ascending=[False, False, False, False, False],
    )
    preferred = preferred.drop_duplicates(subset=dedupe_cols, keep="first")
    return preferred.reset_index(drop=True)


def add_social_fields(df: pd.DataFrame) -> pd.DataFrame:
    if "ig_followers" not in df.columns:
        df["ig_followers"] = 0
    if "fb_likes" not in df.columns:
        df["fb_likes"] = 0

    df["ig_followers"] = numeric(df["ig_followers"])
    df["fb_likes"] = numeric(df["fb_likes"])
    df["follower_count"] = df["ig_followers"] + df["fb_likes"]

    if "avg_video_views" in df.columns:
        df["avg_video_views"] = numeric(df["avg_video_views"])
    if "avg_likes" in df.columns:
        df["avg_likes"] = numeric(df["avg_likes"])

    return df


def rank_final(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    df = normalize_bool_columns(df.copy())
    df = add_social_fields(df)
    scored = score_leads(df)

    scored["_email_rank"] = truthy(scored["has_email_signup"]).astype(int)
    scored["_instagram_rank"] = present(scored["instagram_url"]).astype(int)
    scored["_ig_followers_rank"] = numeric(scored["ig_followers"])
    scored["_review_count_rank"] = numeric(scored["review_count"])

    scored["bakery_priority_score"] = (
        numeric(scored["lead_score"])
        + scored["_email_rank"] * 8
        + scored["_instagram_rank"] * 5
        + scored["_ig_followers_rank"].apply(lambda x: min(12.0, math.log10(x + 1) * 2.4))
        + scored["_review_count_rank"].apply(lambda x: min(4.0, math.log10(x + 1)))
    ).round(2)

    scored = scored.sort_values(
        ["bakery_priority_score", "lead_score", "ig_followers", "review_count", "rating"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    scored.insert(0, "rank", range(1, len(scored) + 1))
    return scored.head(limit).copy()


def write_outputs(df: pd.DataFrame, candidates: pd.DataFrame, run_dir: Path, limit: int, source: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    final_cols = [
        "rank", "name", "address", "city", "state", "phone", "website", "business_type",
        "bakery_priority_score", "lead_score", "tier",
        "has_email_signup", "has_ecommerce", "has_online_ordering",
        "instagram_url", "ig_username", "ig_followers", "ig_posts", "ig_is_business",
        "avg_likes", "avg_video_views", "facebook_url", "fb_likes", "follower_count",
        "rating", "review_count", "price_tier",
        "press_mentions", "press_sources", "awards_count", "awards_list",
        "cid", "latitude", "longitude", "search_query", "search_city",
        "google_type", "google_types", "match_confidence", "reclass_action",
    ]
    final_cols = [c for c in final_cols if c in df.columns]

    final_path = run_dir / f"bakery_leads_top_{limit}_20260525.csv"
    candidates_path = run_dir / "bakery_candidates_enriched.csv"
    df[final_cols].to_csv(final_path, index=False)
    candidates.to_csv(candidates_path, index=False)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        "candidate_rows": int(len(candidates)),
        "final_rows": int(len(df)),
        "final_with_email_signup": int(truthy(df["has_email_signup"]).sum()) if "has_email_signup" in df else 0,
        "final_with_instagram_url": int(present(df["instagram_url"]).sum()) if "instagram_url" in df else 0,
        "final_with_ig_followers": int((numeric(df.get("ig_followers", pd.Series(index=df.index))) > 0).sum()),
        "median_ig_followers": float(numeric(df.get("ig_followers", pd.Series(index=df.index))).median()),
        "median_lead_score": float(numeric(df["lead_score"]).median()) if "lead_score" in df else 0,
        "median_priority_score": float(numeric(df["bakery_priority_score"]).median()),
        "files": {
            "top_leads": str(final_path),
            "enriched_candidates": str(candidates_path),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top independent bakery leads.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--enrich-instagram", action="store_true")
    args = parser.parse_args()

    candidates = load_bakery_candidates(args.source)
    args.run_dir.mkdir(parents=True, exist_ok=True)

    seed_path = args.run_dir / "bakery_candidates_seed.csv"
    candidates.to_csv(seed_path, index=False)
    print(f"Seed candidates: {len(candidates)} -> {seed_path}")

    enriched = candidates
    if args.enrich_instagram:
        enrich_module.OUTPUT_DIR = str(args.run_dir)
        enriched = enrich_instagram(candidates.copy())

    final = rank_final(enriched, args.limit)
    write_outputs(final, enriched, args.run_dir, args.limit, args.source)


if __name__ == "__main__":
    main()
