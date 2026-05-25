"""Hanna Raskin — The Food Section (Southern US food media + regional restaurants)."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="food_section",
        publication_name="Hanna Raskin (The Food Section)",
        archive_url="https://thefoodsection.substack.com/archive",
        max_posts=40,
    )
