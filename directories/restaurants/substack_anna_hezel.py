"""Anna Hezel — food writer, Substack newsletter."""
from __future__ import annotations

import pandas as pd

from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="anna_hezel",
        publication_name="Anna Hezel",
        # Anna Hezel's newsletter has moved between domains; verify in v2.
        archive_url="https://annahezel.substack.com/archive",
        max_posts=30,
    )
