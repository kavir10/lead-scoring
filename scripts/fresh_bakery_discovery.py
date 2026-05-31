"""
Fresh bakery lead discovery with strict Google type verification.

This intentionally does not read the prior bakery corpus. It queries Serper Maps
again, stores raw responses, then keeps only rows with bakery/pastry category
evidence or a strong bakery name signal.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CITIES, CHAIN_KEYWORDS, SERPER_API_KEY


RUN_DIR = ROOT / "output" / "fresh_bakery_leads_20260525"

BAKERY_QUERIES = [
    "bakery",
    "artisan bakery",
    "sourdough bakery",
    "patisserie",
    "boulangerie",
    "pastry shop",
    "bread bakery",
    "bagel shop",
    "cake shop",
    "donut shop",
    "french bakery",
    "best bakery",
]

STRONG_TYPE_RE = re.compile(
    r"\b(?:bakery|bakeries|patisserie|pâtisserie|pastry shop|bagel shop|"
    r"cake shop|cookie shop|pie shop|donut shop|doughnut shop|wholesale bakery|"
    r"chinese bakery|wedding bakery)\b",
    re.I,
)
ADJACENT_TYPE_RE = re.compile(
    r"\b(?:dessert shop|dessert restaurant|chocolate shop|confectionery|"
    r"candy store|ice cream shop|creperie)\b",
    re.I,
)
NAME_RE = re.compile(
    r"\b(?:bakery|bakeshop|bakehouse|boulangerie|patisserie|pâtisserie|"
    r"pastry|pastries|bread|bagel|donut|doughnut|cake|cakes|cookie|cookies|"
    r"pie|pies|macaron|croissant|cupcake|cupcakes)\b",
    re.I,
)
RESTAURANT_ONLY_RE = re.compile(
    r"\b(?:restaurant|bistro|bar|grill|steakhouse|sushi|ramen|pizza restaurant|"
    r"italian restaurant|american restaurant|japanese restaurant|mexican restaurant|"
    r"thai restaurant|seafood restaurant|vegan restaurant|vegetarian restaurant)\b",
    re.I,
)

_rate_lock = threading.Lock()
_last_times: list[float] = []


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


def parse_city_state(address: str) -> tuple[str, str]:
    address = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in address.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        m = re.match(r"^([A-Z]{2})\s*\d*", parts[i])
        if m:
            return (parts[i - 1] if i else "", m.group(1))
    return ("", "")


def is_chain(name: str) -> bool:
    text = str(name or "").lower()
    return any(keyword in text for keyword in CHAIN_KEYWORDS)


def call_serper_maps(query: str, city: str, rps: int) -> list[dict]:
    rate_limit(rps)
    headers = {"X-API-KEY": SERPER_API_KEY or "", "Content-Type": "application/json"}
    payload = {
        "q": query,
        "location": f"{city}, United States",
        "gl": "us",
        "hl": "en",
        "num": 20,
    }
    for attempt in range(3):
        try:
            resp = requests.post("https://google.serper.dev/maps", headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            places = resp.json().get("places", [])
            rows = []
            for p in places:
                types = p.get("types") or []
                town, state = parse_city_state(p.get("address", ""))
                rows.append(
                    {
                        "name": p.get("title", ""),
                        "address": p.get("address", ""),
                        "city": town,
                        "state": state,
                        "phone": p.get("phoneNumber", ""),
                        "website": p.get("website", ""),
                        "rating": p.get("rating"),
                        "review_count": p.get("ratingCount", 0),
                        "google_type": p.get("type", ""),
                        "google_types": ", ".join(types) if isinstance(types, list) else str(types or ""),
                        "price_level": p.get("priceLevel", ""),
                        "latitude": p.get("latitude"),
                        "longitude": p.get("longitude"),
                        "cid": p.get("cid", ""),
                        "search_query": query,
                        "search_city": city,
                        "business_type": "bakery",
                    }
                )
            return rows
        except requests.RequestException:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    return []


def verification_reason(row: pd.Series) -> str:
    name = str(row.get("name", ""))
    type_text = f"{row.get('google_type', '')} {row.get('google_types', '')}"
    has_strong_type = bool(STRONG_TYPE_RE.search(type_text))
    has_adjacent_type = bool(ADJACENT_TYPE_RE.search(type_text))
    has_name = bool(NAME_RE.search(name))
    restaurant_only = bool(RESTAURANT_ONLY_RE.search(type_text)) and not (has_strong_type or has_adjacent_type)

    if is_chain(name):
        return "reject_chain"
    if has_strong_type:
        return "keep_strong_google_type"
    if has_adjacent_type and has_name:
        return "keep_adjacent_type_plus_name"
    if has_name and not restaurant_only:
        return "keep_strong_name_signal"
    return "reject_not_verified_bakery"


def quality_score(df: pd.DataFrame) -> pd.Series:
    rating = pd.to_numeric(df["rating"], errors="coerce").fillna(0)
    reviews = pd.to_numeric(df["review_count"], errors="coerce").fillna(0)
    type_bonus = df["verification_reason"].map(
        {
            "keep_strong_google_type": 20,
            "keep_adjacent_type_plus_name": 14,
            "keep_strong_name_signal": 10,
        }
    ).fillna(0)
    website_bonus = df["website"].fillna("").astype(str).str.strip().ne("").astype(int) * 8
    rating_score = rating.clip(0, 5) * 8
    review_score = reviews.apply(lambda x: min(20, 4 * (len(str(int(x))) - 1 if x > 0 else 0)))
    return (type_bonus + website_bonus + rating_score + review_score).round(1)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_phone_clean"] = out["phone"].fillna("").astype(str).str.replace(r"[^\d]", "", regex=True)
    out["_name_addr_key"] = (
        out["name"].fillna("").astype(str).str.lower().str.replace(r"[^\w]+", " ", regex=True).str.strip()
        + "|"
        + out["address"].fillna("").astype(str).str.lower().str.replace(r"[^\w]+", " ", regex=True).str.strip()
    )
    with_phone = out[out["_phone_clean"].ne("")].drop_duplicates("_phone_clean", keep="first")
    no_phone = out[out["_phone_clean"].eq("")].drop_duplicates("_name_addr_key", keep="first")
    out = pd.concat([with_phone, no_phone], ignore_index=True)
    return out.drop(columns=["_phone_clean", "_name_addr_key"])


def discover(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SERPER_API_KEY:
        raise SystemExit("SERPER_API_KEY is missing")

    cities = CITIES[: args.max_cities] if args.max_cities else CITIES
    queries = BAKERY_QUERIES[: args.max_queries] if args.max_queries else BAKERY_QUERIES
    tasks = [(query, city) for query in queries for city in cities]
    if args.max_searches:
        tasks = tasks[: args.max_searches]

    print(f"Fresh bakery discovery: {len(tasks):,} Serper Maps searches")
    print(f"Queries: {', '.join(queries)}")
    print(f"Cities: {len(cities):,}; workers={args.workers}; rps={args.rps}")

    all_rows: list[dict] = []
    started = time.monotonic()
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(call_serper_maps, query, city, args.rps): (query, city) for query, city in tasks}
        for future in as_completed(futures):
            completed += 1
            rows = future.result()
            all_rows.extend(rows)
            if completed % 100 == 0 or completed == len(tasks):
                elapsed = max(time.monotonic() - started, 1)
                print(
                    f"  {completed:,}/{len(tasks):,} searches | "
                    f"{completed / elapsed:.1f} req/s | raw rows {len(all_rows):,}",
                    flush=True,
                )

    raw = pd.DataFrame(all_rows)
    if raw.empty:
        return raw, raw

    raw["verification_reason"] = raw.apply(verification_reason, axis=1)
    raw["is_verified_bakery"] = raw["verification_reason"].str.startswith("keep_")
    filtered = raw[raw["is_verified_bakery"]].copy()
    filtered = dedupe(filtered)
    filtered["fresh_quality_score"] = quality_score(filtered)
    filtered = filtered.sort_values(
        ["fresh_quality_score", "review_count", "rating"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return raw, filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh bakery discovery using strict Serper Maps verification.")
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--max-searches", type=int, default=0)
    parser.add_argument("--max-cities", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--rps", type=int, default=25)
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    raw, filtered = discover(args)
    raw_path = args.run_dir / "fresh_bakery_serper_raw.csv"
    filtered_path = args.run_dir / "fresh_bakery_verified.csv"
    raw.to_csv(raw_path, index=False)
    filtered.to_csv(filtered_path, index=False)

    print("\nVerification reasons:")
    if not raw.empty:
        print(raw["verification_reason"].value_counts().to_string())
    print(f"\nRaw rows: {len(raw):,} -> {raw_path}")
    print(f"Verified bakery rows: {len(filtered):,} -> {filtered_path}")

    if not filtered.empty:
        sample_path = args.run_dir / "fresh_bakery_verified_qa_sample.csv"
        filtered.sample(min(100, len(filtered)), random_state=20260525).to_csv(sample_path, index=False)
        print(f"QA sample: {sample_path}")


if __name__ == "__main__":
    main()
