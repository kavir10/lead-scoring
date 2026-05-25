"""
Williams-Sonoma Marketplace — curated food + specialty vendors.

The W-S 'Made by Small Businesses' / 'Marketplace' section lists independent
food brands. Plain HTTP doesn't surface vendor pages reliably; Playwright
fallback is the default.
"""
from __future__ import annotations

import re
import time

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


URLS = [
    "https://www.williams-sonoma.com/shop/food/foods-by-region/",
    "https://www.williams-sonoma.com/shop/food/small-batch-artisan-foods/",
]


def _fetch(url: str) -> str:
    html = fetch_html(url)
    if html and "williams-sonoma" in html.lower():
        return html
    try:
        with playwright_session() as (page, _ctx, _br):
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=12_000)
            except Exception:
                pass
            return page.content() or ""
    except Exception as e:
        print(f"  [ws_marketplace] playwright failed: {e}", flush=True)
        return ""


def _extract_vendor_blurbs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for card in soup.select("div.product, div.shop-grid__item, article.product-tile"):
        title_el = card.find(["h3", "h4", "a"])
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        # Williams-Sonoma product titles often include "[Brand] [Product]" — strip product noise
        if not title:
            continue
        # Vendor brand is usually the first 2-3 words; keep up to first hyphen/em-dash
        brand = re.split(r"[—–\-:]", title)[0].strip()
        if len(brand) < 3 or len(brand) > 60:
            continue
        out.append({"name": brand, "title": title})
    return out


def scrape(**_kwargs) -> pd.DataFrame:
    """v1: W-S product cards rarely include vendor city/state — leave empty,
    let downstream enrichment geocode. Skip if site changes block this."""
    rows: list[dict] = []
    seen: set[str] = set()
    for url in URLS:
        print(f"  [ws_marketplace] fetching {url}", flush=True)
        html = _fetch(url)
        if not html:
            continue
        vendors = _extract_vendor_blurbs(html)
        print(f"  [ws_marketplace] +{len(vendors)} vendor blurbs", flush=True)
        for v in vendors:
            key = v["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append(make_row(
                source="d2c_williams_sonoma",
                tier=1,
                business_type="specialty",
                name=v["name"],
                distinction="Williams-Sonoma Marketplace vendor",
                source_url=url,
                blurb=v.get("title", ""),
            ))
        time.sleep(0.8)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
