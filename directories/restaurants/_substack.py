"""
Shared helper for Substack / newsletter-archive scrapers.

Per source module supplies:
  - publication_slug (e.g. "alicia_kennedy")
  - publication_name (e.g. "Alicia Kennedy")
  - archive_url       (Substack archive endpoint, e.g. "https://aliciakennedy.substack.com/archive")
  - distinction_label (e.g. "Mentioned by Alicia Kennedy")
  - max_posts         (cap per-run cost)

The helper:
  1. Fetches archive page(s) (httpx -> Playwright fallback)
  2. Pulls last N post URLs
  3. For each post: fetches body text, runs Claude (Haiku 4.5) extraction
     for venue mentions with sentiment + context
  4. Returns canonical SCHEMA rows
"""
from __future__ import annotations

import json
import os
import re
import textwrap
import time
from urllib.parse import urljoin

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


_EXTRACT_SYSTEM = textwrap.dedent("""
You read a food / restaurant newsletter post. Extract every US-based
restaurant, wine bar, wine shop, bakery, butcher, cheesemonger, or
specialty food retailer NAMED in this post. For each venue, return:

{
  "venue_name": "<canonical name>",
  "city": "<US city>",
  "state": "<2-letter US state code>",
  "context": "<one-sentence quote or paraphrase of why the writer mentioned this venue>",
  "sentiment": "positive | neutral | negative",
  "business_type": "restaurant | wine_store | wine_bar | bakery | butcher | cheese | specialty"
}

Rules:
- US-only. Skip international venues silently.
- Drop chains and large hotel-group restaurants (Marriott, Hilton).
- If sentiment is negative (the writer is criticizing the venue), still
  include it — downstream filtering decides. Be honest about sentiment.
- Return ONLY a JSON array. No prose, no markdown fences. Empty array if
  no venues found.
""").strip()


def _fetch(url: str, *, prefer_playwright: bool = False) -> str:
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
        print(f"  [substack] playwright failed: {e}", flush=True)
        return ""


def _extract_post_links(archive_html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(archive_html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if "/p/" not in href and "/post/" not in href:
            continue
        full = urljoin(base, href.split("?")[0])
        if full in seen:
            continue
        seen.add(full)
        title = a.get_text(" ", strip=True)[:140]
        out.append((full, title))
    return out


def _readable_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:60_000]


def _call_claude(post_text: str, *, model: str = "claude-haiku-4-5-20251001") -> list[dict]:
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
            model=model, max_tokens=4096, system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": post_text}],
        )
    except Exception as e:
        print(f"  [substack] api error: {e}", flush=True)
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
        if not isinstance(d, dict) or not d.get("venue_name"):
            continue
        out.append({
            "venue_name": str(d.get("venue_name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "context": str(d.get("context", "")).strip(),
            "sentiment": str(d.get("sentiment", "neutral")).strip().lower(),
            "business_type": str(d.get("business_type", "restaurant")).strip().lower(),
        })
    return out


def scrape_publication(
    *,
    publication_slug: str,
    publication_name: str,
    archive_url: str,
    distinction_label: str | None = None,
    max_posts: int = 50,
    drop_negative: bool = True,
    sleep_between: float = 0.8,
) -> pd.DataFrame:
    print(f"  [substack:{publication_slug}] fetching archive {archive_url}", flush=True)
    html = _fetch(archive_url)
    if not html:
        return pd.DataFrame(columns=SCHEMA)
    posts = _extract_post_links(html, archive_url)[:max_posts]
    print(f"  [substack:{publication_slug}] {len(posts)} posts", flush=True)
    distinction_label = distinction_label or f"Mentioned by {publication_name}"
    rows: list[dict] = []
    for i, (url, title) in enumerate(posts):
        print(f"  [substack:{publication_slug}] ({i + 1}/{len(posts)}) {title[:60]}", flush=True)
        post_html = _fetch(url)
        if not post_html:
            continue
        text = _readable_text(post_html)
        if len(text) < 400:
            continue
        venues = _call_claude(text)
        for v in venues:
            if drop_negative and v["sentiment"] == "negative":
                continue
            rows.append(make_row(
                source=f"substack_{publication_slug}",
                tier=1,
                business_type=v.get("business_type", "restaurant"),
                name=v["venue_name"],
                city=v.get("city", ""),
                state=v.get("state", ""),
                country="us",
                distinction=f"{distinction_label} — '{v.get('context', '')[:140]}'",
                source_url=url,
                blurb=f"sentiment={v['sentiment']}; post_title={title[:80]}",
            ))
        time.sleep(sleep_between)
    return to_dataframe(rows)
