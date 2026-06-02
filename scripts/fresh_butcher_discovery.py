"""
Fresh butcher lead discovery with prior-corpus suppression.

This mirrors the fresh bakery run, but first audits prior butcher files and
suppresses already-found butcher businesses by CID, phone, website, and
name/address keys. The search footprint intentionally leans on neighborhoods
and expanded city/suburb locations so it is not just a replay of the April
butcher query grid.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from butcher import BANNED_STATES, load_eligible_butcher_cities
from config import CHAIN_KEYWORDS, SERPER_API_KEY


RUN_DIR = ROOT / "output" / "fresh_butcher_leads_20260531"
DEFAULT_PRIOR_SOURCE = (
    ROOT
    / "output"
    / "custom-serper-scoring_kavir_20260402_"
    "bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_"
    "73915_all_clubs_v2.reclassified_20260422.csv"
)
NEIGHBORHOOD_SOURCE = ROOT / "research" / "trendy_neighborhoods" / "trendy_neighborhoods_top100_us_20260531.csv"

BUTCHER_QUERIES = [
    "butcher shop",
    "specialty meat market",
    "artisan meat market",
    "local meat market",
    "premium meat market",
    "whole animal butcher",
    "dry aged meat market",
    "custom cut meat",
    "sausage shop",
    "charcuterie shop",
    "salumi shop",
    "carniceria",
    "halal meat market",
    "kosher meat market",
    "italian meat market",
    "polish meat market",
    "smokehouse meat market",
    "farm butcher shop",
]

STRONG_TYPE_RE = re.compile(
    r"\b(?:butcher shop|meat products store|meat market|meat processor|"
    r"meat wholesaler|poultry store)\b",
    re.I,
)
ADJACENT_TYPE_RE = re.compile(
    r"\b(?:charcuterie|deli|delicatessen|grocery store|market|"
    r"food products supplier|farm shop|wholesale grocer|store|"
    r"specialty food store)\b",
    re.I,
)
NAME_RE = re.compile(
    r"\b(?:butcher|butchery|meat market|meat shop|carniceria|carnicería|"
    r"charcuterie|salumi|salumeria|sausage|smokehouse|smoked meats|"
    r"halal meat|kosher meat|prime meats|provisions|poultry|game meat)\b",
    re.I,
)
RESTAURANT_ONLY_RE = re.compile(
    r"\b(?:restaurant|bar|grill|steakhouse|bbq|barbecue|pizza|sushi|ramen|"
    r"taco|burger|cafe|coffee shop|brewery|distillery)\b",
    re.I,
)

_rate_lock = threading.Lock()
_last_times: list[float] = []


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


def clean_phone(value: object) -> str:
    return re.sub(r"[^\d]", "", str(value or ""))


def norm_text(value: object) -> str:
    return re.sub(r"[^\w]+", " ", str(value or "").lower()).strip()


def host(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.match(r"https?://", text, flags=re.I):
        text = "https://" + text
    parsed = urlparse(text)
    netloc = parsed.netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def parse_city_state(address: object) -> tuple[str, str]:
    address = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in address.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        match = re.match(r"^([A-Z]{2})\s*\d*", parts[i])
        if match:
            return (parts[i - 1] if i else "", match.group(1))
    return "", ""


def looks_like_chain(name: object) -> bool:
    text = str(name or "").lower()
    return any(keyword in text for keyword in CHAIN_KEYWORDS)


def is_butcher_row(df: pd.DataFrame) -> pd.Series:
    if "business_type" in df.columns:
        return df["business_type"].fillna("").astype(str).str.lower().eq("butcher")
    cols = [c for c in ["name", "google_type", "google_types", "type", "types", "search_query", "source"] if c in df]
    if not cols:
        return pd.Series(False, index=df.index)
    text = df[cols].fillna("").astype(str).agg(" ".join, axis=1)
    return text.str.contains(r"\b(?:butcher|meat market|charcuterie|carniceria|meat shop)\b", case=False, regex=True)


def load_prior_butcher_rows(paths: list[Path]) -> tuple[pd.DataFrame, dict]:
    frames: list[pd.DataFrame] = []
    file_summaries = []
    for path in paths:
        if not path.exists():
            file_summaries.append({"file": str(path), "status": "missing", "rows": 0, "butcher_rows": 0})
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception as exc:
            file_summaries.append({"file": str(path), "status": "error", "error": str(exc), "rows": 0, "butcher_rows": 0})
            continue
        mask = is_butcher_row(df)
        butcher = df[mask].copy()
        butcher["_prior_file"] = str(path)
        frames.append(butcher)
        file_summaries.append({"file": str(path), "status": "ok", "rows": int(len(df)), "butcher_rows": int(len(butcher))})

    prior = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    audit = {"files": file_summaries, "prior_butcher_rows": int(len(prior))}
    return prior, audit


def make_suppression_sets(prior: pd.DataFrame) -> dict[str, set[str]]:
    if prior.empty:
        return {"cid": set(), "phone": set(), "host": set(), "name_address": set(), "name_state": set()}

    out = prior.copy()
    out["_phone"] = out.get("phone", "").map(clean_phone) if "phone" in out else ""
    out["_cid"] = out.get("cid", "").fillna("").astype(str).str.strip() if "cid" in out else ""
    out["_host"] = out.get("website", "").map(host) if "website" in out else ""
    out["_name"] = out.get("name", "").map(norm_text) if "name" in out else ""
    out["_address"] = out.get("address", "").map(norm_text) if "address" in out else ""
    out["_state"] = out.get("state", "").fillna("").astype(str).str.upper().str.strip() if "state" in out else ""
    out["_city"] = out.get("city", "").map(norm_text) if "city" in out else ""

    host_counts = out.loc[out["_host"].ne(""), "_host"].value_counts()
    single_hosts = set(host_counts[host_counts.eq(1)].index)

    return {
        "cid": set(out.loc[out["_cid"].ne(""), "_cid"]),
        "phone": set(out.loc[out["_phone"].str.len().ge(10), "_phone"]),
        "host": single_hosts,
        "name_address": set((out["_name"] + "|" + out["_address"])[out["_name"].ne("") & out["_address"].ne("")]),
        "name_state": set((out["_name"] + "|" + out["_state"])[out["_name"].ne("") & out["_state"].ne("")]),
    }


def suppression_reason(row: pd.Series, sets: dict[str, set[str]]) -> str:
    cid = str(row.get("cid") or "").strip()
    phone = clean_phone(row.get("phone"))
    website_host = host(row.get("website"))
    name = norm_text(row.get("name"))
    address = norm_text(row.get("address"))
    state = str(row.get("state") or "").upper().strip()

    if cid and cid in sets["cid"]:
        return "prior_cid"
    if len(phone) >= 10 and phone in sets["phone"]:
        return "prior_phone"
    if website_host and website_host in sets["host"]:
        return "prior_single_location_host"
    if name and address and f"{name}|{address}" in sets["name_address"]:
        return "prior_name_address"
    if name and state and f"{name}|{state}" in sets["name_state"]:
        return "prior_name_state"
    return ""


def verification_reason(row: pd.Series) -> str:
    name = str(row.get("name", ""))
    state = str(row.get("state", "") or "").upper()
    type_text = f"{row.get('google_type', '')} {row.get('google_types', '')}"
    combined = f"{name} {type_text}"
    has_strong_type = bool(STRONG_TYPE_RE.search(type_text))
    has_adjacent_type = bool(ADJACENT_TYPE_RE.search(type_text))
    has_name = bool(NAME_RE.search(name))
    restaurant_only = bool(RESTAURANT_ONLY_RE.search(type_text)) and not (has_strong_type or has_name)

    if state in BANNED_STATES:
        return "reject_banned_state"
    if not re.fullmatch(r"[A-Z]{2}", state):
        return "reject_unknown_state"
    if looks_like_chain(name):
        return "reject_chain"
    if has_strong_type:
        return "keep_strong_google_type"
    if has_adjacent_type and has_name:
        return "keep_adjacent_type_plus_name"
    if has_name and not restaurant_only:
        return "keep_strong_name_signal"
    if "butcher" in combined.lower() and not restaurant_only:
        return "keep_butcher_text_signal"
    return "reject_not_verified_butcher"


def quality_score(df: pd.DataFrame) -> pd.Series:
    rating = pd.to_numeric(df.get("rating", 0), errors="coerce").fillna(0)
    reviews = pd.to_numeric(df.get("review_count", 0), errors="coerce").fillna(0)
    type_bonus = df["verification_reason"].map(
        {
            "keep_strong_google_type": 28,
            "keep_adjacent_type_plus_name": 22,
            "keep_strong_name_signal": 18,
            "keep_butcher_text_signal": 14,
        }
    ).fillna(0)
    website_bonus = df.get("website", "").fillna("").astype(str).str.strip().ne("").astype(int) * 8
    rating_score = rating.clip(0, 5) * 7
    review_score = reviews.apply(lambda x: min(24, math.log10(x + 1) * 6 if x > 0 else 0))
    return (type_bonus + website_bonus + rating_score + review_score).round(2)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_phone_clean"] = out.get("phone", "").map(clean_phone) if "phone" in out else ""
    out["_cid_clean"] = out.get("cid", "").fillna("").astype(str).str.strip() if "cid" in out else ""
    out["_name_addr_key"] = out.get("name", "").map(norm_text) + "|" + out.get("address", "").map(norm_text)
    pieces = []
    if out["_cid_clean"].ne("").any():
        pieces.append(out[out["_cid_clean"].ne("")].drop_duplicates("_cid_clean", keep="first"))
    no_cid = out[out["_cid_clean"].eq("")]
    if no_cid["_phone_clean"].str.len().ge(10).any():
        with_phone = no_cid[no_cid["_phone_clean"].str.len().ge(10)].drop_duplicates("_phone_clean", keep="first")
        pieces.append(with_phone)
        no_cid = no_cid[no_cid["_phone_clean"].str.len().lt(10)]
    pieces.append(no_cid.drop_duplicates("_name_addr_key", keep="first"))
    return pd.concat(pieces, ignore_index=True).drop(columns=["_phone_clean", "_cid_clean", "_name_addr_key"])


def load_locations(args: argparse.Namespace, prior: pd.DataFrame) -> list[str]:
    locations: list[str] = []

    if args.include_neighborhoods and NEIGHBORHOOD_SOURCE.exists():
        n = pd.read_csv(NEIGHBORHOOD_SOURCE)
        for _, row in n.iterrows():
            city = str(row.get("city", "")).strip()
            state = str(row.get("state", "")).strip()
            hood = str(row.get("neighborhood", "")).strip()
            if hood and city and state:
                locations.append(f"{hood}, {city}, {state}")

    cities = load_eligible_butcher_cities(min_population=args.min_population)
    city_locations = cities["location"].tolist()

    if args.skip_prior_locations and not prior.empty and "search_city" in prior.columns:
        prior_locations = set(prior["search_city"].fillna("").astype(str).str.strip())
        city_locations = [loc for loc in city_locations if loc not in prior_locations]

    locations.extend(city_locations)

    seen = set()
    unique = []
    for loc in locations:
        if loc and loc not in seen:
            unique.append(loc)
            seen.add(loc)
    if args.max_locations:
        unique = unique[: args.max_locations]
    return unique


def call_serper_maps(query: str, location: str, rps: int) -> list[dict]:
    rate_limit(rps)
    headers = {"X-API-KEY": SERPER_API_KEY or "", "Content-Type": "application/json"}
    payload = {"q": query, "location": f"{location}, United States", "gl": "us", "hl": "en", "num": 20}
    for attempt in range(3):
        try:
            resp = requests.post("https://google.serper.dev/maps", headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            rows = []
            for p in resp.json().get("places", []):
                types = p.get("types") or []
                town, state = parse_city_state(p.get("address", ""))
                rows.append(
                    {
                        "name": p.get("title", ""),
                        "address": p.get("address", ""),
                        "city": town,
                        "state": state,
                        "phone": p.get("phoneNumber", ""),
                        "website": p.get("website", ""),
                        "rating": p.get("rating"),
                        "review_count": p.get("ratingCount", 0),
                        "google_type": p.get("type", ""),
                        "google_types": ", ".join(types) if isinstance(types, list) else str(types or ""),
                        "price_level": p.get("priceLevel", ""),
                        "latitude": p.get("latitude"),
                        "longitude": p.get("longitude"),
                        "cid": p.get("cid", ""),
                        "search_query": query,
                        "search_city": location,
                        "business_type": "butcher",
                    }
                )
            return rows
        except requests.RequestException:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    return []


def discover(args: argparse.Namespace, prior: pd.DataFrame, suppression_sets: dict[str, set[str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not SERPER_API_KEY:
        raise SystemExit("SERPER_API_KEY is missing")

    locations = load_locations(args, prior)
    queries = BUTCHER_QUERIES[: args.max_queries] if args.max_queries else BUTCHER_QUERIES
    tasks = [(query, location) for query in queries for location in locations]
    if args.max_searches:
        tasks = tasks[: args.max_searches]

    print(f"Fresh butcher discovery: {len(tasks):,} Serper Maps searches")
    print(f"Queries: {', '.join(queries)}")
    print(f"Locations: {len(locations):,}; workers={args.workers}; rps={args.rps}")

    all_rows: list[dict] = []
    started = time.monotonic()
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(call_serper_maps, query, location, args.rps): (query, location) for query, location in tasks}
        for future in as_completed(futures):
            completed += 1
            rows = future.result()
            all_rows.extend(rows)
            if completed % 100 == 0 or completed == len(tasks):
                elapsed = max(time.monotonic() - started, 1)
                print(
                    f"  {completed:,}/{len(tasks):,} searches | "
                    f"{completed / elapsed:.1f} req/s | raw rows {len(all_rows):,}",
                    flush=True,
                )

    raw = pd.DataFrame(all_rows)
    if raw.empty:
        return raw, raw, raw

    raw["verification_reason"] = raw.apply(verification_reason, axis=1)
    raw["is_verified_butcher"] = raw["verification_reason"].str.startswith("keep_")
    raw["prior_suppression_reason"] = raw.apply(lambda row: suppression_reason(row, suppression_sets), axis=1)
    raw["is_new_to_prior_butcher_corpus"] = raw["prior_suppression_reason"].eq("")

    verified = dedupe(raw[raw["is_verified_butcher"]].copy())
    verified["fresh_quality_score"] = quality_score(verified)
    verified = verified.sort_values(["fresh_quality_score", "review_count", "rating"], ascending=[False, False, False]).reset_index(drop=True)

    new_verified = verified[verified["is_new_to_prior_butcher_corpus"]].copy().reset_index(drop=True)
    new_verified.insert(0, "discovery_rank", range(1, len(new_verified) + 1))
    return raw, verified, new_verified


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh butcher discovery using Serper Maps plus prior suppression.")
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--prior-source", type=Path, action="append", default=[DEFAULT_PRIOR_SOURCE])
    parser.add_argument("--max-searches", type=int, default=0)
    parser.add_argument("--max-locations", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--min-population", type=int, default=25_000)
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--rps", type=int, default=25)
    parser.add_argument("--skip-prior-locations", action="store_true")
    parser.add_argument("--include-neighborhoods", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)

    prior, audit = load_prior_butcher_rows(args.prior_source)
    suppression_sets = make_suppression_sets(prior)
    audit.update(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "suppression_keys": {key: len(value) for key, value in suppression_sets.items()},
            "queries": BUTCHER_QUERIES,
        }
    )
    (args.run_dir / "prior_butcher_audit.json").write_text(json.dumps(audit, indent=2) + "\n")

    raw, verified, new_verified = discover(args, prior, suppression_sets)
    raw_path = args.run_dir / "fresh_butcher_serper_raw.csv"
    verified_path = args.run_dir / "fresh_butcher_verified.csv"
    new_path = args.run_dir / "fresh_butcher_new_candidates.csv"
    raw.to_csv(raw_path, index=False)
    verified.to_csv(verified_path, index=False)
    new_verified.to_csv(new_path, index=False)

    print("\nVerification reasons:")
    if not raw.empty:
        print(raw["verification_reason"].value_counts().to_string())
    print("\nPrior suppression reasons:")
    if not raw.empty:
        print(raw["prior_suppression_reason"].replace("", "new").value_counts().to_string())

    print(f"\nRaw rows: {len(raw):,} -> {raw_path}")
    print(f"Verified butcher rows: {len(verified):,} -> {verified_path}")
    print(f"New verified butcher rows: {len(new_verified):,} -> {new_path}")

    if not new_verified.empty:
        sample_path = args.run_dir / "fresh_butcher_new_candidates_qa_sample.csv"
        new_verified.sample(min(100, len(new_verified)), random_state=20260531).to_csv(sample_path, index=False)
        print(f"QA sample: {sample_path}")


if __name__ == "__main__":
    main()
