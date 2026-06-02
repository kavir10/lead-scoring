"""
Fresh wine-store discovery via Serper Maps.

This expands beyond the existing corpus with wine-retail-specific queries while
leaving final ICP qualification to scripts/build_wine_leads.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CITIES, SERPER_API_KEY  # noqa: E402


RUN_DIR = ROOT / "output" / "fresh_wine_leads_20260602"

WINE_QUERIES = [
    ("wine store", 12),
    ("wine shop", 12),
    ("independent wine shop", 11),
    ("natural wine shop", 11),
    ("wine merchant", 10),
    ("fine wine store", 10),
    ("curated wine shop", 10),
    ("bottle shop wine", 9),
    ("wine cellar store", 9),
    ("wine boutique", 9),
    ("organic wine store", 8),
    ("biodynamic wine shop", 8),
    ("sommelier wine shop", 8),
    ("champagne wine shop", 7),
    ("wine and cheese shop", 7),
    ("local wine store", 7),
]

WINE_TYPE_RE = re.compile(r"\b(?:wine store|wine cellar|wine club)\b", re.I)
WINE_NAME_RE = re.compile(
    r"\b(?:wine|wines|vino|vinoteca|cellar|cellars|bottle shop|bottleshop)\b",
    re.I,
)
REJECT_RE = re.compile(
    r"\b(?:wine bar|bar & grill|restaurant|winery|vineyard|brewery|distillery|"
    r"liquor store|state liquor|grocery store|supermarket|theatre|theater|"
    r"country club|hotel|resort|book store|gift shop|candle store)\b",
    re.I,
)

_rate_lock = threading.Lock()
_last_times: list[float] = []


@dataclass(frozen=True)
class SearchTask:
    query: str
    query_weight: int
    location: str


def rate_limit(rps: int) -> None:
    with _rate_lock:
        now = time.monotonic()
        while _last_times and _last_times[0] < now - 1:
            _last_times.pop(0)
        if len(_last_times) >= rps:
            wait = _last_times[0] + 1 - now
            if wait > 0:
                time.sleep(wait)
        _last_times.append(time.monotonic())


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def host(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    netloc = parsed.netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def parse_city_state(address: object) -> tuple[str, str]:
    text = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        match = re.match(r"^([A-Z]{2})\s*\d{0,5}$", parts[i])
        if match:
            return (parts[i - 1] if i else "", match.group(1))
    return "", ""


def dedupe_key(row: pd.Series) -> str:
    phone = re.sub(r"\D+", "", str(row.get("phone", "")))
    if len(phone) >= 10:
        return f"phone:{phone[-10:]}"
    website = host(row.get("website"))
    if website:
        return f"host:{website}"
    return f"name:{clean_text(row.get('name')).lower()}|{clean_text(row.get('address')).lower()}"


def likely_wine_store(row: dict) -> bool:
    text = " ".join(
        str(row.get(field, ""))
        for field in ["name", "google_type", "google_types", "website"]
    )
    if REJECT_RE.search(text):
        return False
    return WINE_TYPE_RE.search(text) is not None or WINE_NAME_RE.search(text) is not None


def search(task: SearchTask, api_key: str, rps: int) -> list[dict]:
    rate_limit(rps)
    url = "https://google.serper.dev/maps"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": task.query,
        "location": f"{task.location}, United States",
        "gl": "us",
        "hl": "en",
        "num": 20,
    }
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code in {429, 500, 502, 503, 504}:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            rows = []
            for place in resp.json().get("places", []):
                types = place.get("types") or []
                row = {
                    "source": "fresh_wine_serper_maps",
                    "business_type": "wine_store",
                    "search_query": task.query,
                    "query_weight": task.query_weight,
                    "search_city": task.location,
                    "name": clean_text(place.get("title")),
                    "address": clean_text(place.get("address")),
                    "rating": place.get("rating"),
                    "review_count": place.get("ratingCount", 0),
                    "google_type": clean_text(place.get("type")),
                    "google_types": ", ".join(types) if isinstance(types, list) else clean_text(types),
                    "phone": clean_text(place.get("phoneNumber")),
                    "website": clean_text(place.get("website")),
                    "price_level": clean_text(place.get("priceLevel")),
                    "latitude": place.get("latitude"),
                    "longitude": place.get("longitude"),
                    "cid": clean_text(place.get("cid")),
                }
                rows.append(row)
            return rows
        except requests.RequestException:
            if attempt == 2:
                return []
            time.sleep(2 ** attempt)
    return []


def build_tasks(max_cities: int, max_queries: int, max_searches: int) -> list[SearchTask]:
    cities = CITIES[:max_cities] if max_cities else CITIES
    queries = WINE_QUERIES[:max_queries] if max_queries else WINE_QUERIES
    tasks = [SearchTask(query, weight, city) for query, weight in queries for city in cities]
    return tasks[:max_searches] if max_searches else tasks


def discover(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("SERPER_API_KEY") or SERPER_API_KEY
    if not api_key:
        raise SystemExit("SERPER_API_KEY is not set")

    tasks = build_tasks(args.max_cities, args.max_queries, args.max_searches)
    print(f"Fresh wine searches: {len(tasks):,}")
    print(f"Locations: {args.max_cities or len(CITIES):,}; queries: {args.max_queries or len(WINE_QUERIES):,}")

    all_rows: list[dict] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(search, task, api_key, args.rps): task for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            rows = future.result()
            all_rows.extend(rows)
            if i == 1 or i % 100 == 0 or i == len(tasks):
                elapsed = max(1, time.monotonic() - started)
                print(f"[{i:,}/{len(tasks):,}] raw={len(all_rows):,} rate={i / elapsed:.1f}/s", flush=True)

    if not all_rows:
        raise SystemExit("No fresh search results returned")

    raw = pd.DataFrame(all_rows)
    parsed = raw["address"].apply(parse_city_state)
    raw["city"] = parsed.apply(lambda item: item[0])
    raw["state"] = parsed.apply(lambda item: item[1])
    raw["fresh_wine_candidate"] = raw.apply(lambda row: likely_wine_store(row.to_dict()), axis=1)

    candidates = raw[raw["fresh_wine_candidate"]].copy()
    candidates["_dedupe_key"] = candidates.apply(dedupe_key, axis=1)
    candidates = (
        candidates.sort_values(["query_weight", "review_count", "rating"], ascending=[False, False, False])
        .drop_duplicates("_dedupe_key", keep="first")
        .reset_index(drop=True)
    )
    return raw, candidates


def write_outputs(raw: pd.DataFrame, candidates: pd.DataFrame, args: argparse.Namespace) -> None:
    args.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = args.run_dir / f"fresh_wine_serper_raw_{stamp}.csv"
    candidates_path = args.run_dir / f"fresh_wine_serper_candidates_{len(candidates)}_{stamp}.csv"
    summary_path = args.run_dir / f"fresh_wine_serper_summary_{stamp}.json"

    raw.to_csv(raw_path, index=False, quoting=csv.QUOTE_MINIMAL)
    candidates.to_csv(candidates_path, index=False)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_rows": int(len(raw)),
        "candidate_rows": int(len(candidates)),
        "raw_path": str(raw_path),
        "candidates_path": str(candidates_path),
        "searches": int(args.max_searches) if args.max_searches else int((args.max_cities or len(CITIES)) * (args.max_queries or len(WINE_QUERIES))),
        "candidate_google_types": candidates["google_type"].fillna("").astype(str).value_counts().head(25).to_dict(),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh wine-store discovery via Serper Maps.")
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--max-cities", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--max-searches", type=int, default=0)
    parser.add_argument("--workers", type=int, default=30)
    parser.add_argument("--rps", type=int, default=20)
    args = parser.parse_args()

    raw, candidates = discover(args)
    write_outputs(raw, candidates, args)


if __name__ == "__main__":
    main()
