"""
Court of Master Sommeliers Americas — Master Sommeliers directory scrape.

Strategy: docs/strategies/03_somm_credentialing.md

The CMS Americas publishes the full Master Sommelier roster at
https://www.mastersommeliers.org/members. The page lists ~170 active US
Master Sommeliers with name + city. Employer field is NOT included; we
enrich each name via Serper Web to identify their current employer (the
restaurant / wine program is the actual lead).

Per author/sommelier resolution mirrors directories/restaurants/cookbook_authors.py.
"""
from __future__ import annotations

import json
import os
import re
import textwrap
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


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

ROSTER_URL = "https://www.mastersommeliers.org/members"

_EXTRACT_SYSTEM = textwrap.dedent("""
You read a short snippet about a Master Sommelier in the US. Extract the
sommelier's CURRENT employer (the restaurant, wine bar, wine shop, or
wine-related business they currently work at).

Return ONLY a JSON array (no prose). Each element:

{
  "employer_name": "<canonical business name>",
  "city": "<US city>",
  "state": "<2-letter US state>",
  "business_type": "restaurant | wine_store | wine_bar | hotel_restaurant | wholesale | consulting | other",
  "role": "wine director | sommelier | beverage director | owner | consultant | educator | other",
  "confidence": "high | medium | low"
}

Rules:
- Include ONLY the most recent / current employer. If they founded their own
  consulting practice, return that.
- If you cannot confidently identify a current employer, return [].
- US-only. Skip non-US employers silently.
- Skip employers in wholesale/distribution unless the sommelier is the owner.
""").strip()


def _scrape_roster() -> list[dict]:
    """Pull the public roster. Plays nice with WAF — Playwright fallback."""
    html = fetch_html(ROSTER_URL)
    if not html or "<body" not in html.lower():
        print("  [somm_cms] HTTP fetch failed; trying Playwright", flush=True)
        try:
            with playwright_session() as (page, _ctx, _br):
                page.goto(ROSTER_URL, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12_000)
                except Exception:
                    pass
                html = page.content() or ""
        except Exception as e:
            print(f"  [somm_cms] Playwright failed: {e}", flush=True)
            return []
    soup = BeautifulSoup(html, "html.parser")
    members: list[dict] = []
    # The CMS site structures member cards loosely. Heuristic: look for h2/h3
    # within member sections, plus a city/state suffix. Adjust selector based
    # on actual DOM at run time.
    for card in soup.select("div.member, li.member, article.member, .member-card, .ms-card"):
        name_el = card.find(["h2", "h3", "h4", "a", "strong"])
        name = name_el.get_text(strip=True) if name_el else card.get_text(" ", strip=True)
        if not name or len(name) > 80:
            continue
        loc_el = card.find(class_=re.compile(r"(location|city|locale|region)", re.I))
        loc = loc_el.get_text(strip=True) if loc_el else ""
        members.append({"name": name, "location_hint": loc})
    # Fallback: try parsing any <li> or <p> that looks like "Firstname Lastname, MS — City, ST"
    if not members:
        for el in soup.find_all(["li", "p", "div"]):
            text = el.get_text(" ", strip=True)
            m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z'`-]+){1,3})(?:,\s*MS)?\s*[—–\-]\s*([A-Z][a-zA-Z\s.]+,\s*[A-Z]{2})$", text)
            if m:
                members.append({"name": m.group(1).strip(), "location_hint": m.group(2).strip()})
    return members


def _serper_web(query: str, *, num: int = 5) -> list[dict]:
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
        print(f"  [somm_cms] serper error: {e}", flush=True)
        return []


def _build_snippet(name: str, location: str, results: list[dict]) -> str:
    chunks = [f"Sommelier: {name}", f"Location hint: {location}" if location else ""]
    for r in results[:5]:
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        link = r.get("link") or ""
        chunks.append(f"- {title}\n  {snippet}\n  [{link}]")
    return "\n\n".join(c for c in chunks if c)


def _call_claude(snippet: str, model: str = "claude-sonnet-4-5-20250929") -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    client = Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model, max_tokens=512, system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": snippet}],
        )
    except Exception as e:
        print(f"  [somm_cms] api error: {e}", flush=True)
        return []
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: list[dict] = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict) or not d.get("employer_name"):
            continue
        out.append({
            "employer_name": str(d.get("employer_name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "business_type": str(d.get("business_type", "restaurant")).strip().lower(),
            "role": str(d.get("role", "")).strip().lower(),
            "confidence": str(d.get("confidence", "low")).strip().lower(),
        })
    return out


def scrape(**_kwargs) -> pd.DataFrame:
    members = _scrape_roster()
    if not members:
        print("  [somm_cms] no members parsed from roster; check selector", flush=True)
        return pd.DataFrame(columns=SCHEMA)
    print(f"  [somm_cms] roster parsed: {len(members)} master sommeliers", flush=True)
    rows: list[dict] = []
    for m in members:
        name = m["name"]
        loc = m.get("location_hint", "")
        query = f'"{name}" master sommelier wine director restaurant {loc}'.strip()
        print(f"  [somm_cms] resolving {name!r}", flush=True)
        results = _serper_web(query, num=5)
        if not results:
            continue
        snippet = _build_snippet(name, loc, results)
        employers = _call_claude(snippet)
        for emp in employers:
            if emp["confidence"] == "low":
                continue
            if emp["business_type"] in {"wholesale", "consulting"}:
                # These are leads of a different shape; flag in blurb but keep
                pass
            btype_map = {
                "restaurant": "restaurant",
                "wine_store": "wine_store",
                "wine_bar": "restaurant",
                "hotel_restaurant": "restaurant",
                "wholesale": "wholesale",
                "consulting": "consulting",
            }
            rows.append(make_row(
                source="somm_cms_master",
                tier=1,
                business_type=btype_map.get(emp["business_type"], "restaurant"),
                name=emp["employer_name"],
                city=emp.get("city", ""),
                state=emp.get("state", ""),
                country="us",
                distinction=f"Employer of Master Sommelier {name}",
                source_url=ROSTER_URL,
                blurb=f"sommelier={name}; role={emp.get('role', '')}; conf={emp.get('confidence', '')}",
            ))
        time.sleep(0.5)
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)}")
