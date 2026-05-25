"""
Goldbelly — D2C food marketplace shipping nationally from independent
restaurants, bakeries, butchers, and specialty retailers.

Merchants are listed at https://www.goldbelly.com/merchants and also surface
in category pages (/restaurants, /bakery, /butchers, etc.). Each merchant
page names the venue + city + state + blurb.

Strategy: docs/strategies/04_d2c_marketplaces.md
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from awards._lib import (
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
    playwright_session,
    to_dataframe,
)


BASE = "https://www.goldbelly.com"
LISTING_URLS = [
    f"{BASE}/merchants",
    f"{BASE}/restaurants",
    f"{BASE}/bakeries",
    f"{BASE}/butchers",
    f"{BASE}/bbq",
    f"{BASE}/pizza",
    f"{BASE}/cheese-shops",
]


def _fetch(url: str) -> str:
    html = fetch_html(url)
    if not html or "goldbelly" not in html.lower():
        try:
            with playwright_session() as (page, _ctx, _br):
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12_000)
                except Exception:
                    pass
                html = page.content() or ""
        except Exception as e:
            print(f"  [goldbelly] playwright failed: {e}", flush=True)
            return ""
    return html


def _extract_merchant_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.select('a[href*="/merchants/"]'):
        href = a.get("href") or ""
        if href and "/merchants/" in href and not href.endswith("/merchants"):
            full = urljoin(BASE, href.split("?")[0])
            links.append(full)
    return list(dict.fromkeys(links))


def _parse_merchant_page(url: str) -> dict | None:
    html = _fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find(["h1"])
    name = title.get_text(strip=True) if title else ""
    if not name:
        return None
    # City/state usually appears near the merchant name as "City, ST" text
    body_text = soup.get_text(" ", strip=True)[:3000]
    m = re.search(r"\b([A-Z][a-zA-Z\s.'\-]+?),\s*([A-Z]{2})\b", body_text)
    city, state = ("", "")
    if m:
        city, state = m.group(1).strip(), normalize_state(m.group(2))
    blurb_el = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    blurb = (blurb_el.get("content") or "")[:300] if blurb_el else ""
    return {"name": name, "city": city, "state": state, "blurb": blurb, "url": url}


def scrape(**_kwargs) -> pd.DataFrame:
    seen_urls: set[str] = set()
    for listing_url in LISTING_URLS:
        print(f"  [goldbelly] listing {listing_url}", flush=True)
        html = _fetch(listing_url)
        if not html:
            continue
        seen_urls.update(_extract_merchant_links(html))
        time.sleep(0.6)
    print(f"  [goldbelly] {len(seen_urls)} unique merchant URLs", flush=True)
    rows: list[dict] = []
    for i, url in enumerate(sorted(seen_urls)):
        if i % 25 == 0 and i > 0:
            print(f"  [goldbelly] parsed {i}/{len(seen_urls)} merchants", flush=True)
        info = _parse_merchant_page(url)
        if not info:
            continue
        # Heuristic vertical inference from URL or name
        url_lower = url.lower()
        if "bakery" in url_lower or "bake" in info["name"].lower():
            btype = "bakery"
        elif "butcher" in url_lower or "bbq" in url_lower or "meat" in info["name"].lower():
            btype = "butcher"
        elif "cheese" in url_lower:
            btype = "cheese"
        elif "pizza" in url_lower:
            btype = "restaurant"
        else:
            btype = "restaurant"
        rows.append(make_row(
            source="d2c_goldbelly",
            tier=1,
            business_type=btype,
            name=info["name"],
            city=info["city"],
            state=info["state"],
            country="us",
            distinction="Goldbelly merchant — ships nationwide",
            source_url=info["url"],
            blurb=info["blurb"],
        ))
        time.sleep(0.3)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
