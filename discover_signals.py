"""
Trigger-based signal discovery. Parallel to discover_awards.py /
discover_directories.py but for timing-signal lanes: existing clubs, paused
clubs, manual preorder pain, sold-out demand, seasonal preorders, fresh
press, Reddit customer language. Strategy + lane catalog: docs/SIGNALS.md.

Usage:
    source .venv/bin/activate

    # list all lanes
    python discover_signals.py --list

    # preview the exact Serper queries a lane would run (no API calls)
    python discover_signals.py --source club_transition --dry-run

    # one lane, capped (good first run)
    python discover_signals.py --source club_transition --limit 30

    # one lane, city-scoped to the first 20 cities in config.CITIES
    python discover_signals.py --source sold_out_demand --cities 20

    # everything (Serper + Claude costs apply — see docs/SIGNALS.md)
    python discover_signals.py --all

    # rebuild master only
    python discover_signals.py --master-only

Outputs:
    output/signals/<slug>_<YYYYMMDD>.csv   - per lane
    output/signals_all_<YYYYMMDD>.csv      - master union
"""
from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from signals import ALL_SOURCES, by_slug
from signals._lib import (
    OUTPUT_DIR,
    ROOT,
    SIGNAL_SCHEMA,
    dedupe_signals,
    to_signal_dataframe,
)


def save_source(df: pd.DataFrame, slug: str, *, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"{slug}_{stamp}.csv"
    df = to_signal_dataframe(df.to_dict("records") if not df.empty else [])
    df = dedupe_signals(df)
    df.to_csv(path, index=False)
    print(f"  Saved {len(df):>5} rows -> {path.relative_to(ROOT)}", flush=True)
    return path


def _select_sources(args) -> list[tuple]:
    if args.source:
        row = by_slug(args.source)
        if not row:
            sys.exit(f"Unknown lane: {args.source}. Run --list to see options.")
        return [row]
    pool = list(ALL_SOURCES)
    if args.category:
        pool = [r for r in pool if r[1] == args.category]
    if not args.all and not args.category:
        sys.exit("Pick one: --source X | --category Y | --all | --master-only | --list")
    return pool


def _run_one(slug: str, category: str, tier: int, module_path: str,
             business_type: str, requires_auth: bool, *, options: dict) -> int:
    print(f"\n[{slug}] category={category} tier={tier}", flush=True)
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        print(f"  SKIP — module not importable: {e}", flush=True)
        save_source(to_signal_dataframe([]), slug)
        return 0
    try:
        df = mod.scrape(**options)
    except Exception as e:
        print(f"  ERROR — {e}", flush=True)
        traceback.print_exc(limit=3)
        save_source(to_signal_dataframe([]), slug)
        return 0
    if df is None or df.empty:
        if options.get("dry_run"):
            return 0
        print(f"  No rows from {slug}", flush=True)
        save_source(to_signal_dataframe([]), slug)
        return 0
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
    master_path = ROOT / "output" / f"signals_all_{stamp}.csv"
    if not frames:
        pd.DataFrame(columns=SIGNAL_SCHEMA).to_csv(master_path, index=False)
        print(f"\n  No lane CSVs found — wrote empty master at {master_path.relative_to(ROOT)}")
        return master_path
    master = pd.concat(frames, ignore_index=True)
    # Keep one row per (lane, name, city): the same business surfacing in
    # several lanes is signal, so cross-lane duplicates stay.
    master["name_n"] = master["name"].str.lower().str.strip()
    master["city_n"] = master["city"].str.lower().str.strip()
    master = master.drop_duplicates(["source", "name_n", "city_n"], keep="first")
    master = master.drop(columns=["name_n", "city_n"]).reset_index(drop=True)
    master.to_csv(master_path, index=False)
    print(f"\n  Master: {len(master)} rows across {master['source'].nunique()} lanes -> {master_path.relative_to(ROOT)}")
    print("\n  Rows per lane:")
    for src, n in master["source"].value_counts().items():
        print(f"    {src:<26} {n}")
    return master_path


def _list_sources() -> None:
    print("\nSignal lanes:")
    by_cat: dict[str, list[tuple]] = {}
    for row in ALL_SOURCES:
        by_cat.setdefault(row[1], []).append(row)
    for cat, rows in by_cat.items():
        print(f"\n  [{cat}]")
        for slug, _cat, tier, _mod, btype, _auth in rows:
            print(f"    tier{tier}  {slug:<24} {btype}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=str, help="Run a single lane by slug")
    p.add_argument("--category", type=str, help="Run all lanes in this category (transition/pain/demand/press/community)")
    p.add_argument("--all", action="store_true", help="Run every lane")
    p.add_argument("--list", action="store_true", help="List all lanes and exit")
    p.add_argument("--master-only", action="store_true", help="Skip scraping; rebuild master from existing CSVs")
    p.add_argument("--dry-run", action="store_true", help="Print the queries a lane would run; no API calls")
    p.add_argument("--limit", type=int, default=0, help="Cap Serper queries (phrase lanes) or LLM articles/threads (press/reddit). 0 = lane default")
    p.add_argument("--cities", type=int, default=0, help="Also scope phrase queries to the first N cities in config.CITIES (0 = national queries only)")
    p.add_argument("--no-verify", action="store_true", help="Skip on-page verification (faster, noisier; names come from search titles)")
    p.add_argument("--skip-master", action="store_true", help="Don't rebuild the master file at the end")
    args = p.parse_args()

    if args.list:
        _list_sources()
        return
    if args.master_only:
        build_master()
        return

    options = {
        "limit": args.limit,
        "cities": args.cities,
        "verify": not args.no_verify,
        "dry_run": args.dry_run,
    }

    sources = _select_sources(args)
    print(f"\n{'='*60}")
    print(f"SIGNAL DISCOVERY  ({len(sources)} lanes)  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")

    total = 0
    for row in sources:
        total += _run_one(*row, options=options)

    print(f"\n  TOTAL ROWS WRITTEN: {total}")

    if not args.dry_run and not args.skip_master:
        build_master()


if __name__ == "__main__":
    main()
