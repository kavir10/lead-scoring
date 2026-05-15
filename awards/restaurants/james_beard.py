"""
James Beard Foundation Awards — restaurants/chefs/hospitality.

Strategy: JBF publishes results at https://www.jamesbeard.org/awards/search,
but the page is JS-rendered and uses an internal API for filtering. We use
Playwright to load the search page and paginate through results.

Categories we keep:
  - Outstanding Restaurant
  - Outstanding Restaurateur
  - Outstanding Chef
  - Outstanding Hospitality
  - Best New Restaurant
  - Outstanding Wine Program
  - Outstanding Wine and Other Beverages Program
  - Outstanding Pastry Chef or Baker
  - Outstanding Bakery
  - Best Chef <region> (winners only — semis would balloon the list)
  - Outstanding Hospitality

Years: 2015-present (recent enough to be commercially relevant).

The JBF site's structure changes periodically — if scraping fails, the module
falls back to a curated set of "Restaurant and Chef Awards" landing-page URLs
fed through the LLM extractor.
"""
from __future__ import annotations

import re

import pandas as pd

from awards._lib import (
    SCHEMA,
    fetch_html,
    normalize_state,
    parse_city_state,
    playwright_session,
    to_dataframe,
)
from awards.llm_extract import extract_businesses_from_url

KEEP_CATEGORIES = [
    "outstanding restaurant",
    "outstanding restaurateur",
    "outstanding chef",
    "outstanding hospitality",
    "best new restaurant",
    "outstanding wine program",
    "outstanding wine and other beverages program",
    "outstanding wine, beer, or spirits producer",
    "outstanding pastry chef",
    "outstanding pastry chef or baker",
    "outstanding baker",
    "outstanding bakery",
    "best chef",  # regional best chefs
]

# JBF URL slugs change yearly; rely on search to find the current locations.
SEARCH_QUERIES: list[tuple[str, str]] = [
    ("james beard awards 2024 restaurant and chef winners",
     "James Beard 2024 Restaurant & Chef winners — extract restaurants/chefs/bakeries with city+state. distinction = 'James Beard <Category> 2024'."),
    ("james beard awards 2023 restaurant and chef winners",
     "James Beard 2023 Restaurant & Chef winners. distinction = 'James Beard <Category> 2023'."),
    ("james beard outstanding restaurant winner",
     "JBF Outstanding Restaurant winners across years. distinction = 'James Beard Outstanding Restaurant <Year>'."),
    ("james beard outstanding bakery winner",
     "JBF Outstanding Bakery winners. distinction = 'James Beard Outstanding Bakery <Year>'."),
    ("james beard outstanding wine program winner",
     "JBF Outstanding Wine Program winners. distinction = 'James Beard Outstanding Wine Program <Year>'."),
    ("james beard best new restaurant winner",
     "JBF Best New Restaurant winners. distinction = 'James Beard Best New Restaurant <Year>'."),
    ("james beard outstanding pastry chef baker winner",
     "JBF Outstanding Pastry Chef/Baker — extract chefs and the bakery they work at. distinction = 'James Beard Outstanding Pastry Chef/Baker <Year>'."),
    ("james beard best chef finalist winner",
     "JBF regional Best Chef winners across regions. distinction = 'James Beard Best Chef <Region> <Year>'."),
]


def _category_keep(category: str) -> bool:
    c = category.lower()
    return any(k in c for k in KEEP_CATEGORIES)


def _scrape_search_page() -> list[dict]:
    """Best-effort Playwright pull of /awards/search results."""
    rows: list[dict] = []
    base = "https://www.jamesbeard.org/awards/search"
    try:
        with playwright_session() as (page, _ctx, _br):
            page.goto(base, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_selector("[data-page='awards-search'], .award-result, main", timeout=20_000)
            except Exception:
                pass

            # Many JBF result cards live in `.search-result` or similar — the JS
            # framework renders them with consistent attribute hooks. We try a few.
            selectors = [
                ".award-result-card",
                ".search-result",
                "[class*='ResultCard']",
                "article.card",
            ]
            handles: list = []
            for sel in selectors:
                found = page.query_selector_all(sel)
                if found:
                    handles = found
                    break

            if not handles:
                print("  [jbf] no result cards found via Playwright; using LLM fallback", flush=True)
                return []

            for h in handles:
                txt = (h.inner_text() or "").strip()
                if not txt:
                    continue
                # Pull a year, category, and recipient name out of the text. JBF cards
                # tend to read "<Year> <Category> <Recipient> — <Restaurant>, <City, ST>".
                year_m = re.search(r"\b(20\d{2})\b", txt)
                year = year_m.group(1) if year_m else ""
                # Heuristic category match
                cat_lower = txt.lower()
                category = ""
                for k in KEEP_CATEGORIES:
                    if k in cat_lower:
                        category = k.title()
                        break
                if not category:
                    continue
                # Restaurant name: take the first line that isn't a year/category
                lines = [l.strip() for l in txt.splitlines() if l.strip()]
                name = ""
                city = state = ""
                for l in lines:
                    if l.lower() == category.lower():
                        continue
                    if year and l == year:
                        continue
                    if "—" in l or "–" in l:
                        a, b = re.split(r"\s*[—–]\s*", l, maxsplit=1)
                        # Restaurant — City, ST
                        if "," in b:
                            name = a.strip()
                            city, state = parse_city_state(b)
                            break
                    if "," in l:
                        # "Restaurant, City, ST"
                        parts = [p.strip() for p in l.split(",")]
                        if len(parts) >= 3 and len(parts[-1]) <= 3:
                            name = ", ".join(parts[:-2])
                            city = parts[-2]
                            state = normalize_state(parts[-1])
                            break
                if not name:
                    continue
                rows.append({
                    "name": name,
                    "city": city,
                    "state": state,
                    "country": "us",
                    "distinction": f"James Beard {category}",
                    "year": year,
                    "source_url": base,
                    "blurb": txt[:200],
                })
    except Exception as e:
        print(f"  [jbf] playwright error: {e}", flush=True)
        return []
    return rows


def scrape(**_kwargs) -> pd.DataFrame:
    # The search-page Playwright path is brittle (selectors change). Skip it
    # and go straight to search-driven LLM extraction.
    from awards._editorial import scrape_articles
    return scrape_articles(
        source_slug="james_beard",
        tier=1,
        business_type="restaurant",
        search_queries=SEARCH_QUERIES,
        search_domains=["jamesbeard.org", "eater.com", "foodandwine.com"],
        distinction_default="James Beard Award",
    )
