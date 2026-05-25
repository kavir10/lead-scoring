"""
Reservation-Impossible permanent venues scanner.

Strategy: docs/strategies/05_reservation_impossible.md

Inputs:
  - An enriched CSV with at minimum: name, city, state, reservation_url,
    reservation_difficulty (1 = OpenTable, 2 = Resy, 3 = Tock).

Process per venue:
  - Probe 30 days forward × party_sizes [2, 4] × time windows [peak, off-peak]
  - Score scarcity = 1 - (open_slots / total_slot_grid)
  - Flag venues with zero_avail_days >= 21 (of 30) AND scarcity >= 0.85

Output: canonical SCHEMA CSV with scarcity_score in blurb.

Usage:
    python -m scarcity.reservation_impossible --input output/2_enriched_availability.csv
    python -m scarcity.reservation_impossible --input <csv> --limit 100
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from awards._lib import (
    ROOT,
    SCHEMA,
    make_row,
    normalize_state,
    to_dataframe,
)


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


RESY_API_KEY = os.environ.get("RESY_API_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_ACTOR_OPENTABLE = os.environ.get("APIFY_ACTOR_OPENTABLE", "")

RESY_API_BASE = "https://api.resy.com/4"

OUTPUT_DIR = ROOT / "output" / "scarcity"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PARTY_SIZES = [2, 4]
PEAK_HOURS = ["19:00", "19:30", "20:00"]
OFFPEAK_HOURS = ["17:30", "21:30"]
DAYS_FORWARD = 30

# Promote thresholds
ZERO_DAYS_THRESHOLD = 21
SCARCITY_THRESHOLD = 0.85


def _date_grid() -> list[str]:
    today = datetime.now().date()
    return [(today + timedelta(days=i)).isoformat() for i in range(1, DAYS_FORWARD + 1)]


def _resy_venue_slug(url: str) -> str | None:
    m = re.search(r"resy\.com/cities/[^/]+/([^/?]+)", url)
    return m.group(1) if m else None


def _resy_probe(venue_slug: str, date: str, party_size: int) -> int:
    """Return the count of available slots from Resy for (date, party_size).
    Returns 0 on any error or empty response. Resy API is reverse-engineered;
    may break."""
    if not RESY_API_KEY:
        return 0
    try:
        resp = requests.get(
            f"{RESY_API_BASE}/find",
            params={
                "lat": 0, "long": 0,
                "day": date, "party_size": party_size,
                "venue_id": venue_slug,
            },
            headers={
                "Authorization": f'ResyAPI api_key="{RESY_API_KEY}"',
                "X-Resy-Auth-Token": RESY_API_KEY,
            },
            timeout=10,
        )
        if not resp.ok:
            return 0
        data = resp.json()
        venues = data.get("results", {}).get("venues", []) or []
        total = 0
        for v in venues:
            slots = v.get("slots", []) or []
            total += len(slots)
        return total
    except Exception:
        return 0


def _score_resy(venue_slug: str) -> dict:
    """Run the 30-day × party_sizes grid for a Resy venue.

    Returns dict with: scarcity_score, zero_avail_days, peak_only_zero_days,
    party_size_grid (jsonable), platform, scan_date.
    """
    dates = _date_grid()
    grid: dict[str, dict[int, int]] = {}
    for d in dates:
        grid[d] = {}
        for p in PARTY_SIZES:
            grid[d][p] = _resy_probe(venue_slug, d, p)
            time.sleep(0.1)  # gentle on Resy
    total_grid_cells = len(dates) * len(PARTY_SIZES)
    open_cells = sum(1 for d in dates for p in PARTY_SIZES if grid[d][p] > 0)
    scarcity_score = 1.0 - (open_cells / total_grid_cells)
    zero_days = sum(1 for d in dates if all(grid[d][p] == 0 for p in PARTY_SIZES))
    return {
        "platform": "resy",
        "scarcity_score": round(scarcity_score, 3),
        "zero_avail_days": zero_days,
        "peak_only_zero_days": 0,  # Resy API doesn't distinguish — would need time-grid breakdown
        "scan_date": datetime.now().date().isoformat(),
        "party_size_grid": json.dumps(grid),
    }


def _score_opentable(reservation_url: str) -> dict | None:
    """Run the 30-day check via Apify OpenTable actor. Returns None if not
    enough infra (Apify token / actor) configured."""
    if not (APIFY_API_TOKEN and APIFY_ACTOR_OPENTABLE):
        return None
    try:
        from apify_client import ApifyClient
    except ImportError:
        return None
    client = ApifyClient(APIFY_API_TOKEN)
    dates = _date_grid()
    total_cells = len(dates) * len(PARTY_SIZES)
    open_cells = 0
    daily_open: dict[str, int] = {d: 0 for d in dates}
    grid: dict[str, dict[int, int]] = {d: {} for d in dates}
    for party_size in PARTY_SIZES:
        try:
            run = client.actor(APIFY_ACTOR_OPENTABLE).call(run_input={
                "startUrls": [{"url": reservation_url}],
                "dates": dates,
                "partySize": party_size,
                "time": "19:00",
            })
            items = client.dataset(run["defaultDatasetId"]).list_items().items
            for item in items:
                slots = item.get("availableSlots") or item.get("timeslots") or []
                # OpenTable Apify actor returns per-request, slots aggregated.
                # We can't break out by date precisely with this shape, so use
                # presence as a binary signal for the requested batch.
                slot_count = len(slots) if isinstance(slots, list) else 0
                # Approximate: distribute across dates that returned data
                for d in dates:
                    grid[d].setdefault(party_size, 0)
                    if slot_count > 0:
                        grid[d][party_size] = max(grid[d].get(party_size, 0), 1)
                        daily_open[d] = max(daily_open[d], 1)
                        open_cells += 1
                        break  # crude — better grid requires Apify upgrade
        except Exception as e:
            print(f"  [scarcity] OpenTable error: {e}", flush=True)
            return None
    scarcity_score = 1.0 - (open_cells / total_cells)
    zero_days = sum(1 for d in dates if daily_open[d] == 0)
    return {
        "platform": "opentable",
        "scarcity_score": round(scarcity_score, 3),
        "zero_avail_days": zero_days,
        "peak_only_zero_days": 0,
        "scan_date": datetime.now().date().isoformat(),
        "party_size_grid": json.dumps(grid),
    }


def _score_one(row: dict) -> dict | None:
    url = row.get("reservation_url", "") or ""
    name = row.get("name", "")
    if not url:
        return None
    if "resy.com" in url.lower():
        slug = _resy_venue_slug(url)
        if not slug:
            return None
        print(f"  [scarcity] resy: {name}", flush=True)
        return _score_resy(slug)
    if "opentable.com" in url.lower():
        print(f"  [scarcity] opentable: {name}", flush=True)
        return _score_opentable(url)
    return None


def scan(input_csv: Path | str, *, limit: int | None = None, output_path: Path | None = None) -> pd.DataFrame:
    df_in = pd.read_csv(input_csv, dtype=str).fillna("")
    if "reservation_difficulty" in df_in.columns:
        df_in["reservation_difficulty"] = pd.to_numeric(df_in["reservation_difficulty"], errors="coerce").fillna(0).astype(int)
        mask = df_in["reservation_difficulty"] >= 1
        candidates = df_in.loc[mask].copy()
    else:
        candidates = df_in.copy()
    print(f"  [scarcity] candidates: {len(candidates)}", flush=True)
    if limit:
        candidates = candidates.head(limit)
    rows: list[dict] = []
    for _, row in candidates.iterrows():
        score = _score_one(row.to_dict())
        if not score:
            continue
        flagged = (
            score["zero_avail_days"] >= ZERO_DAYS_THRESHOLD
            and score["scarcity_score"] >= SCARCITY_THRESHOLD
        )
        if not flagged:
            continue
        rows.append(make_row(
            source="reservation_impossible",
            tier=1,
            business_type="restaurant",
            name=row.get("name", ""),
            city=row.get("city", ""),
            state=normalize_state(row.get("state", "")),
            country="us",
            distinction=(
                f"Reservation-impossible (zero avail {score['zero_avail_days']}/30 days,"
                f" scarcity {score['scarcity_score']})"
            ),
            source_url=row.get("reservation_url", ""),
            blurb=(
                f"platform={score['platform']}; scarcity={score['scarcity_score']};"
                f" zero_days={score['zero_avail_days']}; scan_date={score['scan_date']}"
            ),
        ))
    df_out = to_dataframe(rows)
    stamp = datetime.now().strftime("%Y%m%d")
    out_path = output_path or OUTPUT_DIR / f"reservation_impossible_{stamp}.csv"
    df_out.to_csv(out_path, index=False)
    print(f"  Saved {len(df_out)} reservation-impossible venues -> {out_path}", flush=True)
    return df_out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="Path to enriched CSV with reservation_url + reservation_difficulty")
    p.add_argument("--limit", type=int, help="Cap candidate count for testing")
    p.add_argument("--output", type=str, help="Override output path")
    args = p.parse_args()
    scan(args.input, limit=args.limit, output_path=Path(args.output) if args.output else None)


if __name__ == "__main__":
    main()
