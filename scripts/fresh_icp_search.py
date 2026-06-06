"""
Fresh ICP discovery for specialty retail.

This script intentionally does not read existing lead CSVs as source material.
It uses the ICP doc for qualification rules, config.py for cities/API settings,
and live Serper Maps searches for discovery.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
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
sys.path.insert(0, str(ROOT))

from config import CITIES, CHAIN_KEYWORDS, SERPER_API_KEY  # noqa: E402


OUTPUT_DIR = ROOT / "output"
ICP_PATH = ROOT / "docs" / "ICP.md"

TARGET_VERTICALS = {
    "wine_store": 32,
    "butcher": 30,
    "cheese_shop": 28,
    "deli": 23,
    "fish_market": 22,
    "specialty_grocer": 20,
}

QUERY_PLAN = {
    "wine_store": [
        ("natural wine shop", 12),
        ("independent wine shop", 11),
        ("curated wine shop", 10),
        ("wine club membership", 10),
        ("sommelier wine shop", 10),
        ("biodynamic wine shop", 9),
        ("organic wine store", 8),
        ("wine merchant", 8),
        ("wine boutique", 8),
        ("wine and cheese shop", 7),
        ("fine wine store", 7),
        ("bottle shop natural wine", 7),
    ],
    "butcher": [
        ("whole animal butcher", 12),
        ("artisan butcher shop", 11),
        ("independent butcher shop", 10),
        ("craft butcher", 10),
        ("premium meat market", 9),
        ("sustainable butcher shop", 9),
        ("heritage breed butcher", 8),
        ("local butcher shop", 7),
        ("charcuterie shop", 7),
        ("deli and butcher", 6),
    ],
    "cheese_shop": [
        ("cheese monger", 12),
        ("artisan cheese shop", 11),
        ("fromagerie", 11),
        ("specialty cheese store", 10),
        ("gourmet cheese store", 9),
        ("cheese and charcuterie shop", 8),
        ("fine cheese shop", 8),
        ("cheese tasting shop", 7),
    ],
    "fish_market": [
        ("fishmonger", 12),
        ("fresh seafood market", 10),
        ("sustainable seafood market", 10),
        ("premium fish market", 9),
        ("sushi grade fish market", 8),
        ("oyster market", 8),
        ("gourmet seafood shop", 7),
        ("seafood counter", 6),
    ],
    "deli": [
        ("artisan deli", 11),
        ("gourmet deli", 10),
        ("specialty deli", 9),
        ("deli and market", 8),
        ("italian deli", 8),
        ("jewish deli", 8),
        ("charcuterie deli", 7),
        ("neighborhood deli", 6),
    ],
    "specialty_grocer": [
        ("specialty food store", 11),
        ("gourmet market", 10),
        ("specialty grocery store", 10),
        ("provisions market", 9),
        ("curated grocery", 9),
        ("artisan grocery", 8),
        ("gourmet food shop", 8),
        ("local food market", 7),
        ("italian grocery store", 6),
        ("european grocery store", 6),
    ],
}

TYPE_ALLOW = {
    "wine_store": {"wine store", "wine cellar", "wine club", "wine wholesaler and importer"},
    "butcher": {"butcher shop", "butcher shop deli", "meat products store", "meat market", "charcuterie"},
    "cheese_shop": {"cheese shop"},
    "fish_market": {"seafood market", "fish market", "seafood store", "fishmonger", "fish store"},
    "deli": {"deli", "delicatessen"},
    "specialty_grocer": {
        "gourmet grocery store",
        "specialty food store",
        "italian grocery store",
        "european grocery store",
        "japanese grocery store",
        "organic food store",
        "natural goods store",
        "fresh food market",
        "produce market",
        "farm shop",
        "spice store",
        "pasta shop",
    },
}

TYPE_REJECT = {
    "liquor store",
    "state liquor store",
    "beer store",
    "bar",
    "bar & grill",
    "wine bar",
    "cocktail bar",
    "sports bar",
    "pub",
    "gastropub",
    "lounge bar",
    "brewery",
    "brewpub",
    "distillery",
    "sake brewery",
    "winery",
    "vineyard",
    "restaurant",
    "pizza restaurant",
    "breakfast restaurant",
    "brunch restaurant",
    "gluten-free restaurant",
    "health food restaurant",
    "vegan restaurant",
    "vegetarian restaurant",
    "convenience store",
    "grocery store",
    "supermarket",
    "discount store",
    "wholesale grocer",
    "wine wholesaler and importer",
    "e-commerce service",
    "food manufacturer",
    "food producer",
    "grow shop",
    "oxygen cocktail spot",
    "department store",
    "shopping mall",
    "caterer",
    "mobile caterer",
    "event venue",
    "live music venue",
    "night club",
    "coffee shop",
    "cafe",
    "fast food restaurant",
}

TEXT_REJECT = [
    r"\bliquor\b",
    r"\bspirits?\b",
    r"\bpackage store\b",
    r"\bbeer\b",
    r"\bbeverage depot\b",
    r"\bdiscount\b",
    r"\bwholesale\b",
    r"\bwholesaler\b",
    r"\bwarehouse\b",
    r"\bsupermarket\b",
    r"\bmarketplace\b",
    r"\bgas\b",
    r"\bcasino\b",
    r"\bvenue\b",
    r"\bcatering\b",
    r"\bcaterer\b",
    r"\brestaurant\b",
    r"\bpizza\b",
    r"\bgastropub\b",
    r"\blounge\b",
    r"\bpub\b",
    r"\bbar\b",
    r"\bcoming soon\b",
]

WINE_COMMODITY_REJECT = [
    "tito", "smirnoff", "buzzballz", "michelob", "budweiser", "barefoot",
    "yellowtail", "cupcake", "apothic", "meiomi", "josh", "bogle",
]

POSITIVE_TERMS = [
    "artisan", "craft", "curated", "natural", "organic", "biodynamic",
    "sustainable", "heritage", "whole animal", "fromagerie", "monger",
    "provisions", "specialty", "gourmet", "local", "independent",
    "club", "subscription", "producer", "small batch", "farmstead",
]

PREMIUM_CITIES = {
    "New York, New York", "Brooklyn, New York", "Los Angeles, California",
    "San Francisco, California", "Chicago, Illinois", "Boston, Massachusetts",
    "Washington, District of Columbia", "Seattle, Washington",
    "Portland, Oregon", "Austin, Texas", "Denver, Colorado",
    "Atlanta, Georgia", "Nashville, Tennessee", "Miami, Florida",
    "Charleston, South Carolina", "New Orleans, Louisiana",
    "Philadelphia, Pennsylvania", "Minneapolis, Minnesota",
}


@dataclass(frozen=True)
class SearchTask:
    vertical: str
    query: str
    query_weight: int
    city: str


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def domain(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    return host.removeprefix("www.")


def parse_town_state(address: str) -> tuple[str, str]:
    address = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in address.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        match = re.match(r"^([A-Z]{2})\s*\d{0,5}$", parts[i])
        if match:
            return (parts[i - 1] if i else "", match.group(1))
    return ("", "")


def read_icp_summary() -> str:
    text = ICP_PATH.read_text(encoding="utf-8")
    keep = []
    for phrase in [
        "Butcher Shop", "Wine Shop", "Cheese Shop", "Market / Deli",
        "Specialty Grocer", "Liquor stores", "Fewer than 20",
        "Wine shops", "Wine bars are mostly out",
    ]:
        if phrase in text:
            keep.append(phrase)
    return "; ".join(keep)


def search_serper(task: SearchTask, api_key: str) -> list[dict]:
    url = "https://google.serper.dev/maps"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": task.query,
        "location": f"{task.city}, United States",
        "gl": "us",
        "hl": "en",
        "num": 20,
    }
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            rows = []
            for place in resp.json().get("places", []):
                types = place.get("types") or []
                rows.append({
                    "source": "fresh_serper_maps",
                    "searched_vertical": task.vertical,
                    "search_query": task.query,
                    "query_weight": task.query_weight,
                    "search_city": task.city,
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
                })
            return rows
        except requests.RequestException:
            if attempt == 2:
                return []
            time.sleep(2 ** attempt)
    return []


def looks_like_chain(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in CHAIN_KEYWORDS)


def classify(row: pd.Series) -> str:
    searched = row["searched_vertical"]
    google_type = norm(row.get("google_type"))
    google_types = {norm(t) for t in str(row.get("google_types", "")).split(",") if t.strip()}
    text = norm(f"{row.get('name')} {row.get('google_type')} {row.get('google_types')}")

    all_types = {google_type, *google_types}
    if all_types & TYPE_REJECT:
        return "reject"

    for vertical in ["cheese_shop", "fish_market", "deli", "butcher", "wine_store", "specialty_grocer"]:
        if google_type in TYPE_ALLOW[vertical]:
            return vertical

    # Order matters: "charcuterie" often appears on cheese shops and markets,
    # so classify the more specific shop type before falling back to butcher.
    for vertical in ["cheese_shop", "fish_market", "deli", "butcher", "wine_store", "specialty_grocer"]:
        allowed = TYPE_ALLOW[vertical]
        if all_types & allowed:
            return vertical

    if searched == "wine_store":
        if re.search(r"\bwine (shop|store|merchant|cellar|club|boutique)\b|\bbottle shop\b", text):
            return "wine_store"
        return "reject"
    if searched == "butcher" and re.search(r"\bbutcher\b|\bmeat market\b|\bcharcuterie\b", text):
        return "butcher"
    if searched == "cheese_shop" and re.search(r"\bcheese\b|\bfromagerie\b", text):
        return "cheese_shop"
    if searched == "fish_market" and re.search(r"\bfish(monger| market)?\b|\bseafood\b|\boyster\b", text):
        return "fish_market"
    if searched == "deli" and re.search(r"\bdeli\b|\bdelicatessen\b", text):
        return "deli"
    if searched == "specialty_grocer" and re.search(r"\bgourmet\b|\bspecialty\b|\bprovisions\b|\bgrocer\b|\bmarket\b", text):
        return "specialty_grocer"
    return "reject"


def rejection_reason(row: pd.Series) -> str:
    name = str(row.get("name", ""))
    combined = norm(f"{name} {row.get('google_type')} {row.get('google_types')} {row.get('website')}")
    if looks_like_chain(name):
        return "chain_keyword"
    for pattern in TEXT_REJECT:
        if re.search(pattern, combined):
            return "anti_icp_text"
    if row.get("business_type") == "wine_store" and any(term in combined for term in WINE_COMMODITY_REJECT):
        return "commodity_wine_or_liquor"
    if not str(row.get("website", "")).strip():
        return "missing_website"
    rating = pd.to_numeric(row.get("rating"), errors="coerce")
    reviews = pd.to_numeric(row.get("review_count"), errors="coerce")
    if pd.isna(reviews) or reviews < 20:
        return "review_floor"
    if pd.isna(rating) or rating < 4.0:
        return "rating_floor"
    if row.get("business_type") == "reject":
        return "non_target_type"
    return ""


def score_row(row: pd.Series) -> float:
    vertical = row["business_type"]
    rating = pd.to_numeric(row.get("rating"), errors="coerce")
    reviews = pd.to_numeric(row.get("review_count"), errors="coerce")
    query_weight = pd.to_numeric(row.get("query_weight"), errors="coerce")
    rating = 0 if pd.isna(rating) else float(rating)
    reviews = 0 if pd.isna(reviews) else float(reviews)
    query_weight = 0 if pd.isna(query_weight) else float(query_weight)

    text = norm(f"{row.get('name')} {row.get('search_query')} {row.get('google_type')} {row.get('google_types')}")
    score = TARGET_VERTICALS.get(vertical, 0)
    score += query_weight
    score += min(18, math.log1p(reviews) * 3.0)
    score += max(0, (rating - 4.0) * 14)
    score += 5 if row.get("website") else 0
    score += 4 if str(row.get("price_level", "")).count("$") >= 2 else 0
    score += 4 if row.get("search_city") in PREMIUM_CITIES else 0
    score += sum(2.0 for term in POSITIVE_TERMS if term in text)
    if vertical == "wine_store" and "wine bar" in text:
        score -= 18
    if vertical == "specialty_grocer" and "grocery store" in text:
        score -= 8
    return round(score, 2)


def build_tasks(max_cities: int, max_queries_per_vertical: int) -> list[SearchTask]:
    cities = CITIES[:max_cities] if max_cities else CITIES
    tasks: list[SearchTask] = []
    for vertical, weighted_queries in QUERY_PLAN.items():
        for query, weight in weighted_queries[:max_queries_per_vertical]:
            for city in cities:
                tasks.append(SearchTask(vertical, query, weight, city))
    return tasks


def discover(args: argparse.Namespace) -> pd.DataFrame:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("SERPER_API_KEY") or SERPER_API_KEY
    if not api_key:
        raise SystemExit("SERPER_API_KEY is not set")

    print(f"ICP source: {ICP_PATH}")
    print(f"ICP anchors: {read_icp_summary()}")

    all_rows: list[dict] = []
    raw_seen = 0
    tasks = build_tasks(args.max_cities, args.max_queries_per_vertical)
    if args.max_searches:
        tasks = tasks[: args.max_searches]

    print(f"Fresh searches: {len(tasks):,} Serper Maps calls")
    print("Existing lead CSVs: not loaded")

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(search_serper, task, api_key): task for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            rows = future.result()
            raw_seen += len(rows)
            all_rows.extend(rows)
            if i == 1 or i % 100 == 0 or i == len(tasks):
                elapsed = max(time.monotonic() - started, 1)
                print(f"[{i:,}/{len(tasks):,}] raw={raw_seen:,} rate={i / elapsed:.1f} searches/s", flush=True)

    if not all_rows:
        raise SystemExit("No fresh search results returned")

    raw = pd.DataFrame(all_rows)
    parsed = raw["address"].apply(parse_town_state)
    raw["city"] = parsed.apply(lambda x: x[0])
    raw["state"] = parsed.apply(lambda x: x[1])
    raw["business_type"] = raw.apply(classify, axis=1)
    raw["reject_reason"] = raw.apply(rejection_reason, axis=1)

    accepted = raw[raw["reject_reason"].eq("")].copy()
    accepted["fresh_icp_score"] = accepted.apply(score_row, axis=1)
    accepted["_domain"] = accepted["website"].apply(domain)
    accepted["_phone"] = accepted["phone"].astype(str).str.replace(r"\D+", "", regex=True)
    accepted["_name_city"] = accepted.apply(
        lambda r: f"{norm(r['name'])}|{norm(r['city'])}|{str(r['state']).upper()}",
        axis=1,
    )
    accepted["_dedupe_key"] = accepted["_phone"].where(accepted["_phone"].str.len() >= 10, "")
    accepted["_dedupe_key"] = accepted["_dedupe_key"].where(
        accepted["_dedupe_key"].ne(""),
        accepted["_domain"].where(accepted["_domain"].ne(""), accepted["_name_city"]),
    )
    accepted = (
        accepted.sort_values(["fresh_icp_score", "review_count"], ascending=[False, False])
        .drop_duplicates("_dedupe_key", keep="first")
        .reset_index(drop=True)
    )

    return raw, accepted


def filter_and_rank_raw(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    parsed = raw["address"].apply(parse_town_state)
    raw = raw.copy()
    raw["city"] = parsed.apply(lambda x: x[0])
    raw["state"] = parsed.apply(lambda x: x[1])
    raw["business_type"] = raw.apply(classify, axis=1)
    raw["reject_reason"] = raw.apply(rejection_reason, axis=1)

    accepted = raw[raw["reject_reason"].eq("")].copy()
    accepted["fresh_icp_score"] = accepted.apply(score_row, axis=1)
    accepted["_domain"] = accepted["website"].apply(domain)
    accepted["_phone"] = accepted["phone"].astype(str).str.replace(r"\D+", "", regex=True)
    accepted["_name_city"] = accepted.apply(
        lambda r: f"{norm(r['name'])}|{norm(r['city'])}|{str(r['state']).upper()}",
        axis=1,
    )
    accepted["_dedupe_key"] = accepted["_phone"].where(accepted["_phone"].str.len() >= 10, "")
    accepted["_dedupe_key"] = accepted["_dedupe_key"].where(
        accepted["_dedupe_key"].ne(""),
        accepted["_domain"].where(accepted["_domain"].ne(""), accepted["_name_city"]),
    )
    accepted = (
        accepted.sort_values(["fresh_icp_score", "review_count"], ascending=[False, False])
        .drop_duplicates("_dedupe_key", keep="first")
        .reset_index(drop=True)
    )
    return raw, accepted


def balanced_top(accepted: pd.DataFrame, target: int) -> pd.DataFrame:
    quotas = {
        "wine_store": 350,
        "butcher": 200,
        "cheese_shop": 150,
        "fish_market": 100,
        "deli": 100,
        "specialty_grocer": 100,
    }
    if target != 1000:
        scale = target / 1000
        quotas = {k: int(v * scale) for k, v in quotas.items()}

    chunks = []
    used = set()
    for business_type, quota in quotas.items():
        part = accepted[accepted["business_type"].eq(business_type)].head(quota)
        chunks.append(part)
        used.update(part.index)

    selected = pd.concat(chunks, ignore_index=False) if chunks else accepted.head(0)
    if len(selected) < target:
        remainder = accepted[~accepted.index.isin(used)].head(target - len(selected))
        selected = pd.concat([selected, remainder], ignore_index=False)

    return selected.sort_values(["fresh_icp_score", "review_count"], ascending=[False, False]).head(target)


def write_outputs(raw: pd.DataFrame, accepted: pd.DataFrame, target: int) -> tuple[Path, Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(exist_ok=True)

    raw_path = OUTPUT_DIR / f"fresh_icp_search_raw_{stamp}.csv"
    top_path = OUTPUT_DIR / f"fresh_icp_search_top_{min(target, len(accepted))}_{stamp}.csv"
    report_path = OUTPUT_DIR / f"fresh_icp_search_report_{stamp}.txt"

    raw.to_csv(raw_path, index=False, quoting=csv.QUOTE_MINIMAL)

    columns = [
        "name", "business_type", "fresh_icp_score", "city", "state", "address",
        "phone", "website", "rating", "review_count", "google_type",
        "google_types", "price_level", "search_query", "search_city",
        "latitude", "longitude", "cid",
    ]
    top = balanced_top(accepted, target).copy()
    top[[c for c in columns if c in top.columns]].to_csv(top_path, index=False)

    report = [
        "Fresh ICP Search Report",
        f"Generated: {stamp}",
        f"ICP doc: {ICP_PATH}",
        "Existing lead CSVs used as source: no",
        "",
        f"Raw search rows: {len(raw):,}",
        f"Accepted deduped rows: {len(accepted):,}",
        f"Top output rows: {len(top):,}",
        "",
        "Top output by business_type:",
        top["business_type"].value_counts().to_string() if not top.empty else "(none)",
        "",
        "Accepted by business_type:",
        accepted["business_type"].value_counts().to_string() if not accepted.empty else "(none)",
        "",
        "Rejected by reason:",
        raw["reject_reason"].replace("", "accepted").value_counts().to_string(),
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    return raw_path, top_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh ICP search from live Maps results")
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--max-cities", type=int, default=160)
    parser.add_argument("--max-queries-per-vertical", type=int, default=8)
    parser.add_argument("--max-searches", type=int, default=0)
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--raw-input", type=str, help="Re-filter a raw CSV from this script without new searches")
    args = parser.parse_args()

    if args.raw_input:
        print(f"Re-filtering fresh raw search file: {args.raw_input}")
        print("Existing lead CSVs: not loaded")
        raw = pd.read_csv(args.raw_input, low_memory=False)
        raw, accepted = filter_and_rank_raw(raw)
    else:
        raw, accepted = discover(args)
    raw_path, top_path, report_path = write_outputs(raw, accepted, args.target)

    print(f"\nRaw results: {raw_path}")
    print(f"Top results: {top_path}")
    print(f"Report: {report_path}")
    print(f"Accepted deduped rows: {len(accepted):,}")
    if len(accepted) < args.target:
        print(f"WARNING: only {len(accepted):,} rows accepted; rerun with more cities/queries.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
