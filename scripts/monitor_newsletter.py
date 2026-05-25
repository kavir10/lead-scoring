"""
Monitor the newsletter scrape OR recovery — every 5K new rows, emit a
milestone snapshot. Polls a progress CSV; writes a snapshot block when the
row count crosses each 5K boundary. Auto-detects recovery progress files
and adds a `recovered_via` breakdown if that column exists.

Stops automatically when the scraper process dies AND no new rows arrive
for `--idle-grace` seconds (default 300).

Usage:
    python scripts/monitor_newsletter.py                              # main scrape
    python scripts/monitor_newsletter.py --mode recovery              # recovery
    python scripts/monitor_newsletter.py --progress <path> \\
            --seed-total 22377 --log <path> --process-name <name>     # custom
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PROGRESS = os.path.join(ROOT, "output/newsletter_merchants/raw/scrape_progress.csv")
SEED = os.path.join(ROOT, "output/newsletter_merchants/inputs/seed_100k.csv")
DEFAULT_LOG = os.path.join(ROOT, "output/newsletter_merchants/raw/monitor.log")
RECOVERY_PROGRESS = os.path.join(ROOT, "output/newsletter_merchants/raw/recovery_progress.csv")
RECOVERY_INPUT = os.path.join(ROOT, "output/newsletter_merchants/inputs/recovery_input.csv")
RECOVERY_LOG = os.path.join(ROOT, "output/newsletter_merchants/raw/recovery_monitor.log")

MILESTONE = 5000


def row_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "rb") as f:
            return max(0, sum(1 for _ in f) - 1)  # minus header
    except Exception:
        return 0


def process_running(name: str) -> bool:
    """Returns True if a process matching `name` is in `ps`."""
    try:
        out = subprocess.check_output(["pgrep", "-f", name], stderr=subprocess.DEVNULL)
        return bool(out.strip())
    except subprocess.CalledProcessError:
        return False
    except Exception:
        return False


def snapshot(n_rows: int, seed_total: int, t_start: float, log, progress_path: str) -> None:
    """Read progress, compute summary, write a milestone block."""
    try:
        df = pd.read_csv(progress_path, dtype=str).fillna("")
    except Exception as e:
        log.write(f"[{datetime.now().isoformat(timespec='seconds')}] snapshot read failed: {e}\n")
        log.flush()
        return

    df = df.drop_duplicates(subset=["cid"], keep="last")

    sig = (df["any_signal"].astype(str) != "").sum()
    esp = (df["esp_platforms"].astype(str) != "").sum()
    form = (df["form_present"].astype(str) == "1").sum()
    popup = (df["popup_signal"].astype(str) == "1").sum()
    newsletter_url = (df["newsletter_url"].astype(str) != "").sum()

    err_mask = df["website_status"].astype(str).str.match(r"^(?!200|non_html).+", na=False)
    err = int(err_mask.sum())

    esp_exp = df["esp_platforms"].astype(str).str.split(";").explode().str.strip()
    esp_exp = esp_exp[esp_exp != ""]
    top_esps = esp_exp.value_counts().head(10)

    by_vert = df.groupby("business_type").size().sort_values(ascending=False)

    elapsed = time.time() - t_start
    overall_rate = len(df) / elapsed if elapsed > 0 else 0
    remaining = max(0, seed_total - len(df))
    eta_min = (remaining / overall_rate / 60) if overall_rate > 0 else 0

    stamp = datetime.now().isoformat(timespec="seconds")
    log.write(f"\n{'='*70}\n")
    log.write(f"MILESTONE @ {n_rows:,} rows  ({stamp})\n")
    log.write(f"{'='*70}\n")
    log.write(f"  Scraped:           {len(df):,} / {seed_total:,} ({len(df)/seed_total*100:.1f}%)\n")
    log.write(f"  Any signal:        {sig:,}  ({sig/len(df)*100:.1f}%)\n")
    log.write(f"  ESP detected:      {esp:,}  ({esp/len(df)*100:.1f}%)\n")
    log.write(f"  Newsletter form:   {form:,}  ({form/len(df)*100:.1f}%)\n")
    log.write(f"  Popup library:     {popup:,}  ({popup/len(df)*100:.1f}%)\n")
    log.write(f"  Public newsletter: {newsletter_url:,}\n")
    log.write(f"  Errors:            {err:,}  ({err/len(df)*100:.1f}%)\n")
    log.write(f"  Run rate:          {overall_rate:.1f} rows/s   ETA {eta_min:.1f} min\n")
    log.write(f"\n  Top ESPs:\n")
    for esp_name, count in top_esps.items():
        log.write(f"    {esp_name:<28} {count:>6,}\n")
    log.write(f"\n  Scraped by vertical:\n")
    for vert, count in by_vert.items():
        log.write(f"    {vert:<20} {count:>6,}\n")

    # Recovery-specific block
    if "recovered_via" in df.columns:
        rv = df["recovered_via"].astype(str)
        rv_counts = rv.value_counts()
        log.write(f"\n  Recovery breakdown:\n")
        for k, v in rv_counts.items():
            log.write(f"    {k:<28} {v:>6,}\n")
    log.flush()


def main(interval: float, idle_grace: int, progress_path: str,
         seed_total: int, log_path: str, process_name: str):
    if seed_total <= 0:
        print(f"Seed total invalid ({seed_total}).", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    f = open(log_path, "a", buffering=1)  # line-buffered
    start_count = row_count(progress_path)
    t_start = time.time()
    last_milestone = (start_count // MILESTONE) * MILESTONE
    last_row_count = start_count
    last_change = time.time()

    f.write(
        f"\n{'#'*70}\n# Monitor started {datetime.now().isoformat(timespec='seconds')}\n"
        f"# Progress: {progress_path}\n"
        f"# Watching process: {process_name}\n"
        f"# Seed total: {seed_total:,}\n"
        f"# Starting from row count: {start_count:,}\n"
        f"# Milestone interval: every {MILESTONE:,} rows\n"
        f"{'#'*70}\n"
    )
    f.flush()

    if start_count > 0:
        snapshot(start_count, seed_total, t_start, f, progress_path)

    while True:
        time.sleep(interval)
        n = row_count(progress_path)
        if n != last_row_count:
            last_change = time.time()
            last_row_count = n

        while n >= last_milestone + MILESTONE:
            last_milestone += MILESTONE
            snapshot(last_milestone, seed_total, t_start, f, progress_path)

        if n >= seed_total:
            f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] Reached seed total. Monitor exiting.\n")
            snapshot(n, seed_total, t_start, f, progress_path)
            f.flush()
            f.close()
            return

        if not process_running(process_name) and (time.time() - last_change) > idle_grace:
            f.write(
                f"\n[{datetime.now().isoformat(timespec='seconds')}] "
                f"Process gone + idle {idle_grace}s. Monitor exiting at {n:,}/{seed_total:,}.\n"
            )
            snapshot(n, seed_total, t_start, f, progress_path)
            f.flush()
            f.close()
            return


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["scrape", "recovery"], default="scrape")
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--idle-grace", type=int, default=300)
    ap.add_argument("--progress", default=None, help="Progress CSV path (overrides --mode)")
    ap.add_argument("--seed-total", type=int, default=0, help="Total seed rows (overrides --mode)")
    ap.add_argument("--log", default=None, help="Monitor log path")
    ap.add_argument("--process-name", default=None, help="Process name to watch via pgrep")
    args = ap.parse_args()

    if args.mode == "recovery":
        progress = args.progress or RECOVERY_PROGRESS
        seed_total = args.seed_total or row_count(RECOVERY_INPUT)
        log = args.log or RECOVERY_LOG
        proc = args.process_name or "recover_newsletter.py"
    else:
        progress = args.progress or DEFAULT_PROGRESS
        seed_total = args.seed_total or row_count(SEED)
        log = args.log or DEFAULT_LOG
        proc = args.process_name or "scrape_newsletter.py"

    main(args.interval, args.idle_grace, progress, seed_total, log, proc)
