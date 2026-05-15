"""
Cheesemonger Invitational (CMI) — winners archive.

Note: CMI awards individuals, not shops. We extract the monger AND the shop
they work at when the article mentions it; the lead is the SHOP.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("cheesemonger invitational winner cheese shop",
     "Cheesemonger Invitational winners — for each winner extract their cheese shop/employer (the 'name' is the SHOP, person in blurb). distinction = 'CMI <Place> <Year>'."),
    ("cheesemonger invitational finalist cheese shop",
     "CMI finalists. distinction = 'CMI Finalist <Year>'."),
    ("cheesemonger invitational champion winner",
     "CMI champion / runner-up. distinction = 'CMI Champion <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="cheesemonger_invitational",
        tier=1,
        business_type="cheesemonger",
        search_queries=SEARCH_QUERIES,
        search_domains=["cheesemongerinvitational.com", "culturecheesemag.com",
                        "eater.com", "seriouseats.com"],
        distinction_default="Cheesemonger Invitational",
    )
