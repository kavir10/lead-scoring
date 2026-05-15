"""
Orchestration: seed URLs + Serper queries -> readable text -> LLM extract ->
filter & tag -> DataFrame.
"""
from __future__ import annotations

import time

import pandas as pd

from awards._lib import SCHEMA, dedupe, filter_us, to_dataframe

from . import filters
from .extractor import extract_from_text
from .fetch import fetch_readable, serper_search
from .sources import SEED_URLS, SEARCH_QUERIES

SOURCE_SLUG = "best_wine_shops"
TIER = 1
BUSINESS_TYPE = "wine_store"
DEFAULT_DISTINCTION = "Best Wine Shops editorial mention"

# Extended schema = canonical SCHEMA + two boolean tag columns.
EXT_SCHEMA: list[str] = SCHEMA + ["is_large_indie", "is_online_only"]


def _build_snippet_blob(results: list[dict]) -> str:
    parts: list[str] = []
    for r in results:
        title = (r.get("title") or "").strip()
        snip = (r.get("snippet") or "").strip()
        link = r.get("link", "")
        if title or snip:
            parts.append(f"[{link}]\n{title}\n{snip}")
    return "\n\n".join(parts)


def _row_from(item: dict, *, src_url: str) -> dict:
    name = item["name"]
    return {
        "source": SOURCE_SLUG,
        "tier": TIER,
        "business_type": BUSINESS_TYPE,
        "name": name,
        "city": item.get("city", ""),
        "state": item.get("state", ""),
        "country": item.get("country", "us") or "us",
        "distinction": item.get("distinction") or DEFAULT_DISTINCTION,
        "year": "",
        "source_url": src_url,
        "blurb": item.get("blurb", ""),
        "is_large_indie": bool(item.get("is_large_indie", False)) or filters.is_large_indie(name),
        "is_online_only": bool(item.get("is_online_only", False)) or filters.is_online_only(name),
    }


def _extract_url(url: str, hint: str, *, seen: set[str]) -> list[dict]:
    if not url or url in seen:
        return []
    seen.add(url)
    text = fetch_readable(url)
    if len(text) < 400:
        print(f"  [skip] readable text too thin ({len(text)} chars) for {url}", flush=True)
        return []
    print(f"  [llm] {url} ({len(text)} chars)", flush=True)
    return extract_from_text(text, source_url=url, hint=hint)


def scrape(
    *,
    use_seeds: bool = True,
    use_search: bool = True,
    max_per_query: int = 5,
    dry_run: bool = False,
) -> pd.DataFrame:
    rows: list[dict] = []
    seen: set[str] = set()

    if dry_run:
        print(f"[dry-run] would fetch {len(SEED_URLS)} seed URLs and run "
              f"{len(SEARCH_QUERIES)} Serper queries (max {max_per_query} per query).",
              flush=True)
        return _to_df([])

    # 1) Seed URLs
    if use_seeds:
        print(f"\n=== Seeds ({len(SEED_URLS)}) ===", flush=True)
        for url, hint in SEED_URLS:
            items = _extract_url(url, hint, seen=seen)
            print(f"    +{len(items)} from {url}", flush=True)
            for it in items:
                rows.append(_row_from(it, src_url=url))
            time.sleep(0.3)

    # 2) Serper-discovered articles
    if use_search:
        print(f"\n=== Serper queries ({len(SEARCH_QUERIES)}) ===", flush=True)
        for q, hint in SEARCH_QUERIES:
            results = serper_search(q, num=max_per_query)[:max_per_query]
            if not results:
                print(f"  [search] no results for '{q}'", flush=True)
                continue
            print(f"  [search] '{q}': {len(results)} candidates", flush=True)
            before = len(rows)
            for r in results:
                url = r.get("link") or ""
                items = _extract_url(url, hint, seen=seen)
                if items:
                    print(f"      +{len(items)} from {url}", flush=True)
                for it in items:
                    rows.append(_row_from(it, src_url=url))
                time.sleep(0.3)

            # Snippet fallback if every candidate article yielded nothing
            if len(rows) == before:
                blob = _build_snippet_blob(results)
                if len(blob) >= 200:
                    print(f"  [snippet-fallback] '{q}' ({len(blob)} chars)", flush=True)
                    src = results[0].get("link", "") if results else ""
                    items = extract_from_text(
                        blob,
                        source_url=src,
                        hint=hint + " (Input is concatenated search-result snippets; extract every shop named.)",
                    )
                    print(f"      +{len(items)} from snippet fallback", flush=True)
                    for it in items:
                        rows.append(_row_from(it, src_url=src))

    return _to_df(rows)


def _to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=EXT_SCHEMA)
    df = pd.DataFrame(rows)
    for col in EXT_SCHEMA:
        if col not in df.columns:
            df[col] = "" if col not in ("is_large_indie", "is_online_only") else False
    df = df[EXT_SCHEMA]

    # 1) US only
    df = filter_us(df)

    # 2) Hard chain filter
    if not df.empty:
        chain_mask = df["name"].fillna("").map(filters.is_chain)
        dropped = int(chain_mask.sum())
        if dropped:
            print(f"  [filter] dropped {dropped} chain-name rows", flush=True)
        df = df[~chain_mask].copy()

    # 3) Backstop tag pass (in case the LLM missed)
    if not df.empty:
        df["is_large_indie"] = df["is_large_indie"] | df["name"].fillna("").map(filters.is_large_indie)
        df["is_online_only"] = df["is_online_only"] | df["name"].fillna("").map(filters.is_online_only)

    # 4) Dedupe by (name, city) — `dedupe()` operates on SCHEMA cols only;
    # carry the tag cols by index alignment afterward.
    if not df.empty:
        deduped_core = dedupe(df[SCHEMA].copy())
        df = deduped_core.join(df[["is_large_indie", "is_online_only"]], how="left")
        df = df[EXT_SCHEMA]

    return df.reset_index(drop=True)
