"""
Shared infrastructure for award scrapers.

Every per-source module in `awards.<category>.<source>` should:
  - import `SCHEMA`, `normalize_state`, `is_us_country`, `make_row`, `save_source`
  - return a `pandas.DataFrame` from `scrape()` matching SCHEMA
  - use `playwright_session()` for any Playwright work (handles WAF, UA, retries)
  - use `fetch_html()` for plain HTTP

Idempotency: every per-source CSV is rewritten on each run (date-stamped path).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

# Canonical schema. Order matters — used when writing CSVs.
SCHEMA: list[str] = [
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

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "awards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

US_STATES = {
    # 2-letter to full
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "new york state": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "washington state": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "washington dc": "DC", "washington d.c.": "DC",
}


def normalize_state(value: str | None) -> str:
    """Return 2-letter US state code if recognizable, else original trimmed string."""
    if not value:
        return ""
    v = str(value).strip()
    if not v:
        return ""
    upper = v.upper()
    if upper in US_STATES:
        return upper
    code = STATE_NAME_TO_CODE.get(v.lower().strip())
    return code or v


def is_us_country(value: str | None) -> bool:
    if not value:
        return False
    v = str(value).strip().lower()
    return v in {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}


def parse_city_state(text: str) -> tuple[str, str]:
    """'Brooklyn, NY' / 'New York, New York' -> ('Brooklyn', 'NY')."""
    if not text:
        return ("", "")
    m = re.match(r"\s*([^,]+?)\s*,\s*([^,]+?)\s*$", text)
    if not m:
        return (text.strip(), "")
    city = m.group(1).strip()
    state = normalize_state(m.group(2).strip())
    return (city, state)


def make_row(
    *,
    source: str,
    tier: int,
    business_type: str,
    name: str,
    city: str = "",
    state: str = "",
    country: str = "us",
    distinction: str = "",
    year: int | str | None = None,
    source_url: str = "",
    blurb: str = "",
) -> dict[str, Any]:
    return {
        "source": source,
        "tier": int(tier),
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


def filter_us(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["country"].fillna("").str.lower().isin(["us", "usa", "united states"])].copy()


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Within a single source's output: keep the first occurrence per (name, city)
    case-insensitive. Across sources we keep duplicates intentionally — multiple
    awards reinforce the lead score.
    """
    if df.empty:
        return df
    key = (df["name"].fillna("").str.lower().str.strip()
           + "||"
           + df["city"].fillna("").str.lower().str.strip())
    df = df.assign(_dedupe_key=key)
    df = df.drop_duplicates("_dedupe_key", keep="first")
    return df.drop(columns="_dedupe_key").reset_index(drop=True)


def to_dataframe(rows: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        return pd.DataFrame(columns=SCHEMA)
    for col in SCHEMA:
        if col not in df.columns:
            df[col] = ""
    return df[SCHEMA]


def save_source(df: pd.DataFrame, slug: str, *, stamp: str | None = None) -> Path:
    """Write per-source CSV with date stamp. Always overwrites today's file."""
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"{slug}_{stamp}.csv"
    df = to_dataframe(df.to_dict("records") if not df.empty else [])
    df = filter_us(df)
    df = dedupe(df)
    df.to_csv(path, index=False)
    print(f"  Saved {len(df):>5} rows -> {path.relative_to(ROOT)}", flush=True)
    return path


def latest_for_slug(slug: str) -> Path | None:
    # Use regex match on the date suffix so e.g. slug="michelin" doesn't
    # accidentally pick up `michelin_grape_*.csv` (sibling slug).
    pat = re.compile(rf"^{re.escape(slug)}_\d{{8}}\.csv$")
    files = sorted(p for p in OUTPUT_DIR.glob(f"{slug}_*.csv") if pat.match(p.name))
    return files[-1] if files else None


def load_latest(slug: str) -> pd.DataFrame:
    p = latest_for_slug(slug)
    if not p:
        return pd.DataFrame(columns=SCHEMA)
    return pd.read_csv(p, dtype=str).fillna("")


# -- Playwright session ------------------------------------------------------

@contextmanager
def playwright_session(*, headed: bool = False, cookies: list[dict] | None = None):
    """
    Yields (page, context, browser). Handles WAF JS challenges (Michelin pattern).
    Cookies (Playwright format) optional for paywalled sources.
    """
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not headed)
    context = browser.new_context(
        user_agent=UA, locale="en-US", viewport={"width": 1280, "height": 900}
    )
    if cookies:
        context.add_cookies(cookies)
    page = context.new_page()
    try:
        yield page, context, browser
    finally:
        try:
            browser.close()
        finally:
            pw.stop()


def load_cookies_from_file(path: str) -> list[dict]:
    """Accepts either Playwright JSON cookie export or a list of {name,value,domain}."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and "cookies" in data:
        return data["cookies"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized cookie file shape at {path}")


# -- HTTP fetch --------------------------------------------------------------

def fetch_html(url: str, *, timeout: int = 30, retries: int = 3, sleep: float = 1.5) -> str:
    """GET with browser TLS impersonation (curl_cffi/chrome120) + retries.

    Falls back to plain requests if curl_cffi raises. WAF-protected sites
    (Cloudflare/Akamai) typically need the impersonation; plain origins
    don't care either way. Returns text or '' if exhausted.
    """
    try:
        from curl_cffi import requests as _cffi  # local import: optional dep
    except ImportError:
        _cffi = None

    last_exc: Exception | None = None
    for attempt in range(retries):
        # Path 1: curl_cffi with chrome120 impersonation
        if _cffi is not None:
            try:
                r = _cffi.get(
                    url,
                    impersonate="chrome120",
                    timeout=timeout,
                    allow_redirects=True,
                )
                if r.status_code == 200:
                    return r.text
                if r.status_code in (403, 429, 503):
                    time.sleep(sleep * (attempt + 1))
                    continue
                # 404 with substantive body is often a WAF / SPA — keep it.
                if r.status_code == 404 and len(r.text or "") > 1500:
                    return r.text
                print(f"  [http {r.status_code}] {url}", flush=True)
                return ""
            except Exception as e:
                last_exc = e
        # Path 2: plain requests fallback
        try:
            r = requests.get(
                url,
                headers={"User-Agent": UA, "Accept-Language": "en-US,en"},
                timeout=timeout,
                allow_redirects=True,
            )
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429, 503):
                time.sleep(sleep * (attempt + 1))
                continue
            print(f"  [http {r.status_code}] {url}", flush=True)
            return ""
        except requests.RequestException as e:
            last_exc = e
            time.sleep(sleep * (attempt + 1))
    if last_exc:
        print(f"  [http error] {url}: {last_exc}", flush=True)
    return ""


# -- Master union ------------------------------------------------------------

def build_master(*, stamp: str | None = None) -> Path:
    """Union every per-source CSV from today (or latest if today missing) into a
    single master file at output/awards_all_<YYYYMMDD>.csv."""
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
