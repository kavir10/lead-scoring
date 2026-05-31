"""Christopher J. Yates — Pen & Palate (Hudson Valley + NYC restaurant reviews)."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="pen_and_palate",
        publication_name="Pen & Palate (Christopher J. Yates)",
        archive_url="https://christopherjyates.substack.com/archive",
        max_posts=40,
    )
