"""
Award discovery package — one module per source under <category>/.

Every module exposes:

    def scrape(**kwargs) -> pandas.DataFrame

returning rows in the canonical schema defined in `_lib.SCHEMA`.

The orchestrator (`discover_awards.py`) iterates `ALL_SOURCES`, calls each
`scrape()`, writes per-source CSVs, then unions them into the master file.

Adding a source: drop a module in the right category dir, then register it
here. Slug must match the filename (without .py).
"""

from __future__ import annotations

# (slug, category, tier, module_path, business_type, requires_auth)
# Tier and business_type are defaults — modules may override per-row.
ALL_SOURCES: list[tuple[str, str, int, str, str, bool]] = [
    # Restaurants
    ("michelin",                 "restaurants", 1, "awards.restaurants.michelin",                  "restaurant", False),
    ("james_beard",              "restaurants", 1, "awards.restaurants.james_beard",               "restaurant", False),
    ("worlds_50_best",           "restaurants", 1, "awards.restaurants.worlds_50_best",            "restaurant", False),
    ("resy_100",                 "restaurants", 1, "awards.restaurants.resy_100",                  "restaurant", False),
    ("eater",                    "restaurants", 1, "awards.restaurants.eater",                     "restaurant", False),
    ("bon_appetit",              "restaurants", 1, "awards.restaurants.bon_appetit",               "restaurant", False),
    ("nyt",                      "restaurants", 1, "awards.restaurants.nyt",                       "restaurant", True),
    ("esquire",                  "restaurants", 1, "awards.restaurants.esquire",                   "restaurant", False),
    ("food_and_wine_chefs",      "restaurants", 2, "awards.restaurants.food_and_wine_chefs",       "restaurant", False),
    ("wine_spectator_restaurants","restaurants", 3, "awards.restaurants.wine_spectator_restaurants","restaurant", False),

    # Wine
    ("wine_spectator_grand",     "wine", 1, "awards.wine.wine_spectator_grand",         "wine_store", False),
    ("wine_enthusiast_star",     "wine", 1, "awards.wine.wine_enthusiast_star",         "wine_store", False),
    ("wine_enthusiast_shops",    "wine", 1, "awards.wine.wine_enthusiast_shops",        "wine_store", False),
    ("michelin_grape",           "wine", 1, "awards.wine.michelin_grape",               "wine_store", False),
    ("vinepair_50",              "wine", 1, "awards.wine.vinepair_50",                  "wine_store", False),
    ("punch",                    "wine", 1, "awards.wine.punch",                        "wine_store", False),
    ("world_of_fine_wine",       "wine", 2, "awards.wine.world_of_fine_wine",           "wine_store", False),
    ("sommeliers_choice",        "wine", 2, "awards.wine.sommeliers_choice",            "wine_store", False),
    ("food_and_wine_visionaries","wine", 2, "awards.wine.food_and_wine_visionaries",    "wine_store", False),
    ("decanter",                 "wine", 3, "awards.wine.decanter",                     "wine_store", True),

    # Bakery
    ("jbf_bakery",               "bakery", 1, "awards.bakery.jbf_bakery",               "bakery", False),
    ("bon_appetit_bakery",       "bakery", 1, "awards.bakery.bon_appetit_bakery",       "bakery", False),
    ("eater_bakery",             "bakery", 1, "awards.bakery.eater_bakery",             "bakery", False),
    ("food_and_wine_bakery",     "bakery", 1, "awards.bakery.food_and_wine_bakery",     "bakery", False),
    ("coupe_du_monde",           "bakery", 2, "awards.bakery.coupe_du_monde",           "bakery", False),
    ("ibie_world_bread",         "bakery", 2, "awards.bakery.ibie_world_bread",         "bakery", False),
    ("panettone_world_cup",      "bakery", 2, "awards.bakery.panettone_world_cup",      "bakery", False),

    # Cheese
    ("cheesemonger_invitational","cheese", 1, "awards.cheese.cheesemonger_invitational","cheesemonger", False),
    ("mondial_du_fromage",       "cheese", 1, "awards.cheese.mondial_du_fromage",       "cheesemonger", False),
    ("culture_magazine",         "cheese", 1, "awards.cheese.culture_magazine",         "cheesemonger", False),
    ("eater_cheese",             "cheese", 1, "awards.cheese.eater_cheese",             "cheesemonger", False),
    ("food_and_wine_cheese",     "cheese", 1, "awards.cheese.food_and_wine_cheese",     "cheesemonger", False),
    ("american_cmi",             "cheese", 2, "awards.cheese.american_cmi",             "cheesemonger", False),
    ("academy_of_cheese",        "cheese", 2, "awards.cheese.academy_of_cheese",        "cheesemonger", False),

    # Butcher
    ("aamp",                     "butcher", 1, "awards.butcher.aamp",                   "butcher", False),
    ("good_food_charcuterie",    "butcher", 1, "awards.butcher.good_food_charcuterie",  "butcher", False),
    ("sofi_charcuterie",         "butcher", 2, "awards.butcher.sofi_charcuterie",       "butcher", False),
    ("fabi_butcher",             "butcher", 2, "awards.butcher.fabi_butcher",           "butcher", False),

    # Specialty
    ("sofi_general",             "specialty", 1, "awards.specialty.sofi_general",       "specialty", False),
    ("good_food_general",        "specialty", 1, "awards.specialty.good_food_general",  "specialty", False),
    ("fabi_general",             "specialty", 2, "awards.specialty.fabi_general",       "specialty", False),
    ("sfa_leadership",           "specialty", 2, "awards.specialty.sfa_leadership",     "specialty", False),
    ("wine_enthusiast_retailer", "specialty", 2, "awards.specialty.wine_enthusiast_retailer","specialty", False),
]


def by_slug(slug: str):
    for row in ALL_SOURCES:
        if row[0] == slug:
            return row
    return None
