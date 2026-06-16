#!/usr/bin/env python3
"""Apply a domain-backfill mapping onto the per-vertical master CSVs.

A backfill agent produces a mapping CSV with columns: name,city,website
(one row per business it resolved). This script fills the empty `website`
field on matching master rows, keyed by normalized name+city. It never
overwrites a website that is already present, and writes the master in place
(masters are regenerated artifacts, not source CSVs).

Usage: python scripts/apply_domain_backfill.py <vertical> <mapping.csv>
Stdlib only.
"""

import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "innovative_leads"

_norm_re = re.compile(r"[^a-z0-9 ]+")
_stop = {"the", "a", "an", "and", "&", "co", "inc", "llc", "shop", "shoppe"}


def nname(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = _norm_re.sub(" ", s.lower())
    return " ".join(t for t in s.split() if t not in _stop)


def ncity(city: str) -> str:
    return _norm_re.sub(" ", (city or "").lower()).strip()


def main() -> None:
    vertical, mapping_path = sys.argv[1], sys.argv[2]
    master = sorted(BASE.glob(f"master_{vertical}_*.csv"))[-1]

    fills: dict[tuple[str, str], str] = {}
    with open(mapping_path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            w = (r.get("website") or "").strip()
            if w:
                fills[(nname(r.get("name", "")), ncity(r.get("city", "")))] = w

    with open(master, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames
        rows = list(reader)

    n = 0
    for row in rows:
        if (row.get("website") or "").strip():
            continue
        key = (nname(row["name"]), ncity(row["city"]))
        if key in fills:
            row["website"] = fills[key]
            n += 1

    with open(master, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    have = sum(1 for r in rows if (r.get("website") or "").strip())
    print(f"{master.name}: filled {n} websites; now {have}/{len(rows)} populated")


if __name__ == "__main__":
    main()
