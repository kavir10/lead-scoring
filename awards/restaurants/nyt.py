"""
New York Times — restaurant reviews and "best of" lists.

Auth-walled. Pass `--cookies-from cookies/nyt.json` (Playwright cookie export
or list-of-dicts JSON). Without cookies the orchestrator skips this source.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles
from awards._lib import to_dataframe

ARTICLES: list[tuple[str, str]] = [
    ("https://www.nytimes.com/2024/12/03/dining/best-new-restaurants-nyc.html",
     "NYT The Best New Restaurants of 2024 — distinction = 'NYT Best New 2024'."),
    ("https://www.nytimes.com/interactive/2024/dining/best-restaurants-new-york.html",
     "NYT The Best Restaurants in NYC 2024 — distinction = 'NYT Best Restaurant NYC 2024'."),
    ("https://www.nytimes.com/2023/11/27/dining/best-new-restaurants.html",
     "NYT Best New Restaurants 2023 — distinction = 'NYT Best New 2023'."),
]


def scrape(*, cookies=None, **_kwargs) -> pd.DataFrame:
    if not cookies:
        # Orchestrator should already skip auth sources without cookies, but
        # belt and suspenders.
        print("  [nyt] no cookies supplied; cannot fetch paywalled content", flush=True)
        return to_dataframe([])

    # Use Playwright with cookies to fetch each article, then feed text to LLM.
    from awards._lib import playwright_session
    from awards.llm_extract import extract_businesses_from_text
    from awards._lib import normalize_state

    rows = []
    with playwright_session(cookies=cookies) as (page, _ctx, _br):
        for url, hint in ARTICLES:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_load_state("networkidle", timeout=15_000)
                text = page.evaluate("() => document.body.innerText") or ""
            except Exception as e:
                print(f"  [nyt] failed to load {url}: {e}", flush=True)
                continue
            if len(text) < 800:
                print(f"  [nyt] insufficient text from {url} (paywall?)", flush=True)
                continue
            for r in extract_businesses_from_text(text, source_url=url, hint=hint):
                rows.append({
                    "source": "nyt",
                    "tier": 1,
                    "business_type": "restaurant",
                    "name": r["name"],
                    "city": r["city"],
                    "state": normalize_state(r["state"]),
                    "country": "us",
                    "distinction": r.get("distinction") or "NYT Best Restaurant",
                    "year": "",
                    "source_url": url,
                    "blurb": r.get("blurb", ""),
                })
    return to_dataframe(rows)
