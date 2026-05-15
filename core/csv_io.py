"""
CSV write helpers.

`save_source` is the generic version of what awards/_lib.py historically
implemented inline. Each per-source CSV gets a YYYYMMDD date stamp; today's
file is overwritten on re-run.

Filtering (US-only) and dedupe (by name+city) are applied by default so
every pipeline writes the same kind of cleaned per-source CSV. Pipelines
that want raw output can pass `filter=False, dedupe=False`.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from . import ROOT
from .geo import filter_banned_states as _filter_banned_states, filter_us as _filter_us
from .schema import AWARDS_SCHEMA, to_dataframe


def save_source(
    df: pd.DataFrame,
    slug: str,
    out_dir: Path | str,
    *,
    stamp: str | None = None,
    schema: list[str] | None = None,
    filter_us: bool = True,
    filter_banned: bool = True,
    dedupe_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    verbose: bool = True,
) -> Path:
    """Write per-source CSV to `<out_dir>/<slug>_<YYYYMMDD>.csv`.

    Default behavior: coerce to schema, drop non-US rows, drop rows whose
    state is in BANNED_STATES, dedupe by name+city. Pass `filter_banned=False`
    to keep banned-state rows (rare — research only). Pass `dedupe_fn=None`
    to skip dedupe.
    """
    if dedupe_fn is None:
        # Late import to avoid cycle
        from .dedupe import dedupe_by_name_city
        dedupe_fn = dedupe_by_name_city

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    path = out_dir / f"{slug}_{stamp}.csv"

    df = to_dataframe(df.to_dict("records") if not df.empty else [], schema=schema or AWARDS_SCHEMA)
    if filter_us:
        df = _filter_us(df)
    if filter_banned:
        df = _filter_banned_states(df)
    df = dedupe_fn(df)
    df.to_csv(path, index=False)
    if verbose:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        print(f"  Saved {len(df):>5} rows -> {rel}", flush=True)
    return path


def latest_for_slug(slug: str, out_dir: Path | str) -> Path | None:
    """Return the most-recent `<slug>_*.csv` in out_dir, or None."""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return None
    files = sorted(out_dir.glob(f"{slug}_*.csv"))
    return files[-1] if files else None


def load_latest(slug: str, out_dir: Path | str, schema: list[str] | None = None) -> pd.DataFrame:
    """Load the most-recent CSV for `slug`, or an empty DataFrame with `schema`."""
    p = latest_for_slug(slug, out_dir)
    if not p:
        return pd.DataFrame(columns=schema or AWARDS_SCHEMA)
    return pd.read_csv(p, dtype=str).fillna("")
