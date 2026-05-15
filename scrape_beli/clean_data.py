"""Comprehensive data-cleaning pass on the Beli leads CSV.

Operations:
1. Strip whitespace, normalize unicode in text fields
2. Cuisine: lowercase + dedupe tokens + sort
3. Add `website_type`:  direct | linktree | reservation_platform | kickstarter | blank
4. Add `quality_flag`:  pipe-separated tags (handle_location_mismatch, caption_only,
                        multi_city_brand, no_followers, etc.)
5. Add `chain_locations`: count of rows with same normalized business_name (>1 = chain)
6. Coerce ig_followers to int (0 for NaN)
7. Trim bio to single-line, max 250 chars
8. Drop literal "nan" strings
9. Title-case city if all-lowercase
"""
import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter


def strip_text(s):
    if s is None:
        return ""
    s = str(s)
    if s.lower() == "nan":
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_key(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def clean_cuisine(s: str) -> str:
    """Lowercase, split on commas, dedupe, sort, rejoin."""
    if not s:
        return ""
    parts = [p.strip().lower() for p in re.split(r"[,/;]+", s) if p.strip()]
    # dedupe preserving first-seen order then sort alpha
    seen = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return ", ".join(sorted(seen))


def website_type(url: str) -> str:
    if not url:
        return "blank"
    u = url.lower()
    if "linktr.ee" in u or "linkin.bio" in u or "beacons.ai" in u or "lnk.bio" in u:
        return "linktree"
    if "opentable.com" in u or "resy.com" in u or "tables.toasttab.com" in u or "sevenrooms.com" in u or "exploretock.com" in u:
        return "reservation_platform"
    if "kickstarter.com" in u or "gofundme.com" in u or "patreon.com" in u:
        return "crowdfunding"
    if "instagram.com" in u or "facebook.com" in u or "tiktok.com" in u:
        return "social_only"
    if "doordash.com" in u or "ubereats.com" in u or "grubhub.com" in u or "seamless.com" in u or "toasttab.com/order" in u:
        return "delivery_platform"
    return "direct"


def detect_handle_location_mismatch(name: str, handle: str, city: str) -> bool:
    """Flag if handle suffix names a non-US city while the assigned city is US."""
    if not handle or not city:
        return False
    h = handle.lower()
    name_norm = norm_key(name)
    city_norm = norm_key(city)
    non_us = ["london", "paris", "tokyo", "toronto", "dubai", "sydney", "melbourne",
              "berlin", "madrid", "barcelona", "milan", "rome", "amsterdam"]
    for token in non_us:
        if token in h and token not in name_norm and token not in city_norm:
            return True
    return False


def title_case_smart(s: str) -> str:
    """Title-case unless string already has any uppercase."""
    if not s:
        return s
    if any(c.isupper() for c in s):
        return s
    return s.title()


# City -> metro grouping. Used to catch dups where Beli used different city granularity
# (e.g. "Brooklyn" vs "New York" for the same restaurant).
CITY_TO_METRO = {
    "new york": "NYC", "brooklyn": "NYC", "queens": "NYC", "manhattan": "NYC", "bronx": "NYC",
    "boston": "Boston", "cambridge": "Boston", "brookline": "Boston", "somerville": "Boston",
    "los angeles": "LA", "silver lake": "LA", "west hollywood": "LA", "beverly hills": "LA",
    "sawtelle": "LA", "east hollywood": "LA", "santa monica": "LA", "venice": "LA",
    "hollywood": "LA", "hermosa beach": "LA", "gardena": "LA", "arcadia": "LA",
    "san francisco": "SF Bay", "oakland": "SF Bay", "berkeley": "SF Bay", "san jose": "SF Bay",
    "miami": "Miami", "miami beach": "Miami",
    "washington": "DC", "alexandria": "DC",
}


def metro(city: str) -> str:
    return CITY_TO_METRO.get(norm_key(city), norm_key(city))


TEXT_FIELDS_TRIM = ["business_name", "ig_handle", "website", "city", "state",
                    "category", "cuisine", "confidence", "source",
                    "ig_business_category", "post_type", "post_title",
                    "caption_summary", "source_post_url", "shortCode"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = list(reader.fieldnames or [])

    print(f"  Input: {len(rows)} rows", flush=True)

    # Metro-aware dedup pass: when no IG handle distinguishes them, treat
    # (norm_name, metro) as the same business. Keep most-specific row.
    SPECIFICITY = {
        "NYC":   {"new york": 1, "brooklyn": 2, "manhattan": 2, "queens": 2, "bronx": 2},
        "Boston":{"boston": 1, "cambridge": 2, "brookline": 2, "somerville": 2},
        "LA":    {"los angeles": 1, "silver lake": 2, "west hollywood": 2, "beverly hills": 2,
                  "santa monica": 2, "venice": 2, "hollywood": 2, "hermosa beach": 2},
        "Miami": {"miami": 1, "miami beach": 2},
    }

    def specificity(city: str, met: str) -> int:
        return SPECIFICITY.get(met, {}).get(norm_key(city), 1)

    # Group ALL rows by (norm_name, metro). For each group:
    #  - Keep all distinct handles (different businesses sharing a name in same metro = legit)
    #  - Drop no-handle rows when a handle-row exists in same group (caption-only is subsumed)
    #  - Among no-handle-only groups, keep most specific city + highest confidence
    CONF = {"high": 3, "med": 2, "low": 1, "": 0, None: 0}
    metro_groups = {}
    for r in rows:
        key = (norm_key(r.get("business_name", "")), metro(r.get("city", "")))
        metro_groups.setdefault(key, []).append(r)

    deduped = []
    n_metro_dropped = 0
    for key, grp in metro_groups.items():
        if len(grp) == 1:
            deduped.append(grp[0])
            continue
        with_h = [r for r in grp if (r.get("ig_handle") or "").strip()]
        no_h = [r for r in grp if not (r.get("ig_handle") or "").strip()]
        if with_h:
            # keep one row per unique handle
            by_handle = {}
            for r in with_h:
                h = r["ig_handle"].lower().strip()
                if h not in by_handle or CONF.get(r.get("confidence"), 0) > CONF.get(by_handle[h].get("confidence"), 0):
                    by_handle[h] = r
            deduped.extend(by_handle.values())
            n_metro_dropped += (len(with_h) - len(by_handle)) + len(no_h)
        else:
            no_h.sort(key=lambda r: (
                specificity(r.get("city", ""), key[1]),
                CONF.get(r.get("confidence"), 0),
            ), reverse=True)
            deduped.append(no_h[0])
            n_metro_dropped += len(no_h) - 1
    rows = deduped
    print(f"  Metro-aware dedup: dropped {n_metro_dropped} duplicates (Brooklyn/NYC, Cambridge/Boston, etc.)", flush=True)

    # Pre-compute chain counts
    name_counts = Counter(norm_key(r.get("business_name", "")) for r in rows)

    cleaned = []
    n_cuisine_changed = 0
    n_quality_flagged = 0
    flag_counter = Counter()

    for r in rows:
        # Strip + normalize text fields
        for f in TEXT_FIELDS_TRIM:
            if f in r:
                r[f] = strip_text(r.get(f))

        # bio: collapse newlines + cap at 250
        bio = strip_text(r.get("bio"))
        if len(bio) > 250:
            bio = bio[:247] + "..."
        r["bio"] = bio

        # caption_full: keep as-is but strip trailing whitespace
        cap = r.get("caption_full") or ""
        r["caption_full"] = cap.strip()

        # cuisine
        before = r.get("cuisine", "")
        after = clean_cuisine(before)
        if after != before:
            n_cuisine_changed += 1
        r["cuisine"] = after

        # city: title-case if all-lower
        r["city"] = title_case_smart(r.get("city", ""))

        # ig_followers -> int
        try:
            v = float(r.get("ig_followers") or 0)
            r["ig_followers"] = int(v) if v >= 0 else 0
        except (ValueError, TypeError):
            r["ig_followers"] = 0

        # state uppercase
        r["state"] = (r.get("state") or "").upper()

        # website_type
        r["website_type"] = website_type(r.get("website", ""))

        # chain_locations
        norm_name = norm_key(r.get("business_name", ""))
        r["chain_locations"] = name_counts.get(norm_name, 1)

        # quality_flag
        flags = []
        if detect_handle_location_mismatch(r.get("business_name", ""), r.get("ig_handle", ""), r.get("city", "")):
            flags.append("handle_location_mismatch")
        if not (r.get("ig_handle") or "").strip():
            flags.append("no_handle")
        if r["ig_followers"] == 0 and (r.get("ig_handle") or "").strip():
            flags.append("no_followers_data")
        if r.get("confidence") == "low":
            flags.append("low_confidence")
        if r["chain_locations"] > 1:
            flags.append("multi_city_brand")
        if r["website_type"] == "blank":
            flags.append("no_website")
        elif r["website_type"] in ("linktree", "social_only"):
            flags.append(f"website_{r['website_type']}")

        if flags:
            n_quality_flagged += 1
            for ff in flags:
                flag_counter[ff] += 1
        r["quality_flag"] = "|".join(flags)

        cleaned.append(r)

    # Output column order: identifying fields first, signal fields, context fields last
    new_cols = [
        "business_name", "ig_handle", "website", "website_type",
        "city", "state", "category", "cuisine",
        "confidence", "quality_flag", "chain_locations",
        "ig_followers", "ig_business_category", "bio",
        "source", "post_type", "post_title", "caption_summary",
        "caption_full", "source_post_url", "shortCode",
    ]
    # preserve any unexpected legacy cols
    for c in cols:
        if c not in new_cols:
            new_cols.append(c)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=new_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(cleaned)

    print(f"  Output: {len(cleaned)} rows -> {args.output}", flush=True)
    print(f"  Cuisine fields normalized: {n_cuisine_changed}", flush=True)
    print(f"  Rows with at least one quality_flag: {n_quality_flagged}", flush=True)
    print(f"  Flag counts:")
    for k, v in flag_counter.most_common():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
