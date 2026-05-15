"""
Butcher source-scrape discovery.

Standalone runner for the butcher vertical. Scrapes alternative source lanes
(Good Meat Finder, EatWild, Good Food Awards, AGA, stockist pages) without
running Google/Serper discovery or any enrichment phases.

Usage:
    source .venv/bin/activate
    python discover_butchers.py

Outputs:
    output/butcher/1_discovered_butchers.csv            - deduped source leads
    output/butcher/source_discovered_butchers_<ts>.csv  - timestamped snapshot
    output/butcher/source_raw_butchers_<ts>.csv         - raw rows pre-dedupe
    output/butcher/source_scrape_status_<ts>.csv        - per-source status
"""
from __future__ import annotations

import os

from butcher_sources import run_butcher_source_scrape

OUTPUT_DIR = os.path.join("output", "butcher")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print("BUTCHER SOURCE SCRAPE")
    print(f"{'='*60}")
    print("Sources: Good Meat Finder, EatWild, Good Food Awards, AGA, stockist pages")

    df, status_df = run_butcher_source_scrape(OUTPUT_DIR)

    print("\nSource scrape statuses:")
    if not status_df.empty:
        print(status_df[["source", "status", "rows", "url"]].to_string(index=False))
    print(f"\nSaved {len(df)} deduped source leads to {OUTPUT_DIR}/1_discovered_butchers.csv")


if __name__ == "__main__":
    main()
