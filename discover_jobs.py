"""
Food-industry job-board discovery — channel 02.

Strategy: docs/strategies/02_food_job_boards.md

Usage:
    source .venv/bin/activate

    python discover_jobs.py --list
    python discover_jobs.py --source job_indeed_serper
    python discover_jobs.py --all

Outputs:
    output/jobs/<slug>_<YYYYMMDD>.csv
    output/jobs_all_<YYYYMMDD>.csv
"""
from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from awards._lib import (
    SCHEMA,
    ROOT,
    dedupe,
    filter_us,
    to_dataframe,
)
from jobs import ALL_SOURCES, by_slug

OUTPUT_DIR = ROOT / "output" / "jobs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_source(df: pd.DataFrame, slug: str, *, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"{slug}_{stamp}.csv"
    df = to_dataframe(df.to_dict("records") if not df.empty else [])
    df = filter_us(df)
    df = dedupe(df)
    df.to_csv(path, index=False)
    print(f"  Saved {len(df):>5} rows -> {path.relative_to(ROOT)}", flush=True)
    return path


def _run_one(slug: str, tier: int, module_path: str, business_type: str) -> int:
    print(f"\n[{slug}] tier={tier} type={business_type}", flush=True)
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
    master_path = ROOT / "output" / f"jobs_all_{stamp}.csv"
    if not frames:
        pd.DataFrame(columns=SCHEMA).to_csv(master_path, index=False)
        print(f"\n  No source CSVs — wrote empty master at {master_path.relative_to(ROOT)}")
        return master_path
    master = pd.concat(frames, ignore_index=True)
    master["name_n"] = master["name"].str.lower().str.strip()
    master["city_n"] = master["city"].str.lower().str.strip()
    master = master.drop_duplicates(["source", "name_n", "city_n"], keep="first")
    master = master.drop(columns=["name_n", "city_n"]).reset_index(drop=True)
    master.to_csv(master_path, index=False)
    print(f"\n  Master: {len(master)} rows across {master['source'].nunique()} sources -> {master_path.relative_to(ROOT)}")
    return master_path


def _list_sources():
    print("\nJob board sources:")
    for slug, tier, mod, btype in ALL_SOURCES:
        print(f"  tier{tier}  {slug:<28} {btype}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=str)
    p.add_argument("--all", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--master-only", action="store_true")
    args = p.parse_args()

    if args.list:
        _list_sources()
        return
    if args.master_only:
        build_master()
        return

    if args.source:
        row = by_slug(args.source)
        if not row:
            sys.exit(f"Unknown source: {args.source}")
        sources = [row]
    elif args.all:
        sources = list(ALL_SOURCES)
    else:
        sys.exit("Pick one: --source X | --all | --master-only | --list")

    print(f"\n{'='*60}\nJOBS DISCOVERY ({len(sources)} sources)  {datetime.now():%Y-%m-%d %H:%M}\n{'='*60}")
    total = 0
    for row in sources:
        total += _run_one(*row)
    print(f"\n  TOTAL ROWS WRITTEN: {total}")
    build_master()


if __name__ == "__main__":
    main()
