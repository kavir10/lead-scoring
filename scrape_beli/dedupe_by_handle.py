"""Final pass: merge rows that share the same ig_handle.

When the same handle appears multiple times (different name spelling or city
granularity), keep one row per handle — the most-complete one — and prefer
the more canonical city (NYC > Brooklyn, Boston > Somerville).
"""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict


CONF_RANK = {"high": 3, "med": 2, "low": 1, "": 0, None: 0}

# Higher = more canonical (city-level over neighborhood-level)
CITY_PREF = {
    "new york": 2, "brooklyn": 1, "queens": 1, "manhattan": 1, "bronx": 1, "astoria": 1,
    "boston": 2, "cambridge": 1, "somerville": 1, "brookline": 1,
    "los angeles": 2, "hollywood": 1, "silver lake": 1, "west hollywood": 1,
    "santa monica": 1, "venice": 1, "beverly hills": 1, "sawtelle": 1,
    "san francisco": 2, "oakland": 1, "berkeley": 1,
    "washington": 2, "alexandria": 1,
    "miami": 2, "miami beach": 1,
}


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def signal_score(r):
    score = 0
    for f in ("website", "bio", "ig_business_category", "cuisine", "post_title", "caption_summary"):
        if (r.get(f) or "").strip():
            score += 1
    score += CONF_RANK.get(r.get("confidence"), 0) * 2
    try:
        if int(float(r.get("ig_followers") or 0)) > 0:
            score += 1
    except (ValueError, TypeError):
        pass
    # Prefer more canonical city
    score += CITY_PREF.get(norm(r.get("city")), 0)
    # Prefer longer business name (usually more complete)
    score += min(len((r.get("business_name") or "").strip()), 40) / 40
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

    by_handle = defaultdict(list)
    no_handle = []
    for r in rows:
        h = (r.get("ig_handle") or "").lower().strip()
        if h:
            by_handle[h].append(r)
        else:
            no_handle.append(r)

    kept = list(no_handle)
    dropped = 0
    for h, grp in by_handle.items():
        if len(grp) == 1:
            kept.append(grp[0])
            continue
        grp.sort(key=signal_score, reverse=True)
        winner = grp[0]
        # merge: prefer non-empty fields from any sibling row
        for sib in grp[1:]:
            for k, v in sib.items():
                if not (winner.get(k) or "").strip() and (v or "").strip():
                    winner[k] = v
        kept.append(winner)
        dropped += len(grp) - 1

    print(f"  Handle-dedupe: dropped {dropped} duplicate-handle rows", flush=True)

    # Sanity
    handles = [(r.get("ig_handle") or "").lower().strip() for r in kept]
    handles = [h for h in handles if h]
    assert len(handles) == len(set(handles)), "still residual handle dups"
    print(f"  Output: {len(kept)} rows  (unique handles: {len(set(handles))})", flush=True)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)
    print(f"  Saved -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
