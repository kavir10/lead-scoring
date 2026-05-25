"""Adam Reiner — The Restaurant Manifesto."""
from __future__ import annotations

import pandas as pd

from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="adam_reiner",
        publication_name="Adam Reiner (The Restaurant Manifesto)",
        archive_url="https://restaurantmanifesto.substack.com/archive",
        max_posts=40,
    )
