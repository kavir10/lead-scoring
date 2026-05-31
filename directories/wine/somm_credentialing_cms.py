"""
Court of Master Sommeliers Americas — Master Sommeliers directory scrape.

Strategy: docs/strategies/03_somm_credentialing.md

The CMS Americas publishes the entire ~170-person Master Sommelier roster as a
structured HTML table at https://www.mastersommeliers.org/masters/list with
columns: Year | First Name | Last Name | Employer | City | State | Country |
Good Standing | Profile.

The employer field is populated directly — no Serper / LLM resolution needed.
We just parse the table.
"""
from __future__ import annotations

import os

import pandas as pd
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


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

ROSTER_URL = "https://www.mastersommeliers.org/masters/list?field_first_name_value=&field_last_name_value=&city=&province=All&page={page}"


def _fetch_page(page: int) -> str:
    url = ROSTER_URL.format(page=page)
    html = fetch_html(url)
    if html and "<table" in html.lower():
        return html
    try:
        with playwright_session() as (p, _ctx, _br):
            p.goto(url, wait_until="domcontentloaded", timeout=30_000)
            return p.content() or ""
    except Exception as e:
        print(f"  [somm_cms] playwright fallback failed: {e}", flush=True)
        return ""


# Skip employers that obviously aren't restaurants we sell into. We keep
# wholesale / distributor rows out of the final CSV but flag them in a
# wholesale CSV for separate handling.
_NON_RESTAURANT_KEYWORDS = (
    "wine consultant",
    "wine consulting",
    "consultant",
    "consulting",
    "winery owner",
    "winery",
    "vineyard",
    "wine import",
    "importer",
    "distribut",
    "wholesale",
    "wine sales",
    "wine spirits",
    "retired",
    "court of master sommeliers",
    "guildsomm",
    "advanced sommelier",
    "wine school",
    "wine education",
)


def _classify(employer: str) -> tuple[str, bool]:
    """Return (business_type, keep). business_type maps to canonical schema."""
    if not employer:
        return ("restaurant", False)
    lower = employer.lower()
    if any(k in lower for k in _NON_RESTAURANT_KEYWORDS):
        return ("wholesale", False)
    if "hotel" in lower or "resort" in lower:
        return ("restaurant", True)
    if "wine shop" in lower or "wine bar" in lower or "wine store" in lower or "bottle shop" in lower:
        return ("wine_store", True)
    return ("restaurant", True)


def _parse_table_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows: list[dict] = []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 7:
            continue
        year, first, last, employer, city, state, country = cells[:7]
        if (country or "").lower() not in {"united states", "us", "usa"}:
            continue
        rows.append({
            "year": year,
            "name_first": first,
            "name_last": last,
            "employer": employer,
            "city": city,
            "state": normalize_state(state),
        })
    return rows


def scrape(**_kwargs) -> pd.DataFrame:
    all_members: list[dict] = []
    seen_pages: set[str] = set()
    for page in range(0, 20):  # CMS has < 200 members, ~50 per page is plenty
        print(f"  [somm_cms] fetching page {page}", flush=True)
        html = _fetch_page(page)
        if not html:
            break
        page_rows = _parse_table_rows(html)
        if not page_rows:
            break
        # De-dupe in case the same page returns repeatedly
        page_sig = repr(page_rows[:3])
        if page_sig in seen_pages:
            break
        seen_pages.add(page_sig)
        all_members.extend(page_rows)
        print(f"  [somm_cms] page {page}: +{len(page_rows)} members", flush=True)
        if len(page_rows) < 25:  # last page is partial
            break

    if not all_members:
        print("  [somm_cms] no rows parsed — selector or URL drift", flush=True)
        return pd.DataFrame(columns=SCHEMA)

    rows: list[dict] = []
    for m in all_members:
        full_name = f"{m['name_first']} {m['name_last']}".strip()
        btype, keep = _classify(m["employer"])
        if not keep:
            continue
        if not m["employer"] or len(m["employer"]) < 2:
            continue
        rows.append(make_row(
            source="somm_cms_master",
            tier=1,
            business_type=btype,
            name=m["employer"],
            city=m["city"],
            state=m["state"],
            country="us",
            distinction=f"Employer of Master Sommelier {full_name} (cert {m['year']})",
            year=m["year"] or None,
            source_url=ROSTER_URL.split("?")[0],
            blurb=f"sommelier={full_name}; cert_year={m['year']}",
        ))
    print(f"  [somm_cms] {len(all_members)} members -> {len(rows)} kept rows", flush=True)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
