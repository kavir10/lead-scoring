"""Shared helpers for food-job-board scrapers."""
from __future__ import annotations

import os
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from awards._lib import (
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
    playwright_session,
    to_dataframe,
)


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

WINE_ROLE_QUERIES = [
    '"wine director"',
    '"sommelier"',
    '"beverage director"',
    '"head sommelier"',
    '"wine buyer"',
    '"beverage program manager"',
]

DEFAULT_METROS = [
    "New York, NY", "Brooklyn, NY", "Los Angeles, CA", "San Francisco, CA",
    "Chicago, IL", "Austin, TX", "Houston, TX", "Dallas, TX", "Miami, FL",
    "Boston, MA", "Washington, DC", "Seattle, WA", "Portland, OR",
    "Philadelphia, PA", "Atlanta, GA", "Nashville, TN", "Charleston, SC",
    "New Orleans, LA", "Denver, CO", "Minneapolis, MN", "Detroit, MI",
    "Las Vegas, NV", "San Diego, CA", "Phoenix, AZ", "Pittsburgh, PA",
]


def serper_web(query: str, *, num: int = 20) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num, "gl": "us", "hl": "en"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("organic", []) or []
    except Exception as e:
        print(f"  [jobs] serper error: {e}", flush=True)
        return []


def fetch_listing_html(url: str, *, prefer_playwright: bool = False) -> str:
    if not prefer_playwright:
        html = fetch_html(url)
        if html and "<body" in html.lower():
            return html
    try:
        with playwright_session() as (page, _ctx, _br):
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            return page.content() or ""
    except Exception as e:
        print(f"  [jobs] playwright failed for {url}: {e}", flush=True)
        return ""


_CITY_STATE_RE = re.compile(r"([A-Z][a-zA-Z\s.'\-]+?),\s*([A-Z]{2})\b")


def split_city_state(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = _CITY_STATE_RE.search(text)
    if m:
        return m.group(1).strip(), normalize_state(m.group(2))
    return text.strip(), ""


def make_job_row(
    *,
    source: str,
    employer: str,
    role: str,
    posted_at: str = "",
    city: str = "",
    state: str = "",
    listing_url: str = "",
    tier: int = 1,
) -> dict:
    distinction = f"Hiring: {role}" + (f" ({posted_at})" if posted_at else "")
    blurb = f"role={role}; posted_at={posted_at}; listing_url={listing_url}"
    return make_row(
        source=source,
        tier=tier,
        business_type="restaurant",
        name=employer,
        city=city,
        state=state,
        country="us",
        distinction=distinction,
        source_url=listing_url,
        blurb=blurb,
    )


__all__ = [
    "SCHEMA", "WINE_ROLE_QUERIES", "DEFAULT_METROS",
    "serper_web", "fetch_listing_html", "split_city_state",
    "make_job_row", "to_dataframe", "BeautifulSoup",
]
