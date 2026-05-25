"""
Eater newsletter — eater.com archive feed.

Eater publishes newsletter editions and feature articles that name specific
venues. We pull recent articles from the homepage archive feeds.
"""
from __future__ import annotations

import pandas as pd

from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="eater",
        publication_name="Eater (newsletter / archive)",
        archive_url="https://www.eater.com/archives",
        max_posts=40,
    )
