"""Eater NY Substack — NYC food coverage."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="eater_ny",
        publication_name="Eater NY (Substack)",
        archive_url="https://eaterny.substack.com/archive",
        max_posts=50,
    )
