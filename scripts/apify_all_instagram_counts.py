"""
Fetch Apify Instagram profile counts for every Instagram URL in the bakery list.

This is checkpointed and resumable. It stores one row per returned Instagram
profile, then merges counts back into the Clay input files.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from apify_client import ApifyClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import APIFY_API_TOKEN

RUN_DIR = ROOT / "output" / "fresh_bakery_leads_20260525"
ACTOR_ID = "apify/instagram-profile-scraper"
USERNAME_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")
SKIP_USERNAMES = {"p", "reel", "reels", "stories", "explore", "accounts", "share"}


def extract_username(value: str) -> str:
    text = str(value or "").strip()
    if not text:
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


def load_usernames(input_path: Path) -> list[str]:
    df = pd.read_csv(input_path)
    if "instagram_url" not in df.columns:
        raise SystemExit(f"{input_path} has no instagram_url column")
    usernames = []
    for _, row in df.iterrows():
        username = extract_username(row.get("ig_username", "")) or extract_username(row.get("instagram_url", ""))
        if username:
            usernames.append(username)
    return sorted(set(usernames))


def load_existing(path: Path) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()


def scrape_batch(usernames: list[str], batch_label: str) -> pd.DataFrame:
    client = ApifyClient(APIFY_API_TOKEN)
    print(f"  Apify batch {batch_label}: {len(usernames)} usernames", flush=True)
    run = client.actor(ACTOR_ID).call(run_input={"usernames": usernames})
    items = client.dataset(run["defaultDatasetId"]).list_items().items
    rows: list[dict] = []
    for item in items:
        username = str(item.get("username") or "").lower()
        rows.append(
            {
                "ig_username": username,
                "ig_followers_apify_all": item.get("followersCount", 0) or 0,
                "ig_posts_apify_all": item.get("postsCount", 0) or 0,
                "ig_full_name_apify_all": item.get("fullName") or item.get("full_name") or "",
                "ig_is_private_apify_all": item.get("private") if "private" in item else item.get("isPrivate"),
                "ig_is_verified_apify_all": item.get("verified") if "verified" in item else item.get("isVerified"),
                "ig_apify_all_url": item.get("url") or f"https://www.instagram.com/{username}/",
            }
        )
    return pd.DataFrame(rows)


def append_recovered(output_path: Path, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = load_existing(output_path)
    combined = pd.concat([existing, new_rows], ignore_index=True)
    if not combined.empty and "ig_username" in combined.columns:
        combined["ig_username"] = combined["ig_username"].fillna("").astype(str).str.lower()
        combined = combined.drop_duplicates("ig_username", keep="last")
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    combined.to_csv(tmp, index=False)
    tmp.replace(output_path)
    return combined


def merge_into_file(source_path: Path, recovered: pd.DataFrame, output_path: Path) -> dict:
    df = pd.read_csv(source_path)
    if "instagram_url" not in df.columns:
        return {"file": str(source_path), "rows": len(df), "merged": 0}

    if "ig_username" not in df.columns:
        df["ig_username"] = ""
    df["ig_username"] = df["ig_username"].fillna("").astype(str).apply(extract_username)
    missing_user = df["ig_username"].eq("")
    df.loc[missing_user, "ig_username"] = df.loc[missing_user, "instagram_url"].apply(extract_username)

    recovered = recovered.copy()
    recovered["ig_username"] = recovered["ig_username"].fillna("").astype(str).str.lower()
    recovered["ig_followers_apify_all"] = pd.to_numeric(recovered["ig_followers_apify_all"], errors="coerce").fillna(0)
    recovered["ig_posts_apify_all"] = pd.to_numeric(recovered["ig_posts_apify_all"], errors="coerce").fillna(0)
    lookup = recovered[recovered["ig_followers_apify_all"].gt(0)].drop_duplicates("ig_username", keep="last").set_index("ig_username")

    for col in ["ig_followers", "ig_posts"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "ig_count_source" not in df.columns:
        df["ig_count_source"] = ""
    df["ig_apify_all_recovered"] = False

    merged = 0
    for idx, row in df.iterrows():
        username = str(row.get("ig_username", "")).lower()
        if not username or username not in lookup.index:
            continue
        data = lookup.loc[username]
        df.at[idx, "ig_followers"] = data["ig_followers_apify_all"]
        df.at[idx, "ig_posts"] = data["ig_posts_apify_all"]
        df.at[idx, "ig_full_name"] = data.get("ig_full_name_apify_all", "")
        df.at[idx, "ig_is_private"] = data.get("ig_is_private_apify_all", "")
        df.at[idx, "ig_count_source"] = "apify_instagram_profile_scraper_all"
        df.at[idx, "ig_apify_all_recovered"] = True
        merged += 1

    df.to_csv(output_path, index=False)
    return {
        "file": str(source_path),
        "output": str(output_path),
        "rows": int(len(df)),
        "rows_with_instagram": int(df["instagram_url"].fillna("").astype(str).str.strip().ne("").sum()),
        "rows_with_counts": int(pd.to_numeric(df["ig_followers"], errors="coerce").fillna(0).gt(0).sum()),
        "merged_rows": int(merged),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Apify counts for all bakery Instagram URLs.")
    parser.add_argument("--input", type=Path, default=RUN_DIR / "fresh_bakery_clay_input_top_5000.csv")
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_bakery_apify_all_ig_counts_recovered.csv")
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not APIFY_API_TOKEN:
        raise SystemExit("APIFY_API_TOKEN is missing")

    usernames = load_usernames(args.input)
    if args.limit:
        usernames = usernames[: args.limit]

    existing = load_existing(args.output)
    done = set(existing.get("ig_username", pd.Series(dtype=str)).fillna("").astype(str).str.lower()) if not existing.empty else set()
    pending = [u for u in usernames if u not in done]

    print(f"Unique IG usernames: {len(usernames):,}")
    print(f"Already recovered/checkpointed: {len(done):,}")
    print(f"Pending: {len(pending):,}")

    batches = [pending[i : i + args.batch_size] for i in range(0, len(pending), args.batch_size)]
    started = time.monotonic()
    recovered = existing

    if batches:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(scrape_batch, batch, f"{idx + 1}/{len(batches)}"): idx
                for idx, batch in enumerate(batches)
            }
            completed = 0
            for future in as_completed(futures):
                rows = future.result()
                recovered = append_recovered(args.output, rows)
                completed += 1
                nonzero = pd.to_numeric(recovered.get("ig_followers_apify_all", 0), errors="coerce").fillna(0).gt(0).sum() if not recovered.empty else 0
                print(
                    f"  Completed {completed}/{len(batches)} batches | "
                    f"checkpoint rows {len(recovered):,} | nonzero {nonzero:,}",
                    flush=True,
                )

    recovered = load_existing(args.output)
    merge_targets = [
        RUN_DIR / "fresh_bakery_clay_input_top_4000.csv",
        RUN_DIR / "fresh_bakery_clay_input_top_5000.csv",
        RUN_DIR / "fresh_bakery_clay_input_top_6000.csv",
        RUN_DIR / "fresh_bakery_clay_input_top_8015.csv",
        RUN_DIR / "fresh_bakery_top_2000_final_apify_counts.csv",
    ]
    merge_summaries = []
    for target in merge_targets:
        if not target.exists():
            continue
        output_path = target.with_name(target.stem + "_apify_all_counts.csv")
        merge_summaries.append(merge_into_file(target, recovered, output_path))

    summary = {
        "input": str(args.input),
        "unique_usernames": len(usernames),
        "checkpoint_rows": int(len(recovered)),
        "nonzero_counts": int(pd.to_numeric(recovered.get("ig_followers_apify_all", 0), errors="coerce").fillna(0).gt(0).sum()) if not recovered.empty else 0,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "recovered_counts_file": str(args.output),
        "merged_files": merge_summaries,
    }
    summary_path = args.output.with_name("fresh_bakery_apify_all_ig_counts_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
