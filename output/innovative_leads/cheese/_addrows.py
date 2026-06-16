#!/usr/bin/env python3
"""Append qualified cheese rows to wave2 CSV, deduping against wave1 + wave2.
Usage: pipe a JSON list of row dicts on stdin.
Row keys: name, city, state, website, source_strategy, source_url, evidence
vertical fixed to 'cheese', date_added fixed to '2026-06-16'.
Prints accepted / skipped counts and skipped names.
"""
import csv, json, sys, re, os

BASE = os.path.dirname(os.path.abspath(__file__))
WAVE1 = os.path.join(BASE, "wave1_mongers_clubs_20260612.csv")
WAVE2 = os.path.join(BASE, "wave2_states_clubs_20260616.csv")

def norm(s):
    s = (s or "").lower().strip()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(the|a|an|llc|inc|co|company|shop|cheese|cheesemonger|cheesemongers|fine|foods|market|gourmet)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def load_names(path):
    names = set()
    if not os.path.exists(path):
        return names
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = r.get("name", "")
            names.add(norm(nm))
            names.add((nm or "").lower().strip())
    return names

def main():
    rows = json.load(sys.stdin)
    existing = load_names(WAVE1) | load_names(WAVE2)
    accepted, skipped = [], []
    seen_this_batch = set()
    with open(WAVE2, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            nm = r.get("name", "").strip()
            key = norm(nm)
            raw = nm.lower().strip()
            if not nm:
                continue
            if key in existing or raw in existing or key in seen_this_batch:
                skipped.append(nm)
                continue
            seen_this_batch.add(key)
            existing.add(key); existing.add(raw)
            w.writerow([
                nm, r.get("city",""), r.get("state",""), r.get("website",""),
                "cheese", r.get("source_strategy",""), r.get("source_url",""),
                r.get("evidence",""), "2026-06-16",
            ])
            accepted.append(nm)
    print(f"ACCEPTED {len(accepted)} | SKIPPED {len(skipped)}")
    if skipped:
        print("skipped: " + "; ".join(skipped))

if __name__ == "__main__":
    main()
