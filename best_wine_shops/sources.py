"""
Seed URLs (user-provided) + Serper search queries used to discover additional
"best wine shops in America" articles. Each entry pairs the URL/query with a
hint string that goes to the LLM so the extracted `distinction` label is
specific instead of a generic "best wine shop".
"""
from __future__ import annotations

# (url, hint)
SEED_URLS: list[tuple[str, str]] = [
    (
        "https://www.chowhound.com/2103109/best-wine-shops-in-the-country/",
        "Chowhound: The Best Wine Shops in the Country. distinction = 'Chowhound Best Wine Shop in the Country'.",
    ),
    (
        "https://vinepair.com/articles/best-wine-shops-2017/",
        "VinePair 50 Best Wine Shops in America 2017. distinction = 'VinePair 50 Best Wine Shops 2017'.",
    ),
    (
        "https://www.sokolin.com/blog/best-us-wine-shop-of-the-world-for-2020-by-bww",
        "Sokolin / Best Wines of the World 2020 — Best US Wine Shop. distinction = 'BWW Best US Wine Shop 2020'.",
    ),
    (
        "https://usawineratings.com/en/blog/leading-wine-retailers-in-usa-55.htm",
        "USA Wine Ratings: Leading Wine Retailers in USA. distinction = 'USA Wine Ratings Leading Wine Retailer'.",
    ),
    (
        "https://www.foodandwine.com/wine/worlds-best-wine-shops",
        "Food & Wine: World's Best Wine Shops. distinction = 'Food & Wine Best Wine Shop'. Only include US entries.",
    ),
    (
        "https://10best.usatoday.com/awards/best-wine-shop/",
        "USA Today 10Best Readers' Choice Awards — Best Wine Shop. distinction = 'USA Today 10Best Wine Shop' + year if visible.",
    ),
    (
        "https://imbibemagazine.com/best-wine-shops/",
        "Imbibe Magazine: Best Wine Shops. distinction = 'Imbibe Best Wine Shop'.",
    ),
]


_NATIONAL = [
    '"best wine shops" "united states"',
    '"best wine shops in america"',
    '"best independent wine shops" usa',
    '"top wine retailers" united states',
    '"best wine stores in america"',
    '"best natural wine shops" united states',
    '"best wine merchants" america',
    '"award winning wine shops" usa',
]

_REGIONS = [
    "Northeast",
    "West Coast",
    "Pacific Northwest",
    "South",
    "Midwest",
    "Mountain West",
]

# Top wine-retail metros by state. Two queries each.
_STATES = [
    "New York", "California", "Illinois", "Texas", "Massachusetts",
    "Florida", "Washington", "Oregon", "Colorado", "Pennsylvania",
    "Georgia", "North Carolina", "Michigan", "Minnesota", "New Jersey",
    "Virginia", "Arizona", "Nevada", "Wisconsin", "Tennessee",
]

# Also a few high-density cities, since some lists are city-bound.
_CITIES = [
    "New York City", "Brooklyn", "Los Angeles", "San Francisco",
    "Chicago", "Houston", "Austin", "Boston", "Miami", "Seattle",
    "Portland", "Denver", "Washington DC", "Philadelphia",
]


def _hint(label: str) -> str:
    return (
        f"Search results / article about best wine shops in {label}. "
        "Extract every independent (non-chain) US wine retailer named. "
        "distinction should reference the article title/publication if identifiable, "
        "otherwise default to 'Best Wine Shop editorial mention'. "
        "Set is_online_only=true ONLY if the article explicitly describes the "
        "business as online-only/e-commerce-only with no physical retail."
    )


def _build_queries() -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    for q in _NATIONAL:
        queries.append((q, _hint("the United States")))
    for region in _REGIONS:
        queries.append((f'"best wine shops" {region}', _hint(region)))
        queries.append((f'"best wine stores" {region}', _hint(region)))
    for state in _STATES:
        queries.append((f'"best wine shops" "{state}"', _hint(state)))
        queries.append((f'"best wine stores" "{state}"', _hint(state)))
    for city in _CITIES:
        queries.append((f'"best wine shops" "{city}"', _hint(city)))
    return queries


SEARCH_QUERIES: list[tuple[str, str]] = _build_queries()
