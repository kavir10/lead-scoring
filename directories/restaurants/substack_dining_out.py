"""Lauren O'Neill — Dining Out."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="dining_out",
        publication_name="Lauren O'Neill (Dining Out)",
        archive_url="https://diningout.substack.com/archive",
        max_posts=40,
    )
