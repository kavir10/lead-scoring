"""The Relisher — chefs share their hometown restaurant recommendations."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="relisher",
        publication_name="The Relisher",
        archive_url="https://therelisher.substack.com/archive",
        max_posts=40,
    )
