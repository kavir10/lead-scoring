"""
Wine Enthusiast Wine Star Awards (Retailer of the Year, Importer of the Year,
American Winery, Lifetime Achievement, etc.).

WE.com is Cloudflare-blocked to headless browsers, so we rely entirely on
search + snippet fallback. WSA winners get individual permalink pages plus
yearly recap articles, both of which leak the winner names in snippets.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

CATEGORIES = [
    "Retailer of the Year",
    "Importer of the Year",
    "Wholesaler of the Year",
    "Restaurant of the Year",
    "Winery of the Year",
    "American Winery of the Year",
    "European Winery of the Year",
    "New World Winery of the Year",
    "Wine Region of the Year",
    "Person of the Year",
    "Innovator of the Year",
    "Lifetime Achievement",
    "Social Visionary",
    "Sommelier of the Year",
]

YEARS = [2024, 2023, 2022, 2021, 2020, 2019]

SEARCH_QUERIES: list[tuple[str, str]] = []
for cat in CATEGORIES:
    SEARCH_QUERIES.append((
        f'site:wineenthusiast.com "{cat}" wine star',
        f"WE Wine Star — {cat}. The 'name' is the business; person in blurb if applicable. distinction = 'WE Wine Star: {cat} <Year>'.",
    ))
for year in YEARS:
    SEARCH_QUERIES.append((
        f'site:wineenthusiast.com wine star awards {year} winners',
        f"WE Wine Star Awards {year} full winners list. distinction = 'WE Wine Star: <Category> {year}'.",
    ))
SEARCH_QUERIES.append((
    'wine enthusiast wine star awards retailer of the year',
    "WE Retailer of the Year recipients across years (search third-party coverage too). distinction = 'WE Wine Star: Retailer of the Year <Year>'.",
))


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="wine_enthusiast_star",
        tier=1,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["wineenthusiast.com", "shankennewsdaily.com",
                        "winebusiness.com", "wineindustryadvisor.com"],
        distinction_default="WE Wine Star Award",
        max_per_query=5,
    )
