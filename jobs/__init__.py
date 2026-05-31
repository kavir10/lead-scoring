"""
Food-industry job-board scraping for the wine-director / sommelier /
beverage-director / GM intent signal.

Strategy: docs/strategies/02_food_job_boards.md

Each module exposes `scrape(**kwargs) -> pd.DataFrame` returning canonical
schema rows where:
  source       = "job_<board>"
  tier         = 1
  business_type= "restaurant"
  distinction  = "Hiring: <role> ({posted_at_date})"
  blurb        = "role={...}; posted_at={...}; listing_url={...}"
"""
from __future__ import annotations

# (slug, tier, module_path, business_type)
ALL_SOURCES: list[tuple[str, int, str, str]] = [
    ("job_culinary_agents",  1, "jobs.culinary_agents",   "restaurant"),
    ("job_poached",          1, "jobs.poached",           "restaurant"),
    ("job_indeed_serper",    1, "jobs.indeed_serper",     "restaurant"),
    ("job_sevenrooms_hire",  1, "jobs.sevenrooms_hire",   "restaurant"),
    ("job_restaurant_zone",  1, "jobs.restaurant_zone",   "restaurant"),
]


def by_slug(slug: str):
    for row in ALL_SOURCES:
        if row[0] == slug:
            return row
    return None
