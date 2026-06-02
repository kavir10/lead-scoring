"""
Augment fresh butcher Facebook output with Instagram follower counts.

The canonical convention in this repo is:
    follower_count = ig_followers + fb_likes

This script fetches Instagram profile counts through Apify, merges them into
the Facebook-augmented butcher file, and rewrites the canonical
custom-serper-scoring output with combined social counts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
from apify_client import ApifyClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import APIFY_API_TOKEN


RUN_DIR = ROOT / "output" / "fresh_butcher_leads_20260531"
ACTOR_ID = "apify/instagram-profile-scraper"
USERNAME_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")
SKIP_USERNAMES = {"p", "reel", "reels", "stories", "explore", "accounts", "share"}


def extract_username(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return ""
    if "instagram.com" not in text and re.fullmatch(r"[A-Za-z0-9_.]+", text):
        username = text
    else:
        match = USERNAME_RE.search(text)
        if not match:
            return ""
        username = match.group(1)
    username = username.strip(".").lower()
    return "" if username in SKIP_USERNAMES else username


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def load_existing(path: Path) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def load_usernames(df: pd.DataFrame) -> list[str]:
    usernames: list[str] = []
    for _, row in df.iterrows():
        username = extract_username(row.get("ig_username", "")) or extract_username(row.get("instagram_url", ""))
        if username:
            usernames.append(username)
    return sorted(set(usernames))


def scrape_batch(usernames: list[str], batch_label: str) -> pd.DataFrame:
    client = ApifyClient(APIFY_API_TOKEN)
    print(f"  Apify IG batch {batch_label}: {len(usernames)} usernames", flush=True)
    run = client.actor(ACTOR_ID).call(run_input={"usernames": usernames})
    items = client.dataset(run["defaultDatasetId"]).list_items().items
    rows: list[dict] = []
    for item in items:
        username = str(item.get("username") or "").lower()
        if not username:
            continue
        rows.append(
            {
                "ig_username": username,
                "ig_followers": item.get("followersCount", 0) or 0,
                "ig_posts": item.get("postsCount", 0) or 0,
                "ig_full_name": item.get("fullName") or item.get("full_name") or "",
                "ig_is_private": item.get("private") if "private" in item else item.get("isPrivate"),
                "ig_is_verified": item.get("verified") if "verified" in item else item.get("isVerified"),
                "ig_count_source": "apify/instagram-profile-scraper",
                "ig_profile_url": item.get("url") or f"https://www.instagram.com/{username}/",
            }
        )
    return pd.DataFrame(rows)


def append_checkpoint(output_path: Path, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = load_existing(output_path)
    combined = pd.concat([existing, new_rows], ignore_index=True)
    if not combined.empty and "ig_username" in combined.columns:
        combined["ig_username"] = combined["ig_username"].fillna("").astype(str).str.lower()
        combined = combined.drop_duplicates("ig_username", keep="last")
    write_csv(combined, output_path)
    return combined


def recover_instagram_counts(
    usernames: list[str],
    counts_path: Path,
    batch_size: int,
    workers: int,
    limit: int,
    skip_fetch: bool,
) -> pd.DataFrame:
    if not APIFY_API_TOKEN:
        raise SystemExit("APIFY_API_TOKEN is missing")

    if limit:
        usernames = usernames[:limit]
    existing = load_existing(counts_path)
    done = set(existing.get("ig_username", pd.Series(dtype=str)).fillna("").astype(str).str.lower()) if not existing.empty else set()
    pending = [u for u in usernames if u not in done]

    print(f"Unique IG usernames: {len(usernames):,}")
    print(f"Already checkpointed: {len(done):,}")
    print(f"Pending: {len(pending):,}")

    if skip_fetch:
        return existing

    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    recovered = existing
    if batches:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(scrape_batch, batch, f"{idx + 1}/{len(batches)}"): idx
                for idx, batch in enumerate(batches)
            }
            completed = 0
            for future in as_completed(futures):
                rows = future.result()
                recovered = append_checkpoint(counts_path, rows)
                completed += 1
                nonzero = numeric(recovered.get("ig_followers", pd.Series(dtype=int))).gt(0).sum() if not recovered.empty else 0
                print(
                    f"  Completed {completed}/{len(batches)} batches | "
                    f"checkpoint rows {len(recovered):,} | nonzero {nonzero:,}",
                    flush=True,
                )
    return load_existing(counts_path)


def merge_counts(df: pd.DataFrame, recovered: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = df.copy()
    for col in ["ig_username", "ig_followers", "ig_posts", "ig_full_name", "ig_is_private", "ig_is_verified", "ig_count_source"]:
        if col not in df.columns:
            df[col] = "" if col not in {"ig_followers", "ig_posts"} else 0
        df[col] = df[col].astype(object)

    df["ig_username"] = df["ig_username"].fillna("").astype(str).apply(extract_username)
    missing_user = df["ig_username"].eq("")
    df.loc[missing_user, "ig_username"] = df.loc[missing_user, "instagram_url"].apply(extract_username)

    if recovered.empty:
        df["ig_followers"] = numeric(df["ig_followers"])
        df["ig_posts"] = numeric(df["ig_posts"])
        return df, 0

    recovered = recovered.copy()
    recovered["ig_username"] = recovered["ig_username"].fillna("").astype(str).str.lower()
    recovered["ig_followers"] = numeric(recovered["ig_followers"])
    recovered["ig_posts"] = numeric(recovered["ig_posts"])
    lookup = recovered[recovered["ig_followers"].gt(0)].drop_duplicates("ig_username", keep="last").set_index("ig_username")

    merged = 0
    for idx, row in df.iterrows():
        username = str(row.get("ig_username", "")).lower()
        if not username or username not in lookup.index:
            continue
        data = lookup.loc[username]
        df.at[idx, "ig_followers"] = int(data["ig_followers"])
        df.at[idx, "ig_posts"] = int(data["ig_posts"])
        df.at[idx, "ig_full_name"] = data.get("ig_full_name", "")
        df.at[idx, "ig_is_private"] = str(data.get("ig_is_private", ""))
        df.at[idx, "ig_is_verified"] = str(data.get("ig_is_verified", ""))
        df.at[idx, "ig_count_source"] = data.get("ig_count_source", "apify/instagram-profile-scraper")
        merged += 1

    df["ig_followers"] = numeric(df["ig_followers"])
    df["ig_posts"] = numeric(df["ig_posts"])
    return df, merged


def write_custom_output(df: pd.DataFrame, custom_output: Path) -> None:
    out = df.copy()
    if "business_type" not in out.columns:
        out["business_type"] = "butcher"
    if "lead_score" not in out.columns and "butcher_seed_score" in out.columns:
        out["lead_score"] = out["butcher_seed_score"]
    if "tier" not in out.columns:
        out["tier"] = "Fresh Butcher Lead"
    if "has_ecommerce" not in out.columns and "has_ecommerce_signal" in out.columns:
        out["has_ecommerce"] = out["has_ecommerce_signal"]

    custom_cols = [
        "name", "address", "city", "state", "phone", "website", "business_type",
        "lead_score", "tier",
        "review_count", "rating",
        "instagram_url", "ig_followers",
        "facebook_url", "fb_likes",
        "has_email_signup", "has_ecommerce",
    ]
    custom_cols = [col for col in custom_cols if col in out.columns]
    write_csv(out[custom_cols], custom_output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge butcher IG follower counts and recompute combined follower_count.")
    parser.add_argument("--input", type=Path, default=RUN_DIR / "fresh_butcher_facebook_augmented_20260601.csv")
    parser.add_argument("--counts-output", type=Path, default=RUN_DIR / "fresh_butcher_apify_ig_counts_20260601.csv")
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_butcher_social_augmented_20260601.csv")
    parser.add_argument("--custom-output", type=Path, default=ROOT / "output" / "custom-serper-scoring_kavir_20260601_butcher_5000_top.csv")
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    df = pd.read_csv(args.input, low_memory=False)
    usernames = load_usernames(df)
    recovered = recover_instagram_counts(usernames, args.counts_output, args.batch_size, args.workers, args.limit, args.skip_fetch)
    df, merged = merge_counts(df, recovered)

    fb = numeric(df["fb_likes"]) if "fb_likes" in df.columns else pd.Series(0, index=df.index, dtype=int)
    ig = numeric(df["ig_followers"])
    df["follower_count"] = ig + fb

    write_csv(df, args.output)
    write_custom_output(df, args.custom_output)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(df)),
        "unique_ig_usernames": int(len(usernames)),
        "ig_counts_checkpoint_rows": int(len(recovered)),
        "ig_counts_merged_rows": int(merged),
        "rows_with_ig_followers": int(ig.gt(0).sum()),
        "rows_with_fb_likes": int(fb.gt(0).sum()),
        "rows_with_combined_follower_count": int(df["follower_count"].gt(0).sum()),
        "median_ig_followers_for_counted": float(ig[ig.gt(0)].median()) if ig.gt(0).any() else 0,
        "median_fb_likes_for_counted": float(fb[fb.gt(0)].median()) if fb.gt(0).any() else 0,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "files": {
            "counts": str(args.counts_output),
            "augmented": str(args.output),
            "custom_serper_top": str(args.custom_output),
        },
    }
    summary_path = args.output.with_name(args.output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
