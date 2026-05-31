"""
Restaurant Zone (restaurantzone.net) — hospitality job board.
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


def _parse(result: dict) -> dict | None:
    link = result.get("link", "") or ""
    if "restaurantzone" not in link.lower():
        return None
    title = (result.get("title", "") or "").strip()
    snippet = (result.get("snippet", "") or "").strip()
    # Title format: "{Role} at {Employer}" or "{Role} - {Employer}"
    m = re.match(r"^(.+?)\s+(?:at|—|–|-|\|)\s+(.+?)$", title)
    if not m:
        return None
    role, employer = m.group(1).strip(), m.group(2).strip()
    if len(employer) < 3:
        return None
    city, state = split_city_state(snippet)
    return {
        "employer": employer, "role": role[:80],
        "city": city, "state": state, "listing_url": link,
    }


def scrape(**_kwargs) -> pd.DataFrame:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for role_q in WINE_ROLE_QUERIES:
        for metro in DEFAULT_METROS:
            q = f'site:restaurantzone.net {role_q} "{metro}"'
            print(f"  [job_restaurant_zone] {q}", flush=True)
            results = serper_web(q, num=10)
            for r in results:
                parsed = _parse(r)
                if not parsed:
                    continue
                key = (parsed["employer"].lower(), parsed["city"].lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append(make_job_row(source="job_restaurant_zone", **parsed))
            time.sleep(0.4)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
