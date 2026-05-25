"""Vittles — Jonathan Nunn et al. UK-led, growing US coverage."""
from __future__ import annotations

import pandas as pd

from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="vittles",
        publication_name="Vittles",
        archive_url="https://vittles.substack.com/archive",
        max_posts=60,
    )
