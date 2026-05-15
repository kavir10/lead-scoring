"""
Canonical row schemas used across pipelines.

CANONICAL_LEAD_COLUMNS is the smallest set every pipeline (Serper, awards,
directories, best_wine_shops, butcher, beli) is expected to populate. Richer
pipelines (awards, Serper post-enrichment) add columns on top.

AWARDS_SCHEMA matches what `awards/_lib.py` historically wrote. Re-exported
here so awards modules can import either.
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from .geo import normalize_state


# Awards/editorial discovery schema. Order matters — used when writing CSVs.
AWARDS_SCHEMA: list[str] = [
    "source",
    "tier",
    "business_type",
    "name",
    "city",
    "state",
    "country",
    "distinction",
    "year",
    "source_url",
    "blurb",
]

# Smallest set every pipeline writes. Richer pipelines extend.
CANONICAL_LEAD_COLUMNS: list[str] = [
    "name",
    "address",
    "city",
    "state",
    "country",
    "phone",
    "website",
    "business_type",
    "source",
    "source_url",
]


def make_row(
    *,
    source: str,
    tier: int = 0,
    business_type: str = "",
    name: str = "",
    city: str = "",
    state: str = "",
    country: str = "us",
    distinction: str = "",
    year: int | str | None = None,
    source_url: str = "",
    blurb: str = "",
) -> dict[str, Any]:
    """Build a row matching AWARDS_SCHEMA with normalized state + trimmed fields."""
    return {
        "source": source,
        "tier": int(tier) if tier else 0,
        "business_type": business_type,
        "name": (name or "").strip(),
        "city": (city or "").strip(),
        "state": normalize_state(state),
        "country": (country or "").strip().lower() or "us",
        "distinction": (distinction or "").strip(),
        "year": "" if year is None else str(year),
        "source_url": (source_url or "").strip(),
        "blurb": (blurb or "").strip(),
    }


def to_dataframe(
    rows: Iterable[dict],
    schema: list[str] | None = None,
) -> pd.DataFrame:
    """Coerce an iterable of dicts to a DataFrame matching `schema`.

    Empty input -> an empty DataFrame with schema columns. Missing columns
    are filled with empty strings. Extra columns in rows are dropped.
    Defaults to AWARDS_SCHEMA when not provided.
    """
    cols = schema or AWARDS_SCHEMA
    df = pd.DataFrame(list(rows))
    if df.empty:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols]
