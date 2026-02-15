"""
Phase 1: Discover leads via Serper Maps API across multiple business types.
"""
import re
import time
import requests
import pandas as pd
from config import (
    SERPER_API_KEY, SEARCH_QUERIES, CITIES,
    BUSINESS_TYPE_MAP, CHAIN_KEYWORDS, LIQUOR_KEYWORDS,
)


def search_serper_maps(query: str, location: str) -> list[dict]:
    """Search Serper Maps API for a query + location combo."""
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

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        places = data.get("places", [])

        results = []
        for p in places:
            results.append({
                "name": p.get("title", ""),
                "address": p.get("address", ""),
                "rating": p.get("rating"),
                "review_count": p.get("ratingCount", 0),
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
        print(f"  [ERROR] Serper request failed for '{query}' in {location}: {e}")
        return []


def parse_town_state(address: str) -> tuple[str, str]:
    """Extract town and state from a Serper Maps address string.

    Typical formats:
      '123 Main St, Chicago, IL 60601'
      'Chicago, IL'
      '123 Main St, New York, NY 10001, United States'
    """
    if not address:
        return "", ""

    # Remove trailing country
    address = re.sub(r",?\s*United States\s*$", "", address, flags=re.I)

    parts = [p.strip() for p in address.split(",")]

    # Walk backwards to find 'STATE ZIP' or 'STATE'
    for i in range(len(parts) - 1, -1, -1):
        # Match 'IL 60601' or 'IL' or 'New York' (2-word state)
        m = re.match(r"^([A-Z]{2})\s*\d*$", parts[i].strip())
        if m:
            state = m.group(1)
            town = parts[i - 1].strip() if i >= 1 else ""
            return town, state

    # Fallback: if address looks like "City, ST", try last two parts
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


def discover_leads() -> pd.DataFrame:
    """Run all search queries across all cities and deduplicate."""
    all_results = []

    # Count total searches for progress display
    total_searches = sum(len(queries) for queries in SEARCH_QUERIES.values()) * len(CITIES)
    search_num = 0

    print(f"\n{'='*60}")
    print(f"PHASE 1: DISCOVERING LEADS")
    print(f"{'='*60}")
    print(f"Business types: {', '.join(SEARCH_QUERIES.keys())}")
    print(f"Running {total_searches} searches across {len(CITIES)} cities")
    print()

    for category, queries in SEARCH_QUERIES.items():
        business_type = BUSINESS_TYPE_MAP[category]
        print(f"\n--- {category.upper()} (tagged as '{business_type}') ---")

        for query in queries:
            for city in CITIES:
                search_num += 1
                print(f"  [{search_num}/{total_searches}] \"{query}\" in {city}...", end=" ")
                results = search_serper_maps(query, city)
                print(f"found {len(results)}")

                # Tag each result with business type and search category
                for r in results:
                    r["business_type"] = business_type
                    r["search_category"] = category

                all_results.extend(results)
                time.sleep(0.3)  # Rate limit

    print(f"\nTotal raw results: {len(all_results)}")

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

    # Clean phone numbers for dedup
    df["phone_clean"] = df["phone"].str.replace(r"[^\d]", "", regex=True)

    # Dedup by phone (most reliable)
    df_deduped = df.drop_duplicates(subset=["phone_clean"], keep="first")

    # For entries without phone, dedup by name + address
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

    # --- Must have a website (needed for enrichment) ---
    df_final = df_final[df_final["website"].str.len() > 0]

    # --- Quality floor: reviews and rating thresholds ---
    # Restaurants: 50+ reviews, 4.2+ rating (high volume, stricter floor)
    # Butcher/Wine: 20+ reviews, 4.0+ rating (niche businesses, fewer reviews)
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

    print(f"\nAfter deduplication: {len(df_final)} unique leads (removed {before - len(df_final)} dupes)")
    print(f"  Filtered out {n_chains} chains, {n_liquor} liquor stores")
    print(f"  Required: website + reviews floor (50 restaurant / 20 butcher & wine)")

    # Breakdown by type
    for bt in df_final["business_type"].unique():
        n = (df_final["business_type"] == bt).sum()
        print(f"  {bt}: {n}")

    return df_final


if __name__ == "__main__":
    df = discover_leads()
    if not df.empty:
        print(f"\nTop 20 by review count:")
        print(df[["name", "city", "state", "business_type", "rating", "review_count", "website"]].head(20).to_string())
