"""
Butcher source-scrape discovery.

Standalone runner for the butcher vertical. Scrapes alternative source lanes
(Good Meat Finder, EatWild, Good Food Awards, AGA, stockist pages) without
running Google/Serper discovery or any enrichment phases.

Usage:
    source .venv/bin/activate
    python discover_butchers.py                              # all non-banned states
    python discover_butchers.py --state CA                   # CA only
    python discover_butchers.py --states CA,NY,TX            # subset
    python discover_butchers.py --cities "New York,Los Angeles"  # via TOP_US_CITIES

Outputs:
    output/butcher/1_discovered_butchers.csv            - deduped source leads
    output/butcher/source_discovered_butchers_<ts>.csv  - timestamped snapshot
    output/butcher/source_raw_butchers_<ts>.csv         - raw rows pre-dedupe
    output/butcher/source_scrape_status_<ts>.csv        - per-source status
"""
from __future__ import annotations

import argparse
import os

from butcher_sources import run_butcher_source_scrape
from core.geo import STATE_ABBREVIATIONS, US_STATES, slice_cities

OUTPUT_DIR = os.path.join("output", "butcher")


def _resolve_states(args) -> set[str] | None:
    """Build the optional state-filter set from --state/--states/--cities flags."""
    states: set[str] = set()
    if args.state:
        states.add(_to_abbr(args.state))
    if args.states:
        for s in args.states.split(","):
            s = s.strip()
            if s:
                states.add(_to_abbr(s))
    if args.cities:
        wanted = [c.strip() for c in args.cities.split(",") if c.strip()]
        for _city, abbr, _full, _pop in slice_cities(cities=wanted):
            states.add(abbr)
    return states or None


def _to_abbr(value: str) -> str:
    v = value.strip()
    if v.upper() in US_STATES:
        return v.upper()
    abbr = STATE_ABBREVIATIONS.get(v.title())
    if abbr:
        return abbr
    raise SystemExit(f"Unknown state: {value!r}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", type=str, help="Single state (2-letter or full name)")
    p.add_argument("--states", type=str, help="Comma-separated list of states")
    p.add_argument("--cities", type=str, help="Comma-separated cities (resolves to their states via TOP_US_CITIES)")
    args = p.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    states_filter = _resolve_states(args)

    print(f"\n{'='*60}")
    print("BUTCHER SOURCE SCRAPE")
    print(f"{'='*60}")
    print("Sources: Good Meat Finder, EatWild, Good Food Awards, AGA, stockist pages")
    if states_filter:
        print(f"State filter: {', '.join(sorted(states_filter))} (applies to per-state sources like EatWild)")

    df, status_df = run_butcher_source_scrape(OUTPUT_DIR, states_filter=states_filter)

    print("\nSource scrape statuses:")
    if not status_df.empty:
        print(status_df[["source", "status", "rows", "url"]].to_string(index=False))
    print(f"\nSaved {len(df)} deduped source leads to {OUTPUT_DIR}/1_discovered_butchers.csv")


if __name__ == "__main__":
    main()
