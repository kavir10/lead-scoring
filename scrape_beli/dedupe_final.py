"""Smart dedupe pass:
- Group by (normalized business_name, normalized city).
- If group has rows with AND without ig_handle, drop handle-less rows (subsumed).
- If multiple rows with DIFFERENT handles → keep all (different businesses).
- If multiple handle-less → keep highest confidence, then most signal columns filled.
- Cross-check no remaining ig_handle duplicates afterward.
"""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict


CONF_RANK = {"high": 3, "med": 2, "low": 1, "": 0, None: 0}


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def signal_score(row: dict) -> int:
    """Higher = more complete row."""
    score = 0
    for f in ("ig_handle", "website", "bio", "ig_business_category", "cuisine"):
        v = row.get(f) or ""
        if str(v).strip():
            score += 1
    score += CONF_RANK.get(row.get("confidence"), 0) * 2
    try:
        followers = int(float(row.get("ig_followers") or 0))
    except (ValueError, TypeError):
        followers = 0
    if followers > 0:
        score += 1
    return score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames

    print(f"  Input: {len(rows)} rows", flush=True)

    # Group by (norm_name, norm_city)
    groups = defaultdict(list)
    for r in rows:
        key = (norm(r.get("business_name", "")), norm(r.get("city", "")))
        groups[key].append(r)

    kept = []
    dropped = 0
    merged_count = 0

    for key, grp in groups.items():
        if len(grp) == 1:
            kept.append(grp[0])
            continue

        # Split by handle presence
        with_handle = [r for r in grp if (r.get("ig_handle") or "").strip()]
        no_handle = [r for r in grp if not (r.get("ig_handle") or "").strip()]

        if with_handle:
            # Group rows with handles by handle
            by_handle = defaultdict(list)
            for r in with_handle:
                by_handle[(r["ig_handle"] or "").lower().strip()].append(r)
            # For each unique handle, keep best row
            for h, hrows in by_handle.items():
                hrows.sort(key=signal_score, reverse=True)
                kept.append(hrows[0])
                dropped += len(hrows) - 1
            # All no-handle rows are subsumed by the tagged version
            dropped += len(no_handle)
            merged_count += len(no_handle)
        else:
            # All handle-less. Keep the most-signal row.
            no_handle.sort(key=signal_score, reverse=True)
            kept.append(no_handle[0])
            dropped += len(no_handle) - 1

    print(f"  Output: {len(kept)} rows (dropped {dropped} dups, merged {merged_count} caption-only into tagged)", flush=True)

    # Sanity: no handle dups
    handles = [(r.get("ig_handle") or "").lower().strip() for r in kept]
    handles = [h for h in handles if h]
    if len(handles) != len(set(handles)):
        from collections import Counter
        c = Counter(handles)
        bad = {k: v for k, v in c.items() if v > 1}
        print(f"  [WARN] residual handle dups: {bad}", flush=True)
    else:
        print(f"  Handle uniqueness OK ({len(set(handles))} unique handles)", flush=True)

    # Sanity: no (name, city) dups remaining
    pairs = [(norm(r.get("business_name", "")), norm(r.get("city", ""))) for r in kept]
    from collections import Counter
    pair_counts = Counter(pairs)
    pair_dups = {k: v for k, v in pair_counts.items() if v > 1}
    if pair_dups:
        print(f"  Note: {len(pair_dups)} (name,city) pairs still have multiple rows — these are different handles (legit different businesses or multi-location):", flush=True)
        for k, v in list(pair_dups.items())[:5]:
            print(f"    {k}: {v}", flush=True)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)
    print(f"  Saved -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
