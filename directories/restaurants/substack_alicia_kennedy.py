"""Alicia Kennedy — From the Desk of Alicia Kennedy."""
from __future__ import annotations

import pandas as pd

from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="alicia_kennedy",
        publication_name="Alicia Kennedy",
        archive_url="https://www.aliciakennedy.news/archive",
        max_posts=40,
    )
