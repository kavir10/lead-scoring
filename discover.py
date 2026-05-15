"""
Phase 1: Discover leads via Serper Maps API across multiple business types.
Uses concurrent requests to stay within Serper's 50 req/s rate limit.
"""
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd
from config import (
    SERPER_API_KEY, SEARCH_QUERIES, CITIES,
    BUSINESS_TYPE_MAP, CHAIN_KEYWORDS, LIQUOR_KEYWORDS,
)
from core.geo import BANNED_STATES

# --- Concurrency settings ---
MAX_WORKERS = 80       # 80 parallel HTTP requests; each blocks ~4s avg = ~20 req/s
RATE_LIMIT_RPS = 45    # Stay under 50 req/s Serper Start plan limit
_rate_lock = threading.Lock()
_last_times: list[float] = []


def _rate_limit():
    """Token-bucket style rate limiter — blocks if we'd exceed RATE_LIMIT_RPS."""
    with _rate_lock:
        now = time.monotonic()
        # Prune timestamps older than 1 second
        while _last_times and _last_times[0] < now - 1.0:
            _last_times.pop(0)
        if len(_last_times) >= RATE_LIMIT_RPS:
            sleep_until = _last_times[0] + 1.0
            wait = sleep_until - now
            if wait > 0:
                time.sleep(wait)
        _last_times.append(time.monotonic())


def search_serper_maps(query: str, location: str, max_retries: int = 3) -> list[dict]:
    """Search Serper Maps API for a query + location combo with retry on rate limits."""
    _rate_limit()

    url = "https://google.serper.dev/maps"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "location": f"{location}, United States",
        "gl": "us",
        "hl": "en",
        "num": 20,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            places = data.get("places", [])

            results = []
            for p in places:
                # Serper Maps returns the Google category as `type` (string) and `types` (list).
                # `category` is not a real field — old code left this empty.
                types_list = p.get("types") or []
                results.append({
                    "name": p.get("title", ""),
                    "address": p.get("address", ""),
                    "rating": p.get("rating"),
                    "review_count": p.get("ratingCount", 0),
                    "type": p.get("type", ""),
                    "types": ", ".join(types_list) if isinstance(types_list, list) else "",
                    "category": p.get("category", ""),
                    "phone": p.get("phoneNumber", ""),
                    "website": p.get("website", ""),
                    "price_level": p.get("priceLevel", ""),
                    "latitude": p.get("latitude"),
                    "longitude": p.get("longitude"),
                    "cid": p.get("cid", ""),
                    "search_query": query,
                    "search_city": location,
                })
            return results

        except requests.RequestException as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            if status in (400, 429) and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                time.sleep(wait)
                continue
            return []
    return []


def _search_task(category: str, query: str, city: str) -> list[dict]:
    """Single search task for the thread pool. Returns tagged results."""
    business_type = BUSINESS_TYPE_MAP[category]
    results = search_serper_maps(query, city)
    for r in results:
        r["business_type"] = business_type
        r["search_category"] = category
    return results


def parse_town_state(address: str) -> tuple[str, str]:
    """Extract town and state from a Serper Maps address string."""
    if not address:
        return "", ""

    address = re.sub(r",?\s*United States\s*$", "", address, flags=re.I)
    parts = [p.strip() for p in address.split(",")]

    for i in range(len(parts) - 1, -1, -1):
        m = re.match(r"^([A-Z]{2})\s*\d*$", parts[i].strip())
        if m:
            state = m.group(1)
            town = parts[i - 1].strip() if i >= 1 else ""
            return town, state

    if len(parts) >= 2:
        m = re.match(r"^([A-Z]{2})$", parts[-1].strip())
        if m:
            return parts[-2].strip(), m.group(1)

    return "", ""


def is_chain(name: str) -> bool:
    """Check if a business name matches a known chain."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in CHAIN_KEYWORDS)


def is_liquor_store(name: str, category: str) -> bool:
    """Check if a result is a liquor store (filter out from wine_store results)."""
    combined = f"{name} {category}".lower()
    return any(kw in combined for kw in LIQUOR_KEYWORDS)


def discover_leads(types: list[str] | None = None, max_searches: int = 0, max_cities: int = 0) -> pd.DataFrame:
    """Run all search queries across all cities using concurrent requests.

    Args:
        types: Optional list of business types to discover.
        max_searches: Stop after this many API calls (0 = unlimited).
        max_cities: Limit to the first N cities (0 = all).
    """
    # Filter search queries by requested types
    active_queries = SEARCH_QUERIES
    if types:
        active_queries = {
            cat: queries for cat, queries in SEARCH_QUERIES.items()
            if BUSINESS_TYPE_MAP[cat] in types
        }
        if not active_queries:
            print(f"No search categories match types: {types}")
            return pd.DataFrame()

    cities = CITIES[:max_cities] if max_cities > 0 else CITIES

    # Build full task list: (category, query, city)
    tasks = []
    for category, queries in active_queries.items():
        for query in queries:
            for city in cities:
                tasks.append((category, query, city))

    if max_searches > 0:
        tasks = tasks[:max_searches]

    total = len(tasks)
    type_label = ", ".join(types) if types else "all"
    print(f"\n{'='*60}")
    print(f"PHASE 1: DISCOVERING LEADS ({type_label})")
    print(f"{'='*60}")
    print(f"Search categories: {', '.join(active_queries.keys())}")
    print(f"Total searches: {total:,} across {len(cities)} cities")
    print(f"Concurrency: {MAX_WORKERS} workers, rate limit {RATE_LIMIT_RPS} req/s")
    print()

    all_results = []
    completed = 0
    errors = 0
    start_time = time.monotonic()
    last_print = start_time

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_search_task, cat, query, city): (cat, query, city)
            for cat, query, city in tasks
        }

        for future in as_completed(futures):
            completed += 1
            try:
                results = future.result()
                all_results.extend(results)
            except Exception:
                errors += 1

            # Progress update every 2 seconds
            now = time.monotonic()
            if now - last_print >= 2.0 or completed == total:
                elapsed = now - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta_s = (total - completed) / rate if rate > 0 else 0
                eta_m = eta_s / 60
                print(
                    f"  [{completed:,}/{total:,}] "
                    f"{rate:.1f} req/s | "
                    f"raw results: {len(all_results):,} | "
                    f"errors: {errors} | "
                    f"ETA: {eta_m:.0f}m",
                    flush=True,
                )
                last_print = now

    elapsed_total = time.monotonic() - start_time
    print(f"\nDiscovery complete in {elapsed_total/60:.1f} minutes")
    print(f"Total raw results: {len(all_results):,}")

    if not all_results:
        print("No results found!")
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # --- Parse town / state from address ---
    parsed = df["address"].apply(parse_town_state)
    df["city"] = parsed.apply(lambda x: x[0])
    df["state"] = parsed.apply(lambda x: x[1])

    # --- Dedup ---
    before = len(df)

    df["phone_clean"] = df["phone"].str.replace(r"[^\d]", "", regex=True)
    df_deduped = df.drop_duplicates(subset=["phone_clean"], keep="first")

    mask_no_phone = df_deduped["phone_clean"] == ""
    df_with_phone = df_deduped[~mask_no_phone]
    df_no_phone = df_deduped[mask_no_phone].drop_duplicates(
        subset=["name", "address"], keep="first"
    )

    df_final = pd.concat([df_with_phone, df_no_phone], ignore_index=True)
    df_final = df_final.drop(columns=["phone_clean"])

    # --- Filter chains ---
    chain_mask = df_final["name"].apply(is_chain)
    n_chains = chain_mask.sum()
    df_final = df_final[~chain_mask]

    # --- Filter liquor stores from wine results ---
    liquor_mask = (df_final["business_type"] == "wine_store") & df_final.apply(
        lambda r: is_liquor_store(r["name"], r["category"]), axis=1
    )
    n_liquor = liquor_mask.sum()
    df_final = df_final[~liquor_mask]

    # --- Drop banned states (states Table22 doesn't ship to) ---
    banned_mask = df_final["state"].str.upper().isin(BANNED_STATES)
    n_banned = banned_mask.sum()
    df_final = df_final[~banned_mask]

    # --- Must have a website (needed for enrichment) ---
    df_final = df_final[df_final["website"].str.len() > 0]

    # --- Quality floor: reviews and rating thresholds ---
    is_restaurant = df_final["business_type"] == "restaurant"
    restaurant_mask = is_restaurant & (df_final["review_count"] >= 50) & (df_final["rating"] >= 4.2)
    niche_mask = ~is_restaurant & (df_final["review_count"] >= 20) & (df_final["rating"] >= 4.0)
    df_final = df_final[restaurant_mask | niche_mask]

    # --- Convert price_level to numeric tier ---
    def parse_price(p):
        if isinstance(p, str):
            return p.count("$")
        return 0
    df_final["price_tier"] = df_final["price_level"].apply(parse_price)

    # Sort by review count descending
    df_final = df_final.sort_values("review_count", ascending=False).reset_index(drop=True)

    print(f"\nAfter deduplication: {len(df_final):,} unique leads (removed {before - len(df_final):,} dupes)")
    print(f"  Filtered out {n_chains} chains, {n_liquor} liquor stores, {n_banned} banned-state rows")
    print(f"  Required: website + reviews floor (50 restaurant / 20 niche)")

    # Breakdown by type
    for bt in sorted(df_final["business_type"].unique()):
        n = (df_final["business_type"] == bt).sum()
        print(f"  {bt}: {n}")

    return df_final


if __name__ == "__main__":
    df = discover_leads()
    if not df.empty:
        print(f"\nTop 20 by review count:")
        print(df[["name", "city", "state", "business_type", "rating", "review_count", "website"]].head(20).to_string())
