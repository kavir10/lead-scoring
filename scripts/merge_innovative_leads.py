#!/usr/bin/env python3
"""Merge + dedupe per-agent innovative-lead CSVs into per-vertical masters.

Reads every CSV under output/innovative_leads/<vertical>/, normalizes, dedupes
by (normalized name, city) and by website host where present, and writes
output/innovative_leads/master_<vertical>_<YYYYMMDD>.csv. Prints per-vertical
counts so the loop can track progress toward 1,000 each.

Stdlib only — the remote container has no venv.
"""

import csv
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "innovative_leads"
VERTICALS = ["restaurants", "butchers", "cheese", "bakeries", "wine"]
COLUMNS = [
    "name", "city", "state", "website", "vertical",
    "source_strategy", "source_url", "evidence", "date_added",
]

BANNED_BUTCHER_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}

_norm_re = re.compile(r"[^a-z0-9 ]+")
_stop_words = {"the", "a", "an", "and", "&", "co", "inc", "llc", "shop", "shoppe"}


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = _norm_re.sub(" ", s.lower())
    toks = [t for t in s.split() if t not in _stop_words]
    return " ".join(toks)


def norm_city(city: str) -> str:
    return _norm_re.sub(" ", (city or "").lower()).strip()


def site_host(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    if not u.startswith("http"):
        u = "https://" + u
    try:
        host = urlparse(u).netloc.lower()
    except ValueError:
        return ""
    return host.removeprefix("www.")


def merge_vertical(vertical: str, stamp: str) -> int:
    vdir = BASE / vertical
    rows = []
    for f in sorted(vdir.glob("*.csv")):
        if f.name.startswith("master_"):
            continue
        try:
            with open(f, newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    rows.append({c: (row.get(c) or "").strip() for c in COLUMNS})
        except Exception as e:  # noqa: BLE001 - keep merging other files
            print(f"  WARN {f.name}: {e}", file=sys.stderr)

    seen_keys: set = set()
    seen_hosts: set = set()
    out = []
    for r in rows:
        if not r["name"] or not r["city"]:
            continue
        state = r["state"].upper().strip()
        if len(state) > 2:
            r["state"] = state  # leave non-standard for QA rather than guess
        else:
            r["state"] = state
        if vertical == "butchers" and state in BANNED_BUTCHER_STATES:
            continue
        r["vertical"] = vertical
        key = (norm_name(r["name"]), norm_city(r["city"]))
        if key in seen_keys:
            continue
        host = site_host(r["website"])
        if host and host in seen_hosts:
            continue
        seen_keys.add(key)
        if host:
            seen_hosts.add(host)
        out.append(r)

    out_path = BASE / f"master_{vertical}_{stamp}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    print(f"{vertical:12s} raw={len(rows):5d} deduped={len(out):5d} -> {out_path.name}")
    return len(out)


def main() -> None:
    stamp = date.today().strftime("%Y%m%d")
    total = 0
    for v in VERTICALS:
        (BASE / v).mkdir(parents=True, exist_ok=True)
        total += merge_vertical(v, stamp)
    print(f"{'TOTAL':12s} deduped={total}")


if __name__ == "__main__":
    main()
