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
    "butcher_premium": [
        "best butcher shop",
        "artisan butcher shop",
        "craft butcher",
        "whole animal butcher",
        "dry aged beef butcher",
        "heritage breed butcher",
        "wagyu butcher",
        "prime meat shop",
        "gourmet butcher shop",
        "nose to tail butcher",
        "sustainable butcher shop",
        "organic butcher shop",
        "pasture raised meat shop",
        "grass fed butcher",
        "farm to table butcher",
        "premium meat market",
    ],
    "butcher_local": [
        "specialty butcher shop",
        "independent butcher shop",
        "local butcher shop",
        "neighborhood butcher",
        "favorite butcher shop",
        "family butcher shop",
        "top rated butcher",
        "custom cut butcher",
        "meat market",
        "charcuterie shop",
        "smoked meat shop",
        "old fashioned butcher",
        "halal butcher shop",
        "kosher butcher shop",
        "european butcher shop",
        "italian butcher shop",
        "german butcher shop",
        "deli and butcher",
        "sausage maker shop",
        "meat shop near me",
    ],
    "wine_store_premium": [
        "wine shop",
        "natural wine shop",
        "wine boutique",
        "fine wine store",
        "curated wine shop",
        "sommelier wine shop",
        "rare wine shop",
        "organic wine store",
        "biodynamic wine shop",
        "wine cellar store",
        "premium wine store",
        "artisan wine shop",
        "wine merchant",
        "wine import shop",
        "french wine shop",
        "italian wine shop",
    ],
    "wine_store_local": [
        "wine club membership",
        "favorite wine store",
        "independent wine shop",
        "top rated wine store",
        "neighborhood wine shop",
        "local wine store",
        "wine and cheese shop",
        "best wine store",
        "wine bar and shop",
        "wine tasting shop",
        "hidden gem wine store",
        "boutique wine shop",
        "wine and spirits shop",
        "wine store near me",
        "craft wine shop",
        "family wine shop",
        "wine cellar shop",
        "wine delivery shop",
    ],
}

# Map search categories to the business_type tag stored on each lead
BUSINESS_TYPE_MAP = {
    "restaurant_destination": "restaurant",
    "restaurant_neighborhood": "restaurant",
    "butcher_premium": "butcher",
    "butcher_local": "butcher",
    "wine_store_premium": "wine_store",
    "wine_store_local": "wine_store",
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
    # Additional foodie cities for broader butcher/wine coverage
    "Napa, California",
    "Sonoma, California",
    "Portland, Maine",
    "Cambridge, Massachusetts",
    "Pasadena, California",
    "Santa Monica, California",
    "Berkeley, California",
    "Hoboken, New Jersey",
    "Jersey City, New Jersey",
    "Alexandria, Virginia",
    "Scottsdale, Arizona",
    "Fort Worth, Texas",
    "Greenville, South Carolina",
    "Durham, North Carolina",
    "Ann Arbor, Michigan",
    "Chattanooga, Tennessee",
    "Knoxville, Tennessee",
    "Omaha, Nebraska",
    "Des Moines, Iowa",
    "Honolulu, Hawaii",
    "Bend, Oregon",
    "Albuquerque, New Mexico",
    "Wilmington, North Carolina",
    "Lexington, Kentucky",
    "Grand Rapids, Michigan",
    # Wave 2: Suburbs and additional metro areas for butcher/wine density
    "Evanston, Illinois",
    "Oak Park, Illinois",
    "Naperville, Illinois",
    "Westchester, New York",
    "White Plains, New York",
    "Long Island, New York",
    "Stamford, Connecticut",
    "Greenwich, Connecticut",
    "New Haven, Connecticut",
    "Hartford, Connecticut",
    "Montclair, New Jersey",
    "Princeton, New Jersey",
    "Morristown, New Jersey",
    "Bethesda, Maryland",
    "Annapolis, Maryland",
    "Arlington, Virginia",
    "Falls Church, Virginia",
    "Fairfax, Virginia",
    "Charlottesville, Virginia",
    "Decatur, Georgia",
    "Marietta, Georgia",
    "Alpharetta, Georgia",
    "Plano, Texas",
    "Frisco, Texas",
    "The Woodlands, Texas",
    "Boulder, Colorado",
    "Fort Collins, Colorado",
    "Bellevue, Washington",
    "Kirkland, Washington",
    "Tacoma, Washington",
    "Lake Oswego, Oregon",
    "Eugene, Oregon",
    "Mill Valley, California",
    "Walnut Creek, California",
    "Palo Alto, California",
    "San Jose, California",
    "Irvine, California",
    "Newport Beach, California",
    "La Jolla, California",
    "Santa Barbara, California",
    "Carmel, California",
    "Healdsburg, California",
    "St. Helena, California",
    "Edina, Minnesota",
    "Wayzata, Minnesota",
    "St. Paul, Minnesota",
    "Brookline, Massachusetts",
    "Wellesley, Massachusetts",
    "Newton, Massachusetts",
    "Northampton, Massachusetts",
    "Boca Raton, Florida",
    "Naples, Florida",
    "Sarasota, Florida",
    "West Palm Beach, Florida",
    "Jacksonville, Florida",
    "Coral Gables, Florida",
    "Delray Beach, Florida",
    "Traverse City, Michigan",
    "Birmingham, Michigan",
    "Royal Oak, Michigan",
    "Reno, Nevada",
    "Las Vegas, Nevada",
    "Spokane, Washington",
    "Bozeman, Montana",
    "Missoula, Montana",
    "Jackson, Wyoming",
    "Park City, Utah",
    "Savannah, Georgia",
    "Ashland, Oregon",
    "Sedona, Arizona",
    "Tempe, Arizona",
    "Little Rock, Arkansas",
    "Fayetteville, Arkansas",
    "Oklahoma City, Oklahoma",
    "Tulsa, Oklahoma",
    "Wichita, Kansas",
    "Overland Park, Kansas",
    "Sioux Falls, South Dakota",
    "Fargo, North Dakota",
    "Columbia, South Carolina",
    "Hilton Head, South Carolina",
    "Norfolk, Virginia",
    "Virginia Beach, Virginia",
    "Wilmington, Delaware",
    "Lancaster, Pennsylvania",
    "Media, Pennsylvania",
    "Wayne, Pennsylvania",
    "Doylestown, Pennsylvania",
    "Woodstock, New York",
    "Hudson, New York",
    "Rhinebeck, New York",
    "Sag Harbor, New York",
    "East Hampton, New York",
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
    # Butcher/meat chains
    "omaha steaks", "honey baked ham", "the honey baked",
    "arby's", "boston market",
    # Wine chains
    "wine.com", "vivino", "drizly",
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
    "tastingtable.com", "seriouseats.com",
    # Wine-specific press
    "wineenthusiast.com", "winemag.com", "vinepair.com",
    "wine-searcher.com", "decanter.com",
    # Meat/butcher-specific press
    "meatpoultry.com", "meatingplace.com",
]

# Reservation platform priority (higher = harder to get into)
RESERVATION_PLATFORMS = {
    "exploretock.com": 3,   # Tock — typically hardest
    "resy.com": 2,          # Resy
    "opentable.com": 1,     # OpenTable
}
