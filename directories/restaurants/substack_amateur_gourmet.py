"""Adam Roberts — The Amateur Gourmet (NYC restaurant recommendations + top-10 lists)."""
from __future__ import annotations
import pandas as pd
from directories.restaurants._substack import scrape_publication


def scrape(**_kwargs) -> pd.DataFrame:
    return scrape_publication(
        publication_slug="amateur_gourmet",
        publication_name="Adam Roberts (Amateur Gourmet)",
        archive_url="https://amateurgourmet.substack.com/archive",
        max_posts=50,
    )
