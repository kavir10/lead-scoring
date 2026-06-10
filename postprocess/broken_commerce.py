"""
Broken-commerce intent detection (idea #33 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Takes any lead CSV with a `website` column and probes common commerce paths
(/shop, /order, /club, /subscribe, /membership, /preorder, /gift) plus the
club_url column if present (detect_clubs output). Flags pages that are dead
(404/410) or stale ("coming soon", "under construction", empty shells).

A broken club or preorder page is warmer than no page: it proves prior
intent plus an operational failure Table22 fixes — that's the outbound hook.

Adds columns: broken_commerce (bool), broken_paths, broken_kinds.
Never modifies the input; writes <input>_broken_commerce_<YYYYMMDD>.csv.

Usage:
    python postprocess/broken_commerce.py input.csv
    python postprocess/broken_commerce.py input.csv --threads 30 --limit 100
    python postprocess/broken_commerce.py input.csv --flagged-only
"""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

COMMERCE_PATHS = ["/shop", "/order", "/club", "/subscribe", "/membership", "/preorder", "/gift"]

STALE_MARKERS = re.compile(
    r"coming soon|under construction|currently unavailable|page not found|"
    r"no longer available|check back soon|temporarily closed", re.I)

MIN_LIVE_CHARS = 800  # smaller bodies on a commerce path are shells


def base_url(website: str) -> str:
    w = str(website or "").strip()
    if not w:
        return ""
    if not w.startswith("http"):
        w = "https://" + w
    return w.rstrip("/")


def probe(url: str) -> tuple[str, str]:
    """-> (kind, detail). kind: dead | stale | live | skip."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, allow_redirects=True)
    except requests.RequestException:
        return "skip", "unreachable"
    if r.status_code in (404, 410):
        return "dead", str(r.status_code)
    if r.status_code != 200:
        return "skip", str(r.status_code)
    text = r.text or ""
    if STALE_MARKERS.search(text):
        return "stale", STALE_MARKERS.search(text).group(0).lower()
    if len(text) < MIN_LIVE_CHARS:
        return "stale", "near-empty page"
    return "live", ""


def check_row(row: dict) -> dict:
    """Probe the row's commerce surfaces. Only paths that *exist as links or
    known URLs* count as broken when dead — a 404 on a path the site never
    had is meaningless, so we require the homepage to link the path OR the
    path to come from club_url."""
    base = base_url(row.get("website", ""))
    out = {"broken_commerce": False, "broken_paths": "", "broken_kinds": ""}
    if not base:
        return out

    targets: list[str] = []
    club_url = str(row.get("club_url", "") or "").strip()
    if club_url.startswith("http"):
        targets.append(club_url)

    # Find which commerce paths the homepage actually links to.
    try:
        home = requests.get(base, headers={"User-Agent": UA}, timeout=12)
        home_html = home.text.lower() if home.status_code == 200 else ""
    except requests.RequestException:
        home_html = ""
    for path in COMMERCE_PATHS:
        if home_html and re.search(rf'href=["\'][^"\']*{re.escape(path)}\b', home_html):
            targets.append(base + path)

    broken_paths, broken_kinds = [], []
    for url in dict.fromkeys(targets):  # de-dupe, keep order
        kind, detail = probe(url)
        if kind in ("dead", "stale"):
            broken_paths.append(url)
            broken_kinds.append(f"{kind}:{detail}")
    if broken_paths:
        out["broken_commerce"] = True
        out["broken_paths"] = " | ".join(broken_paths)
        out["broken_kinds"] = " | ".join(broken_kinds)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Lead CSV with a website column (club_url used too if present)")
    ap.add_argument("--threads", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0, help="Only process first N rows (debug)")
    ap.add_argument("--flagged-only", action="store_true", help="Output only rows with broken commerce")
    ap.add_argument("-o", "--output", default="", help="Output path (default: <input stem>_broken_commerce_<YYYYMMDD>.csv)")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    if "website" not in df.columns:
        sys.exit("Input needs a website column.")
    if args.limit > 0:
        df = df.head(args.limit).copy()

    records = df.to_dict("records")
    results: list[dict | None] = [None] * len(records)
    done = 0
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = {pool.submit(check_row, rec): i for i, rec in enumerate(records)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception:
                results[i] = {"broken_commerce": False, "broken_paths": "", "broken_kinds": ""}
            done += 1
            if done % 50 == 0 or done == len(records):
                print(f"  [{done}/{len(records)}] checked", flush=True)

    for col in ("broken_commerce", "broken_paths", "broken_kinds"):
        df[col] = [r[col] for r in results]

    flagged = df[df["broken_commerce"] == True]  # noqa: E712
    out_df = flagged if args.flagged_only else df
    stamp = datetime.now().strftime("%Y%m%d")
    out_path = args.output or str(Path("output") / f"{Path(args.input).stem}_broken_commerce_{stamp}.csv")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"\n  {len(flagged)} of {len(df)} rows flagged broken-commerce -> {out_path}")


if __name__ == "__main__":
    main()
