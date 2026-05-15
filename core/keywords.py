"""
Shared keyword lists used for chain/liquor filtering across pipelines.

Previously lived in `config.py`. `config.py` re-exports these to preserve
existing import sites (`from config import CHAIN_KEYWORDS`).

Add new pipeline-agnostic keyword constants here. Club-specific lists
(`CLUB_KEYWORDS`, `PLATFORM_SIGNALS`, `CLUB_URL_PATHS`,
`CLUB_TYPE_PATTERNS`) stay in `detect_clubs.py` because only club detection
uses them.
"""
from __future__ import annotations

# National / chain businesses we filter out of Maps + editorial results.
# Aggressive on purpose: includes non-food chains that surface in Maps.
CHAIN_KEYWORDS: list[str] = [
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
    # Bakery chains
    "nothing bundt cakes", "crumbl", "insomnia cookies", "great harvest",
    "corner bakery", "au bon pain", "paris baguette", "tous les jours",
    "porto's", "la boulange", "85 degrees", "85°c", "cinnabon",
    "auntie anne", "einstein bagel", "bruegger's", "noah's bagels",
    # Deli chains
    "jason's deli", "mcalister's", "schlotzsky", "potbelly",
    "quiznos", "which wich", "wawa", "sheetz",
    # Specialty grocer chains
    "fresh thyme", "earth fare", "natural grocers", "the fresh market",
    "fresh market", "central market", "bristol farms", "gelson's",
    "new seasons", "lazy acres",
    # Non-food chains that appear in maps results
    "michaels", "hobby lobby", "at home", "williams-sonoma", "williams sonoma",
    "jersey mike", "jimmy john", "subway", "firehouse subs",
    "panera", "chipotle", "five guys", "shake shack", "wingstop",
    "buffalo wild wings", "hooters", "tgi friday", "denny's", "ihop",
    "waffle house", "cracker barrel", "bob evans", "golden corral",
    "texas roadhouse", "longhorn steakhouse", "carrabba",
    "bonefish grill", "cheddar's", "steak 'n shake",
    "home depot", "lowe's", "bed bath", "pottery barn", "crate & barrel",
    "sur la table", "world market", "pier 1 imports", "restoration hardware",
    "bass pro", "cabela's", "academy sports", "dick's sporting",
    "petsmart", "petco", "tractor supply",
    # Grocery / big-box chains
    "99 ranch", "h mart", "grocery outlet", "food 4 less",
    "homegoods", "home goods", "marshalls", "tj maxx", "tjmaxx",
    "scheels", "rei ", "nordstrom", "macy's", "macys",
    "best buy", "staples", "office depot",
]


# Liquor-store keywords used to filter out non-wine retail.
LIQUOR_KEYWORDS: list[str] = [
    "liquor", "spirits", "beer & wine", "package store",
    "beer store", "beverage",
]
