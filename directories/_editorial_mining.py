"""
Editorial-mention mining for distributors / purveyors with no public customer
list.

Some supply-chain leverage points (Pat LaFrieda, Browne Trading, Jasper Hill,
Niman Ranch, etc.) do not publish their restaurant client list. Their
clients are surfaced in editorial coverage instead ("Eleven Madison Park
serves LaFrieda beef", "Le Bernardin's caviar is from Browne Trading").

This helper turns that pattern into a scrape() function:

  1. For each "lens" query (chef quote, supply mention, NYT/Eater coverage)
     hit Serper Web search.
  2. Concatenate top-N organic title+snippet+link blocks.
  3. Hand the snippet wad to Claude with a tight extraction prompt.
  4. Return canonical SCHEMA rows.

Cost per distributor: ~5 Serper calls * $0.001 + 1 Claude Sonnet call ~$0.02.
"""
from __future__ import annotations

import json
import os
import re
import textwrap
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from awards._lib import (
    SCHEMA,
    make_row,
    normalize_state,
    to_dataframe,
)


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


_EDITORIAL_SYSTEM = textwrap.dedent("""
You read editorial coverage snippets about a food-supply company / distributor
/ purveyor. The snippets mention RESTAURANTS that buy from this purveyor.

Return ONLY a JSON array (no prose, no markdown fences). Each element:

{
  "restaurant_name": "<canonical restaurant name>",
  "city": "<US city>",
  "state": "<2-letter US state code>",
  "confidence": "high | medium | low",
  "evidence_quote": "<short snippet that established the link, under 200 chars>"
}

Rules:
- Include only US restaurants the snippets clearly tie to this purveyor as a
  customer. Skip mentions that are not customer relationships (mentions of
  the purveyor's own name, food writers' general mentions, etc.).
- If the snippet only says "many top NYC chefs use X" without naming a
  restaurant, do NOT invent restaurants. Skip.
- Confidence: "high" only when the snippet directly attributes the
  ingredient/relationship; "medium" if it's implied by context; "low" if
  it's a guess.
- Drop hotel restaurants from major chains (Marriott, Hilton, Hyatt).
- Return [] if nothing extractable.
""").strip()


_BLOCK_KEYWORDS = ("amazon.com", "ebay.com", "goldbelly.com", "instagram.com", "facebook.com")


def _serper_web(query: str, *, num: int = 8) -> list[dict]:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print("  [editorial] SERPER_API_KEY missing", flush=True)
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
        print(f"  [editorial] serper error for {query!r}: {e}", flush=True)
        return []


def _build_snippet(distributor_name: str, results: list[dict]) -> str:
    chunks: list[str] = [f"Purveyor / distributor: {distributor_name}"]
    for r in results:
        link = (r.get("link") or "").lower()
        if any(b in link for b in _BLOCK_KEYWORDS):
            continue
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        if not snippet and not title:
            continue
        chunks.append(f"- {title}\n  {snippet}\n  [{link}]")
    return "\n\n".join(chunks)


def _call_claude(snippet: str, model: str = "claude-sonnet-4-5-20250929") -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [editorial] anthropic SDK not installed", flush=True)
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [editorial] ANTHROPIC_API_KEY not set", flush=True)
        return []
    client = Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_EDITORIAL_SYSTEM,
            messages=[{"role": "user", "content": snippet}],
        )
    except Exception as e:
        print(f"  [editorial] api error: {e}", flush=True)
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
    if not isinstance(data, list):
        return []
    for d in data:
        if not isinstance(d, dict) or not d.get("restaurant_name"):
            continue
        out.append({
            "restaurant_name": str(d.get("restaurant_name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "confidence": str(d.get("confidence", "low")).strip().lower(),
            "evidence_quote": str(d.get("evidence_quote", "")).strip(),
        })
    return out


def mine_distributor_mentions(
    *,
    distributor_slug: str,
    distributor_name: str,
    queries: list[str] | None = None,
    business_type: str = "restaurant",
    tier: int = 1,
    sleep_between: float = 0.7,
) -> pd.DataFrame:
    """
    Run a fixed bank of Serper queries against the distributor's customer
    surface and return canonical SCHEMA rows.

    Default queries (override per-distributor):
      - "<name>" restaurants customers chef
      - "supplied by <name>" restaurant
      - "<name>" chef purveyor
    """
    if queries is None:
        queries = [
            f'"{distributor_name}" restaurants chef customer',
            f'"supplied by {distributor_name}" restaurant',
            f'"{distributor_name}" purveyor chef',
            f'"{distributor_name}" "uses" OR "serves" restaurant',
            f'"{distributor_name}" New York OR Chicago OR Los Angeles restaurant',
        ]

    all_results: list[dict] = []
    seen_links: set[str] = set()
    for q in queries:
        res = _serper_web(q, num=8)
        time.sleep(sleep_between)
        for r in res:
            link = r.get("link") or ""
            if link in seen_links:
                continue
            seen_links.add(link)
            all_results.append(r)
        print(f"  [editorial:{distributor_slug}] query={q!r} -> {len(res)}", flush=True)

    if not all_results:
        return pd.DataFrame(columns=SCHEMA)

    snippet = _build_snippet(distributor_name, all_results)
    print(f"  [editorial:{distributor_slug}] LLM extract from {len(all_results)} results", flush=True)
    venues = _call_claude(snippet)
    if not venues:
        print(f"  [editorial:{distributor_slug}] LLM returned 0 venues", flush=True)
        return pd.DataFrame(columns=SCHEMA)

    rows: list[dict] = []
    for v in venues:
        if v["confidence"] == "low":
            continue
        rows.append(make_row(
            source=f"distributor_{distributor_slug}",
            tier=tier,
            business_type=business_type,
            name=v["restaurant_name"],
            city=v.get("city", ""),
            state=v.get("state", ""),
            country="us",
            distinction=f"Customer of {distributor_name}",
            source_url="",
            blurb=f"editorial_mention; confidence={v['confidence']}; evidence={v.get('evidence_quote', '')[:160]}",
        ))
    print(f"  [editorial:{distributor_slug}] +{len(rows)} extracted (after low-conf filter)", flush=True)
    return to_dataframe(rows)
