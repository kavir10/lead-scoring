"""
Goldbelly — D2C food marketplace shipping nationally.

Goldbelly's site is locked behind aggressive Cloudflare challenges on every
endpoint, including sitemaps and individual merchant pages. Even curl_cffi
+ Playwright cannot reach the merchant grid. The merchants ARE indexed by
Google though — pivoting to Serper-snippet mining over `site:goldbelly.com`
queries.

Strategy: docs/strategies/04_d2c_marketplaces.md
"""
from __future__ import annotations

import os
import re
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from awards._lib import (
    SCHEMA,
    make_row,
    normalize_state,
    to_dataframe,
)


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))


# Verticals carved by city — Serper depth caps at ~100 results, so we slice
# by topic and major metro to maximize unique merchant URLs surfaced.
_SLICES = [
    "site:goldbelly.com restaurants New York",
    "site:goldbelly.com restaurants Los Angeles",
    "site:goldbelly.com restaurants Chicago",
    "site:goldbelly.com restaurants New Orleans",
    "site:goldbelly.com restaurants Texas",
    "site:goldbelly.com restaurants Philadelphia",
    "site:goldbelly.com bakery",
    "site:goldbelly.com bakery New York",
    "site:goldbelly.com pizza",
    "site:goldbelly.com bbq",
    "site:goldbelly.com cheese",
    "site:goldbelly.com butcher",
    "site:goldbelly.com seafood",
    "site:goldbelly.com Italian",
    "site:goldbelly.com Mexican",
    "site:goldbelly.com deli sandwich",
    "site:goldbelly.com steakhouse",
]


def _serper(query: str, num: int = 30) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num, "gl": "us", "hl": "en"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("organic", []) or []
    except Exception as e:
        print(f"  [goldbelly] serper error: {e}", flush=True)
        return []


def _parse_serp(result: dict) -> dict | None:
    """Extract name + city + state from a Goldbelly merchant SERP result."""
    link = result.get("link", "") or ""
    title = (result.get("title") or "").strip()
    snippet = (result.get("snippet") or "").strip()

    if "goldbelly.com" not in link:
        return None
    # Filter out category/home pages — we only want individual merchant URLs
    if not re.search(r"goldbelly\.com/(?:restaurants|merchants|bakeries|butchers|stores)/[a-z0-9-]+", link):
        return None

    # Title format: "Merchant Name on Goldbelly" or "Merchant Name | Goldbelly"
    name = re.split(r"\s*[\|\-–—]\s*", title.split(" on Goldbelly")[0])[0].strip()
    name = re.sub(r"\s*\|\s*Goldbelly.*$", "", name).strip()
    name = re.sub(r"\s+Delivers Nationwide\s*$", "", name, flags=re.I).strip()
    if not name or len(name) > 80:
        return None
    if name.lower() in {"goldbelly", "restaurants", "bakeries"}:
        return None

    # City/state from snippet — Goldbelly snippets often say "Based in <City>, <ST>" or "from <City>, <ST>"
    city, state = "", ""
    m = re.search(r"(?:from|based in|ships from)\s+([A-Z][a-zA-Z\s.'\-]+?),\s*([A-Z]{2})\b", snippet)
    if m:
        city, state = m.group(1).strip(), normalize_state(m.group(2))
    else:
        m = re.search(r"\b([A-Z][a-zA-Z\s.'\-]{2,30}),\s*([A-Z]{2})\b", snippet)
        if m:
            city, state = m.group(1).strip(), normalize_state(m.group(2))

    # Infer vertical from URL
    if "/bakeries/" in link or "/bakery/" in link:
        btype = "bakery"
    elif "/butchers/" in link or "/butcher/" in link:
        btype = "butcher"
    elif "/cheese" in link:
        btype = "cheese"
    elif "/seafood" in link:
        btype = "fish"
    elif "/pizza" in link:
        btype = "restaurant"
    else:
        btype = "restaurant"

    return {
        "name": name,
        "city": city,
        "state": state,
        "url": link,
        "btype": btype,
        "blurb": snippet[:250],
    }


def scrape(**_kwargs) -> pd.DataFrame:
    seen_urls: set[str] = set()
    rows: list[dict] = []
    for q in _SLICES:
        print(f"  [goldbelly] serper {q!r}", flush=True)
        results = _serper(q, num=30)
        for r in results:
            info = _parse_serp(r)
            if not info or info["url"] in seen_urls:
                continue
            seen_urls.add(info["url"])
            rows.append(make_row(
                source="d2c_goldbelly",
                tier=1,
                business_type=info["btype"],
                name=info["name"],
                city=info["city"],
                state=info["state"],
                country="us",
                distinction="Goldbelly merchant — ships nationwide",
                source_url=info["url"],
                blurb=info["blurb"],
            ))
        time.sleep(0.5)
    print(f"  [goldbelly] {len(rows)} unique merchants extracted", flush=True)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
