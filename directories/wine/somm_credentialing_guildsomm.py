"""
GuildSomm member directory — Advanced + Master cert tier.

Strategy: docs/strategies/03_somm_credentialing.md

GuildSomm publishes a partial public member directory at
https://www.guildsomm.com/members. Members opt in to a public profile that
includes name + employer + city. ~250 advanced+ tier members have public
profiles.

Scrape recipe:
  - Crawl paginated directory pages
  - For each member, parse name, employer, city, state, cert level
  - No LLM enrichment needed (employer is structured)
"""
from __future__ import annotations

import re
import time

import pandas as pd
from bs4 import BeautifulSoup

from awards._lib import (
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
    playwright_session,
    to_dataframe,
)


DIRECTORY_BASE = "https://www.guildsomm.com/members"


def _fetch_page(url: str) -> str:
    html = fetch_html(url)
    if not html or "<body" not in html.lower() or "guildsomm" not in html.lower():
        try:
            with playwright_session() as (page, _ctx, _br):
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                html = page.content() or ""
        except Exception as e:
            print(f"  [guildsomm] playwright failed: {e}", flush=True)
            return ""
    return html


def _parse_member_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    members: list[dict] = []
    # GuildSomm member cards — selector subject to DOM change; iterate likely
    # patterns and bail on first that yields rows.
    for sel in (".member-card", ".profile-card", ".user-card", "article.member", "li.member"):
        cards = soup.select(sel)
        if not cards:
            continue
        for c in cards:
            name_el = c.find(["h2", "h3", "h4", "a"])
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue
            employer = ""
            location = ""
            cert = ""
            for label_el in c.find_all(class_=re.compile(r"(employer|company|workplace)", re.I)):
                employer = label_el.get_text(strip=True)
                break
            for label_el in c.find_all(class_=re.compile(r"(location|city|address)", re.I)):
                location = label_el.get_text(strip=True)
                break
            for label_el in c.find_all(class_=re.compile(r"(cert|level|tier|credential)", re.I)):
                cert = label_el.get_text(strip=True)
                break
            members.append({"name": name, "employer": employer, "location": location, "cert": cert})
        if members:
            return members
    return members


def _parse_location(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = re.search(r"([A-Z][a-zA-Z\s.\-']+?),\s*([A-Z]{2})\b", text)
    if m:
        return m.group(1).strip(), normalize_state(m.group(2))
    return text.strip(), ""


def scrape(**_kwargs) -> pd.DataFrame:
    """
    Note: GuildSomm directory may require login. If first page yields no
    member cards, scraper returns empty and logs a warning — manual cookie
    capture would be needed (out of scope for v1).
    """
    rows: list[dict] = []
    page_num = 1
    seen = 0
    while page_num <= 25:  # safety bound
        url = DIRECTORY_BASE if page_num == 1 else f"{DIRECTORY_BASE}?page={page_num}"
        print(f"  [guildsomm] fetching page {page_num}", flush=True)
        html = _fetch_page(url)
        if not html:
            break
        members = _parse_member_cards(html)
        if not members:
            if page_num == 1:
                print("  [guildsomm] no member cards parsed — directory may require auth", flush=True)
            break
        new_rows_this_page = 0
        for m in members:
            if not m.get("employer"):
                continue
            cert = (m.get("cert") or "").lower()
            if not any(t in cert for t in ("advanced", "master", "certified")):
                # Skip introductory-tier; signal too weak
                continue
            city, state = _parse_location(m.get("location", ""))
            rows.append(make_row(
                source="somm_guildsomm",
                tier=1,
                business_type="restaurant",
                name=m["employer"],
                city=city,
                state=state,
                country="us",
                distinction=f"Employer of {m['cert']} GuildSomm member {m['name']}",
                source_url=url,
                blurb=f"sommelier={m['name']}; cert={m['cert']}",
            ))
            new_rows_this_page += 1
        seen += len(members)
        if new_rows_this_page == 0 and page_num > 1:
            break
        page_num += 1
        time.sleep(0.7)
    print(f"  [guildsomm] members seen: {seen}; rows kept: {len(rows)}", flush=True)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
