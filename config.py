import os
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Search queries by business type
SEARCH_QUERIES = {
    "restaurant_destination": [
        "best restaurant",
        "fine dining",
        "destination restaurant",
        "tasting menu restaurant",
    ],
    "restaurant_neighborhood": [
        "popular restaurant",
        "farm to table restaurant",
        "neighborhood restaurant",
        "best new restaurant",
    ],
    "butcher": [
        "artisan butcher shop",
        "craft butcher",
        "whole animal butcher",
        "specialty butcher shop",
    ],
    "wine_store": [
        "wine shop",
        "natural wine shop",
        "wine boutique",
        "fine wine store",
    ],
}

# Map search categories to the business_type tag stored on each lead
BUSINESS_TYPE_MAP = {
    "restaurant_destination": "restaurant",
    "restaurant_neighborhood": "restaurant",
    "butcher": "butcher",
    "wine_store": "wine_store",
}

# Top US metros + foodie cities
CITIES = [
    "New York, New York",
    "Brooklyn, New York",
    "Los Angeles, California",
    "San Francisco, California",
    "Oakland, California",
    "Chicago, Illinois",
    "Portland, Oregon",
    "Seattle, Washington",
    "Austin, Texas",
    "Dallas, Texas",
    "Houston, Texas",
    "Denver, Colorado",
    "Nashville, Tennessee",
    "Atlanta, Georgia",
    "Boston, Massachusetts",
    "Philadelphia, Pennsylvania",
    "Washington, DC",
    "Minneapolis, Minnesota",
    "New Orleans, Louisiana",
    "Miami, Florida",
    "San Diego, California",
    "Phoenix, Arizona",
    "Detroit, Michigan",
    "Charlotte, North Carolina",
    "Raleigh, North Carolina",
    "Asheville, North Carolina",
    "Charleston, South Carolina",
    "Savannah, Georgia",
    "Pittsburgh, Pennsylvania",
    "Baltimore, Maryland",
    "St. Louis, Missouri",
    "Kansas City, Missouri",
    "Salt Lake City, Utah",
    "Richmond, Virginia",
    "Louisville, Kentucky",
    "Indianapolis, Indiana",
    "Columbus, Ohio",
    "Cleveland, Ohio",
    "Cincinnati, Ohio",
    "Milwaukee, Wisconsin",
    "Madison, Wisconsin",
    "Boise, Idaho",
    "Tucson, Arizona",
    "Sacramento, California",
    "San Antonio, Texas",
    "Tampa, Florida",
    "Orlando, Florida",
    "Providence, Rhode Island",
    "Burlington, Vermont",
    "Santa Fe, New Mexico",
]

# SHAP-aligned scoring weights (out of 100)
# Partner Type (SHAP #1) is implicit — we tag it during discovery.
# City (SHAP #4) and Google Business Type (SHAP #7) are metadata, not scored.
SCORING_WEIGHTS = {
    "reservation_difficulty": 18,  # SHAP #2 — top actionable signal
    "avg_video_views":        15,  # SHAP #3
    "follower_count":         12,  # SHAP #5
    "press_mentions":         12,  # SHAP #8
    "awards_count":           10,  # SHAP #11 + #18
    "domain_age":              8,  # SHAP #6
    "google_rating":           5,  # SHAP #13
    "avg_likes":               5,  # SHAP #14
    "price_tier":              5,  # SHAP #16
    "has_email_signup":        5,  # bonus — outreach readiness
    "has_ecommerce":           5,  # bonus — fulfillment readiness
}

# Chain keywords to filter out (applies to all business types)
CHAIN_KEYWORDS = [
    "walmart", "costco", "whole foods", "trader joe", "kroger",
    "safeway", "albertsons", "publix", "heb", "h-e-b", "target",
    "sam's club", "aldi", "wegmans", "sprouts", "fresh market",
    "harris teeter", "food lion", "giant", "stop & shop",
    "applebee", "chili's", "olive garden", "red lobster",
    "outback", "cheesecake factory", "p.f. chang", "ruth's chris",
    "capital grille", "morton's", "total wine", "binny's",
    "bevmo", "spec's",
]

# Liquor-store keywords to filter out of wine_store results
LIQUOR_KEYWORDS = [
    "liquor", "spirits", "beer & wine", "package store",
    "beer store", "beverage",
]

# Press / food media domains for mention searches
PRESS_DOMAINS = [
    "eater.com", "bonappetit.com", "nytimes.com",
    "foodandwine.com", "saveur.com", "theinfatuation.com",
]

# Reservation platform priority (higher = harder to get into)
RESERVATION_PLATFORMS = {
    "exploretock.com": 3,   # Tock — typically hardest
    "resy.com": 2,          # Resy
    "opentable.com": 1,     # OpenTable
}
