"""
Multi-award lead discovery. Mirrors the Michelin scraper pattern but spans
~30 awards across restaurants, wine, bakery, cheese, butcher, and specialty.

Usage:
    source .venv/bin/activate

    # one source
    python discover_awards.py --source james_beard

    # everything in a category
    python discover_awards.py --category bakery

    # everything at a tier
    python discover_awards.py --tier 1

    # everything (will skip 🔒 sources without --cookies-from)
    python discover_awards.py --all

    # auth-walled source
    python discover_awards.py --source nyt --cookies-from cookies/nyt.json

    # rebuild master from existing per-source CSVs only (no scraping)
    python discover_awards.py --master-only

Outputs:
    output/awards/<source_slug>_<YYYYMMDD>.csv  - one per source
    output/awards_all_<YYYYMMDD>.csv            - master union
"""
from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from datetime import datetime

import pandas as pd

from awards import ALL_SOURCES, by_slug
from awards._lib import (
    build_master,
    load_cookies_from_file,
    save_source,
    to_dataframe,
)


def _select_sources(args) -> list[tuple]:
    if args.source:
        row = by_slug(args.source)
        if not row:
            sys.exit(f"Unknown source: {args.source}. See docs/AWARDS.md for the list.")
        return [row]
    pool = list(ALL_SOURCES)
    if args.category:
        pool = [r for r in pool if r[1] == args.category]
    if args.tier:
        pool = [r for r in pool if r[2] == args.tier]
    if not args.all and not (args.category or args.tier):
        sys.exit("Pick one: --source X | --category Y | --tier N | --all | --master-only")
    return pool


def _run_one(slug: str, category: str, tier: int, module_path: str, business_type: str, requires_auth: bool, *, cookies, headed: bool) -> int:
    print(f"\n[{slug}] tier={tier} category={category} type={business_type}", flush=True)
    if requires_auth and cookies is None:
        print(f"  SKIP — auth required (use --cookies-from for {slug})", flush=True)
        save_source(to_dataframe([]), slug)
        return 0
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        print(f"  SKIP — module not importable: {e}", flush=True)
        save_source(to_dataframe([]), slug)
        return 0
    if not hasattr(mod, "scrape"):
        print(f"  SKIP — module has no scrape()", flush=True)
        save_source(to_dataframe([]), slug)
        return 0
    try:
        df = mod.scrape(cookies=cookies, headed=headed) if requires_auth else mod.scrape(headed=headed)
    except TypeError:
        df = mod.scrape()  # legacy signature
    except Exception as e:
        print(f"  ERROR — {e}", flush=True)
        traceback.print_exc(limit=3)
        save_source(to_dataframe([]), slug)
        return 0
    if df is None or df.empty:
        print(f"  No rows from {slug}", flush=True)
        save_source(to_dataframe([]), slug)
        return 0
    # Backfill the source/tier/business_type if the module didn't set them.
    if "source" not in df.columns or df["source"].fillna("").eq("").all():
        df["source"] = slug
    if "tier" not in df.columns or df["tier"].fillna("").eq("").all():
        df["tier"] = tier
    if "business_type" not in df.columns or df["business_type"].fillna("").eq("").all():
        df["business_type"] = business_type
    save_source(df, slug)
    return len(df)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=str, help="Run a single source by slug")
    p.add_argument("--category", type=str, help="Run all sources in this category")
    p.add_argument("--tier", type=int, help="Run all sources at this tier (1-3)")
    p.add_argument("--all", action="store_true", help="Run every source")
    p.add_argument("--master-only", action="store_true", help="Skip scraping; just rebuild the master file")
    p.add_argument("--cookies-from", type=str, default="", help="Path to JSON cookie file for auth sources")
    p.add_argument("--headed", action="store_true", help="Run Playwright in headed mode (debug)")
    p.add_argument("--skip-master", action="store_true", help="Don't rebuild the master file at the end")
    args = p.parse_args()

    if args.master_only:
        build_master()
        return

    cookies = load_cookies_from_file(args.cookies_from) if args.cookies_from else None

    sources = _select_sources(args)
    print(f"\n{'='*60}")
    print(f"AWARDS DISCOVERY  ({len(sources)} sources)  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")

    total = 0
    for row in sources:
        total += _run_one(*row, cookies=cookies, headed=args.headed)

    print(f"\n  TOTAL ROWS WRITTEN: {total}")

    if not args.skip_master:
        build_master()


if __name__ == "__main__":
    main()
