"""
Fetch + readable-text extraction.

Primary path: httpx (sync) + selectolax HTML parsing.
Fallback path: Playwright (reused from awards._lib.playwright_session) — used
when httpx is blocked (403/429/503) or returns too-thin text.
"""
from __future__ import annotations

import os
import time

import httpx
from selectolax.parser import HTMLParser

from awards._lib import playwright_session

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
MIN_TEXT = 400         # below this we assume the fetch is junk/blocked
MAX_TEXT = 60_000      # cap passed to LLM
RETRYABLE = {403, 429, 503, 502, 520, 522}


def _httpx_get(url: str, *, timeout: int = 25, retries: int = 3) -> tuple[int, str]:
    """Returns (status_code, html). status_code=0 on transport error."""
    backoff = 1.5
    for attempt in range(retries):
        try:
            with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
                r = client.get(url, timeout=timeout)
            if r.status_code == 200:
                return 200, r.text
            if r.status_code in RETRYABLE:
                time.sleep(backoff * (attempt + 1))
                continue
            return r.status_code, ""
        except httpx.HTTPError as e:
            print(f"  [httpx] {url}: {e}", flush=True)
            time.sleep(backoff * (attempt + 1))
    return 0, ""


def _readable(html: str) -> str:
    """selectolax-based readable-text extraction. Picks the richest container."""
    if not html:
        return ""
    tree = HTMLParser(html)
    for sel in ("script", "style", "noscript", "nav", "footer", "aside", "form", "header"):
        for node in tree.css(sel):
            node.decompose()
    candidates: list[str] = []
    for sel in ("article", "main", '[role="main"]', ".entry-content",
                ".post-content", ".article-body", ".content", "body"):
        node = tree.css_first(sel)
        if node is None:
            continue
        t = node.text(separator="\n", strip=True)
        if t:
            candidates.append(t)
    text = max(candidates, key=len) if candidates else ""
    # Collapse runs of blank lines
    out_lines: list[str] = []
    blank = 0
    for line in text.splitlines():
        if line.strip():
            out_lines.append(line)
            blank = 0
        else:
            blank += 1
            if blank <= 1:
                out_lines.append("")
    return "\n".join(out_lines)[:MAX_TEXT]


def _playwright_text(url: str) -> str:
    try:
        with playwright_session() as (page, _ctx, _br):
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=12_000)
            except Exception:
                pass
            html = page.content()
        return _readable(html)
    except Exception as e:
        print(f"  [playwright] {url}: {e}", flush=True)
        return ""


def fetch_readable(url: str) -> str:
    """Get readable article text. httpx → Playwright fallback if blocked/thin."""
    status, html = _httpx_get(url)
    text = _readable(html) if html else ""
    if status in RETRYABLE or len(text) < MIN_TEXT:
        print(f"  [fetch] httpx={status} text={len(text)}; trying playwright {url}", flush=True)
        text = _playwright_text(url)
    return text


# -- Serper -----------------------------------------------------------------

def serper_search(query: str, *, num: int = 10) -> list[dict]:
    """Web search via Serper. Returns `organic` results (list of dicts)."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print("  [serper] SERPER_API_KEY missing; skipping", flush=True)
        return []
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num, "gl": "us", "hl": "en"},
            )
        if r.status_code != 200:
            print(f"  [serper] {r.status_code} for '{query}'", flush=True)
            return []
        return r.json().get("organic", []) or []
    except httpx.HTTPError as e:
        print(f"  [serper] {query}: {e}", flush=True)
        return []
