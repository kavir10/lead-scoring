"""
Fetch public Instagram follower/post counts without Apify.

Uses Instagram's web_profile_info endpoint first, then falls back to public page
meta descriptions when present.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "output" / "fresh_bakery_leads_20260525"

USERNAME_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")
SKIP_USERNAMES = {"p", "reel", "reels", "stories", "explore", "accounts", "share"}
COMPACT_NUM_RE = re.compile(r"([\d,.]+)\s*([KMB])?", re.I)


def extract_username(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    match = USERNAME_RE.search(url)
    if not match:
        return ""
    username = match.group(1).strip(".").lower()
    return "" if username in SKIP_USERNAMES else username


def parse_compact_number(raw: str) -> int | None:
    match = COMPACT_NUM_RE.search(str(raw or ""))
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return int(value * multiplier)


def parse_meta_counts(content: str) -> tuple[int | None, int | None]:
    followers = None
    posts = None
    follower_match = re.search(r"([\d,.]+\s*[KMB]?)\s+Followers", content, flags=re.I)
    post_match = re.search(r"([\d,.]+\s*[KMB]?)\s+Posts", content, flags=re.I)
    if follower_match:
        followers = parse_compact_number(follower_match.group(1))
    if post_match:
        posts = parse_compact_number(post_match.group(1))
    return followers, posts


def fetch_instagram_counts(username: str) -> dict:
    result = {
        "ig_username": username,
        "ig_followers": None,
        "ig_posts": None,
        "ig_full_name": "",
        "ig_is_private": None,
        "ig_count_source": "",
        "ig_fetch_status": "",
        "ig_fetch_error": "",
    }
    if not username:
        result["ig_fetch_error"] = "missing_username"
        return result

    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "x-ig-app-id": "936619743392459",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-requested-with": "XMLHttpRequest",
        "referer": f"https://www.instagram.com/{username}/",
    }

    try:
        resp = requests.get(api_url, headers=headers, impersonate="chrome120", timeout=20)
        result["ig_fetch_status"] = str(resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            user = (data.get("data") or {}).get("user") or {}
            result["ig_followers"] = (user.get("edge_followed_by") or {}).get("count")
            result["ig_posts"] = (user.get("edge_owner_to_timeline_media") or {}).get("count")
            result["ig_full_name"] = user.get("full_name") or ""
            result["ig_is_private"] = user.get("is_private")
            result["ig_count_source"] = "web_profile_info"
            return result
    except Exception as exc:
        result["ig_fetch_error"] = type(exc).__name__

    try:
        page_url = f"https://www.instagram.com/{username}/"
        resp = requests.get(page_url, impersonate="chrome120", timeout=20)
        result["ig_fetch_status"] = str(resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all("meta"):
            content = tag.get("content") or ""
            if "followers" not in content.lower() or "posts" not in content.lower():
                continue
            followers, posts = parse_meta_counts(content)
            if followers is not None or posts is not None:
                result["ig_followers"] = followers
                result["ig_posts"] = posts
                result["ig_count_source"] = "page_meta"
                return result
    except Exception as exc:
        result["ig_fetch_error"] = result["ig_fetch_error"] or type(exc).__name__

    if not result["ig_fetch_error"]:
        result["ig_fetch_error"] = "no_counts_found"
    return result


def write_checkpoint(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public Instagram follower/post counts.")
    parser.add_argument("--input", type=Path, default=RUN_DIR / "fresh_bakery_email_crawled.csv")
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_bakery_instagram_counts.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if args.limit:
        df = df.head(args.limit).copy()
    df = df.reset_index(drop=True)

    if "instagram_url" not in df.columns:
        raise SystemExit(f"{args.input} has no instagram_url column")

    df["ig_username"] = df["instagram_url"].apply(extract_username)
    for col in ["ig_followers", "ig_posts", "ig_full_name", "ig_is_private", "ig_count_source", "ig_fetch_status", "ig_fetch_error"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(object)

    todo = df.index[df["ig_username"].fillna("").astype(str).str.strip().ne("")].tolist()
    print(f"Fetching Instagram counts for {len(todo):,}/{len(df):,} rows with usernames")

    started = time.monotonic()
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_instagram_counts, str(df.at[i, "ig_username"])): i for i in todo}
        for future in as_completed(futures):
            i = futures[future]
            result = future.result()
            for col, value in result.items():
                df.at[i, col] = value
            completed += 1
            if completed % 25 == 0 or completed == len(todo):
                elapsed = max(time.monotonic() - started, 1)
                got = pd.to_numeric(df["ig_followers"], errors="coerce").fillna(0).gt(0).sum()
                print(f"  {completed:,}/{len(todo):,} | {completed/elapsed:.1f}/s | counts found {got:,}", flush=True)
            if completed % args.checkpoint_every == 0:
                write_checkpoint(df, args.output)

    write_checkpoint(df, args.output)
    found = pd.to_numeric(df["ig_followers"], errors="coerce").fillna(0).gt(0).sum()
    print(f"Counts found: {found:,}/{len(todo):,}")
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
