"""
Coupe du Monde de la Boulangerie — Bread World Cup. US team competitors and
their home bakeries. Tiny cohort but extremely high prestige.

Source: Wikipedia historical results + Bread Bakers Guild of America announcements.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("coupe du monde de la boulangerie team usa members",
     "Coupe du Monde de la Boulangerie US team members and their home bakeries (where they work). The 'name' should be the BAKERY, person in blurb. distinction = 'Coupe du Monde Team USA <Year>'."),
    ("bread bakers guild of america coupe du monde team",
     "BBGA Coupe du Monde US team — extract bakers and bakeries. distinction = 'Coupe du Monde Team USA <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="coupe_du_monde",
        tier=2,
        business_type="bakery",
        search_queries=SEARCH_QUERIES,
        search_domains=["bbga.org", "wikipedia.org", "kingarthurbaking.com",
                        "modernistcuisine.com", "bakemag.com"],
        distinction_default="Coupe du Monde Team USA",
    )
