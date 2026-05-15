"""Phase 1: Fetch posts from @beli_eats via Apify."""
import argparse
import json
import os
import sys

from dotenv import load_dotenv

from core.apify import run_actor

load_dotenv()

ACTOR = "apify/instagram-post-scraper"

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch(username: str, limit: int) -> list[dict]:
    print(f"  Calling {ACTOR} for @{username}, limit={limit}...", flush=True)
    items = run_actor(ACTOR, {"username": [username], "resultsLimit": limit})
    print(f"  Got {len(items)} posts", flush=True)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", default="beli_eats")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = args.out or os.path.join(OUT_DIR, f"raw_posts_{args.limit}.json")
    items = fetch(args.username, args.limit)

    with open(out_path, "w") as f:
        json.dump(items, f, indent=2, default=str)
    print(f"  Saved -> {out_path}", flush=True)

    # quick summary
    for i, it in enumerate(items):
        cap = (it.get("caption") or "").replace("\n", " ")[:80]
        n_imgs = len(it.get("images") or []) + len(it.get("childPosts") or [])
        print(f"  [{i+1}] {it.get('shortCode')} type={it.get('type')} imgs={n_imgs} | {cap}", flush=True)


if __name__ == "__main__":
    main()
