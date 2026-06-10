"""
Reddit customer-language mining (ideas #43, #44, #16 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Searches Reddit's public JSON API for the phrases customers use about
supply-constrained local favorites ("always sells out", "worth the drive",
"impossible to get a reservation"), then Claude extracts the named
businesses from each thread. This catches small-market local dominance that
review/follower counts miss (docs/ICP.md: don't DQ small-market leads on
raw volume), and the thread itself is sales-ready evidence in the
customer's own words.

Best-effort: Reddit rate-limits unauthenticated JSON aggressively, and the
LLM step needs ANTHROPIC_API_KEY. `limit` caps threads sent to Claude.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from awards._lib import make_row
from signals._lib import SIGNAL_SCHEMA, UA, to_signal_dataframe

# (search phrase, vertical hint, business_type for extracted rows)
SEARCHES: list[tuple[str, str, str]] = [
    ("always sells out", "bakery", "bakery"),
    ("always sells out", "butcher", "butcher"),
    ("worth the drive", "bakery", "bakery"),
    ("worth the drive", "butcher shop", "butcher"),
    ("worth the drive", "wine shop", "wine"),
    ("hidden gem", "cheese shop", "cheese"),
    ("hidden gem", "wine shop", "wine"),
    ("impossible to get a reservation", "restaurant", "neighbourhood_restaurant"),
    ("line out the door", "bakery", "bakery"),
    ("best butcher in", "", "butcher"),
]

DEFAULT_THREAD_CAP = 40
MIN_THREAD_CHARS = 200


def _reddit_search(query: str, *, max_retries: int = 3) -> list[dict]:
    """Public JSON search. Returns post data dicts ({} on failure)."""
    for attempt in range(max_retries):
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "limit": 25, "sort": "relevance", "t": "year"},
                headers={"User-Agent": UA},
                timeout=20,
            )
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            children = r.json().get("data", {}).get("children", [])
            return [c.get("data", {}) for c in children]
        except (requests.RequestException, ValueError) as e:
            print(f"  [reddit_demand] search failed for {query!r}: {e}", flush=True)
            time.sleep(2 * (attempt + 1))
    return []


def scrape(*, limit: int = 0, dry_run: bool = False, **_ignored) -> pd.DataFrame:
    thread_cap = limit if limit > 0 else DEFAULT_THREAD_CAP

    if dry_run:
        for phrase, vertical, _ in SEARCHES:
            print(f'    DRY RUN (reddit): "{phrase}" {vertical}'.rstrip(), flush=True)
        return pd.DataFrame(columns=SIGNAL_SCHEMA)

    # Collect threads with enough text to be worth an LLM call.
    threads: list[dict] = []
    seen_ids: set[str] = set()
    for phrase, vertical, btype in SEARCHES:
        query = f'"{phrase}" {vertical}'.strip()
        for post in _reddit_search(query):
            pid = post.get("id", "")
            text = f"{post.get('title', '')}\n\n{post.get('selftext', '')}".strip()
            if not pid or pid in seen_ids or len(text) < MIN_THREAD_CHARS:
                continue
            seen_ids.add(pid)
            threads.append({
                "text": text[:8000],
                "permalink": "https://www.reddit.com" + post.get("permalink", ""),
                "subreddit": post.get("subreddit", ""),
                "phrase": phrase,
                "business_type": btype,
            })
        time.sleep(1.5)  # be polite to the unauthenticated endpoint
        if len(threads) >= thread_cap:
            break
    threads = threads[:thread_cap]
    print(f"  {len(threads)} Reddit threads to extract", flush=True)

    from awards.llm_extract import extract_businesses_from_text

    rows: list[dict] = []
    for t in threads:
        try:
            extracted = extract_businesses_from_text(
                t["text"],
                source_url=t["permalink"],
                hint=(f"This is a Reddit thread from r/{t['subreddit']}. Extract "
                      f"specific food businesses mentioned positively by name. "
                      f"The subreddit name often implies the city (e.g. FoodNYC "
                      f"= New York). Skip generic mentions and chains."),
            )
        except Exception as e:
            print(f"  [reddit_demand] extract failed for {t['permalink']}: {e}", flush=True)
            continue
        for biz in extracted:
            row = make_row(
                source="reddit_demand",
                tier=2,
                business_type=t["business_type"],
                name=biz.get("name", ""),
                city=biz.get("city", ""),
                state=biz.get("state", ""),
                distinction="Reddit customer-demand mention",
                source_url=t["permalink"],
                blurb=biz.get("blurb", ""),
            )
            row["trigger"] = f'reddit: "{t["phrase"]}" (r/{t["subreddit"]})'
            row["evidence_url"] = t["permalink"]
            row["evidence_snippet"] = (biz.get("blurb") or t["text"][:300])[:300]
            rows.append(row)
    return to_signal_dataframe(rows)
