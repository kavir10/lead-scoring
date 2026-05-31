"""
Top up missing Instagram follower/post counts using Apify.

This is intentionally scoped to the missing-count rows from the fresh bakery
top-2000 list, then merges recovered counts into updated final CSVs.
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


def scrape_batch(usernames: list[str], batch_label: str) -> list[dict]:
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
                "ig_followers_apify": item.get("followersCount", 0) or 0,
                "ig_posts_apify": item.get("postsCount", 0) or 0,
                "ig_full_name_apify": item.get("fullName") or item.get("full_name") or "",
                "ig_is_private_apify": item.get("private") if "private" in item else item.get("isPrivate"),
                "ig_is_verified_apify": item.get("verified") if "verified" in item else item.get("isVerified"),
                "ig_apify_url": item.get("url") or f"https://www.instagram.com/{username}/",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Use Apify to top up missing bakery IG counts.")
    parser.add_argument("--missing", type=Path, default=RUN_DIR / "fresh_bakery_top_2000_missing_ig_counts.csv")
    parser.add_argument("--top", type=Path, default=RUN_DIR / "fresh_bakery_top_2000_final.csv")
    parser.add_argument("--all-ranked", type=Path, default=RUN_DIR / "fresh_bakery_final_all_ranked.csv")
    parser.add_argument("--output-prefix", type=str, default="fresh_bakery")
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    if not APIFY_API_TOKEN:
        raise SystemExit("APIFY_API_TOKEN is missing")

    missing = pd.read_csv(args.missing)
    usernames = []
    for _, row in missing.iterrows():
        username = extract_username(row.get("ig_username", "")) or extract_username(row.get("instagram_url", ""))
        if username:
            usernames.append(username)
    usernames = sorted(set(usernames))

    print(f"Unique valid missing usernames: {len(usernames):,}")
    if not usernames:
        raise SystemExit("No valid usernames to scrape")

    batches = [usernames[i : i + args.batch_size] for i in range(0, len(usernames), args.batch_size)]
    all_rows: list[dict] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(scrape_batch, batch, f"{idx + 1}/{len(batches)}"): idx
            for idx, batch in enumerate(batches)
        }
        completed = 0
        for future in as_completed(futures):
            batch_rows = future.result()
            all_rows.extend(batch_rows)
            completed += 1
            print(
                f"  Completed {completed}/{len(batches)} batches | recovered rows {len(all_rows):,}",
                flush=True,
            )

    recovered = pd.DataFrame(all_rows)
    recovered_path = RUN_DIR / f"{args.output_prefix}_apify_ig_counts_recovered.csv"
    recovered.to_csv(recovered_path, index=False)

    recovered_nonzero = recovered[pd.to_numeric(recovered["ig_followers_apify"], errors="coerce").fillna(0) > 0].copy()
    recovered_nonzero = recovered_nonzero.drop_duplicates("ig_username", keep="first")
    lookup = recovered_nonzero.set_index("ig_username").to_dict("index")

    def merge_counts(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "ig_username" not in out.columns:
            out["ig_username"] = out["instagram_url"].apply(extract_username)
        else:
            out["ig_username"] = out["ig_username"].fillna("").astype(str).apply(extract_username)
            missing_username = out["ig_username"].eq("")
            out.loc[missing_username, "ig_username"] = out.loc[missing_username, "instagram_url"].apply(extract_username)

        for col in ["ig_followers", "ig_posts"]:
            out[col] = pd.to_numeric(out.get(col, 0), errors="coerce").fillna(0)

        out["ig_count_source"] = out.get("ig_count_source", "").fillna("").astype(str)
        out["ig_apify_recovered"] = False

        for idx, row in out.iterrows():
            if row["ig_followers"] > 0:
                continue
            data = lookup.get(str(row.get("ig_username", "")).lower())
            if not data:
                continue
            out.at[idx, "ig_followers"] = data["ig_followers_apify"]
            out.at[idx, "ig_posts"] = data["ig_posts_apify"]
            out.at[idx, "ig_full_name"] = data["ig_full_name_apify"]
            out.at[idx, "ig_is_private"] = data["ig_is_private_apify"]
            out.at[idx, "ig_count_source"] = "apify_instagram_profile_scraper"
            out.at[idx, "ig_fetch_error"] = ""
            out.at[idx, "ig_apify_recovered"] = True

        return out

    top = merge_counts(pd.read_csv(args.top))
    all_ranked = merge_counts(pd.read_csv(args.all_ranked))

    top_path = RUN_DIR / f"{args.output_prefix}_top_2000_final_apify_counts.csv"
    all_path = RUN_DIR / f"{args.output_prefix}_final_all_ranked_apify_counts.csv"
    still_missing_path = RUN_DIR / f"{args.output_prefix}_top_2000_still_missing_ig_counts.csv"

    top.to_csv(top_path, index=False)
    all_ranked.to_csv(all_path, index=False)
    top[pd.to_numeric(top["ig_followers"], errors="coerce").fillna(0).eq(0) & top["instagram_url"].fillna("").astype(str).str.strip().ne("")].to_csv(still_missing_path, index=False)

    summary = {
        "requested_unique_usernames": len(usernames),
        "apify_rows_returned": int(len(recovered)),
        "apify_nonzero_counts": int(len(recovered_nonzero)),
        "top_2000_counts_after_apify": int(pd.to_numeric(top["ig_followers"], errors="coerce").fillna(0).gt(0).sum()),
        "top_2000_still_missing": int(pd.to_numeric(top["ig_followers"], errors="coerce").fillna(0).eq(0).sum()),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "files": {
            "recovered_counts": str(recovered_path),
            "top_2000_apify_counts": str(top_path),
            "all_ranked_apify_counts": str(all_path),
            "still_missing": str(still_missing_path),
        },
    }
    summary_path = RUN_DIR / f"{args.output_prefix}_apify_ig_counts_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
