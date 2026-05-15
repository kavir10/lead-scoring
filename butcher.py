"""
Butcher-specific national discovery helpers.

State + city tables live in `core.geo` so every pipeline shares them.
This module keeps butcher-specific bits: eligible-city loading, the
`why_high_quality` outreach rationale, and timestamped output paths.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd

# Re-exports for back-compat: prior versions defined these locally here.
from core.geo import (
    BANNED_STATES,
    STATE_ABBREVIATIONS,
    STATE_NAMES,
    TOP_US_CITIES,
)


PLACE_SUFFIX_RE = re.compile(
    r"\s+("
    r"city|town|village|borough|CDP|municipality|metro government|"
    r"urban county|unified government|charter township|township"
    r")$",
    re.I,
)


def _clean_place_name(name: str) -> str:
    """Remove Census legal/statistical suffixes from place names."""
    return PLACE_SUFFIX_RE.sub("", str(name).strip()).strip()


def load_eligible_butcher_cities(
    min_population: int = 25_000,
    cities_path: str | None = None,
) -> pd.DataFrame:
    """Load the static top-city list for butcher discovery."""
    if cities_path:
        raw = pd.read_csv(cities_path, sep=None, engine="python")
        if not {"NAME", "USPS", "POPULATION"}.issubset(raw.columns):
            raise ValueError("City source must include NAME, USPS, and POPULATION columns")
        df = raw[["NAME", "USPS", "POPULATION"]].copy()
        df["state"] = df["USPS"].astype(str).str.upper().str.strip()
        df["population"] = pd.to_numeric(df["POPULATION"], errors="coerce").fillna(0).astype(int)
    else:
        df = pd.DataFrame(TOP_US_CITIES, columns=["NAME", "USPS", "state_name", "POPULATION"])
        df["state"] = df["USPS"]
        df["population"] = df["POPULATION"]

    df["city"] = df["NAME"].apply(_clean_place_name)
    df["state_name"] = df["state"].map(STATE_NAMES).fillna(df["state"])

    df = df[(df["population"] >= min_population) & ~df["state"].isin(BANNED_STATES)]
    df = df[df["city"].str.len() > 0]
    df["location"] = df["city"] + ", " + df["state_name"]

    return (
        df[["city", "state", "state_name", "population", "location"]]
        .drop_duplicates(subset=["city", "state"])
        .sort_values("population", ascending=False)
        .reset_index(drop=True)
    )


def save_eligible_cities(df: pd.DataFrame, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "1_cities_eligible.csv")
    df.to_csv(path, index=False)
    return path


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _to_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def build_why_high_quality(row: pd.Series) -> str:
    """Create a compact outreach rationale from the strongest butcher signals."""
    reasons = []

    bool_reasons = [
        ("has_meat_box", "meat box"),
        ("has_csa_or_share", "CSA/meat share"),
        ("has_preorder", "preorder flow"),
        ("ships_meat", "shipping"),
        ("has_pickup", "pickup"),
        ("has_subscription_language", "subscription language"),
        ("has_ecommerce", "ecommerce"),
        ("has_email_signup", "email signup"),
        ("animal_welfare_signal", "animal welfare positioning"),
        ("whole_animal_signal", "whole-animal positioning"),
        ("dry_aged_signal", "dry-aged positioning"),
    ]
    for col, label in bool_reasons:
        if _truthy(row.get(col, False)):
            reasons.append(label)

    rating = row.get("rating")
    review_count = _to_int(row.get("review_count", 0))
    if rating and review_count:
        reasons.append(f"{rating} stars / {review_count} reviews")

    followers = _to_int(row.get("follower_count", 0))
    if followers >= 5_000:
        reasons.append(f"{followers:,} social followers")

    press_mentions = _to_int(row.get("press_mentions", 0))
    if press_mentions:
        reasons.append(f"{press_mentions} press mentions")

    awards = str(row.get("awards_list", "") or "").strip()
    if awards:
        reasons.append(f"awards: {awards}")

    source = str(row.get("butcher_source", "") or row.get("source", "") or "").strip()
    if source and source != "google_maps":
        reasons.append(f"source: {source}")

    return "; ".join(reasons[:6])


def add_why_high_quality(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["why_high_quality"] = df.apply(build_why_high_quality, axis=1)
    return df


def timestamped_path(output_dir: str, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"{prefix}_{stamp}.csv")
