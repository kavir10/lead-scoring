"""
Indeed wine-program job listings, via Serper Web SERP scraping.

Indeed blocks direct scraping aggressively. Serper SERPs surface job-title +
employer in the snippet, which is enough to extract the employer name.

Per role-query: 30-metro panel × paginate 2 deep = 60 SERPs. Per SERP we
keep up to 20 organic results. Dedup by employer + city.
"""
from __future__ import annotations

import re
import time

import pandas as pd

from jobs._lib import (
    DEFAULT_METROS,
    WINE_ROLE_QUERIES,
    make_job_row,
    serper_web,
    split_city_state,
    to_dataframe,
)


def _extract_employer_from_snippet(title: str, snippet: str) -> str | None:
    """Indeed listing titles are 'Job Title - Employer - City, ST'.
    Snippets often repeat the employer in the first sentence."""
    if " - " in title:
        parts = [p.strip() for p in title.split(" - ")]
        # Typical: "Wine Director - Restaurant Name - New York, NY"
        if len(parts) >= 3:
            return parts[1]
        if len(parts) == 2:
            return parts[1]
    m = re.search(r"(?:at|by)\s+([A-Z][A-Za-z'&\s]+?)(?:\s+in\b|\s*[,.]|$)", snippet)
    if m:
        return m.group(1).strip()
    return None


def _parse_listing(result: dict) -> dict | None:
    link = result.get("link", "")
    if "indeed.com" not in link:
        return None
    title = (result.get("title", "") or "").strip()
    snippet = (result.get("snippet", "") or "").strip()
    employer = _extract_employer_from_snippet(title, snippet)
    if not employer or len(employer) < 3:
        return None
    city, state = split_city_state(title + " " + snippet)
    role = title.split(" - ")[0] if " - " in title else title
    return {
        "employer": employer,
        "role": role[:80],
        "city": city,
        "state": state,
        "listing_url": link,
    }


def scrape(**_kwargs) -> pd.DataFrame:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for role_q in WINE_ROLE_QUERIES:
        for metro in DEFAULT_METROS:
            q = f'site:indeed.com {role_q} "{metro}"'
            print(f"  [job_indeed] {q}", flush=True)
            results = serper_web(q, num=15)
            for r in results:
                parsed = _parse_listing(r)
                if not parsed:
                    continue
                key = (parsed["employer"].lower(), parsed["city"].lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append(make_job_row(
                    source="job_indeed_serper",
                    employer=parsed["employer"],
                    role=parsed["role"],
                    city=parsed["city"],
                    state=parsed["state"],
                    listing_url=parsed["listing_url"],
                ))
            time.sleep(0.4)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
