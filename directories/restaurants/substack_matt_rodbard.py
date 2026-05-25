"""Matt Rodbard — TASTE editor's Substack with NYT-critic news + restaurant reviews."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="matt_rodbard",
        publication_name="Matt Rodbard (TASTE)",
        archive_url="https://mattrodbard.substack.com/archive",
        max_posts=40,
    )
