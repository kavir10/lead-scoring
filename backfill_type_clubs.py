"""
Targeted Google-type backfill for the has_club_final=True rows that landed in
no_type / unmapped_type after reclassify_clubs.py.

Reads:  output/clubs_needs_type_backfill.csv  (3,069 unique cids)
Writes: output/type_lookup_clubs.csv          (new file, resumable)

Same Serper Maps call pattern as backfill_type.py. Does NOT touch the original
output/type_lookup.csv — after this completes, merge the two lookups and re-run
reclassify_clubs.py.

Usage:
    python backfill_type_clubs.py --limit 20   # smoke test
    python backfill_type_clubs.py              # full run (~3k calls, ~1-2 min)
"""
import os
import csv
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd

from config import SERPER_API_KEY


INPUT_PATH = "output/clubs_needs_type_backfill.csv"
DEFAULT_OUT = "output/type_lookup_clubs.csv"

MAX_WORKERS = 80
RATE_LIMIT_RPS = 45
_rate_lock = threading.Lock()
_last_times: list[float] = []


def _rate_limit() -> None:
    with _rate_lock:
        now = time.monotonic()
        while _last_times and _last_times[0] < now - 1.0:
            _last_times.pop(0)
        if len(_last_times) >= RATE_LIMIT_RPS:
            wait = _last_times[0] + 1.0 - now
            if wait > 0:
                time.sleep(wait)
        _last_times.append(time.monotonic())


def fetch_type(cid: str, name: str, city: str, state: str, max_retries: int = 3) -> dict | None:
    _rate_limit()
    url = "https://google.serper.dev/maps"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    loc = f"{city}, {state}, United States" if city and state else "United States"
    payload = {"q": name, "location": loc, "gl": "us", "hl": "en", "num": 10}

    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            r.raise_for_status()
            places = r.json().get("places", [])

            match, confidence = None, "none"
            for p in places:
                if str(p.get("cid", "")) == str(cid):
                    match, confidence = p, "cid"
                    break
            if match is None:
                name_low = (name or "").strip().lower()
                for p in places:
                    if p.get("title", "").strip().lower() == name_low:
                        match, confidence = p, "name"
                        break
            if match is None and places:
                match, confidence = places[0], "top"

            if match is None:
                return {"type": "", "types": "", "name_matched": "", "match_confidence": "none"}

            types_list = match.get("types") or []
            return {
                "type": match.get("type", ""),
                "types": ", ".join(types_list) if isinstance(types_list, list) else "",
                "name_matched": match.get("title", ""),
                "match_confidence": confidence,
            }
        except requests.RequestException as e:
            status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            if status in (400, 429) and attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            return None
    return None


def build_input() -> pd.DataFrame:
    df = pd.read_csv(INPUT_PATH, dtype={"cid": str})
    before = len(df)
    df = df.dropna(subset=["cid"])
    df = df[df["cid"].astype(str).str.len() > 0]
    df = df.drop_duplicates(subset=["cid"], keep="first").reset_index(drop=True)
    print(f"Input: {before:,} rows -> {len(df):,} unique cids")
    return df[["cid", "name", "city", "state"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0, help="Stop after N fetches (0=all)")
    args = parser.parse_args()

    if not SERPER_API_KEY:
        print("SERPER_API_KEY missing in .env")
        return

    df = build_input()

    done_cids: set[str] = set()
    if os.path.exists(args.out):
        existing = pd.read_csv(args.out, dtype={"cid": str})
        done_cids = set(existing["cid"].astype(str))
        print(f"Resume: {len(done_cids):,} cids already in {args.out}")

    todo = df[~df["cid"].astype(str).isin(done_cids)].reset_index(drop=True)
    if args.limit:
        todo = todo.head(args.limit)
    total = len(todo)
    print(f"To fetch: {total:,}")
    if total == 0:
        print("Nothing to do.")
        return

    fieldnames = ["cid", "source_name", "source_city", "source_state",
                  "name_matched", "type", "types", "match_confidence"]
    need_header = not os.path.exists(args.out)
    out_f = open(args.out, "a", newline="", buffering=1)
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    if need_header:
        writer.writeheader()
    write_lock = threading.Lock()

    start = time.monotonic()
    last_print = start
    completed = errors = 0

    def task(row):
        res = fetch_type(str(row["cid"]), str(row["name"]),
                         str(row.get("city", "")), str(row.get("state", "")))
        return row, res

    rows = todo.to_dict("records")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(task, r) for r in rows]
        for fut in as_completed(futures):
            completed += 1
            try:
                row, res = fut.result()
                if res is None:
                    errors += 1
                    res = {"type": "", "types": "", "name_matched": "", "match_confidence": "error"}
                with write_lock:
                    writer.writerow({
                        "cid": str(row["cid"]),
                        "source_name": row.get("name", ""),
                        "source_city": row.get("city", ""),
                        "source_state": row.get("state", ""),
                        "name_matched": res.get("name_matched", ""),
                        "type": res.get("type", ""),
                        "types": res.get("types", ""),
                        "match_confidence": res.get("match_confidence", ""),
                    })
            except Exception:
                errors += 1

            now = time.monotonic()
            if now - last_print >= 2.0 or completed == total:
                elapsed = now - start
                rate = completed / elapsed if elapsed else 0
                eta = (total - completed) / rate / 60 if rate else 0
                print(f"  [{completed:,}/{total:,}] {rate:.1f} req/s | errors: {errors} | ETA: {eta:.0f}m", flush=True)
                last_print = now

    out_f.close()
    elapsed = time.monotonic() - start
    print(f"\nDone in {elapsed:.1f}s. Completed {completed:,} | errors {errors}")
    print(f"Lookup: {args.out}")


if __name__ == "__main__":
    main()
