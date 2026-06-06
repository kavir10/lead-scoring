"""
Fresh restaurant discovery via Serper Maps, seeded by trendy neighborhoods.

Each search is geo-biased to a trendy neighborhood (location field), not just a
city, on the proven hypothesis that ~56-64% of Table22 partners sit in trendy
neighborhoods (see research/trendy_neighborhoods/README.md).

ICP qualification follows docs/ICP.md (restaurant playbook + Appendix B cuisine
fit). It uses the Serper-observable subset of the must-haves only: partner type,
reviews, rating, price, cuisine. Reservation difficulty / IG / tenure are left to
a later enrichment pass.

This script does NOT read existing lead CSVs as source material. CID dedupe
against prior output is a separate step (scripts/dedupe_restaurants_by_cid.py).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CHAIN_KEYWORDS, SERPER_API_KEY, TYPE_TO_PARTNER_TYPE  # noqa: E402

OUTPUT_DIR = ROOT / "output"
ICP_PATH = ROOT / "docs" / "ICP.md"
DEFAULT_LOCATIONS = (
    ROOT
    / "research"
    / "trendy_neighborhoods"
    / "trendy_neighborhoods_top100_us_tiered_20260531.csv"
)

# --- Search queries (weighted). Destination-leaning queries carry more weight
#     because destination restaurants ~2x the AGMV of neighborhood ones. ---
RESTAURANT_QUERIES: list[tuple[str, int]] = [
    ("best restaurant", 10),
    ("fine dining", 12),
    ("tasting menu restaurant", 12),
    ("chef driven restaurant", 11),
    ("michelin restaurant", 11),
    ("james beard award restaurant", 10),
    ("farm to table restaurant", 10),
    ("popular restaurant", 8),
    ("best new restaurant", 9),
    ("date night restaurant", 8),
    ("hidden gem restaurant", 8),
    ("best italian restaurant", 9),
    ("wine bar restaurant", 9),
    ("best french restaurant", 8),
    ("mediterranean restaurant", 7),
    ("best seafood restaurant", 7),
]

# --- Cuisine fit (docs/ICP.md Appendix B), keyed on Google Maps `type`. ---
CORE_FIT_TYPES = {
    "Italian restaurant", "Northern Italian restaurant", "Southern Italian restaurant",
    "Sicilian restaurant", "French restaurant", "Modern French restaurant", "Brasserie",
    "Bistro", "Mediterranean restaurant", "Middle Eastern restaurant", "Israeli restaurant",
    "Lebanese restaurant", "Persian restaurant", "Turkish restaurant", "Greek restaurant",
    "Steak house", "Chophouse restaurant", "Japanese steakhouse", "French steakhouse restaurant",
    "New American restaurant", "Traditional American restaurant", "American restaurant",
    "Californian restaurant", "Pacific Northwest restaurant (US)", "Thai restaurant",
    "European restaurant", "Modern European restaurant", "Eastern European restaurant",
    "Tapas restaurant", "Tapas bar", "Spanish restaurant", "Basque restaurant",
    "Small plates restaurant", "Oyster bar restaurant", "Seafood restaurant", "Crab house",
}
EMERGING_FIT_TYPES = {
    "Korean restaurant", "Japanese restaurant", "Sushi restaurant", "Authentic Japanese restaurant",
    "Izakaya restaurant", "Chinese restaurant", "Hot pot restaurant", "Mexican restaurant",
    "Tex-Mex restaurant", "Vietnamese restaurant", "Filipino restaurant", "Barbecue restaurant",
    "Asian fusion restaurant", "Asian restaurant", "Pan-Asian restaurant", "Southeast Asian restaurant",
    "Fusion restaurant", "Eclectic restaurant", "Contemporary Louisiana restaurant",
    "Cajun restaurant", "Creole restaurant", "Soul food restaurant", "Southern restaurant (US)",
    "Indian restaurant", "Modern Indian restaurant", "Kosher restaurant", "Jewish restaurant",
}
LOWER_FIT_TYPES = {
    "Venezuelan restaurant", "Peruvian restaurant", "Brazilian restaurant", "Colombian restaurant",
    "Argentinian restaurant", "Cuban restaurant", "Latin American restaurant", "South American restaurant",
    "Pan-Latin restaurant", "Caribbean restaurant", "Ethiopian restaurant", "West African restaurant",
    "Pizza restaurant", "Breakfast restaurant", "Brunch restaurant", "Diner", "Family restaurant",
    "Lunch restaurant", "Dessert restaurant", "Vegan restaurant", "Vegetarian restaurant",
    "Health food restaurant",
}

# Name/query tokens that promote a lead toward the destination tier
# (docs/ICP.md Tier-1 definition: acclaimed, hard-to-book, chef-led, media-featured).
DESTINATION_SIGNALS = [
    "michelin", "james beard", "tasting menu", "omakase", "prix fixe", "chef driven",
    "chef-driven", "fine dining", "sought after", "michelin star", "michelin recommended",
]
ARTISANAL_SIGNALS = [
    "farm to table", "seasonal", "craft", "house made", "wood fired", "wine list",
    "sommelier", "osteria", "trattoria", "enoteca", "ristorante", "brasserie",
    "tavern", "supper", "kitchen & bar", "wine bar",
]

# Anti-ICP free-text rejects (docs/ICP.md disqualifiers).
TEXT_REJECT = [
    r"\bcatering\b", r"\bcaterer\b", r"\bfood truck\b", r"\bghost kitchen\b",
    r"\bcloud kitchen\b", r"\bdelivery only\b", r"\bconcession\b", r"\bcoming soon\b",
    r"\bfranchise\b", r"\bwinery\b", r"\bbrewery\b", r"\bbrewpub\b", r"\bdistillery\b",
    r"\bnight ?club\b", r"\bbanquet\b", r"\bbuffet\b", r"\bspeakeasy\b",
]

# Non-restaurant venue types: if any appear in the Google `types` list (primary
# or secondary) the row is a venue/producer/lodging, not a sit-down restaurant.
# (QA audit: hotels, wineries, banquet/event/wedding halls, breweries leaked in.)
# Note: bare "Bar"/"Pub" are intentionally NOT here — many real restaurants list a
# bar as a secondary type. A bar-PRIMARY type is already dropped via the type map.
VENUE_REJECT_TYPES = {
    "Banquet hall", "Event venue", "Wedding venue", "Winery", "Vineyard",
    "Hotel", "Resort hotel", "Lodge", "Casino", "Night club", "Brewery",
    "Brewpub", "Distillery", "Buffet restaurant", "Performing arts theater",
    "Country club", "Golf club", "Amusement park", "Banquet hall & event venue",
}

# Hotel / resort / institutional website hosts — a restaurant living on one of
# these domains is an in-house outlet, not an independent business (QA audit).
HOSPITALITY_DOMAINS = (
    "ritzcarlton.com", "marriott.com", "hyatt.com", "hilton.com", "fourseasons.com",
    "mandarinoriental.com", "peninsula.com", "disney.go.com", "disneyworld.disney.go.com",
    "bigcedar.com", "alyeskaresort.com", "eataly.com", "loewshotels.com",
    "omnihotels.com", "fairmont.com", "kimptonhotels.com", "encorebostonharbor.com",
    "mgmresorts.com", "caesars.com", "wynnlasvegas.com",
)

# Per-location franchise URL shapes. Plural /locations/<slug> is multi-location by
# definition; singular /location/<brand-city-state> (hyphenated) is the chain tell.
FRANCHISE_URL_RE = re.compile(r"/locations/[a-z0-9]|/location/[a-z0-9]+-[a-z0-9-]+", re.I)

# Upscale / regional restaurant chains absent from config.CHAIN_KEYWORDS (which is
# tuned for grocery/big-box). Scoped here so other pipelines are unaffected.
RESTAURANT_CHAINS = {
    "fleming's", "flemings", "stk steakhouse", "j. alexander", "j alexander",
    "culinary dropout", "north italia", "landry's", "landrys", "pappadeaux",
    "pappas", "oak steakhouse", "bourbon steak", "sullivan's steakhouse",
    "jeff ruby", "eddie merlot", "melting pot", "happy lamb", "hook & reel",
    "sam snead", "sam sneads",
    "hook and reel", "kincaid's", "kincaids", "bristol seafood", "del frisco",
    "the capital grille", "capital grille", "ruth's chris", "ruths chris",
    "morton's", "mortons the steakhouse", "ocean prime", "seasons 52",
    "cooper's hawk", "coopers hawk", "true food kitchen", "the cheesecake factory",
    "maggiano's", "maggianos", "the melting pot", "benihana", "p.f. chang",
    "pf chang", "fogo de chao", "texas de brazil", "sushi samba", "stk ",
}

# Food-shaped primary-type guard for the regional-cuisine salvage path.
FOODISH_RE = re.compile(
    r"\b(?:restaurant|steak\s?house|steakhouse|chophouse|bistro|brasserie|"
    r"trattoria|osteria|ristorante|izakaya|eatery|tavern|gastropub|grill|"
    r"diner|crab house|hot pot|noodle|ramen|sushi|tapas)\b",
    re.I,
)

PREMIUM_CITIES = {
    "New York", "Brooklyn", "Los Angeles", "San Francisco", "Chicago", "Boston",
    "Washington", "Seattle", "Portland", "Austin", "Denver", "Atlanta",
    "Nashville", "Miami", "Charleston", "New Orleans", "Philadelphia", "Minneapolis",
}

_rate_lock = threading.Lock()
_last_times: list[float] = []

# Lower-fit cuisines (pizza-first, breakfast/brunch, burgers, most Latin American /
# African — docs/ICP.md Appendix B "lower fit / experimental"; pizza-first is a
# near-DQ). Rejected by default; pass --keep-lower-fit to score-demote instead.
EXCLUDE_LOWER_FIT = True


@dataclass(frozen=True)
class SearchTask:
    query: str
    query_weight: int
    neighborhood: str
    city: str
    state: str

    @property
    def location(self) -> str:
        if self.neighborhood:
            return f"{self.neighborhood}, {self.city}, {self.state}"
        return f"{self.city}, {self.state}"


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def domain(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def parse_town_state(address: object) -> tuple[str, str]:
    text = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        match = re.match(r"^([A-Z]{2})\s*\d{0,5}$", parts[i])
        if match:
            return (parts[i - 1] if i else "", match.group(1))
    return ("", "")


def rate_limit(rps: int) -> None:
    with _rate_lock:
        now = time.monotonic()
        while _last_times and _last_times[0] < now - 1:
            _last_times.pop(0)
        if len(_last_times) >= rps:
            wait = _last_times[0] + 1 - now
            if wait > 0:
                time.sleep(wait)
        _last_times.append(time.monotonic())


def load_locations(path: Path, max_neighborhoods: int) -> list[tuple[str, str, str]]:
    df = pd.read_csv(path)
    required = {"city", "state", "neighborhood"}
    if not required.issubset(df.columns):
        raise SystemExit(f"{path} must include columns: city, state, neighborhood")
    locations: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        city = clean_text(row.get("city"))
        state = clean_text(row.get("state"))
        neighborhood = clean_text(row.get("neighborhood"))
        if not city or not state or not neighborhood:
            continue
        key = f"{neighborhood}|{city}|{state}".lower()
        if key in seen:
            continue
        seen.add(key)
        locations.append((neighborhood, city, state))
    return locations[:max_neighborhoods] if max_neighborhoods else locations


def search_serper(task: SearchTask, api_key: str, rps: int) -> list[dict]:
    rate_limit(rps)
    url = "https://google.serper.dev/maps"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "q": task.query,
        "location": f"{task.location}, United States",
        "gl": "us",
        "hl": "en",
        "num": 20,
    }
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            rows = []
            for place in resp.json().get("places", []):
                types = place.get("types") or []
                rows.append({
                    "source": "fresh_restaurant_serper_maps",
                    "search_query": task.query,
                    "query_weight": task.query_weight,
                    "search_neighborhood": task.neighborhood,
                    "search_city": task.city,
                    "search_state": task.state,
                    "search_location": task.location,
                    "name": clean_text(place.get("title")),
                    "address": clean_text(place.get("address")),
                    "rating": place.get("rating"),
                    "review_count": place.get("ratingCount", 0),
                    "google_type": clean_text(place.get("type")),
                    "google_types": ", ".join(types) if isinstance(types, list) else clean_text(types),
                    "phone": clean_text(place.get("phoneNumber")),
                    "website": clean_text(place.get("website")),
                    "price_level": clean_text(place.get("priceLevel")),
                    "latitude": place.get("latitude"),
                    "longitude": place.get("longitude"),
                    "cid": clean_text(place.get("cid")),
                })
            return rows
        except requests.RequestException:
            if attempt == 2:
                return []
            time.sleep(2 ** attempt)
    return []


_APOS_RE = re.compile(r"['’‘`]")
_RESTAURANT_CHAINS_STRIPPED = {_APOS_RE.sub("", c) for c in RESTAURANT_CHAINS}


def looks_like_chain(name: str) -> bool:
    lowered = name.lower()
    if any(keyword in lowered for keyword in CHAIN_KEYWORDS):
        return True
    # Strip apostrophes so curly/straight variants both match ("Fleming's" /
    # "Fleming’s" -> "flemings"). Keywords are stored apostrophe-free too.
    stripped = _APOS_RE.sub("", lowered)
    return any(keyword in stripped for keyword in _RESTAURANT_CHAINS_STRIPPED)


def classify(row: pd.Series) -> str:
    """Map the Google Maps type to a restaurant partner_type, or 'reject'.

    Returns destination_restaurant / neighbourhood_restaurant only. fast_casual
    and every non-restaurant type are rejected (deprioritized / off-ICP).
    """
    gtype = clean_text(row.get("google_type"))
    partner = TYPE_TO_PARTNER_TYPE.get(gtype, "__missing__")
    if partner in ("destination_restaurant", "neighbourhood_restaurant"):
        return partner
    if partner == "fast_casual":
        return "reject"
    if partner is None:
        return "reject"
    # google_type not in the map. Salvage regional cuisines Google labels with
    # types we don't enumerate (e.g. "Shanghainese restaurant") ONLY when the
    # primary type string is itself food-shaped, so non-food primaries like
    # "Recruiter" can't ride in on a noisy secondary `types` entry. Google's
    # primary `type` is authoritative; secondary types are noisy.
    if gtype and not FOODISH_RE.search(gtype):
        return "reject"
    for t in str(row.get("google_types", "")).split(","):
        mapped = TYPE_TO_PARTNER_TYPE.get(clean_text(t))
        if mapped in ("destination_restaurant", "neighbourhood_restaurant"):
            return mapped
    if gtype and FOODISH_RE.search(gtype):
        return "neighbourhood_restaurant"
    return "reject"


def cuisine_fit(gtype: str) -> str:
    if gtype in CORE_FIT_TYPES:
        return "core"
    if gtype in EMERGING_FIT_TYPES:
        return "emerging"
    if gtype in LOWER_FIT_TYPES:
        return "lower"
    return "neutral"


def rejection_reason(row: pd.Series) -> str:
    name = str(row.get("name", ""))
    website = str(row.get("website", "")).strip()
    combined = norm(f"{name} {row.get('google_type')} {row.get('google_types')} {website}")
    types_set = {clean_text(t) for t in str(row.get("google_types", "")).split(",") if t.strip()}
    types_set.add(clean_text(row.get("google_type")))
    if not name:
        return "no_name"
    if looks_like_chain(name):
        return "chain_keyword"
    if website and FRANCHISE_URL_RE.search(website):
        return "franchise_url"
    host = domain(website)
    if host and any(host == d or host.endswith("." + d) for d in HOSPITALITY_DOMAINS):
        return "hospitality_domain"
    if host.endswith(".edu"):
        return "institutional_domain"
    if types_set & VENUE_REJECT_TYPES:
        return "venue_type"
    if EXCLUDE_LOWER_FIT and cuisine_fit(clean_text(row.get("google_type"))) == "lower":
        return "lower_fit_cuisine"
    for pattern in TEXT_REJECT:
        if re.search(pattern, combined):
            return "anti_icp_text"
    if not website:
        return "missing_website"
    reviews = pd.to_numeric(row.get("review_count"), errors="coerce")
    if pd.isna(reviews) or reviews < 50:
        return "review_floor"
    rating = pd.to_numeric(row.get("rating"), errors="coerce")
    if pd.isna(rating) or rating < 4.2:
        return "rating_floor"
    if row.get("partner_type") == "reject":
        return "non_restaurant_type"
    return ""


def score_row(row: pd.Series) -> float:
    """SHAP-aligned ICP score. Partner type dominates (it's SHAP #1), then
    demand/quality proxies available from Serper, then cuisine fit (#10)."""
    partner = row["partner_type"]
    gtype = clean_text(row.get("google_type"))
    rating = pd.to_numeric(row.get("rating"), errors="coerce")
    reviews = pd.to_numeric(row.get("review_count"), errors="coerce")
    weight = pd.to_numeric(row.get("query_weight"), errors="coerce")
    rating = 0.0 if pd.isna(rating) else float(rating)
    reviews = 0.0 if pd.isna(reviews) else float(reviews)
    weight = 0.0 if pd.isna(weight) else float(weight)

    text = norm(f"{row.get('name')} {row.get('search_query')}")

    # Partner type (SHAP #1): destination ~2x neighborhood AGMV.
    score = 30.0 if partner == "destination_restaurant" else 16.0

    # Destination promotion from name/query acclaim signals.
    dest_hits = sum(1 for s in DESTINATION_SIGNALS if s in text)
    score += min(10.0, dest_hits * 4.0)
    if partner == "neighbourhood_restaurant" and dest_hits >= 1:
        score += 4.0  # acclaimed neighborhood spot leans destination

    # Demand / quality proxies.
    score += min(18.0, math.log1p(reviews) * 3.0)
    score += max(0.0, (rating - 4.0) * 14.0)
    score += weight

    # Cuisine fit (Appendix B).
    fit = cuisine_fit(gtype)
    score += {"core": 8.0, "emerging": 4.0, "neutral": 0.0, "lower": -6.0}[fit]

    # Premium positioning + market.
    score += 4.0 if str(row.get("price_level", "")).count("$") >= 3 else (
        2.0 if str(row.get("price_level", "")).count("$") == 2 else 0.0
    )
    if clean_text(row.get("city")) in PREMIUM_CITIES or clean_text(row.get("search_city")) in PREMIUM_CITIES:
        score += 4.0

    # Artisanal / brand-narrative signals (ICP dimension 3).
    score += min(6.0, sum(1.5 for s in ARTISANAL_SIGNALS if s in norm(row.get("name"))))

    return round(score, 2)


def build_tasks(locations: list[tuple[str, str, str]], max_queries: int) -> list[SearchTask]:
    queries = RESTAURANT_QUERIES[:max_queries] if max_queries else RESTAURANT_QUERIES
    return [
        SearchTask(query, weight, nb, city, state)
        for (nb, city, state) in locations
        for (query, weight) in queries
    ]


def filter_and_rank(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = raw.copy()
    parsed = raw["address"].apply(parse_town_state)
    raw["city"] = parsed.apply(lambda x: x[0])
    raw["state"] = parsed.apply(lambda x: x[1])
    raw["partner_type"] = raw.apply(classify, axis=1)
    raw["reject_reason"] = raw.apply(rejection_reason, axis=1)

    accepted = raw[raw["reject_reason"].eq("")].copy()
    if accepted.empty:
        return raw, accepted
    accepted["cuisine_fit"] = accepted["google_type"].apply(lambda g: cuisine_fit(clean_text(g)))
    accepted["icp_score"] = accepted.apply(score_row, axis=1)

    accepted["_domain"] = accepted["website"].apply(domain)
    accepted["_phone"] = accepted["phone"].astype(str).str.replace(r"\D+", "", regex=True)
    accepted["_name_city"] = accepted.apply(
        lambda r: f"{norm(r['name'])}|{norm(r['city'])}|{str(r['state']).upper()}", axis=1
    )
    accepted["_dedupe_key"] = accepted["_phone"].where(accepted["_phone"].str.len() >= 10, "")
    accepted["_dedupe_key"] = accepted["_dedupe_key"].where(
        accepted["_dedupe_key"].ne(""),
        accepted["_domain"].where(accepted["_domain"].ne(""), accepted["_name_city"]),
    )
    accepted = (
        accepted.sort_values(["icp_score", "review_count"], ascending=[False, False])
        .drop_duplicates("_dedupe_key", keep="first")
        .reset_index(drop=True)
    )

    # Multi-location chain collapse: distinct per-location phones survive the
    # phone-keyed dedupe above, but a chain shares one root domain across all of
    # them. >=4 rows on one domain is a chain (ICP allows 1-3 locations), so drop
    # the whole brand. (QA audit: J. Alexander's, Fleming's, STK leaked this way.)
    dom_counts = accepted["_domain"].replace("", pd.NA).value_counts()
    chain_domains = set(dom_counts[dom_counts >= 4].index)
    if chain_domains:
        before = len(accepted)
        accepted = accepted[~accepted["_domain"].isin(chain_domains)].reset_index(drop=True)
        print(f"Chain-domain collapse: dropped {before - len(accepted):,} rows across {len(chain_domains)} domains")
    return raw, accepted


def discover(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("SERPER_API_KEY") or SERPER_API_KEY
    if not api_key:
        raise SystemExit("SERPER_API_KEY is not set")

    locations = load_locations(args.locations_file, args.max_neighborhoods)
    tasks = build_tasks(locations, args.max_queries)
    if args.skip_searches:
        tasks = tasks[args.skip_searches:]
    if args.max_searches:
        tasks = tasks[: args.max_searches]

    print(f"ICP source: {ICP_PATH}")
    print(f"Locations file: {args.locations_file}")
    print(f"Neighborhoods: {len(locations):,}; queries/nbhd: {args.max_queries or len(RESTAURANT_QUERIES)}")
    print(f"Fresh searches: {len(tasks):,} Serper Maps calls")

    all_rows: list[dict] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(search_serper, task, api_key, args.rps): task for task in tasks}
        for i, future in enumerate(as_completed(futures), start=1):
            all_rows.extend(future.result())
            if i == 1 or i % 200 == 0 or i == len(tasks):
                elapsed = max(time.monotonic() - started, 1)
                print(f"[{i:,}/{len(tasks):,}] raw={len(all_rows):,} rate={i / elapsed:.1f}/s", flush=True)

    if not all_rows:
        raise SystemExit("No fresh search results returned")

    raw = pd.DataFrame(all_rows)
    raw, accepted = filter_and_rank(raw)
    return raw, accepted


def write_outputs(raw: pd.DataFrame, accepted: pd.DataFrame, target: int) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / "fresh_restaurant_leads"
    run_dir.mkdir(exist_ok=True)

    raw_path = run_dir / f"fresh_restaurant_raw_{stamp}.csv"
    top = accepted.head(target).copy()
    top_path = run_dir / f"fresh_restaurant_top_{len(top)}_{stamp}.csv"
    report_path = run_dir / f"fresh_restaurant_report_{stamp}.txt"

    columns = [
        "name", "partner_type", "cuisine_fit", "icp_score", "city", "state",
        "address", "phone", "website", "rating", "review_count", "price_level",
        "google_type", "google_types", "search_neighborhood", "search_city",
        "search_state", "search_query", "latitude", "longitude", "cid",
    ]
    raw.to_csv(raw_path, index=False, quoting=csv.QUOTE_MINIMAL)
    top[[c for c in columns if c in top.columns]].to_csv(top_path, index=False)

    report = [
        "Fresh Restaurant Discovery (trendy-neighborhood seeded)",
        f"Generated: {stamp}",
        f"ICP doc: {ICP_PATH}",
        "Existing lead CSVs used as source: no",
        "",
        f"Raw search rows: {len(raw):,}",
        f"Accepted deduped rows: {len(accepted):,}",
        f"Top output rows: {len(top):,}",
        "",
        "Top output by partner_type:",
        top["partner_type"].value_counts().to_string() if not top.empty else "(none)",
        "",
        "Top output by cuisine_fit:",
        top["cuisine_fit"].value_counts().to_string() if not top.empty else "(none)",
        "",
        "Top output by state (head 20):",
        top["state"].value_counts().head(20).to_string() if not top.empty else "(none)",
        "",
        "Rejected by reason:",
        raw["reject_reason"].replace("", "accepted").value_counts().to_string()
        if "reject_reason" in raw.columns else "(n/a)",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"\nRaw results:  {raw_path}")
    print(f"Top results:  {top_path}")
    print(f"Report:       {report_path}")
    print(f"Accepted deduped rows: {len(accepted):,}")
    if len(accepted) < target:
        print(f"WARNING: only {len(accepted):,} accepted; rerun with more neighborhoods/queries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh restaurant discovery seeded by trendy neighborhoods")
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--locations-file", type=Path, default=DEFAULT_LOCATIONS)
    parser.add_argument("--max-neighborhoods", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--max-searches", type=int, default=0)
    parser.add_argument("--skip-searches", type=int, default=0)
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--rps", type=int, default=45)
    parser.add_argument("--raw-input", type=str, help="Re-filter a raw CSV without new searches")
    parser.add_argument("--keep-lower-fit", action="store_true",
                        help="Keep lower-fit cuisines (pizza/breakfast/burger) instead of rejecting them")
    args = parser.parse_args()

    if args.keep_lower_fit:
        global EXCLUDE_LOWER_FIT
        EXCLUDE_LOWER_FIT = False

    if args.raw_input:
        print(f"Re-filtering raw search file: {args.raw_input}")
        raw = pd.read_csv(args.raw_input, low_memory=False)
        raw, accepted = filter_and_rank(raw)
    else:
        raw, accepted = discover(args)
    write_outputs(raw, accepted, args.target)


if __name__ == "__main__":
    main()
