"""
Cleaning pass for the directories master file.

Takes `output/directories_all_<YYYYMMDD>.csv` and produces a sales-ready CSV
with the following operations:

  1. Cross-source dedupe — collapse rows with the same (name, city) across
     sources. Adds `source_count`, `all_sources`, `all_distinctions` columns
     so multi-source signal is preserved.
  2. Chain filter (DELETE) — uses `config.CHAIN_KEYWORDS` via discover.is_chain.
  3. Liquor-store filter (DELETE) — uses `config.LIQUOR_KEYWORDS` via
     discover.is_liquor_store.
  4. Serper Maps lookup — for each remaining row, query Serper Maps with the
     shop name + best-known location to:
       - Verify US location (DELETE non-US)
       - Pull website, address, phone, rating, review_count, lat/lng
       - Re-check chain/liquor against Serper's category data
  5. Website classification — flag (don't delete) as one of:
       - "business"   : a non-platform domain (presumed real business site)
       - "platform"   : Instagram / Facebook / Tock / Resy / Linktree / Squarespace-default /
                        Wixsite / Shopify-default / etc.
       - "missing"    : no website found
       - "invalid"    : website returned but failed HEAD/GET check

Output: `output/directories_cleaned_<YYYYMMDD>.csv`.

Usage:
    source .venv/bin/activate
    python clean_directories.py
    python clean_directories.py --input output/directories_all_20260515.csv
    python clean_directories.py --no-website-check    # skip HEAD/GET, faster
    python clean_directories.py --limit 50            # debug; only process N rows
"""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CHAIN_KEYWORDS, LIQUOR_KEYWORDS  # noqa: E402
from discover import search_serper_maps, parse_town_state  # noqa: E402


# Word-boundary chain match. Avoids false positives like "Geraldine's" matching
# "aldi" or "Big Tree" matching "big y". Multi-word chain keywords ("whole foods",
# "total wine") fall back to substring; those tokens are unambiguous.
_CHAIN_PATTERNS = [
    (kw, re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) if " " not in kw
                else re.compile(re.escape(kw), re.IGNORECASE))
    for kw in CHAIN_KEYWORDS
]


def is_chain(name: str) -> bool:
    """Word-boundary chain check — stricter than discover.is_chain (which does
    substring match and produces false positives)."""
    if not name:
        return False
    return any(pat.search(name) for _, pat in _CHAIN_PATTERNS)


def is_liquor_store(name: str, category: str) -> bool:
    """Match liquor stores by category only. Name-based liquor matching deletes
    legit NY/NJ wine shops licensed as 'Wine & Spirits' (Astor, 67, Bedford, etc.)."""
    cat = (category or "").lower()
    if not cat:
        return False
    return any(kw in cat for kw in LIQUOR_KEYWORDS)


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


# ---------------------------------------------------------------------------
# State inference from lat/lng for Raisin rows (no city/state in source data)
# ---------------------------------------------------------------------------

# Tight state bounding boxes (lat_s, lat_n, lng_w, lng_e). Coarse — used only
# to set Serper's `location` parameter for Raisin entries. Accurate enough
# for that purpose; not used for the final state column (Serper overwrites).
STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    "AL": (30.2, 35.0, -88.5, -84.9),  "AK": (51.0, 71.5, -180.0, -129.0),
    "AZ": (31.3, 37.0, -114.8, -109.0),"AR": (33.0, 36.5, -94.6, -89.6),
    "CA": (32.5, 42.0, -124.5, -114.1),"CO": (37.0, 41.0, -109.1, -102.0),
    "CT": (40.9, 42.1, -73.7, -71.8),  "DE": (38.4, 39.9, -75.8, -75.0),
    "FL": (24.4, 31.0, -87.6, -80.0),  "GA": (30.4, 35.0, -85.6, -80.8),
    "HI": (18.9, 22.3, -160.3, -154.7),"ID": (42.0, 49.0, -117.2, -111.0),
    "IL": (36.9, 42.5, -91.5, -87.5),  "IN": (37.8, 41.8, -88.1, -84.8),
    "IA": (40.4, 43.5, -96.6, -90.1),  "KS": (37.0, 40.0, -102.1, -94.6),
    "KY": (36.5, 39.2, -89.6, -82.0),  "LA": (28.9, 33.0, -94.0, -88.8),
    "ME": (43.0, 47.5, -71.1, -66.9),  "MD": (37.9, 39.7, -79.5, -75.0),
    "MA": (41.2, 42.9, -73.5, -69.9),  "MI": (41.7, 47.5, -90.4, -82.4),
    "MN": (43.5, 49.4, -97.3, -89.5),  "MS": (30.2, 35.0, -91.7, -88.1),
    "MO": (36.0, 40.6, -95.8, -89.1),  "MT": (44.4, 49.0, -116.1, -104.0),
    "NE": (40.0, 43.0, -104.1, -95.3), "NV": (35.0, 42.0, -120.0, -114.0),
    "NH": (42.7, 45.3, -72.6, -70.6),  "NJ": (38.9, 41.4, -75.6, -73.9),
    "NM": (31.3, 37.0, -109.1, -103.0),"NY": (40.5, 45.1, -79.8, -71.9),
    "NC": (33.8, 36.6, -84.4, -75.5),  "ND": (45.9, 49.0, -104.1, -96.6),
    "OH": (38.4, 42.0, -84.8, -80.5),  "OK": (33.6, 37.0, -103.0, -94.4),
    "OR": (41.9, 46.3, -124.6, -116.5),"PA": (39.7, 42.3, -80.6, -74.7),
    "RI": (41.1, 42.0, -71.9, -71.1),  "SC": (32.0, 35.2, -83.4, -78.5),
    "SD": (42.4, 46.0, -104.1, -96.4), "TN": (34.9, 36.7, -90.4, -81.7),
    "TX": (25.8, 36.5, -106.7, -93.5), "UT": (37.0, 42.0, -114.1, -109.0),
    "VT": (42.7, 45.0, -73.5, -71.5),  "VA": (36.5, 39.5, -83.7, -75.2),
    "WA": (45.5, 49.0, -124.8, -116.9),"WV": (37.2, 40.6, -82.7, -77.7),
    "WI": (42.5, 47.1, -92.9, -86.8),  "WY": (41.0, 45.0, -111.1, -104.0),
    "DC": (38.8, 39.0, -77.2, -76.9),
}


def state_from_latlng(lat: float, lng: float) -> str:
    """Return 2-letter state code or '' if no bbox matches."""
    for code, (s, n, w, e) in STATE_BBOX.items():
        if s <= lat <= n and w <= lng <= e:
            return code
    return ""


def parse_latlng_from_blurb(blurb: str) -> tuple[float | None, float | None]:
    """Extract lat/lng from Raisin blurb like 'Raisin id=... lat=40.7 lng=-74.0 likes=3'."""
    if not blurb:
        return None, None
    m = re.search(r"lat=([-0-9.]+)\s+lng=([-0-9.]+)", blurb)
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None


# ---------------------------------------------------------------------------
# Website classification
# ---------------------------------------------------------------------------

PLATFORM_DOMAINS = {
    # Social
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    # Link aggregators
    "linktr.ee": "linktree",
    "linktree.com": "linktree",
    "beacons.ai": "beacons",
    "lnk.bio": "lnkbio",
    # Reservation / order
    "tock.com": "tock",
    "exploretock.com": "tock",
    "www.exploretock.com": "tock",
    "opentable.com": "opentable",
    "www.opentable.com": "opentable",
    "resy.com": "resy",
    "www.resy.com": "resy",
    "yelp.com": "yelp",
    "www.yelp.com": "yelp",
    "doordash.com": "doordash",
    "ubereats.com": "ubereats",
    "grubhub.com": "grubhub",
    # Generic site builders (subdomains only — custom domains pass)
    "squarespace.com": "squarespace_default",
    "wixsite.com": "wix_default",
    "wix.com": "wix_default",
    "shopify.com": "shopify_default",
    "myshopify.com": "shopify_default",
    "weebly.com": "weebly_default",
    "godaddysites.com": "godaddy_default",
    "carrd.co": "carrd",
    "wordpress.com": "wordpress_default",
    "substack.com": "substack",
    # Review/listing
    "tripadvisor.com": "tripadvisor",
    "google.com": "google",
    "maps.google.com": "google_maps",
    "g.page": "google_maps",
    "business.google.com": "google_business",
}


def classify_website(url: str) -> tuple[str, str]:
    """Return (status, platform_name).

    status: "business" | "platform" | "missing"
    platform_name: empty unless platform; e.g. "instagram", "squarespace_default"
    """
    if not url or not isinstance(url, str) or not url.strip():
        return "missing", ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "missing", ""
    if not host:
        return "missing", ""
    if host in PLATFORM_DOMAINS:
        return "platform", PLATFORM_DOMAINS[host]
    # Also catch subdomains of platform domains (e.g. someshop.myshopify.com)
    for platform_host, name in PLATFORM_DOMAINS.items():
        if host.endswith("." + platform_host):
            return "platform", name
    return "business", ""


def verify_website(url: str, timeout: int = 8) -> bool:
    """Quick HEAD/GET to confirm the site responds. False if 4xx/5xx/connect-err."""
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        # HEAD often gets blocked or returns 405; fall back to GET.
        r = requests.head(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        if 200 <= r.status_code < 400:
            return True
        if r.status_code in (403, 405, 501):
            r = requests.get(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            return 200 <= r.status_code < 400
        return False
    except requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# Cross-source dedupe
# ---------------------------------------------------------------------------

def dedupe_cross_source(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse rows with the same (name, city). Aggregates source list/count.

    For Raisin rows (empty city), we also try to match against stockist rows
    by name only — but only when the name is unambiguous (1 stockist row).
    """
    df = df.copy()
    df["_name_n"] = df["name"].fillna("").str.lower().str.strip()
    df["_city_n"] = df["city"].fillna("").str.lower().str.strip()

    # First pass: group by (name, city) for rows that have a city.
    has_city = df[df["_city_n"] != ""]
    no_city = df[df["_city_n"] == ""]

    grouped_with_city = (
        has_city.groupby(["_name_n", "_city_n"])
        .agg(
            name=("name", "first"),
            city=("city", "first"),
            state=("state", "first"),
            country=("country", "first"),
            business_type=("business_type", "first"),
            source_count=("source", "nunique"),
            all_sources=("source", lambda s: "|".join(sorted(set(s)))),
            all_distinctions=("distinction", lambda s: "|".join(sorted(set(d for d in s if d)))),
            source_url=("source_url", "first"),
            blurb=("blurb", "first"),
            tier=("tier", "min"),
        )
        .reset_index(drop=True)
    )

    # Second pass: for no-city rows (Raisin), check whether the name already
    # exists in grouped_with_city. If yes, merge into that row's source list.
    name_index = {r["name"].lower().strip(): i for i, r in grouped_with_city.iterrows()}
    leftover_no_city = []
    for _, r in no_city.iterrows():
        key = r["_name_n"]
        if key in name_index:
            i = name_index[key]
            existing_sources = set(grouped_with_city.at[i, "all_sources"].split("|"))
            existing_sources.add(r["source"])
            grouped_with_city.at[i, "all_sources"] = "|".join(sorted(existing_sources))
            grouped_with_city.at[i, "source_count"] = len(existing_sources)
            existing_distinctions = set(filter(None, grouped_with_city.at[i, "all_distinctions"].split("|")))
            if r["distinction"]:
                existing_distinctions.add(r["distinction"])
            grouped_with_city.at[i, "all_distinctions"] = "|".join(sorted(existing_distinctions))
            # Prefer the blurb that has lat/lng (Raisin)
            if "lat=" in (r.get("blurb") or "") and "lat=" not in (grouped_with_city.at[i, "blurb"] or ""):
                grouped_with_city.at[i, "blurb"] = r["blurb"]
        else:
            leftover_no_city.append(r)

    if leftover_no_city:
        no_city_df = pd.DataFrame(leftover_no_city)
        no_city_grouped = (
            no_city_df.groupby("_name_n")
            .agg(
                name=("name", "first"),
                city=("city", "first"),
                state=("state", "first"),
                country=("country", "first"),
                business_type=("business_type", "first"),
                source_count=("source", "nunique"),
                all_sources=("source", lambda s: "|".join(sorted(set(s)))),
                all_distinctions=("distinction", lambda s: "|".join(sorted(set(d for d in s if d)))),
                source_url=("source_url", "first"),
                blurb=("blurb", "first"),
                tier=("tier", "min"),
            )
            .reset_index(drop=True)
        )
        result = pd.concat([grouped_with_city, no_city_grouped], ignore_index=True)
    else:
        result = grouped_with_city

    return result


# ---------------------------------------------------------------------------
# Serper Maps verification
# ---------------------------------------------------------------------------

def _serper_lookup_for_row(row: dict) -> dict:
    """Look up one shop via Serper Maps. Returns merged dict with verification fields.

    Search strategy:
      - Have city + state: query "<name> wine", location="<city>, <state>"
      - Have state only: query "<name> wine", location="<state>, United States"
      - Have lat/lng (Raisin): infer state from bbox, then as above
      - Neither: skip lookup, mark as no_lookup
    """
    name = row.get("name", "") or ""
    city = (row.get("city") or "").strip()
    state = (row.get("state") or "").strip()
    blurb = row.get("blurb", "") or ""

    # If no state, try inferring from Raisin lat/lng.
    inferred_state = ""
    if not state:
        lat, lng = parse_latlng_from_blurb(blurb)
        if lat is not None and lng is not None:
            inferred_state = state_from_latlng(lat, lng)

    use_state = state or inferred_state

    if city and use_state:
        location = f"{city}, {use_state}"
    elif use_state:
        location = f"{use_state}, United States"
    else:
        return {
            "lookup_status": "no_lookup",
            "serper_name": "",
            "serper_address": "",
            "serper_city": "",
            "serper_state": "",
            "website": "",
            "phone": "",
            "rating": None,
            "review_count": None,
            "lat": None,
            "lng": None,
            "serper_category": "",
            "serper_types": "",
        }

    query = f"{name} wine"
    try:
        results = search_serper_maps(query, location)
    except Exception as e:
        return {"lookup_status": f"error:{type(e).__name__}", "serper_name": "", "serper_address": "",
                "serper_city": "", "serper_state": "", "website": "", "phone": "",
                "rating": None, "review_count": None, "lat": None, "lng": None,
                "serper_category": "", "serper_types": ""}

    if not results:
        return {"lookup_status": "not_found", "serper_name": "", "serper_address": "",
                "serper_city": "", "serper_state": "", "website": "", "phone": "",
                "rating": None, "review_count": None, "lat": None, "lng": None,
                "serper_category": "", "serper_types": ""}

    # Best-match heuristic: top result whose name shares the first significant word
    # with the source name. Falls back to top result.
    name_lower = name.lower()
    first_word = re.split(r"[\s&-]+", name_lower, 1)[0] if name_lower else ""
    chosen = None
    for r in results[:5]:
        rn = (r.get("name") or "").lower()
        if first_word and (first_word in rn or rn.split(" ")[0] in name_lower):
            chosen = r
            break
    chosen = chosen or results[0]

    addr = chosen.get("address", "") or ""
    parsed_city, parsed_state = parse_town_state(addr)

    return {
        "lookup_status": "found",
        "serper_name": chosen.get("name", ""),
        "serper_address": addr,
        "serper_city": parsed_city,
        "serper_state": parsed_state,
        "website": chosen.get("website", "") or "",
        "phone": chosen.get("phone", "") or "",
        "rating": chosen.get("rating"),
        "review_count": chosen.get("review_count"),
        "lat": chosen.get("latitude"),
        "lng": chosen.get("longitude"),
        "serper_category": chosen.get("category", "") or chosen.get("type", ""),
        "serper_types": chosen.get("types", ""),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def latest_master() -> Path:
    files = sorted(OUTPUT_DIR.glob("directories_all_*.csv"))
    if not files:
        raise SystemExit("No directories_all_*.csv found in output/")
    return files[-1]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", type=str, default="", help="Input CSV path (default: latest)")
    p.add_argument("--limit", type=int, default=0, help="Process only N rows (debug)")
    p.add_argument("--workers", type=int, default=8, help="Concurrent Serper lookups")
    p.add_argument("--no-website-check", action="store_true",
                   help="Skip the HTTP HEAD verification of websites (faster, no invalid flag)")
    args = p.parse_args()

    in_path = Path(args.input) if args.input else latest_master()
    print(f"Loading {in_path}")
    df = pd.read_csv(in_path, dtype=str).fillna("")
    print(f"  Loaded {len(df)} rows from {df['source'].nunique()} sources")

    # 1. Cross-source dedupe
    print("\n[1/5] Cross-source dedupe")
    before = len(df)
    df = dedupe_cross_source(df)
    print(f"  {before} -> {len(df)} rows after dedup ({before - len(df)} collapsed)")
    multi = (df["source_count"] > 1).sum()
    print(f"  Rows on 2+ sources: {multi}")

    # 2. Name-based chain filter only (liquor filter runs post-Serper using category)
    print("\n[2/5] Chain filter (name, word-boundary)")
    chain_mask = df["name"].apply(is_chain)
    print(f"  Chains flagged: {chain_mask.sum()}")
    if chain_mask.sum():
        print(f"  Sample: {df.loc[chain_mask, 'name'].head(10).tolist()}")
    df = df[~chain_mask].reset_index(drop=True)
    print(f"  After filter: {len(df)} rows")

    if args.limit > 0:
        df = df.head(args.limit).reset_index(drop=True)
        print(f"\n  --limit {args.limit} applied; processing {len(df)} rows")

    # 3. Serper Maps lookup (concurrent)
    print(f"\n[3/5] Serper Maps verification ({args.workers} workers)")
    lookup_results: list[dict] = [None] * len(df)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_serper_lookup_for_row, df.iloc[i].to_dict()): i for i in range(len(df))}
        completed = 0
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                lookup_results[i] = fut.result()
            except Exception as e:
                lookup_results[i] = {"lookup_status": f"error:{type(e).__name__}"}
            completed += 1
            if completed % 25 == 0 or completed == len(df):
                print(f"  [{completed}/{len(df)}]", flush=True)

    lookup_df = pd.DataFrame(lookup_results)
    df = pd.concat([df.reset_index(drop=True), lookup_df], axis=1)
    print(f"  Lookup status counts:\n{df['lookup_status'].value_counts().to_string()}")

    # 4. Post-Serper filter — non-US drops + chain re-check against Serper-cleaned name.
    # NOTE: we intentionally DO NOT filter by Google's "Liquor store" category here.
    # In NY/NJ wine retailers are licensed (and Google-categorized) as "Liquor store"
    # by default, so that filter false-positive drops marquee shops like Flatiron
    # Wines, Astor Wines, Michael-Towne, Copake Wine Works, etc. Source curation
    # (importer stockist pages) already filters for wine retailers.
    print("\n[4/5] Post-Serper filter (non-US + chain re-check)")
    has_us_state_post = (df["serper_state"] != "") | (df["state"].isin(list(STATE_BBOX.keys())))
    non_us = ~has_us_state_post & (df["lookup_status"] == "found")
    chain2 = df.apply(lambda r: is_chain(r.get("serper_name") or "") or is_chain(r["name"]), axis=1)
    drop_mask = non_us | chain2
    print(f"  Non-US drops: {non_us.sum()}")
    print(f"  Chain drops (post-Serper): {(chain2 & ~non_us).sum()}")
    print(f"  Total dropping: {drop_mask.sum()}")

    # Save dropped rows for review
    dropped = df[drop_mask].copy()
    dropped["drop_reason"] = ""
    dropped.loc[non_us[drop_mask], "drop_reason"] = "non_us"
    dropped.loc[chain2[drop_mask] & ~non_us[drop_mask], "drop_reason"] = "chain"
    stamp_now = datetime.now().strftime("%Y%m%d")
    dropped_path = OUTPUT_DIR / f"directories_dropped_{stamp_now}.csv"
    drop_cols = ["name", "serper_name", "city", "state", "serper_address", "serper_category",
                 "website", "drop_reason"]
    drop_cols = [c for c in drop_cols if c in dropped.columns]
    dropped[drop_cols].to_csv(dropped_path, index=False)
    print(f"  Dropped rows -> {dropped_path.relative_to(ROOT)}")

    df = df[~drop_mask].reset_index(drop=True)
    print(f"  After filter: {len(df)} rows")

    # Promote Serper city/state into the canonical columns when our row lacks them
    df["city"] = df.apply(lambda r: r["city"] if r["city"] else r.get("serper_city", "") or "", axis=1)
    df["state"] = df.apply(lambda r: r["state"] if r["state"] else r.get("serper_state", "") or "", axis=1)

    # 5. Classify websites + optional HTTP check
    print("\n[5/5] Website classification")
    classifications = df["website"].apply(classify_website)
    df["website_status"] = classifications.apply(lambda t: t[0])  # business | platform | missing
    df["website_platform"] = classifications.apply(lambda t: t[1])  # e.g. "instagram"

    if not args.no_website_check:
        print(f"  HTTP verifying {(df['website_status'] != 'missing').sum()} websites...")
        valid: list[bool | None] = [None] * len(df)
        idx_to_check = [(i, df.at[i, "website"]) for i in df.index if df.at[i, "website_status"] != "missing"]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(verify_website, url): i for i, url in idx_to_check}
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    valid[i] = fut.result()
                except Exception:
                    valid[i] = False
                done += 1
                if done % 50 == 0 or done == len(idx_to_check):
                    print(f"  [{done}/{len(idx_to_check)}]", flush=True)
        for i in df.index:
            if df.at[i, "website_status"] == "missing":
                continue
            if not valid[i]:
                # Keep the original classification (business/platform) but also flag invalid
                df.at[i, "website_status"] = (df.at[i, "website_status"] + "_invalid")
    print(f"  Website status counts:\n{df['website_status'].value_counts().to_string()}")

    # Final column order
    cols = [
        "name", "city", "state", "country", "business_type", "tier",
        "source_count", "all_sources", "all_distinctions",
        "website", "website_status", "website_platform",
        "phone", "rating", "review_count",
        "serper_name", "serper_address",
        "lat", "lng",
        "lookup_status", "blurb",
    ]
    cols = [c for c in cols if c in df.columns]
    df = df[cols].copy()

    stamp = datetime.now().strftime("%Y%m%d")
    out_path = OUTPUT_DIR / f"directories_cleaned_{stamp}.csv"
    df.to_csv(out_path, index=False)
    print(f"\nWrote {len(df)} rows -> {out_path.relative_to(ROOT)}")

    # Summary
    print("\n=== Summary ===")
    print(f"  Rows: {len(df)}")
    print(f"  On 2+ sources: {(df['source_count'] > 1).sum()}")
    print(f"  With website: {(df['website'] != '').sum()}")
    print(f"  business website:        {df['website_status'].eq('business').sum()}")
    print(f"  business_invalid:        {df['website_status'].eq('business_invalid').sum()}")
    print(f"  platform website:        {df['website_status'].eq('platform').sum()}")
    print(f"  platform_invalid:        {df['website_status'].eq('platform_invalid').sum()}")
    print(f"  missing website:         {df['website_status'].eq('missing').sum()}")
    print(f"\n  States covered: {df['state'].nunique()}")
    print(df["state"].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
