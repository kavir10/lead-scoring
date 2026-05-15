"""Phase 4-6: Merge caption + OCR candidates, fetch websites, US-filter, output CSV."""
import argparse
import csv
import json
import os
import re
import unicodedata
from collections import OrderedDict

from dotenv import load_dotenv

from core.apify import run_actor as _run_apify_actor
from core.geo import BANNED_STATES, CITY_TO_STATE, NON_US_CITIES, US_STATES

load_dotenv()

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def norm_name(s: str) -> str:
    """Lowercase, strip diacritics, drop punctuation, collapse spaces."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_state(city: str, given_state: str | None) -> str | None:
    """Return 2-letter US state, or None if not US."""
    if given_state and given_state.upper() in US_STATES:
        return given_state.upper()
    if not city:
        return None
    c = norm_name(city)
    if c in NON_US_CITIES:
        return None
    return CITY_TO_STATE.get(c)


def merge_candidates(caption_data, ocr_data):
    """Merge caption + OCR into unified per-post candidate list."""
    ocr_by_post = {r["shortCode"]: r for r in ocr_data}
    merged = []

    for post_result in caption_data:
        if not post_result.get("is_us_relevant"):
            continue
        sc = post_result["shortCode"]
        post_url = post_result["post_url"]
        cap_cands = post_result.get("candidates") or []
        ocr_post = ocr_by_post.get(sc, {})
        ocr_items = []
        for slide in ocr_post.get("slides", []):
            if slide.get("is_intro_or_cover"):
                continue
            for it in slide.get("items", []):
                ocr_items.append({**it, "_slide": slide.get("slide_index")})

        # Build name -> caption candidate map
        cap_by_name = {norm_name(c["business_name"]): c for c in cap_cands}
        used_ocr_keys = set()

        # Pass 1: enrich caption candidates with OCR-confirmed city/cuisine
        for cap in cap_cands:
            key = norm_name(cap["business_name"])
            for j, ocr in enumerate(ocr_items):
                if j in used_ocr_keys:
                    continue
                if norm_name(ocr["business_name"]) == key:
                    used_ocr_keys.add(j)
                    # Prefer OCR city if it's more specific (LA neighborhoods -> LA)
                    if not cap.get("city") and ocr.get("city"):
                        cap["city"] = ocr["city"]
                    if not cap.get("cuisine") and ocr.get("cuisine"):
                        cap["cuisine"] = ocr["cuisine"]
                    cap["source"] = "both" if cap.get("source") in ("caption", "tagged") else cap.get("source", "both")
                    break
            cap["post_url"] = post_url
            cap["shortCode"] = sc
            merged.append(cap)

        # Pass 2: OCR-only items (not matched to any caption candidate)
        for j, ocr in enumerate(ocr_items):
            if j in used_ocr_keys:
                continue
            # Avoid duplicates within OCR (same name across multiple slides)
            if any(norm_name(m["business_name"]) == norm_name(ocr["business_name"]) and m.get("city") == ocr.get("city") for m in merged):
                continue
            merged.append({
                "business_name": ocr["business_name"],
                "ig_handle": ocr.get("ig_handle"),
                "city": ocr.get("city"),
                "state": None,
                "cuisine": ocr.get("cuisine"),
                "type_signal": "unclear",
                "confidence": "low",
                "source": "ocr",
                "post_url": post_url,
                "shortCode": sc,
            })
    return merged


def fetch_websites(handles: list[str]) -> dict:
    """Apify profile scrape -> {handle: {website, bio, category}}"""
    if not handles:
        return {}
    handles = list(set(h.lower().strip() for h in handles if h))
    print(f"  Fetching profile data for {len(handles)} handles...", flush=True)
    results = {}
    batch_size = 30
    for i in range(0, len(handles), batch_size):
        batch = handles[i:i + batch_size]
        try:
            items = _run_apify_actor(
                "apify/instagram-profile-scraper",
                {"usernames": batch},
            )
            for it in items:
                u = (it.get("username") or "").lower()
                if u:
                    results[u] = {
                        "website": it.get("externalUrl") or "",
                        "bio": it.get("biography") or "",
                        "category": it.get("businessCategoryName") or "",
                        "ig_followers": it.get("followersCount") or 0,
                    }
        except Exception as e:
            print(f"    [batch err] {e}", flush=True)
    print(f"  Resolved {len(results)}/{len(handles)} profiles", flush=True)
    return results


def dedupe(rows: list[dict]) -> list[dict]:
    """Dedupe by ig_handle first, then (name, city)."""
    by_handle = OrderedDict()
    no_handle = []
    for r in rows:
        h = (r.get("ig_handle") or "").lower().strip()
        if h:
            if h not in by_handle:
                by_handle[h] = r
            else:
                # merge: keep higher confidence
                existing = by_handle[h]
                conf_rank = {"high": 3, "med": 2, "low": 1}
                if conf_rank.get(r.get("confidence"), 0) > conf_rank.get(existing.get("confidence"), 0):
                    by_handle[h] = r
        else:
            no_handle.append(r)

    # for no-handle, dedupe by (name, city)
    seen = set()
    deduped_no_handle = []
    for r in no_handle:
        key = (norm_name(r.get("business_name", "")), norm_name(r.get("city", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped_no_handle.append(r)

    return list(by_handle.values()) + deduped_no_handle


def classify_category(c: dict) -> str:
    """Map type_signal + cuisine into final category bucket."""
    ts = (c.get("type_signal") or "").lower()
    cuisine = (c.get("cuisine") or "").lower()
    if ts in ("bakery", "coffee", "bar", "dessert"):
        return ts
    if ts in ("neighborhood", "destination", "fast_casual"):
        return f"{ts}_restaurant" if ts != "fast_casual" else "fast_casual"
    # infer from cuisine
    if "bakery" in cuisine or "bagel" in cuisine or "biscuit" in cuisine:
        return "bakery"
    if "coffee" in cuisine or "cafe" in cuisine:
        return "coffee"
    if "ice cream" in cuisine or "dessert" in cuisine or "frozen yogurt" in cuisine:
        return "dessert"
    if "bar" in cuisine or "cocktail" in cuisine:
        return "bar"
    # default
    return "neighborhood_restaurant"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captions", required=True)
    ap.add_argument("--ocr", required=True)
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--skip-websites", action="store_true", help="Skip Apify profile lookup")
    args = ap.parse_args()

    cap_data = json.load(open(args.captions))
    ocr_data = json.load(open(args.ocr))

    print("  Merging caption + OCR...", flush=True)
    merged = merge_candidates(cap_data, ocr_data)
    print(f"  Pre-filter: {len(merged)} candidates", flush=True)

    # US filter
    us_rows = []
    dropped = 0
    for c in merged:
        state = resolve_state(c.get("city"), c.get("state"))
        if state is None:
            dropped += 1
            continue
        c["state"] = state
        us_rows.append(c)
    print(f"  US-only: kept {len(us_rows)}, dropped {dropped} non-US/unresolved", flush=True)

    # Banned-states filter (Table22 doesn't ship to these)
    banned_dropped = sum(1 for c in us_rows if c["state"] in BANNED_STATES)
    us_rows = [c for c in us_rows if c["state"] not in BANNED_STATES]
    if banned_dropped:
        print(f"  Banned-states: dropped {banned_dropped} rows in {sorted(BANNED_STATES)}", flush=True)

    # Dedupe
    deduped = dedupe(us_rows)
    print(f"  Deduped: {len(deduped)}", flush=True)

    # Fetch websites for handles
    if not args.skip_websites:
        handles = [c["ig_handle"] for c in deduped if c.get("ig_handle")]
        profile_data = fetch_websites(handles)
        for c in deduped:
            h = (c.get("ig_handle") or "").lower()
            p = profile_data.get(h, {})
            c["website"] = p.get("website", "")
            c["bio"] = p.get("bio", "")
            c["ig_business_category"] = p.get("category", "")
            c["ig_followers"] = p.get("ig_followers", 0)
    else:
        for c in deduped:
            c.setdefault("website", "")
            c.setdefault("bio", "")
            c.setdefault("ig_business_category", "")
            c.setdefault("ig_followers", 0)

    # Final classify
    for c in deduped:
        c["category"] = classify_category(c)

    # Write CSV
    cols = [
        "business_name", "ig_handle", "website", "city", "state",
        "category", "cuisine", "confidence", "source",
        "ig_followers", "ig_business_category", "bio",
        "source_post_url", "shortCode",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in deduped:
            row = dict(c)
            row["source_post_url"] = c.get("post_url")
            w.writerow(row)
    print(f"  Saved -> {args.out}", flush=True)
    print(f"  Total rows: {len(deduped)}", flush=True)

    # Stats
    from collections import Counter
    cat_counts = Counter(c["category"] for c in deduped)
    state_counts = Counter(c["state"] for c in deduped)
    conf_counts = Counter(c.get("confidence") for c in deduped)
    has_handle = sum(1 for c in deduped if c.get("ig_handle"))
    has_website = sum(1 for c in deduped if c.get("website"))
    print(f"  with ig_handle: {has_handle}/{len(deduped)}")
    print(f"  with website: {has_website}/{len(deduped)}")
    print(f"  by confidence: {dict(conf_counts)}")
    print(f"  by category: {dict(cat_counts)}")
    print(f"  by state: {dict(state_counts)}")


if __name__ == "__main__":
    main()
