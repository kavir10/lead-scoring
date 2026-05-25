"""Ryan Sutton — The Lo Times (NYC pro restaurant critic)."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="lo_times",
        publication_name="Ryan Sutton (The Lo Times)",
        archive_url="https://www.thelotimes.com/archive",
        max_posts=50,
    )
