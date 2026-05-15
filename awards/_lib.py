"""
Awards-specific helpers — thin layer over `core/` for back-compat.

Historical location of the canonical schema, dedupe, filter, playwright_session,
fetch_html. Those now live in `core/` and are imported here so existing
`from awards._lib import …` call sites keep working without churn.

Awards-specific bits stay here:
  OUTPUT_DIR              path to `output/awards/`
  save_source             writes per-source CSV into OUTPUT_DIR
  latest_for_slug         scans OUTPUT_DIR
  load_latest             loads OUTPUT_DIR/<slug>_latest.csv
  build_master            unions per-source CSVs into output/awards_all_<date>.csv
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from core import ROOT
from core.csv_io import save_source as _save_source, latest_for_slug as _latest_for_slug
from core.geo import (
    STATE_NAME_TO_CODE,
    US_STATES,
    filter_us,
    is_us_country,
    normalize_state,
    parse_city_state,
)
from core.http_fetch import (
    UA,
    fetch_readable,
    httpx_get,
    playwright_session,
    readable_text_bs4,
    readable_text_selectolax,
    requests_get_html,
)
from core.schema import AWARDS_SCHEMA as SCHEMA, make_row, to_dataframe
from core.dedupe import dedupe_by_name_city as dedupe


__all__ = [
    "SCHEMA",
    "ROOT",
    "OUTPUT_DIR",
    "UA",
    "US_STATES",
    "STATE_NAME_TO_CODE",
    "normalize_state",
    "is_us_country",
    "parse_city_state",
    "make_row",
    "filter_us",
    "dedupe",
    "to_dataframe",
    "save_source",
    "latest_for_slug",
    "load_latest",
    "playwright_session",
    "load_cookies_from_file",
    "fetch_html",
    "build_master",
]

OUTPUT_DIR = ROOT / "output" / "awards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_source(df: pd.DataFrame, slug: str, *, stamp: str | None = None) -> Path:
    """Write per-source CSV to output/awards/<slug>_<YYYYMMDD>.csv."""
    return _save_source(df, slug, OUTPUT_DIR, stamp=stamp)


def latest_for_slug(slug: str) -> Path | None:
    return _latest_for_slug(slug, OUTPUT_DIR)


def load_latest(slug: str) -> pd.DataFrame:
    p = latest_for_slug(slug)
    if not p:
        return pd.DataFrame(columns=SCHEMA)
    return pd.read_csv(p, dtype=str).fillna("")


def load_cookies_from_file(path: str) -> list[dict]:
    """Accepts either Playwright JSON cookie export or a list of {name,value,domain}."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "cookies" in data:
        return data["cookies"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized cookie file shape at {path}")


def fetch_html(url: str, *, timeout: int = 30, retries: int = 3, sleep: float = 1.5) -> str:
    """GET with UA + retries. Returns text or '' if exhausted.
    Compat alias for `core.http_fetch.requests_get_html`."""
    return requests_get_html(url, timeout=timeout, retries=retries, sleep=sleep)


def build_master(*, stamp: str | None = None) -> Path:
    """Union every per-source CSV from today (or latest if today missing) into
    `output/awards_all_<YYYYMMDD>.csv`."""
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    from awards import ALL_SOURCES
    frames: list[pd.DataFrame] = []
    for slug, *_ in ALL_SOURCES:
        path = OUTPUT_DIR / f"{slug}_{stamp}.csv"
        if not path.exists():
            path = latest_for_slug(slug)
        if not path or not path.exists():
            continue
        df = pd.read_csv(path, dtype=str).fillna("")
        if df.empty:
            continue
        frames.append(df)
    master_path = ROOT / "output" / f"awards_all_{stamp}.csv"
    if not frames:
        pd.DataFrame(columns=SCHEMA).to_csv(master_path, index=False)
        print(f"\n  No source CSVs found — wrote empty master at {master_path.relative_to(ROOT)}")
        return master_path
    master = pd.concat(frames, ignore_index=True)
    # Cross-source dedupe: keep one row per (name, city, source) so multiple awards
    # from different sources are preserved as distinct rows.
    master["name_n"] = master["name"].str.lower().str.strip()
    master["city_n"] = master["city"].str.lower().str.strip()
    master = master.drop_duplicates(["source", "name_n", "city_n"], keep="first")
    master = master.drop(columns=["name_n", "city_n"]).reset_index(drop=True)
    master.to_csv(master_path, index=False)
    print(f"\n  Master: {len(master)} rows across {master['source'].nunique()} sources -> {master_path.relative_to(ROOT)}")
    print("\n  Rows per source:")
    for src, n in master["source"].value_counts().items():
        print(f"    {src:<32} {n}")
    return master_path
