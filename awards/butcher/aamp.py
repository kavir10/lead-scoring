"""
American Association of Meat Processors — Cured Meats Championships +
Outstanding Specialty Meat Retailer.
"""
from __future__ import annotations

import pandas as pd

from awards._editorial import scrape_articles

SEARCH_QUERIES: list[tuple[str, str]] = [
    ("aamp cured meats championship grand champion winners",
     "AAMP Cured Meats Championship — Grand Champion / Reserve Grand Champion / Best of Show. distinction = 'AAMP <Award> <Year>'."),
    ("american association of meat processors outstanding retailer of the year",
     "AAMP Outstanding Specialty Meat Retailer of the Year. distinction = 'AAMP Outstanding Specialty Meat Retailer <Year>'."),
    ("aamp american cured meat championship results",
     "AAMP cured-meat championship results page. distinction = 'AAMP Award <Year>'."),
]


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_articles(
        source_slug="aamp",
        tier=1,
        business_type="butcher",
        search_queries=SEARCH_QUERIES,
        search_domains=["aamp.com", "meatpoultry.com", "provisioneronline.com"],
        distinction_default="AAMP Award",
    )
