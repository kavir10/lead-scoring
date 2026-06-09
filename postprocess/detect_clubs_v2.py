"""
v2: Detect club/subscription/membership programs using async httpx + selectolax.

Same keyword lists and classifier as detect_clubs.py, but swaps the fetcher/parser:
- httpx.AsyncClient with HTTP/2 + concurrency semaphore (much faster than
  requests + ThreadPoolExecutor).
- selectolax.HTMLParser (C-backed, ~20x faster than BeautifulSoup).

Adds four new columns to the output CSV: has_club_v2, club_type_v2, club_url_v2,
club_signals_v2 — preserving v1 columns so v1/v2 can be diffed.

Usage:
    python detect_clubs_v2.py input.csv
    python detect_clubs_v2.py input.csv --concurrency 50
    python detect_clubs_v2.py input.csv -o output/with_clubs_v2.csv
    python detect_clubs_v2.py input.csv --resume
    python detect_clubs_v2.py input.csv --limit 100
"""
import argparse
import asyncio
import os
import sys
import time

import httpx
import pandas as pd
from selectolax.parser import HTMLParser

from detect_clubs import (
    CLUB_KEYWORDS,
    PLATFORM_SIGNALS,
    _classify_club_type,
    _atomic_csv_write,
)


# ─── Fetcher ───────────────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 5.0
MAX_BODY = 500_000  # 500KB cap


async def _fetch(url: str, client: httpx.AsyncClient) -> str | None:
    """GET a URL via httpx, returning raw HTML (or None on failure). Size-capped."""
    try:
        async with client.stream("GET", url, headers=HEADERS) as resp:
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("content-type", "").lower()
            if "html" not in ctype and "text" not in ctype:
                return None
            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_BODY:
                    break
            try:
                return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
            except (LookupError, UnicodeDecodeError):
                return b"".join(chunks).decode("utf-8", errors="replace")
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, RuntimeError):
        return None


# ─── Detection ─────────────────────────────────────────────────────────────

def _scan(raw_text: str) -> list[str]:
    """Return matched signals from a raw HTML string."""
    raw_html = raw_text.lower()

    tree = HTMLParser(raw_text)
    for tag in tree.css("script, style, noscript"):
        tag.decompose()
    text = tree.text(separator=" ", strip=True).lower() if tree.body else raw_html

    signals = []
    for kw in CLUB_KEYWORDS:
        if kw in text:
            signals.append(kw)
    for kw in PLATFORM_SIGNALS:
        if kw in raw_html:
            signals.append(kw)
    return signals


async def detect_club_v2(url: str, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> dict:
    result = {
        "has_club_v2": False,
        "club_type_v2": "",
        "club_url_v2": "",
        "club_signals_v2": "",
    }
    if not url or not isinstance(url, str) or str(url).lower() == "nan":
        return result
    if not url.startswith("http"):
        url = "https://" + url

    async with sem:
        raw = await _fetch(url, client)

    if raw is None:
        return result

    signals = _scan(raw)
    if signals:
        result["has_club_v2"] = True
        result["club_type_v2"] = _classify_club_type(signals)
        result["club_url_v2"] = url
        result["club_signals_v2"] = "; ".join(signals[:10])
    return result


# ─── Batch runner ──────────────────────────────────────────────────────────

V2_COLS = ["has_club_v2", "club_type_v2", "club_url_v2", "club_signals_v2"]


async def _run_chunk(urls_by_idx: dict[int, str], client: httpx.AsyncClient, sem: asyncio.Semaphore) -> dict[int, dict]:
    tasks = {idx: asyncio.create_task(detect_club_v2(url, client, sem)) for idx, url in urls_by_idx.items()}
    results = {}
    for idx, t in tasks.items():
        try:
            results[idx] = await t
        except Exception:
            results[idx] = {"has_club_v2": False, "club_type_v2": "", "club_url_v2": "", "club_signals_v2": ""}
    return results


async def _run_async(input_path: str, output_path: str, concurrency: int, resume: bool, limit: int | None):
    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path, low_memory=False)

    if "website" not in df.columns:
        print("ERROR: CSV must have a 'website' column.")
        sys.exit(1)

    for col in V2_COLS:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].astype("object")

    start_idx = 0
    if resume and os.path.exists(output_path):
        existing = pd.read_csv(output_path, low_memory=False)
        if "has_club_v2" in existing.columns:
            done_mask = existing["has_club_v2"].astype(str).isin(["True", "False"])
            start_idx = int(done_mask.sum())
            for col in V2_COLS:
                if col in existing.columns:
                    df[col] = df[col].astype("object")
                    df.loc[df.index[:start_idx], col] = existing[col].iloc[:start_idx].values
            print(f"  Resuming from row {start_idx}/{len(df)}")

    remaining = df.iloc[start_idx:]
    if limit is not None:
        remaining = remaining.iloc[:limit]
    total = len(df)
    to_process = len(remaining)

    if to_process == 0:
        print("All rows already processed.")
        return

    print(f"  Processing {to_process} websites — concurrency={concurrency}")
    print()

    chunk_size = 500
    chunks = [remaining.iloc[i:i + chunk_size] for i in range(0, to_process, chunk_size)]
    processed = start_idx
    t0 = time.time()
    req_count = 0

    timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)

    # Fresh AsyncClient per chunk: httpx's connection pool degrades after ~10K unique hosts,
    # so we recycle every 500 rows. Semaphore is also per-chunk because it's tied to the loop.
    for chunk_num, chunk in enumerate(chunks):
        sem = asyncio.Semaphore(concurrency)
        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            follow_redirects=True,
            verify=False,  # many small-biz sites have bad certs; parsing > TLS strictness here
        ) as client:
            urls_by_idx = {idx: row.get("website", "") for idx, row in chunk.iterrows()}
            results = await _run_chunk(urls_by_idx, client, sem)

        for idx, data in results.items():
            for col, val in data.items():
                df.at[idx, col] = str(val)

        req_count += len(chunk)
        processed += len(chunk)
        _atomic_csv_write(df, output_path)
        elapsed = time.time() - t0
        rate = req_count / elapsed if elapsed > 0 else 0
        clubs_found = (df["has_club_v2"].astype(str) == "True").sum()
        eta_sec = (to_process - (processed - start_idx)) / rate if rate > 0 else 0
        print(f"  [{processed}/{total}] saved — {clubs_found} v2 clubs — {rate:.1f} req/s — ETA {eta_sec/60:.1f} min")

    clubs_found = (df["has_club_v2"].astype(str) == "True").sum()
    print()
    print("=" * 60)
    print(f"DONE: v2 detected {clubs_found}/{total} ({clubs_found/total*100:.1f}%)")
    if "has_club" in df.columns:
        v1_clubs = (df["has_club"].astype(str) == "True").sum()
        newly_found = ((df["has_club_v2"].astype(str) == "True") & (df["has_club"].astype(str) != "True")).sum()
        lost = ((df["has_club_v2"].astype(str) != "True") & (df["has_club"].astype(str) == "True")).sum()
        print(f"v1: {v1_clubs} | v2: {clubs_found}")
        print(f"  Newly found by v2: {newly_found}")
        print(f"  v1-True but v2-False: {lost}")
    print(f"Output: {output_path}")
    print("=" * 60)

    if clubs_found > 0:
        print("\nv2 club_type breakdown:")
        for ctype, count in df[df["has_club_v2"].astype(str) == "True"]["club_type_v2"].value_counts().items():
            print(f"  {ctype}: {count}")


def main():
    import functools
    global print
    print = functools.partial(print, flush=True)

    parser = argparse.ArgumentParser(description="Detect club/subscription programs via async httpx + selectolax (v2)")
    parser.add_argument("input_csv", help="Path to CSV with a 'website' column")
    parser.add_argument("-o", "--output", help="Output CSV path (default: <input>_v2.csv)")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent requests (default: 50)")
    parser.add_argument("--resume", action="store_true", help="Resume from partial output")
    parser.add_argument("--limit", type=int, default=None, help="Cap rows processed this run")
    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"ERROR: File not found: {args.input_csv}")
        sys.exit(1)

    output_path = args.output or f"{os.path.splitext(args.input_csv)[0]}_v2.csv"
    asyncio.run(_run_async(args.input_csv, output_path, args.concurrency, args.resume, args.limit))


if __name__ == "__main__":
    main()
