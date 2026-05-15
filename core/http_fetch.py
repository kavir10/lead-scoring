"""
HTTP fetching, readable-text extraction, Playwright fallback, Serper search.

Two fetch backends are exposed because both are used today:

  httpx_get(url, ...)        modern, used by best_wine_shops/fetch.py
  requests_get_html(url, ...) requests-based, used by awards/_lib.fetch_html
                              (kept for callers that already use it)

`fetch_readable(url)` is the smart wrapper: httpx → Playwright fallback when
blocked or text too thin.

`playwright_session(...)` is a contextmanager yielding (page, context,
browser). Handles WAF JS challenges. Accepts cookies for paywalled sources.

`readable_text_selectolax(html)` / `readable_text_bs4(html)` reduce HTML to
the richest container's text content. Two parsers because both are used
already; pick whichever fits.

`serper_search(query, ...)` posts to Serper's web search endpoint; returns
the `organic` results list.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any

import httpx
import requests
from selectolax.parser import HTMLParser


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
RETRYABLE: set[int] = {403, 429, 502, 503, 520, 522}

MIN_TEXT = 400         # below this we assume the fetch is junk/blocked
MAX_TEXT = 60_000      # cap passed to LLM callers


def httpx_get(url: str, *, timeout: int = 25, retries: int = 3) -> tuple[int, str]:
    """GET via httpx with UA + retries. Returns (status_code, html).
    status_code=0 on transport error; '' html when status non-200 or retried out.
    """
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


def requests_get_html(url: str, *, timeout: int = 30, retries: int = 3, sleep: float = 1.5) -> str:
    """GET via requests; returns text or '' on failure. Kept for callers that
    already use this signature (awards/_lib.fetch_html)."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": UA, "Accept-Language": "en-US,en"},
                timeout=timeout,
                allow_redirects=True,
            )
            if r.status_code == 200:
                return r.text
            if r.status_code in RETRYABLE:
                time.sleep(sleep * (attempt + 1))
                continue
            print(f"  [http {r.status_code}] {url}", flush=True)
            return ""
        except requests.RequestException as e:
            last_exc = e
            time.sleep(sleep * (attempt + 1))
    if last_exc:
        print(f"  [http error] {url}: {last_exc}", flush=True)
    return ""


def readable_text_selectolax(html: str, *, max_chars: int = MAX_TEXT) -> str:
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
    return "\n".join(out_lines)[:max_chars]


def readable_text_bs4(html: str, *, max_chars: int = MAX_TEXT) -> str:
    """BeautifulSoup-based readable-text extraction. Use when selectolax isn't
    a dependency in the caller (or for compatibility with existing code)."""
    if not html:
        return ""
    import re

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "header"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text[:max_chars]


@contextmanager
def playwright_session(*, headed: bool = False, cookies: list[dict] | None = None):
    """Yields (page, context, browser). Handles WAF JS challenges.
    `cookies` (Playwright JSON format) optional for paywalled sources."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not headed)
    context = browser.new_context(
        user_agent=UA, locale="en-US", viewport={"width": 1280, "height": 900}
    )
    if cookies:
        context.add_cookies(cookies)
    page = context.new_page()
    try:
        yield page, context, browser
    finally:
        try:
            browser.close()
        finally:
            pw.stop()


def fetch_readable(url: str, *, cookies: list[dict] | None = None, min_text: int = MIN_TEXT) -> str:
    """httpx -> Playwright fallback. Returns readable text or ''."""
    status, html = httpx_get(url)
    text = readable_text_selectolax(html) if html else ""
    if status in RETRYABLE or len(text) < min_text:
        print(f"  [fetch] httpx={status} text={len(text)}; trying playwright {url}", flush=True)
        try:
            with playwright_session(cookies=cookies) as (page, _ctx, _br):
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12_000)
                except Exception:
                    pass
                html2 = page.content()
            text = readable_text_selectolax(html2)
        except Exception as e:
            print(f"  [playwright] {url}: {e}", flush=True)
    return text


def serper_search(query: str, *, num: int = 10) -> list[dict[str, Any]]:
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
