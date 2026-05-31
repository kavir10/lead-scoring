"""
Cookbook author → restaurant mapping.

Strategy: docs/strategies/07_cookbook_author_restaurants.md

A working chef who publishes on a prestige food-publishing imprint is almost
certainly running a T1 / upper-T2 restaurant. This module is seed-driven:
maintain a curated CSV of chef-authors (`cookbook_authors_seed.csv`), then
for each author resolve their **current working restaurant(s)** via Serper
Web + LLM extraction.

Public surface:

    scrape(**kwargs) -> pandas.DataFrame   # canonical SCHEMA

Pipeline per author:

  1. Skip if hint_city + author already produced a high-confidence row in
     this run (cache).
  2. Serper Web: f'"{author}" chef restaurant' — pull top 5 organic.
  3. Pick best result (prioritize eater.com, resy.com, opentable.com,
     nytimes.com, the author's personal site).
  4. Fetch the page (httpx -> Playwright fallback), extract the current
     restaurant via Claude.
  5. Emit one canonical row per current restaurant. Drop "former"
     associations.

Output schema: rows with
  source       = "cookbook_author_<publisher_slug>"
  tier         = 1
  business_type= "restaurant"
  distinction  = "{author_name} author of '{book_title}' ({pub_year}, {publisher})"
  year         = pub_year
"""
from __future__ import annotations

import csv
import json
import os
import re
import textwrap
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from awards._lib import (
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
    to_dataframe,
)


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

SEED_CSV = Path(__file__).with_name("cookbook_authors_seed.csv")

_PRIORITY_DOMAINS = (
    "eater.com",
    "resy.com",
    "opentable.com",
    "nytimes.com",
    "infatuation.com",
    "michelin.com",
    "jamesbeard.org",
    "foodandwine.com",
    "bonappetit.com",
    "thrillist.com",
    "latimes.com",
    "sfchronicle.com",
    "chicagotribune.com",
    "wikipedia.org",
)

_BLOCK_KEYWORDS = ("amazon.com", "barnesandnoble", "indiebound", "bookshop.org", "goodreads")

_EXTRACT_SYSTEM = textwrap.dedent("""
You read a short text snippet about a working chef. Extract the chef's
CURRENT working restaurant(s) in the United States.

Return ONLY a JSON array (no prose, no markdown fences). Each element:

{
  "restaurant_name": "<canonical restaurant name>",
  "city": "<US city>",
  "state": "<2-letter US state code>",
  "role": "chef-owner | head chef | executive chef | pastry chef | consulting chef | former",
  "confidence": "high | medium | low"
}

Rules:
- Include only restaurants the chef CURRENTLY works at. If the text says
  they "previously" or "formerly" worked at a place, set role="former" and
  set confidence="low" so it gets filtered.
- If you cannot confidently identify a current restaurant, return [].
- Multiple current restaurants are fine — return all of them.
- US-only. Skip non-US venues silently.
- Drop hotel restaurants from major chains (Marriott, Hilton). Independent
  chef-driven concepts only.
""").strip()


def _slugify_publisher(name: str) -> str:
    if not name or name in {"—", "-", ""}:
        return "unknown"
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    # Truncate publisher imprints to root brand
    if s.startswith("clarkson"):
        return "clarkson_potter"
    if s.startswith("ten_speed"):
        return "ten_speed"
    if s.startswith("knopf"):
        return "knopf"
    if s.startswith("phaidon"):
        return "phaidon"
    if s.startswith("artisan"):
        return "artisan"
    if "harcourt" in s or "houghton" in s:
        return "houghton_mifflin"
    return s[:32]


def _load_seeds() -> list[dict]:
    if not SEED_CSV.exists():
        print(f"  [cookbook_authors] no seed file at {SEED_CSV}", flush=True)
        return []
    rows: list[dict] = []
    with SEED_CSV.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("author_name") or "").strip()
            if not name:
                continue
            rows.append({
                "author_name": name,
                "book_title": (r.get("book_title") or "").strip().strip("—").strip(),
                "publisher": (r.get("publisher") or "").strip().strip("—").strip(),
                "pub_year": (r.get("pub_year") or "").strip().strip("—").strip(),
                "hint_city": (r.get("hint_city") or "").strip(),
                "hint_state": (r.get("hint_state") or "").strip(),
            })
    return rows


def _serper_web(query: str, *, num: int = 6) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print("  [cookbook_authors] SERPER_API_KEY missing; skipping search", flush=True)
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
        print(f"  [cookbook_authors] serper error for '{query}': {e}", flush=True)
        return []


def _pick_best_result(results: list[dict]) -> dict | None:
    for r in results:
        link = (r.get("link") or "").lower()
        if any(b in link for b in _BLOCK_KEYWORDS):
            continue
        if any(d in link for d in _PRIORITY_DOMAINS):
            return r
    for r in results:
        link = (r.get("link") or "").lower()
        if any(b in link for b in _BLOCK_KEYWORDS):
            continue
        return r
    return None


def _build_snippet(author: str, results: list[dict]) -> str:
    """Concatenate titles + snippets from top results — usually enough to identify the venue without fetching."""
    chunks: list[str] = [f"Chef name: {author}"]
    for r in results[:6]:
        link = r.get("link") or ""
        if any(b in link for b in _BLOCK_KEYWORDS):
            continue
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        chunks.append(f"- {title}\n  {snippet}\n  [{link}]")
    return "\n\n".join(chunks)


def _call_claude(snippet: str, model: str = "claude-sonnet-4-5-20250929") -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [cookbook_authors] anthropic SDK not installed; skipping", flush=True)
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [cookbook_authors] ANTHROPIC_API_KEY not set; skipping", flush=True)
        return []
    client = Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": snippet}],
        )
    except Exception as e:
        print(f"  [cookbook_authors] api error: {e}", flush=True)
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
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for d in data:
        if not isinstance(d, dict) or not d.get("restaurant_name"):
            continue
        out.append({
            "restaurant_name": str(d.get("restaurant_name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "role": str(d.get("role", "")).strip().lower(),
            "confidence": str(d.get("confidence", "low")).strip().lower(),
        })
    return out


def _resolve_one_author(seed: dict, *, sleep_between: float = 0.4) -> list[dict]:
    author = seed["author_name"]
    query = f'"{author}" chef restaurant {seed.get("hint_city", "")}'.strip()
    print(f"  [cookbook_authors] {author!r:48} querying", flush=True)
    results = _serper_web(query, num=6)
    if not results:
        return []
    snippet = _build_snippet(author, results)
    venues = _call_claude(snippet)
    if not venues:
        # Try a second pass with a tighter query
        results = _serper_web(f'{author} chef "currently" OR "chef of"', num=6)
        snippet = _build_snippet(author, results)
        venues = _call_claude(snippet)
    time.sleep(sleep_between)
    return venues


def scrape(**_kwargs) -> pd.DataFrame:
    seeds = _load_seeds()
    if not seeds:
        return pd.DataFrame(columns=SCHEMA)
    rows: list[dict] = []
    for seed in seeds:
        venues = _resolve_one_author(seed)
        if not venues:
            continue
        pub_slug = _slugify_publisher(seed.get("publisher", ""))
        for v in venues:
            if v.get("role") == "former" or v.get("confidence") == "low":
                continue
            distinction_book = seed.get("book_title", "")
            distinction = (
                f"{seed['author_name']} — author of '{distinction_book}'"
                if distinction_book else f"{seed['author_name']} — cookbook author"
            )
            if seed.get("publisher"):
                distinction += f" ({seed['publisher']}"
                if seed.get("pub_year"):
                    distinction += f", {seed['pub_year']}"
                distinction += ")"
            rows.append(make_row(
                source=f"cookbook_author_{pub_slug}",
                tier=1,
                business_type="restaurant",
                name=v["restaurant_name"],
                city=v.get("city", ""),
                state=v.get("state", ""),
                country="us",
                distinction=distinction,
                year=seed.get("pub_year") or None,
                source_url="",
                blurb=f"role={v.get('role', '')}; confidence={v.get('confidence', '')}",
            ))
    return to_dataframe(rows)


if __name__ == "__main__":
    df = scrape()
    print(df.head(20))
    print(f"\nTotal rows: {len(df)}")
