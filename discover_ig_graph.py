"""
IG-graph traversal orchestrator — channel 01.

Two phases:
  1. fetch  : pull posts per seed (Apify, costs ~$0.02/seed)
  2. agg    : roll up by venue, emit canonical CSV

Strategy: docs/strategies/01_somm_chef_ig_graph.md

Usage:
    python discover_ig_graph.py --fetch
    python discover_ig_graph.py --fetch --limit 5
    python discover_ig_graph.py --aggregate
    python discover_ig_graph.py --fetch --aggregate
"""
from __future__ import annotations

import argparse

from social_graph.fetch_seed_posts import fetch_all
from social_graph.aggregate_venues import aggregate

from awards._lib import ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fetch", action="store_true", help="Fetch IG posts per seed via Apify")
    p.add_argument("--aggregate", action="store_true", help="Roll up raw posts -> canonical CSV")
    p.add_argument("--handle", type=str, help="Fetch only this seed handle (no @)")
    p.add_argument("--limit", type=int, help="Cap seed count for testing")
    args = p.parse_args()
    if not (args.fetch or args.aggregate):
        p.print_help()
        return
    if args.fetch:
        fetch_all(handle=args.handle, limit=args.limit)
    if args.aggregate:
        df = aggregate()
        from datetime import datetime
        out = ROOT / "output" / "social_graph" / f"somm_chef_ig_graph_{datetime.now():%Y%m%d}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"  Saved {len(df)} venues -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
