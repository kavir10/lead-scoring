"""
Wine Enthusiast — Best Wine Shops in America (and Best Spirits Shops, Best
Neighborhood Wine Shops, Best Online Drinks Shops). The site itself is hard-
blocked by Cloudflare to headless browsers, so we rely on Serper search +
snippet-extraction fallback. Multiple regional queries surface different
snippet sections of each article.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

REGIONS = [
    "Northwest Pacific California",
    "Mountain Pacific California",
    "Northeast",
    "New York",
    "Mid-Atlantic",
    "Southeast",
    "South",
    "Midwest",
    "Texas",
    "Mountain",
    "Southwest",
]

SEARCH_QUERIES: list[tuple[str, str]] = []
for region in REGIONS:
    SEARCH_QUERIES.append((
        f'site:wineenthusiast.com "best wine shops" {region}',
        f"Wine Enthusiast Best Wine Shops — {region} section. distinction = 'Wine Enthusiast Best Wine Shop' + year. Names often appear as bullet/comma-separated lists.",
    ))
    SEARCH_QUERIES.append((
        f'site:wineenthusiast.com "best spirits shops" {region}',
        f"Wine Enthusiast Best Spirits Shops — {region} section. distinction = 'Wine Enthusiast Best Spirits Shop' + year.",
    ))
SEARCH_QUERIES += [
    ("site:wineenthusiast.com best american wine shops",
     "Wine Enthusiast Best American Wine Shops — overview list. distinction = 'Wine Enthusiast Best American Wine Shop'."),
    ("site:wineenthusiast.com best wine shops 2023 community hubs",
     "Wine Enthusiast Best Wine Shops 2023. distinction = 'Wine Enthusiast Best Wine Shop 2023'."),
    ("site:wineenthusiast.com best neighborhood wine shops",
     "Wine Enthusiast Best Neighborhood Wine Shops. distinction = 'Wine Enthusiast Best Neighborhood Wine Shop'."),
    ("site:wineenthusiast.com best online drinks shops wine spirits",
     "Wine Enthusiast Best Online Drinks Shops. distinction = 'Wine Enthusiast Best Online Drinks Shop'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="wine_enthusiast_shops",
        tier=1,
        business_type="wine_store",
        search_queries=SEARCH_QUERIES,
        search_domains=["wineenthusiast.com"],
        distinction_default="WE Best Wine Shops in America",
        max_per_query=6,
    )
