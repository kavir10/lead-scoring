"""
Raisin — natural wine map (raisin.digital).

The Raisin web app exposes a single POST endpoint that returns every venue in
the map with no auth required:

    POST https://www.raisin.digital/en/proxy-map-venues/
    Body: {} (or a {north,south,east,west} bbox to filter)
    Returns: {"data": {"count": N, "items": [{id, name, latitude, longitude, is: [type,...], ...}]}}

A single empty-body POST returns the full global set (~12k venues). We filter
to US lat/lng bounding boxes (continental US + Hawaii + Alaska) and keep only
entries tagged as wine shops (`wine_shop`). Entries that are wine_shop + bar
are kept; pure restaurants/bars are skipped (those flow via other channels).

Address is not exposed in the map API. We emit name + lat/lng (lat/lng in the
`blurb` field) and leave city/state blank — downstream enrichment will resolve
precise address via Google Maps lookup.
"""
from __future__ import annotations

import pandas as pd
import requests

from awards._lib import SCHEMA, make_row, to_dataframe


VENUES_URL = "https://www.raisin.digital/en/proxy-map-venues/"
MAP_URL = "https://www.raisin.digital/en/map/"

# US bboxes split by longitude band to avoid leaking Canadian venues across
# the porous Great Lakes / Quebec / Ontario border. North caps per band:
#   - West of -95° : 49°N (clean US-Canada border)
#   - -95° to -82° : 47°N (Lake Superior / Minnesota / Wisconsin / Michigan UP)
#   - -82° to -75° : 45°N (NY/VT/NH border; loses nothing meaningful in the US)
#   - -75° to -66° : 47.5°N (catches Northern Maine without grabbing Quebec)
US_BBOXES = [
    {"name": "west",        "north": 49.0, "south": 32.0, "west": -125.0, "east": -95.0},
    {"name": "south_tx",    "north": 32.0, "south": 25.8, "west": -107.0, "east": -93.5},
    {"name": "midwest",     "north": 47.0, "south": 36.0, "west": -95.0,  "east": -82.0},
    {"name": "southeast",   "north": 36.0, "south": 24.4, "west": -93.5,  "east": -75.0},
    {"name": "mid_atlantic","north": 45.0, "south": 36.0, "west": -82.0,  "east": -75.0},
    {"name": "northeast_w", "north": 45.0, "south": 40.0, "west": -75.0,  "east": -71.5},
    {"name": "northeast_e", "north": 47.5, "south": 40.0, "west": -71.5,  "east": -66.5},
    {"name": "alaska",      "north": 71.5, "south": 51.0, "west": -180.0, "east": -129.0},
    {"name": "hawaii",      "north": 22.3, "south": 18.9, "west": -160.3, "east": -154.5},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}


def _fetch_all_venues() -> list[dict]:
    """Empty-body POST returns every venue globally (~12k rows)."""
    r = requests.post(VENUES_URL, json={}, headers=HEADERS, timeout=45)
    r.raise_for_status()
    payload = r.json()
    items = payload.get("data", {}).get("items", []) or []
    print(f"  [raisin] global venue count: {payload.get('data', {}).get('count', '?')}", flush=True)
    return items


def _is_us(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    for box in US_BBOXES:
        if box["south"] <= lat <= box["north"] and box["west"] <= lng <= box["east"]:
            return True
    return False


def _is_wine_shop_lead(types: list[str]) -> bool:
    """Keep wine_shop (pure or hybrid). Skip pure restaurants/bars/accommodations."""
    if not types:
        return False
    return "wine_shop" in types


def scrape(**_kwargs) -> pd.DataFrame:
    items = _fetch_all_venues()
    rows = []
    for it in items:
        types = it.get("is") or []
        if not _is_wine_shop_lead(types):
            continue
        lat = it.get("latitude")
        lng = it.get("longitude")
        if not _is_us(lat, lng):
            continue
        # Distinguish pure shops from bar+shop hybrids in the distinction tag.
        if "bar" in types or "restaurant" in types:
            distinction = "Raisin natural wine bar+shop"
        else:
            distinction = "Raisin natural wine shop"
        name = (it.get("name") or "").strip()
        if not name:
            continue
        rows.append(make_row(
            source="raisin_app",
            tier=1,
            business_type="wine_store",
            name=name,
            city="",  # Raisin API doesn't return address; downstream enrichment will resolve
            state="",
            country="us",
            distinction=distinction,
            source_url=MAP_URL,
            blurb=f"Raisin id={it.get('id')} lat={lat} lng={lng} likes={it.get('likevote_number', 0)}",
        ))
    print(f"  [raisin] US wine shops kept: {len(rows)}", flush=True)
    if not rows:
        return pd.DataFrame(columns=SCHEMA)
    return to_dataframe(rows)
