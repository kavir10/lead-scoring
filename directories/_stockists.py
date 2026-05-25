"""
Shared helper for stockist-page scrapers.

Each premium wine importer publishes a "where to buy" / "find our wines" /
"retail partners" page. Shops listed there are by definition ICP-grade leads:
they've been vetted by an importer whose wines we already care about. A shop
that appears on multiple importer pages is gold.

Public surface:

    scrape_stockist_page(
        *,
        importer_slug,     # e.g. "louis_dressner"
        importer_name,     # e.g. "Louis/Dressner Selections"
        urls,              # one or more stockist-page URLs
        strategy="llm",    # "html" | "playwright" | "llm"
        css_selector=None, # required for strategy="html"
        tier=1,
        retailers_only=True,
    ) -> pandas.DataFrame

Returns rows in `awards._lib.SCHEMA` with:
    source       = f"stockist_{importer_slug}"
    business_type= "wine_store"
    distinction  = f"Stockist: {importer_name}"

Cross-source dedupe in build_master() keeps one row per (source, name, city),
so a shop appearing on 8 importer pages stacks as 8 distinct rows — exactly
the "multiple awards reinforce score" pattern the codebase already relies on.
"""
from __future__ import annotations

import json
import os
import re
import textwrap
import time
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from awards._lib import (
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
    parse_city_state,
    playwright_session,
    to_dataframe,
    UA,
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

_DEFAULT_MODEL = "claude-sonnet-4-6"

# Tailored extraction prompt for stockist/retailer pages. Different semantics
# from the awards/llm_extract.py prompt (which is for editorial "best of"
# articles) — a stockist page is a flat retailer list with city/state.
_STOCKIST_SYSTEM = textwrap.dedent("""
You extract structured retailer listings from a wine importer's "where to buy"
or "retail partners" page. The page lists shops/restaurants that carry the
importer's wines.

Return ONLY a JSON array (no prose, no markdown fences). Each element:

{
  "name": "<official retailer/restaurant name>",
  "city": "<city only — no state, no country>",
  "state": "<2-letter US state code, or empty>",
  "country": "us | other",
  "category": "shop | restaurant | bar | unknown",
  "blurb": "<any context the page gives — under 200 chars, or empty>"
}

Rules:
- Include every retailer/restaurant the page lists. Do NOT skip — completeness
  matters more than judgement here.
- "category": choose "shop" for wine shops / bottle shops / wine stores /
  retail / wine merchants. "restaurant" for restaurants / bistros. "bar" for
  wine bars / cocktail bars (unless they also retail, then "shop"). Use
  "unknown" if the page doesn't make it clear.
- Do NOT include the importer itself, distributors, producers, or wineries.
- Do NOT invent cities/states — leave blank if not given.
- Map full state names to 2-letter codes ("California" -> "CA").
- "country": "us" if in the United States; otherwise "other".
- If you cannot find any retailers, return [].
""").strip()


def _readable_text(html: str) -> str:
    """Strip HTML to retailer-list-relevant text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "form"]):
        tag.decompose()
    # Most stockist pages have everything in <main> or <body>; keep nav stripped
    # because some importers shove a giant nav above the retailer list.
    for tag in soup(["nav", "header", "footer", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:80_000]


def _parse_json_array(raw: str) -> list[dict] | None:
    """Parse a JSON array; salvage partials when the LLM response was truncated.

    Returns None only when nothing parseable was found. An empty list means
    the model legitimately returned [].
    """
    start = raw.find("[")
    if start == -1:
        return None
    end = raw.rfind("]")
    if end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            pass  # fall through to salvage
    # Salvage: collect every complete top-level {...} object using brace tracking.
    salvaged: list[dict] = []
    depth = 0
    obj_start = -1
    in_string = False
    escape = False
    for i in range(start + 1, len(raw)):
        c = raw[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and obj_start != -1:
                try:
                    salvaged.append(json.loads(raw[obj_start : i + 1]))
                except json.JSONDecodeError:
                    pass
                obj_start = -1
    return salvaged


def _call_claude(text: str, *, hint: str, model: str) -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [stockist-llm] anthropic SDK not installed; skipping", flush=True)
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [stockist-llm] ANTHROPIC_API_KEY not set; skipping", flush=True)
        return []
    client = Anthropic(api_key=api_key)
    user_block = (f"Hint: {hint}\n\n" if hint else "") + "Page text:\n\n" + text
    raw_parts: list[str] = []
    try:
        with client.messages.stream(
            model=model,
            max_tokens=32_000,
            system=_STOCKIST_SYSTEM,
            messages=[{"role": "user", "content": user_block}],
        ) as stream:
            for chunk in stream.text_stream:
                raw_parts.append(chunk)
    except Exception as e:
        print(f"  [stockist-llm] api error: {e}", flush=True)
        return []
    raw = "".join(raw_parts).strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = _parse_json_array(raw)
    if data is None:
        print(f"  [stockist-llm] could not parse JSON (len={len(raw)})", flush=True)
        print(f"  [stockist-llm] raw head: {raw[:200]!r}", flush=True)
        print(f"  [stockist-llm] raw tail: {raw[-200:]!r}", flush=True)
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for d in data:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        out.append({
            "name": str(d.get("name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "country": str(d.get("country", "us")).strip().lower() or "us",
            "category": str(d.get("category", "unknown")).strip().lower(),
            "blurb": str(d.get("blurb", "")).strip(),
        })
    return out


def _fetch_html_or_playwright(url: str, *, strategy: str) -> str:
    if strategy == "playwright":
        try:
            with playwright_session() as (page, _ctx, _br):
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12_000)
                except Exception:
                    pass
                return page.content() or ""
        except Exception as e:
            print(f"  [stockist] playwright error for {url}: {e}", flush=True)
            return ""
    # WAF-aware fetch: curl_cffi (TLS impersonation) -> plain requests -> Playwright
    from directories._browser_fetch import fetch_html_with_fallback
    return fetch_html_with_fallback(url)


def _parse_html_list(html: str, css_selector: str) -> list[dict]:
    """Extract retailer rows from a known structured HTML list.

    Each matched element is expected to contain the retailer name as direct
    text and (optionally) a "City, ST" string. Best-effort — falls back to
    name-only rows if location can't be parsed.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for el in soup.select(css_selector):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        # Try to split on the last comma-separated "City, ST" suffix.
        m = re.search(r"(.+?)\s*[,–—\-:\s]+([^,]+?,\s*[A-Z]{2})\s*$", text)
        if m:
            name = m.group(1).strip().rstrip(",-–—: ")
            city, state = parse_city_state(m.group(2))
        else:
            name = text
            city, state = "", ""
        if len(name) < 2:
            continue
        rows.append({
            "name": name, "city": city, "state": state,
            "country": "us", "category": "unknown", "blurb": "",
        })
    return rows


def scrape_stockist_page(
    *,
    importer_slug: str,
    importer_name: str,
    urls: list[str],
    strategy: Literal["html", "playwright", "llm"] = "llm",
    css_selector: str | None = None,
    tier: int = 1,
    retailers_only: bool = True,
    hint: str = "",
    model: str = _DEFAULT_MODEL,
    sleep_between: float = 1.0,
    business_type_default: str = "wine_store",
    source_prefix: str = "stockist",
    distinction_label: str = "Stockist",
    keep_categories: set[str] | None = None,
) -> pd.DataFrame:
    """
    Scrape one or more stockist URLs for a single importer; return canonical-schema rows.

    strategy:
      - "html"       : fetch via HTTP, parse with `css_selector` (fastest, no LLM cost)
      - "playwright" : fetch via Playwright (for JS-rendered stockist widgets), then LLM
      - "llm"        : fetch via HTTP (fallback to Playwright if blocked), LLM extract

    retailers_only: when True (default), drops rows where category == "restaurant" or
                    "bar". When False, keeps everything (route restaurants through the
                    restaurant pipeline separately if desired — out of scope here).
    """
    source = f"{source_prefix}_{importer_slug}"
    distinction = f"{distinction_label}: {importer_name}"
    rows: list[dict] = []

    if strategy == "html" and not css_selector:
        raise ValueError(f"strategy='html' requires css_selector for {importer_slug}")

    for url in urls:
        print(f"  [{source}] fetching {url}", flush=True)
        html = _fetch_html_or_playwright(url, strategy="playwright" if strategy == "playwright" else "html")
        if not html and strategy == "llm":
            # Plain HTTP got nothing — try Playwright.
            print(f"  [{source}] HTTP failed; retrying via Playwright", flush=True)
            html = _fetch_html_or_playwright(url, strategy="playwright")
        if not html:
            print(f"  [{source}] no HTML for {url}", flush=True)
            time.sleep(sleep_between)
            continue

        if strategy == "html":
            parsed = _parse_html_list(html, css_selector)  # type: ignore[arg-type]
        else:
            text = _readable_text(html)
            if len(text) < 200:
                print(f"  [{source}] readable text too short ({len(text)})", flush=True)
                time.sleep(sleep_between)
                continue
            print(f"  [{source}] LLM extract from {len(text)} chars", flush=True)
            parsed = _call_claude(text, hint=hint or f"This is the '{importer_name}' stockist/where-to-buy page.", model=model)

        for r in parsed:
            cat = r.get("category", "unknown")
            if retailers_only and cat in {"restaurant", "bar"}:
                continue
            if keep_categories is not None and cat not in keep_categories:
                continue
            if r.get("country", "us") != "us":
                continue
            # Per-row business_type override: when a customer-list page mixes
            # restaurants + retail, let the parsed `category` route the row.
            if cat == "restaurant":
                btype = "restaurant"
            elif cat == "bar":
                btype = "restaurant"
            elif cat == "shop":
                btype = business_type_default if business_type_default != "wine_store" else "wine_store"
            else:
                btype = business_type_default
            rows.append(make_row(
                source=source,
                tier=tier,
                business_type=btype,
                name=r["name"],
                city=r.get("city", ""),
                state=r.get("state", ""),
                country="us",
                distinction=distinction,
                source_url=url,
                blurb=r.get("blurb", ""),
            ))
        print(f"  [{source}] +{len(parsed)} parsed, kept retailers", flush=True)
        time.sleep(sleep_between)

    if not rows:
        return pd.DataFrame(columns=SCHEMA)
    return to_dataframe(rows)
