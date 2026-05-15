"""
Helper used by all prose-list modules (Eater / Bon App / Esquire / VinePair / etc.).

Sources can supply EITHER:
  - article_urls: a fixed list of (url, hint) pairs. Used when URLs are stable.
  - search_queries: a list of (query, hint) pairs that we resolve via Serper
    Web Search and then run LLM extraction over the top N results. Used when
    URLs change yearly (Eater best-new lists, etc.).

Both can be combined; results are unioned and de-duplicated by source URL.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from awards._lib import to_dataframe, normalize_state
from awards.llm_extract import extract_businesses_from_url, extract_businesses_from_text

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def _serper_search(query: str, *, num: int = 10) -> list[dict]:
    """Plain Serper web-search API. Returns the `organic` results."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print("  [editorial] SERPER_API_KEY missing; skipping search", flush=True)
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
        print(f"  [editorial] serper error for '{query}': {e}", flush=True)
        return []


def _filter_results(results: list[dict], *, domain_allow: list[str] | None,
                    keyword_block: list[str]) -> list[dict]:
    out = []
    for r in results:
        link = r.get("link", "") or ""
        title = (r.get("title", "") or "").lower()
        if not link:
            continue
        if domain_allow and not any(d in link for d in domain_allow):
            continue
        if any(b in title for b in keyword_block):
            continue
        out.append(r)
    return out


def scrape_articles(
    *,
    source_slug: str,
    tier: int,
    business_type: str,
    article_urls: list[tuple[str, str]] | None = None,
    search_queries: list[tuple[str, str]] | None = None,
    search_domains: list[str] | None = None,
    search_keyword_block: list[str] | None = None,
    distinction_default: str,
    max_per_query: int = 4,
    snippet_fallback: bool = True,
) -> pd.DataFrame:
    """
    Run LLM extraction over editorial articles surfaced from search or static URLs.

    snippet_fallback: when True, if a search result's article URL produces 0 rows
    (because the publisher blocks bots, returns 404, etc.), the function will
    aggregate the search-result snippets+titles and run LLM extraction on the
    snippet text. Cuts through Cloudflare/WAF-protected sources where snippets
    still leak the business names.
    """
    rows: list[dict] = []
    seen_urls: set[str] = set()
    article_urls = article_urls or []
    search_queries = search_queries or []
    search_keyword_block = search_keyword_block or []

    def _record(items: list[dict], *, src_url: str) -> int:
        for r in items:
            rows.append({
                "source": source_slug,
                "tier": tier,
                "business_type": business_type,
                "name": r["name"],
                "city": r["city"],
                "state": normalize_state(r["state"]),
                "country": "us",
                "distinction": r.get("distinction") or distinction_default,
                "year": "",
                "source_url": src_url,
                "blurb": r.get("blurb", ""),
            })
        return len(items)

    def _consume(url: str, hint: str) -> int:
        if not url or url in seen_urls:
            return 0
        seen_urls.add(url)
        items = extract_businesses_from_url(url, hint=hint)
        return _record(items, src_url=url)

    # 1) Static URLs first.
    for url, hint in article_urls:
        n = _consume(url, hint)
        print(f"    +{n} from {url}", flush=True)

    # 2) Search-discovered URLs.
    for q, hint in search_queries:
        raw_results = _serper_search(q)
        results = _filter_results(raw_results, domain_allow=search_domains,
                                  keyword_block=search_keyword_block)
        results = results[:max_per_query]
        if not results:
            print(f"    [search] no usable results for '{q}'", flush=True)
            continue
        print(f"    [search] '{q}': {len(results)} candidate URLs", flush=True)
        per_query_rows_before = len(rows)
        for r in results:
            url = r.get("link") or ""
            n = _consume(url, hint)
            print(f"      +{n} from {url}", flush=True)
            time.sleep(0.4)

        # Snippet fallback: if this query produced 0 rows from articles, try the
        # snippets directly. Useful for Cloudflare-blocked sources (Wine Enthusiast).
        if snippet_fallback and len(rows) == per_query_rows_before:
            blob = _build_snippet_blob(results)
            if len(blob) >= 200:
                print(f"    [snippet-fallback] '{q}': {len(blob)} chars to LLM", flush=True)
                items = extract_businesses_from_text(
                    blob,
                    source_url=results[0].get("link", "") if results else "",
                    hint=hint + " (Source: search-result snippets — names may appear as comma- or bullet-separated lists; extract every business named.)",
                )
                added = _record(items, src_url=results[0].get("link", "") if results else "")
                print(f"      +{added} from snippet fallback", flush=True)

    return to_dataframe(rows)


def _build_snippet_blob(results: list[dict]) -> str:
    parts = []
    for r in results:
        title = (r.get("title") or "").strip()
        snip = (r.get("snippet") or "").strip()
        link = r.get("link", "")
        if title or snip:
            parts.append(f"[{link}]\n{title}\n{snip}")
    return "\n\n".join(parts)
