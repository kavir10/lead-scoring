"""Mike Nagrant — The Hunger (Chicago food critic, former Sun-Times)."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="the_hunger",
        publication_name="Mike Nagrant (The Hunger)",
        archive_url="https://thehunger.substack.com/archive",
        max_posts=40,
    )
