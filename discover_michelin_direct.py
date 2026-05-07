"""
Direct Michelin Guide scraper using Playwright (bypasses AWS WAF that blocks pure HTTP).

Why Playwright: guide.michelin.com is fronted by AWS WAF JS challenge that
returns 202 with empty body to plain requests/httpx. A real browser solves
the challenge automatically.

Usage:
    python discover_michelin_direct.py --smoke               # 3-stars page 1 only
    python discover_michelin_direct.py --us                  # all tiers, US only
    python discover_michelin_direct.py --us --tiers "3 Stars,2 Stars,1 Star"
    python discover_michelin_direct.py --us --headed         # show browser (debug)

Output: output/michelin_direct_<scope>_<YYYYMMDD>.csv
Schema: tier, name, city, region, distinction, price, cooking_type,
        online_booking, lat, lng, michelin_id, michelin_url
"""

import argparse
import json
import os
import sys
from datetime import datetime

import pandas as pd
from playwright.sync_api import sync_playwright

TIERS = {
    "3 Stars": ("3-stars-michelin", "3 star"),
    "2 Stars": ("2-stars-michelin", "2 star"),
    "1 Star": ("1-star-michelin", "1 star"),
    "Bib Gourmand": ("bib-gourmand", "bib"),
    "Green Star": ("green-star-michelin", "green-star"),
    "Selected": ("the-plate-michelin", "the-plate"),
}
TIER_RANK = {"3 Stars": 5, "2 Stars": 4, "1 Star": 3, "Bib Gourmand": 2, "Green Star": 1, "Selected": 0}
DISTINCTION_TO_TIER = {
    "3 star": "3 Stars",
    "2 star": "2 Stars",
    "1 star": "1 Star",
    "bib": "Bib Gourmand",
    "green-star": "Green Star",
    "the-plate": "Selected",
}
DEFAULT_TIERS = ["3 Stars", "2 Stars", "1 Star", "Bib Gourmand", "Green Star"]
BASE = "https://guide.michelin.com/us/en/restaurants"

# JS extractor — runs in page context, returns one page's worth of cards.
EXTRACT_JS = """
() => {
  const cardEls = document.querySelectorAll('div.card__menu');
  const out = [];
  for (const c of cardEls) {
    const love = c.querySelector('.love-icon');
    if (!love) continue;
    const link = c.querySelector('a.link, h3 a, a.card__menu-image');
    out.push({
      id: c.dataset.id || '',
      lat: c.dataset.lat || '',
      lng: c.dataset.lng || '',
      name: love.getAttribute('data-restaurant-name') || '',
      country: love.getAttribute('data-restaurant-country') || '',
      city: love.getAttribute('data-dtm-city') || '',
      region: love.getAttribute('data-dtm-region') || '',
      distinction: love.getAttribute('data-dtm-distinction') || '',
      price: love.getAttribute('data-dtm-price') || '',
      cooking_type: love.getAttribute('data-cooking-type') || '',
      online_booking: love.getAttribute('data-dtm-online-booking') || '',
      michelin_url: link?.href || '',
    });
  }
  return out;
}
"""


def scrape_tier(page, tier_label: str, country: str = "us", max_pages: int = 60) -> list[dict]:
    """Scrape one tier listing. Stops when on-tier content drops below threshold."""
    slug, expected_distinction = TIERS[tier_label]
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for p in range(1, max_pages + 1):
        url = f"{BASE}/{slug}/page/{p}"
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_selector("div.card__menu, .no-result, footer", timeout=20_000)
        cards = page.evaluate(EXTRACT_JS)
        if not cards:
            break
        on_tier = sum(1 for c in cards if c["distinction"] == expected_distinction)
        # Stop when the page is mostly off-tier (we've fallen off into all-restaurants pagination)
        if on_tier < 5:
            print(f"  {tier_label:<14} page {p:>2}: only {on_tier}/{len(cards)} on-tier, stopping", flush=True)
            break
        country_count = 0
        for c in cards:
            if c["distinction"] != expected_distinction:
                continue
            if c["id"] in seen_ids:
                continue
            if c["id"]:
                seen_ids.add(c["id"])
            if country and c["country"] != country:
                continue
            c["tier"] = DISTINCTION_TO_TIER.get(c["distinction"], tier_label)
            c["online_booking"] = c["online_booking"] == "True"
            rows.append(c)
            country_count += 1
        print(f"  {tier_label:<14} page {p:>2}: {len(cards)} cards ({on_tier} on-tier, {country_count} new {country})", flush=True)
        if on_tier < 20:
            break
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    """Dedupe by Michelin id; fall back to (name, city) when id missing. Keep best tier."""
    seen: dict[tuple, dict] = {}
    for r in rows:
        key = ("id", r["id"]) if r["id"] else ("nc", r["name"].lower(), r["city"].lower())
        cur = seen.get(key)
        if not cur or TIER_RANK.get(r["tier"], 0) > TIER_RANK.get(cur["tier"], 0):
            seen[key] = r
    return list(seen.values())


def report(df: pd.DataFrame) -> None:
    print(f"\n  TOTAL UNIQUE: {len(df)}")
    if df.empty:
        return
    print("\n  By tier (best-tier dedup):")
    for tier, n in df["tier"].value_counts().items():
        print(f"    {tier:<14} {n}")
    print("\n  By city (top 20):")
    for city, n in df["city"].value_counts().head(20).items():
        print(f"    {city:<25} {n}")


def save(df: pd.DataFrame, scope: str) -> str:
    os.makedirs("output", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    path = f"output/michelin_direct_{scope}_{stamp}.csv"
    df.to_csv(path, index=False)
    print(f"\n  Saved {len(df)} rows -> {path}")
    return path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true", help="3-stars page 1 only (fast sanity check)")
    p.add_argument("--us", action="store_true", help="Full US extract across default tiers")
    p.add_argument("--tiers", type=str, default="", help="Comma-separated tier list")
    p.add_argument("--country", type=str, default="us", help="Country filter (default: us)")
    p.add_argument("--include-selected", action="store_true", help="Include 'Selected' tier (huge)")
    p.add_argument("--headed", action="store_true", help="Show browser window (debug)")
    args = p.parse_args()

    if args.smoke:
        tiers = ["3 Stars"]
        scope = "smoke"
        max_pages = 1
    else:
        if args.tiers:
            tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
        elif args.include_selected:
            tiers = DEFAULT_TIERS + ["Selected"]
        else:
            tiers = DEFAULT_TIERS
        scope = f"{args.country}"
        max_pages = 60

    bad = [t for t in tiers if t not in TIERS]
    if bad:
        sys.exit(f"Unknown tiers: {bad}. Valid: {list(TIERS)}")

    print(f"\n{'='*60}")
    print(f"MICHELIN DIRECT ({scope})  tiers={tiers}  country={args.country}")
    print(f"{'='*60}")

    raw: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=45_000)
        for tier in tiers:
            raw.extend(scrape_tier(page, tier, country=args.country, max_pages=max_pages))
        browser.close()

    print(f"\n  Raw rows (pre-dedup): {len(raw)}")
    unique = dedupe(raw)
    df = pd.DataFrame(unique)
    if not df.empty:
        df = df[["tier", "name", "city", "region", "distinction", "price",
                 "cooking_type", "online_booking", "lat", "lng",
                 "michelin_id" if "michelin_id" in df.columns else "id", "michelin_url"]
                ].rename(columns={"id": "michelin_id"})
    report(df)
    save(df, scope)


if __name__ == "__main__":
    main()
