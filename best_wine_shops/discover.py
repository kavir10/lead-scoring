"""
CLI entrypoint for best_wine_shops discovery.

Usage:
    source .venv/bin/activate
    unset ANTHROPIC_API_KEY   # if your shell has the Claude Desktop empty override
    python -m best_wine_shops.discover                  # full run
    python -m best_wine_shops.discover --no-search      # seed URLs only
    python -m best_wine_shops.discover --no-seeds       # serper only
    python -m best_wine_shops.discover --max-per-query 3
    python -m best_wine_shops.discover --dry-run

Output:
    output/best_wine_shops/best_wine_shops_<YYYYMMDD>.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from awards._lib import ROOT
from .scraper import SOURCE_SLUG, scrape


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover US 'best wine shops' editorial mentions.")
    ap.add_argument("--no-seeds", action="store_true", help="skip the 7 seed URLs")
    ap.add_argument("--no-search", action="store_true", help="skip Serper queries")
    ap.add_argument("--max-per-query", type=int, default=5,
                    help="cap candidate articles per Serper query (default 5)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print plan only; no fetches, no LLM calls")
    args = ap.parse_args()

    out_dir = ROOT / "output" / "best_wine_shops"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out_path = out_dir / f"{SOURCE_SLUG}_{stamp}.csv"

    df = scrape(
        use_seeds=not args.no_seeds,
        use_search=not args.no_search,
        max_per_query=args.max_per_query,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print("\n(dry-run) no CSV written.")
        return 0

    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} rows -> {out_path.relative_to(ROOT)}")
    if not df.empty:
        n_large = int(df["is_large_indie"].sum())
        n_online = int(df["is_online_only"].sum())
        print(f"  large indies tagged: {n_large}")
        print(f"  online-only tagged:  {n_online}")
        print(f"  unique source URLs:  {df['source_url'].nunique()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
