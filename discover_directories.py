"""
Directory/stockist lead discovery. Parallel to discover_awards.py but for
non-award sources: curated directories (Raisin, RAW WINE, natty fairs) and
stockist backlink mining (premium importer "where to buy" pages).

Usage:
    source .venv/bin/activate

    # list all sources
    python discover_directories.py --list

    # one source
    python discover_directories.py --source stockist_louis_dressner

    # all wine sources
    python discover_directories.py --category wine

    # everything
    python discover_directories.py --all

    # rebuild master only
    python discover_directories.py --master-only

Outputs:
    output/directories/<slug>_<YYYYMMDD>.csv   - per source
    output/directories_all_<YYYYMMDD>.csv      - master union
"""
from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from core import ROOT
from core.csv_io import save_source as _save_source
from core.schema import AWARDS_SCHEMA as SCHEMA, to_dataframe
from directories import ALL_SOURCES, by_slug

OUTPUT_DIR = ROOT / "output" / "directories"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_source(df: pd.DataFrame, slug: str, *, stamp: str | None = None) -> Path:
    """Write per-source CSV to output/directories/<slug>_<YYYYMMDD>.csv."""
    return _save_source(df, slug, OUTPUT_DIR, stamp=stamp)


def _select_sources(args) -> list[tuple]:
    if args.source:
        row = by_slug(args.source)
        if not row:
            sys.exit(f"Unknown source: {args.source}. Run --list to see options.")
        return [row]
    pool = list(ALL_SOURCES)
    if args.category:
        pool = [r for r in pool if r[1] == args.category]
    if args.tier:
        pool = [r for r in pool if r[2] == args.tier]
    if not args.all and not (args.category or args.tier):
        sys.exit("Pick one: --source X | --category Y | --tier N | --all | --master-only | --list")
    return pool


def _run_one(slug: str, category: str, tier: int, module_path: str, business_type: str, requires_auth: bool, *, headed: bool) -> int:
    print(f"\n[{slug}] tier={tier} category={category} type={business_type}", flush=True)
    if requires_auth:
        print(f"  SKIP — auth required (not yet supported in directories/)", flush=True)
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
        df = mod.scrape(headed=headed)
    except TypeError:
        df = mod.scrape()
    except Exception as e:
        print(f"  ERROR — {e}", flush=True)
        traceback.print_exc(limit=3)
        save_source(to_dataframe([]), slug)
        return 0
    if df is None or df.empty:
        print(f"  No rows from {slug}", flush=True)
        save_source(to_dataframe([]), slug)
        return 0
    # Backfill defaults if module didn't set them.
    if "source" not in df.columns or df["source"].fillna("").eq("").all():
        df["source"] = slug
    if "tier" not in df.columns or df["tier"].fillna("").eq("").all():
        df["tier"] = tier
    if "business_type" not in df.columns or df["business_type"].fillna("").eq("").all():
        df["business_type"] = business_type
    save_source(df, slug)
    return len(df)


def _latest_for_slug(slug: str) -> Path | None:
    files = sorted(OUTPUT_DIR.glob(f"{slug}_*.csv"))
    return files[-1] if files else None


def build_master(*, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    frames: list[pd.DataFrame] = []
    for slug, *_ in ALL_SOURCES:
        path = OUTPUT_DIR / f"{slug}_{stamp}.csv"
        if not path.exists():
            path = _latest_for_slug(slug)
        if not path or not path.exists():
            continue
        df = pd.read_csv(path, dtype=str).fillna("")
        if df.empty:
            continue
        frames.append(df)
    master_path = ROOT / "output" / f"directories_all_{stamp}.csv"
    if not frames:
        pd.DataFrame(columns=SCHEMA).to_csv(master_path, index=False)
        print(f"\n  No source CSVs found — wrote empty master at {master_path.relative_to(ROOT)}")
        return master_path
    master = pd.concat(frames, ignore_index=True)
    master["name_n"] = master["name"].str.lower().str.strip()
    master["city_n"] = master["city"].str.lower().str.strip()
    master = master.drop_duplicates(["source", "name_n", "city_n"], keep="first")
    master = master.drop(columns=["name_n", "city_n"]).reset_index(drop=True)
    master.to_csv(master_path, index=False)
    print(f"\n  Master: {len(master)} rows across {master['source'].nunique()} sources -> {master_path.relative_to(ROOT)}")
    print("\n  Rows per source:")
    for src, n in master["source"].value_counts().items():
        print(f"    {src:<34} {n}")
    return master_path


def _list_sources() -> None:
    print("\nDirectory/stockist sources:")
    by_cat: dict[str, list[tuple]] = {}
    for row in ALL_SOURCES:
        by_cat.setdefault(row[1], []).append(row)
    for cat, rows in by_cat.items():
        print(f"\n  [{cat}]")
        for slug, _cat, tier, mod, btype, auth in rows:
            mark = " (auth)" if auth else ""
            print(f"    tier{tier}  {slug:<32} {btype}{mark}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=str, help="Run a single source by slug")
    p.add_argument("--category", type=str, help="Run all sources in this category")
    p.add_argument("--tier", type=int, help="Run all sources at this tier")
    p.add_argument("--all", action="store_true", help="Run every source")
    p.add_argument("--list", action="store_true", help="List all sources and exit")
    p.add_argument("--master-only", action="store_true", help="Skip scraping; rebuild master from existing CSVs")
    p.add_argument("--headed", action="store_true", help="Run Playwright in headed mode (debug)")
    p.add_argument("--skip-master", action="store_true", help="Don't rebuild the master file at the end")
    args = p.parse_args()

    if args.list:
        _list_sources()
        return
    if args.master_only:
        build_master()
        return

    sources = _select_sources(args)
    print(f"\n{'='*60}")
    print(f"DIRECTORIES DISCOVERY  ({len(sources)} sources)  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")

    total = 0
    for row in sources:
        total += _run_one(*row, headed=args.headed)

    print(f"\n  TOTAL ROWS WRITTEN: {total}")

    if not args.skip_master:
        build_master()


if __name__ == "__main__":
    main()
