"""
Shared engine for trigger-phrase signal lanes.

Every lane in `signals/<slug>.py` finds businesses with a *timely reason to
buy* (an existing club, a manual preorder workflow, sold-out demand, fresh
press) rather than just a category match. Strategy: docs/SIGNALS.md.

The phrase lanes all run the same pipeline:

  1. Serper Web search:  "<trigger phrase>" <vertical keyword> [city]
  2. Drop platform/press/marketplace domains — we want the merchant's own site
  3. Group hits by registered domain, keeping the best evidence snippet
  4. Verify (default on): fetch the page, confirm the trigger phrase is
     actually present, and extract business name + city/state from the page
  5. Emit rows in SIGNAL_SCHEMA (canonical schema + trigger evidence columns)

Per-source CSVs land in output/signals/, master union in
output/signals_all_<YYYYMMDD>.csv (see discover_signals.py).
"""
from __future__ import annotations

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from awards._lib import (  # noqa: E402
    SCHEMA,
    fetch_html,
    make_row,
    normalize_state,
)
from config import CHAIN_KEYWORDS, LIQUOR_KEYWORDS, PRESS_DOMAINS, CITIES  # noqa: E402

load_dotenv(dotenv_path=ROOT / ".env")

OUTPUT_DIR = ROOT / "output" / "signals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Canonical award/directory schema plus the trigger evidence sales needs to
# reference in outbound ("saw you run a meat share…").
SIGNAL_SCHEMA: list[str] = SCHEMA + ["trigger", "evidence_url", "evidence_snippet"]

# Vertical keyword → canonical business_type (values of config.BUSINESS_TYPE_MAP).
# Each lane picks the verticals that make sense for its trigger.
VERTICAL_KEYWORDS: dict[str, list[str]] = {
    "wine":             ["wine shop", "wine store", "bottle shop"],
    "butcher":          ["butcher shop", "butcher", "meat market"],
    "bakery":           ["bakery", "bread bakery"],
    "cheese":           ["cheese shop", "cheesemonger"],
    "deli":             ["deli", "delicatessen"],
    "specialty_grocer": ["specialty grocer", "specialty food shop", "provisions"],
    "neighbourhood_restaurant": ["restaurant"],
}

# Domains that can never be a merchant's own website: marketplaces,
# aggregators, social, press, big-box. Subdomains match too.
PLATFORM_DOMAINS: set[str] = {
    # social / video / community
    "instagram.com", "facebook.com", "twitter.com", "x.com", "tiktok.com",
    "youtube.com", "linkedin.com", "pinterest.com", "reddit.com",
    "nextdoor.com", "threads.net",
    # reviews / listings
    "yelp.com", "tripadvisor.com", "google.com", "mapquest.com",
    "foursquare.com", "zomato.com", "wanderlog.com", "restaurantji.com",
    "birdeye.com", "menupix.com", "allmenus.com", "zmenu.com",
    # ordering / reservation platforms (merchant pages, but name/city
    # extraction is unreliable — revisit as a dedicated lane)
    "doordash.com", "grubhub.com", "ubereats.com", "seamless.com",
    "postmates.com", "caviar.com", "toasttab.com", "exploretock.com",
    "opentable.com", "resy.com", "squareup.com", "square.site",
    "clover.com", "chownow.com", "slicelife.com",
    # marketplaces / big-box
    "goldbelly.com", "amazon.com", "etsy.com", "walmart.com", "costco.com",
    "wholefoodsmarket.com", "target.com", "instacart.com", "totalwine.com",
    "drizly.com", "vivino.com", "wine.com",
    # link-in-bio / newsletter / generic hosting
    "linktr.ee", "beacons.ai", "campsite.bio", "substack.com", "medium.com",
    "mailchi.mp", "eventbrite.com", "groupon.com", "wikipedia.org",
    "yellowpages.com", "bbb.org", "indeed.com", "glassdoor.com",
}
PLATFORM_DOMAINS |= set(PRESS_DOMAINS)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

VERIFY_THREADS = 10


# ---------------------------------------------------------------- Serper

def serper_search(query: str, *, num: int = 20, search_type: str = "search",
                  tbs: str | None = None, max_retries: int = 3) -> list[dict]:
    """Serper Web ('search') or News ('news') query. Returns result dicts
    with title/link/snippet (web) or title/link/snippet/date (news)."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print("  [signals] SERPER_API_KEY not set — skipping search", flush=True)
        return []
    payload: dict = {"q": query, "num": num, "gl": "us", "hl": "en"}
    if tbs:
        payload["tbs"] = tbs
    for attempt in range(max_retries):
        try:
            r = requests.post(
                f"https://google.serper.dev/{search_type}",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("news" if search_type == "news" else "organic", []) or []
        except requests.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (400, 429) and attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            print(f"  [signals] serper error on {query!r}: {e}", flush=True)
            return []
    return []


# ---------------------------------------------------------------- filters

def registered_domain(url: str) -> str:
    """'https://www.foowines.com/club' -> 'foowines.com'. Best-effort, no PSL."""
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    host = host.removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # Handle common two-part TLDs (shopify-style custom domains are rare here)
    if parts[-2] in {"co", "com", "org", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_platform_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in PLATFORM_DOMAINS)


def is_chain_name(name: str) -> bool:
    low = (name or "").lower()
    return any(kw in low for kw in CHAIN_KEYWORDS)


def is_liquor_name(name: str) -> bool:
    low = (name or "").lower()
    return any(kw in low for kw in LIQUOR_KEYWORDS)


# ---------------------------------------------------------------- page verify

_TITLE_NOISE = re.compile(
    r"\b(club|subscription|membership|members?|subscribe|join|order|preorder|"
    r"pre-order|shop online|sold out|waitlist|sign ?up|home|welcome)\b", re.I)

_CITY_STATE_ZIP = re.compile(
    r"([A-Z][A-Za-z.'\- ]{2,30}),\s*([A-Z]{2})\.?\s+\d{5}")


def extract_name_from_html(html: str, domain: str) -> str:
    """Business name from og:site_name, falling back to the cleanest <title>
    segment (the one with the fewest commerce words), then the domain."""
    m = re.search(r'property=["\']og:site_name["\'][^>]*?content=("|\')(.*?)\1', html)
    if not m:
        m = re.search(r'content=("|\')(.*?)\1[^>]*?property=["\']og:site_name', html)
    if m and m.group(2).strip():
        return m.group(2).strip()

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        segments = [s.strip() for s in re.split(r"\s*[|–—\-:·]{1,2}\s+", title) if s.strip()]
        if segments:
            segments.sort(key=lambda s: (len(_TITLE_NOISE.findall(s)), len(s)))
            candidate = segments[0]
            if 2 <= len(candidate) <= 60:
                return candidate
    return domain.rsplit(".", 1)[0].replace("-", " ").title()


def extract_city_state(html: str) -> tuple[str, str]:
    """Best-effort 'City, ST 12345' scan over the raw page."""
    m = _CITY_STATE_ZIP.search(html)
    if not m:
        return "", ""
    return m.group(1).strip(), normalize_state(m.group(2))


def verify_candidate(candidate: dict, phrases: list[str]) -> dict | None:
    """Fetch the evidence page; require one of the trigger phrases on-page.
    Enriches the candidate with name/city/state pulled from the page."""
    html = fetch_html(candidate["evidence_url"], retries=2)
    if not html:
        return None
    low = html.lower()
    matched = next((p for p in phrases if p.lower() in low), None)
    if matched is None:
        return None
    candidate = dict(candidate)
    candidate["trigger"] = matched
    candidate["name"] = extract_name_from_html(html, candidate["domain"])
    city, state = extract_city_state(html)
    candidate["city"], candidate["state"] = city, state
    return candidate


# ---------------------------------------------------------------- phrase lane

def build_queries(triggers_by_type: dict[str, list[str]], *,
                  cities: int = 0) -> list[tuple[str, str, str]]:
    """(business_type, trigger_phrase, full_query) for every combination."""
    city_pool = CITIES[:cities] if cities > 0 else [None]
    out: list[tuple[str, str, str]] = []
    for btype, phrases in triggers_by_type.items():
        for keyword in VERTICAL_KEYWORDS.get(btype, [btype.replace("_", " ")]):
            for phrase in phrases:
                for city in city_pool:
                    q = f'"{phrase}" {keyword}'
                    if city:
                        q += f' "{city.split(",")[0]}"'
                    out.append((btype, phrase, q))
    return out


def phrase_lane_scrape(
    *,
    slug: str,
    lane_label: str,
    triggers_by_type: dict[str, list[str]],
    extra_onpage_phrases: list[str] | None = None,
    limit: int = 0,
    cities: int = 0,
    verify: bool = True,
    dry_run: bool = False,
    num_results: int = 20,
) -> pd.DataFrame:
    """Run the shared phrase-lane pipeline. See module docstring for stages.

    extra_onpage_phrases: accepted as on-page verification evidence in
    addition to the searched phrases (synonyms that confirm the trigger).
    """
    queries = build_queries(triggers_by_type, cities=cities)
    if limit > 0:
        queries = queries[:limit]
    print(f"  {len(queries)} Serper queries", flush=True)

    if dry_run:
        for _, _, q in queries:
            print(f"    DRY RUN: {q}", flush=True)
        return pd.DataFrame(columns=SIGNAL_SCHEMA)

    # Stage 1-3: search, filter platforms, group by domain
    by_domain: dict[str, dict] = {}
    for btype, phrase, q in queries:
        for hit in serper_search(q, num=num_results):
            url = hit.get("link", "")
            domain = registered_domain(url)
            if not domain or is_platform_domain(domain):
                continue
            if domain in by_domain:
                continue
            by_domain[domain] = {
                "domain": domain,
                "business_type": btype,
                "trigger": phrase,
                "evidence_url": url,
                "evidence_snippet": (hit.get("snippet") or "")[:300],
                "query": q,
                "title": hit.get("title", ""),
            }
    print(f"  {len(by_domain)} candidate domains after platform filter", flush=True)

    # Stage 4: verify on-page (concurrent)
    all_phrases = sorted({p for ps in triggers_by_type.values() for p in ps})
    all_phrases += extra_onpage_phrases or []
    candidates = list(by_domain.values())
    verified: list[dict] = []
    if verify and candidates:
        with ThreadPoolExecutor(max_workers=VERIFY_THREADS) as pool:
            futures = {pool.submit(verify_candidate, c, all_phrases): c for c in candidates}
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                except Exception:
                    result = None
                if result:
                    verified.append(result)
        print(f"  {len(verified)} verified on-page (of {len(candidates)})", flush=True)
    else:
        # Unverified: name falls back to the search-result title / domain.
        for c in candidates:
            c = dict(c)
            c["name"] = c["title"] or c["domain"]
            c["city"] = c["state"] = ""
            verified.append(c)

    # Stage 5: rows
    rows = []
    for c in verified:
        if is_chain_name(c["name"]):
            continue
        if c["business_type"] == "wine" and is_liquor_name(c["name"]):
            continue
        row = make_row(
            source=slug,
            tier=1,
            business_type=c["business_type"],
            name=c["name"],
            city=c.get("city", ""),
            state=c.get("state", ""),
            distinction=lane_label,
            source_url=f"https://{c['domain']}",
            blurb=c.get("evidence_snippet", ""),
        )
        row["trigger"] = c.get("trigger", "")
        row["evidence_url"] = c.get("evidence_url", "")
        row["evidence_snippet"] = c.get("evidence_snippet", "")
        rows.append(row)
    return to_signal_dataframe(rows)


# ---------------------------------------------------------------- dataframe io

def to_signal_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=SIGNAL_SCHEMA)
    for col in SIGNAL_SCHEMA:
        if col not in df.columns:
            df[col] = ""
    return df[SIGNAL_SCHEMA]


def dedupe_signals(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (source_url domain, name) — a domain can only be one lead
    within a lane."""
    if df.empty:
        return df
    key = (df["source_url"].fillna("").str.lower().str.strip()
           + "||" + df["name"].fillna("").str.lower().str.strip())
    return (df.assign(_k=key).drop_duplicates("_k", keep="first")
            .drop(columns="_k").reset_index(drop=True))
