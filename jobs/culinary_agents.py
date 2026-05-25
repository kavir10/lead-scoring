"""
Culinary Agents — culinaryagents.com.

Listing pages render server-side; httpx + selectolax sufficient. The site has
faceted filters for role + city. We query for the wine roles across the
30-metro panel.
"""
from __future__ import annotations

import re
import time
from urllib.parse import quote_plus, urljoin

import pandas as pd

from jobs._lib import (
    BeautifulSoup,
    DEFAULT_METROS,
    fetch_listing_html,
    make_job_row,
    split_city_state,
    to_dataframe,
)


BASE = "https://culinaryagents.com"

ROLE_KEYWORDS = [
    "wine-director", "sommelier", "beverage-director", "wine-buyer",
    "head-sommelier", "beverage-manager",
]


def _build_search_url(role: str, metro: str) -> str:
    return f"{BASE}/jobs/search?keywords={quote_plus(role)}&location={quote_plus(metro)}"


def _parse_listings(html: str, listing_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for card in soup.select("article.job-card, li.job-listing, div.job-card, div.search-result"):
        title_el = card.find(["h2", "h3", "a"])
        role = title_el.get_text(strip=True) if title_el else ""
        employer_el = card.find(class_=re.compile(r"(employer|business|company)", re.I))
        employer = employer_el.get_text(strip=True) if employer_el else ""
        loc_el = card.find(class_=re.compile(r"(location|city)", re.I))
        loc = loc_el.get_text(strip=True) if loc_el else ""
        date_el = card.find(class_=re.compile(r"(date|posted)", re.I))
        posted_at = date_el.get_text(strip=True) if date_el else ""
        href = title_el.get("href") if title_el and title_el.name == "a" else ""
        full_link = urljoin(BASE, href) if href else listing_url
        if not employer or not role:
            continue
        city, state = split_city_state(loc)
        out.append({
            "employer": employer, "role": role, "posted_at": posted_at,
            "city": city, "state": state, "listing_url": full_link,
        })
    return out


def scrape(**_kwargs) -> pd.DataFrame:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for role in ROLE_KEYWORDS:
        for metro in DEFAULT_METROS:
            url = _build_search_url(role, metro)
            print(f"  [job_culinary_agents] {role} @ {metro}", flush=True)
            html = fetch_listing_html(url)
            if not html:
                continue
            for parsed in _parse_listings(html, url):
                key = (parsed["employer"].lower(), parsed["city"].lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append(make_job_row(source="job_culinary_agents", **parsed))
            time.sleep(0.7)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
