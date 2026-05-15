"""
LLM-driven extraction for prose editorial lists (Eater, Bon Appétit, NYT, etc.).

Why: many award lists are written articles ("The Best New Restaurants of 2024",
"Hot 10"), not structured data. We fetch the article HTML, strip to readable
text, and ask Claude to return a JSON array of business mentions.

Public surface:

    extract_businesses_from_url(url, *, business_type, source_url_override=None,
                                model="claude-sonnet-4-6", expected_us_only=True)
        -> list[dict]  # each dict ready for awards._lib.make_row(...)

    extract_businesses_from_text(text, *, business_type, source_url, ...)
        -> list[dict]

Each returned dict has: name, city, state, country, distinction, blurb,
source_url. The caller fills in `source`, `tier`, and `business_type`.
"""
from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Any

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from awards._lib import fetch_html, normalize_state

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

_DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM = textwrap.dedent("""
You extract structured business listings from editorial articles. The article
is a "best of" / "award" / "ranked list" article naming specific food
businesses.

Return ONLY a JSON array (no prose, no markdown fences). Each element:

{
  "name": "<official business name>",
  "city": "<city only — no state, no country>",
  "state": "<2-letter US state code, or empty>",
  "country": "us | other",
  "distinction": "<the specific recognition this business received in this article, e.g. 'Hot 10 2024 #3', 'Restaurant of the Year 2023', 'Best New Bakery'>",
  "blurb": "<one-sentence reason given in the article, paraphrased — under 200 chars>"
}

Rules:
- ONLY include businesses the article specifically endorses or ranks. Skip
  passing mentions, comparisons, or background context.
- Do NOT invent cities or states. If the article doesn't say, leave them blank.
- Do NOT include the publication name itself.
- Map full state names to 2-letter codes ("California" -> "CA").
- "country": "us" if the business is in the United States; otherwise "other".
- If the article is region-specific (e.g. "Best Restaurants in Chicago"), set
  city = "Chicago" and state = "IL" for entries with no other location given.
- If you cannot find any qualifying businesses, return [].
""").strip()

_FALLBACK_TEXT_LIMIT = 60_000  # chars sent to Claude


def _readable_text(html: str) -> str:
    """Reduce HTML to article-relevant text. Best-effort, not perfect."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "header"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text[:_FALLBACK_TEXT_LIMIT]


def _call_claude(article_text: str, model: str, hint: str = "") -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [llm] anthropic SDK not installed; skipping", flush=True)
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [llm] ANTHROPIC_API_KEY not set; skipping", flush=True)
        return []

    client = Anthropic(api_key=api_key)
    user_block = (f"Hint: {hint}\n\n" if hint else "") + "Article text:\n\n" + article_text

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_block}],
        )
    except Exception as e:
        print(f"  [llm] api error: {e}", flush=True)
        return []

    raw = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Find the first '[' and last ']' to be defensive
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        print(f"  [llm] could not find JSON array in response (len={len(raw)})", flush=True)
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as e:
        print(f"  [llm] json decode error: {e}", flush=True)
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        if not d.get("name"):
            continue
        out.append({
            "name": str(d.get("name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "country": str(d.get("country", "us")).strip().lower() or "us",
            "distinction": str(d.get("distinction", "")).strip(),
            "blurb": str(d.get("blurb", "")).strip(),
        })
    return out


def extract_businesses_from_text(
    text: str,
    *,
    source_url: str = "",
    hint: str = "",
    model: str = _DEFAULT_MODEL,
    expected_us_only: bool = True,
) -> list[dict]:
    rows = _call_claude(text, model=model, hint=hint)
    for r in rows:
        r["source_url"] = source_url
    if expected_us_only:
        rows = [r for r in rows if r.get("country", "us") == "us"]
    return rows


def _fetch_via_playwright(url: str, *, cookies: list[dict] | None = None) -> str:
    """Used for sites that block plain HTTP (Vox Media / NYT / Wine Spectator)."""
    from awards._lib import playwright_session
    try:
        with playwright_session(cookies=cookies) as (page, _ctx, _br):
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=12_000)
            except Exception:
                pass
            return page.evaluate("() => document.body.innerText") or ""
    except Exception as e:
        print(f"  [llm] playwright fetch error for {url}: {e}", flush=True)
        return ""


def extract_businesses_from_url(
    url: str,
    *,
    hint: str = "",
    model: str = _DEFAULT_MODEL,
    expected_us_only: bool = True,
    cookies: list[dict] | None = None,
) -> list[dict]:
    html = fetch_html(url)
    text = _readable_text(html) if html else ""
    if len(text) < 400:
        # Plain HTTP blocked or article is JS-rendered. Fall back to Playwright.
        text = _fetch_via_playwright(url, cookies=cookies)
    if len(text) < 400:
        print(f"  [llm] could not get readable text for {url} ({len(text)} chars)", flush=True)
        return []
    print(f"  [llm] extracting from {url}  (text {len(text)} chars)", flush=True)
    return extract_businesses_from_text(
        text, source_url=url, hint=hint, model=model, expected_us_only=expected_us_only
    )
