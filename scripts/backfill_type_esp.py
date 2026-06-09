"""
Backfill Google Maps `type` for the ESP signal list cids that aren't yet in
output/type_lookup.csv.

Reuses backfill_type.fetch_type (Serper Maps, cid-matched) and appends to the
same resumable lookup table, so the ESP list gains a type purely via the cid
join — no schema change to the lead file itself.

Usage:
    python scripts/backfill_type_esp.py --limit 50   # smoke test
    python scripts/backfill_type_esp.py              # full gap
"""
import os
import csv
import sys
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "postprocess"))
from backfill_type import fetch_type, MAX_WORKERS  # noqa: E402

ESP_FILE = "output/newsletter_merchants/newsletter_signal_clean_20260531.csv"
OUT = "output/type_lookup.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default=ESP_FILE)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    esp = pd.read_csv(args.esp, dtype={"cid": str}, low_memory=False)
    esp = esp.dropna(subset=["cid"])
    esp = esp[esp["cid"].str.len() > 0].drop_duplicates("cid")

    done = set()
    if os.path.exists(args.out):
        existing = pd.read_csv(args.out, dtype={"cid": str})
        done = set(existing["cid"].astype(str))
        print(f"Resume: {len(done):,} cids already in {args.out}")

    todo = esp[~esp["cid"].isin(done)].reset_index(drop=True)
    if args.limit:
        todo = todo.head(args.limit)
    total = len(todo)
    print(f"ESP cids: {len(esp):,} | missing type: {total:,}")
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
                         str(row.get("city", "") or ""), str(row.get("state", "") or ""))
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
    print(f"\nDone in {(time.monotonic() - start) / 60:.1f} min. Output: {args.out}")


if __name__ == "__main__":
    main()
