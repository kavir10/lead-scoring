"""
Fetch IG posts + tagged-locations for each seed handle.

Uses the Apify IG profile/post scraper. Writes raw JSON to
output/social_graph/raw_<handle>_<YYYYMMDD>.json so aggregation can run
offline without re-burning Apify spend.

Strategy: docs/strategies/01_somm_chef_ig_graph.md

Usage:
    python -m social_graph.fetch_seed_posts                    # all seeds
    python -m social_graph.fetch_seed_posts --handle danielboulud
    python -m social_graph.fetch_seed_posts --limit 5          # first 5 seeds
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from awards._lib import ROOT


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

SEED_CSV = Path(__file__).with_name("industry_seeds.csv")
RAW_DIR = ROOT / "output" / "social_graph" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
# Use the existing actor IDs from main pipeline config.
APIFY_ACTOR_IG_PROFILE = os.environ.get("APIFY_ACTOR_IG_PROFILE", "apify/instagram-profile-scraper")
APIFY_ACTOR_IG_POST = os.environ.get("APIFY_ACTOR_IG_POST", "apify/instagram-post-scraper")

POSTS_PER_SEED = 100


def _load_seeds() -> list[dict]:
    if not SEED_CSV.exists():
        return []
    out: list[dict] = []
    with SEED_CSV.open() as f:
        for row in csv.DictReader(f):
            handle = (row.get("ig_handle") or "").strip().lstrip("@")
            if not handle:
                continue
            out.append({
                "name": row.get("name", "").strip(),
                "role": row.get("role", "").strip(),
                "source": row.get("source", "").strip(),
                "handle": handle,
                "weight": int(row.get("seed_weight") or 5),
            })
    return out


def _fetch_seed(handle: str, *, posts_per_seed: int = POSTS_PER_SEED) -> dict:
    if not APIFY_API_TOKEN:
        return {"error": "APIFY_API_TOKEN missing"}
    try:
        from apify_client import ApifyClient
    except ImportError:
        return {"error": "apify-client not installed"}
    client = ApifyClient(APIFY_API_TOKEN)
    try:
        run = client.actor(APIFY_ACTOR_IG_POST).call(run_input={
            "username": [handle],
            "resultsLimit": posts_per_seed,
            "skipPinnedPosts": False,
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        return {"handle": handle, "posts": items}
    except Exception as e:
        return {"handle": handle, "error": str(e)}


def fetch_all(*, handle: str | None = None, limit: int | None = None) -> None:
    seeds = _load_seeds()
    if handle:
        seeds = [s for s in seeds if s["handle"] == handle.lstrip("@")]
        if not seeds:
            print(f"  [seed_posts] no seed found for handle={handle}", flush=True)
            return
    if limit:
        seeds = seeds[:limit]
    stamp = datetime.now().strftime("%Y%m%d")
    print(f"  [seed_posts] fetching {len(seeds)} seeds", flush=True)
    for s in seeds:
        out_path = RAW_DIR / f"{s['handle']}_{stamp}.json"
        if out_path.exists():
            print(f"  [seed_posts] cached: {s['handle']}", flush=True)
            continue
        print(f"  [seed_posts] fetching @{s['handle']} ({s['name']})", flush=True)
        result = _fetch_seed(s["handle"])
        result["seed_meta"] = s
        out_path.write_text(json.dumps(result, indent=2))
        post_count = len(result.get("posts") or [])
        print(f"  [seed_posts] @{s['handle']} -> {post_count} posts -> {out_path.relative_to(ROOT)}", flush=True)
        time.sleep(1.0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--handle", type=str, help="Single seed handle (no @)")
    p.add_argument("--limit", type=int, help="Cap seed count for testing")
    args = p.parse_args()
    fetch_all(handle=args.handle, limit=args.limit)


if __name__ == "__main__":
    main()
