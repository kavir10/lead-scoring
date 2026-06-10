"""
Fresh-press momentum leads (ideas #8, #38 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Serper News for the last month's "best of" lists and award announcements,
then Claude (awards/llm_extract.py) pulls the named businesses out of each
article. Fresh press creates a demand spike, and a demand spike creates the
operational pressure that makes the Table22 pitch land — recency is the
whole point of this lane (the awards/ pipeline covers the evergreen lists).

LLM extraction is best-effort: requires ANTHROPIC_API_KEY, costs a Claude
call per article. `limit` caps articles processed.
"""
from __future__ import annotations

import pandas as pd

from awards._lib import make_row
from signals._lib import SIGNAL_SCHEMA, serper_search, to_signal_dataframe

# (query, business_type for extracted rows)
NEWS_QUERIES: list[tuple[str, str]] = [
    ('"best new restaurants"',        "neighbourhood_restaurant"),
    ('"best restaurants" 2026',       "neighbourhood_restaurant"),
    ('"best bakeries"',               "bakery"),
    ('"best butcher"',                "butcher"),
    ('"best wine shops"',             "wine"),
    ('"best cheese shops"',           "cheese"),
    ('james beard award semifinalists', "neighbourhood_restaurant"),
    ('good food awards winners',      "specialty_grocer"),
    ('michelin guide new stars',      "neighbourhood_restaurant"),
]

MAX_ARTICLES_PER_QUERY = 5


def scrape(*, limit: int = 0, dry_run: bool = False, **_ignored) -> pd.DataFrame:
    if dry_run:
        for q, _ in NEWS_QUERIES:
            print(f"    DRY RUN (news, last month): {q}", flush=True)
        return pd.DataFrame(columns=SIGNAL_SCHEMA)

    # Collect last-month articles per query.
    articles: list[tuple[str, str, str]] = []  # (url, title, business_type)
    seen: set[str] = set()
    for query, btype in NEWS_QUERIES:
        for hit in serper_search(query, num=10, search_type="news", tbs="qdr:m"):
            url = hit.get("link", "")
            if not url or url in seen:
                continue
            seen.add(url)
            articles.append((url, hit.get("title", ""), btype))
            if len([a for a in articles if a[2] == btype]) >= MAX_ARTICLES_PER_QUERY:
                break
    if limit > 0:
        articles = articles[:limit]
    print(f"  {len(articles)} fresh articles to extract", flush=True)

    from awards.llm_extract import extract_businesses_from_url

    rows: list[dict] = []
    for url, title, btype in articles:
        try:
            extracted = extract_businesses_from_url(
                url,
                hint=("This is a recent news article or 'best of' list about food "
                      "businesses. Extract only specific, named businesses being "
                      "praised or awarded."),
            )
        except Exception as e:
            print(f"  [press_momentum] extract failed for {url}: {e}", flush=True)
            continue
        for biz in extracted:
            row = make_row(
                source="press_momentum",
                tier=1,
                business_type=btype,
                name=biz.get("name", ""),
                city=biz.get("city", ""),
                state=biz.get("state", ""),
                distinction="Fresh press mention (last 30 days)",
                source_url=url,
                blurb=biz.get("blurb", "") or biz.get("distinction", ""),
            )
            row["trigger"] = f"press: {title[:120]}"
            row["evidence_url"] = url
            row["evidence_snippet"] = (biz.get("blurb") or "")[:300]
            rows.append(row)
        print(f"  +{len(extracted):>3}  {title[:80]}", flush=True)
    return to_signal_dataframe(rows)
