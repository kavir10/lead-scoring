import os
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Apify actor IDs for enrichment phases
APIFY_ACTOR_GOOGLE_REVIEWS = "compass/google-maps-reviews-scraper"
APIFY_ACTOR_IG_REELS = "apify/instagram-reel-scraper"
APIFY_ACTOR_IG_POSTS = "apify/instagram-post-scraper"
APIFY_ACTOR_OPENTABLE = "shahidirfan/opentable-scraper"

# Resy API config (reverse-engineered, may be fragile)
RESY_API_BASE = "https://api.resy.com/4"
RESY_API_KEY = os.getenv("RESY_API_KEY", "")

# Search queries by business type
SEARCH_QUERIES = {
    "restaurant_destination": [
        "best restaurant",
        "fine dining",
        "tasting menu restaurant",
        "michelin star restaurant",
        "michelin recommended restaurant",
        "james beard award restaurant",
        "hard to book restaurant",
        "sought after restaurant",
        "eater restaurant",
        "chef driven restaurant",
        "omakase restaurant",
        "prix fixe restaurant",
    ],
    "restaurant_neighborhood": [
        "popular restaurant",
        "farm to table restaurant",
        "neighborhood favorite restaurant",
        "best new restaurant",
        "local favorite restaurant",
        "hidden gem restaurant",
        "best brunch spot",
        "best date night restaurant",
        "best pasta restaurant",
        "best seafood restaurant",
        "best steakhouse",
        "best pizza restaurant",
    ],
    "butcher": [
        "artisan butcher shop",
        "craft butcher",
        "whole animal butcher",
        "specialty butcher shop",
        "independent butcher shop",
        "local butcher shop",
        "dry aged beef butcher",
        "heritage breed butcher",
    ],
    "wine_store": [
        "wine shop",
        "natural wine shop",
        "wine boutique",
        "fine wine store",
        "wine club membership",
        "favorite wine store",
        "independent wine shop",
        "curated wine shop",
        "top rated wine store",
        "sommelier wine shop",
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

# Keywords for Google Review reservation sentiment analysis
RESERVATION_DIFFICULTY_KEYWORDS = [
    "hard to get a reservation", "hard to get in", "booked weeks out",
    "booked out", "impossible to get", "can't get a table",
    "couldn't get a reservation", "waitlist", "wait list", "fully booked",
    "no availability", "sold out", "book weeks in advance",
    "book months in advance", "good luck getting", "nearly impossible",
]

# Google Reviews config
GOOGLE_REVIEWS_MAX_PER_PLACE = 30  # Cost: ~$0.0006/review

# SHAP-aligned scoring weights (out of 100)
# Partner Type (SHAP #1) is implicit — we tag it during discovery.
# City (SHAP #4) and Google Business Type (SHAP #7) are metadata, not scored.
SCORING_WEIGHTS = {
    "reservation_difficulty": 15,  # SHAP #2 — composite (platform + review sentiment + availability)
    "avg_video_views":         8,  # Re-enabled via IG Reels actor
    "follower_count":         14,  # SHAP #5 — IG followers + FB likes
    "review_count":            5,  # Google review volume
    "press_mentions":         15,  # SHAP #8 — food media coverage
    "awards_count":           12,  # SHAP #11 + #18 — James Beard, Michelin, etc
    "google_rating":           8,  # SHAP #13 — Google rating quality
    "avg_likes":               5,  # Re-enabled via IG Post actor
    "price_tier":              5,  # SHAP #16 — $$$ level
    "has_email_signup":        7,  # bonus — outreach readiness
    "has_ecommerce":           6,  # bonus — fulfillment readiness
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
