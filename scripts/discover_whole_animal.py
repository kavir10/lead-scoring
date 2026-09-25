"""
Serper Maps lanes for the whole-animal butcher list.

  lookup   — match each row of an existing list (Name/City/State) to its
             Google Maps listing: corrected website, street address, opening
             hours, place type, CID.
  discover — craft-keyword Maps sweep across config.CITIES for net-new shops.

Both write Maps fields in the same shape so the outputs can be unioned and
passed to scripts/verify_whole_animal.py.

    python scripts/discover_whole_animal.py lookup  IN.csv  OUT.csv
    python scripts/discover_whole_animal.py discover OUT.csv [--max-cities N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CITIES  # noqa: E402
from discover import is_chain, parse_town_state  # noqa: E402

BANNED_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}

CRAFT_QUERIES = ["whole animal butcher", "nose to tail butcher"]

# Google place types that are walk-in retail. Processors and wholesalers are
# kept only if their own website shows retail hours (decided downstream).
RETAIL_TYPES = re.compile(
    r"butcher|meat market|meat products store|deli|charcuterie|grocery|market|"
    r"specialty food|gourmet|farm shop|farm stand|general store|food store|restaurant",
    re.I)
MEAT_TYPES = re.compile(r"butcher|meat|charcuterie|deli|farm", re.I)


def _norm_name(s: str) -> str:
    s = (s or "").lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(the|llc|inc|co|company|shop|butchery|butcher|butchers|meats?|market)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _maps_fields(p: dict) -> dict:
    town, state = parse_town_state(p.get("address", ""))
    return {
        "maps_name": p.get("name", ""),
        "maps_address": p.get("address", ""),
        "maps_city": town,
        "maps_state": state,
        "maps_type": p.get("type", ""),
        "maps_types": p.get("types", ""),
        "maps_website": p.get("website", "") or "",
        "maps_phone": p.get("phone", ""),
        "maps_rating": p.get("rating"),
        "maps_reviews": p.get("review_count", 0),
        "maps_hours": p.get("opening_hours", ""),
        "cid": str(p.get("cid", "") or ""),
    }


def _search(query: str, location: str, retries: int = 3) -> list[dict]:
    """Serper Maps call that keeps openingHours (discover.search_serper_maps drops it)."""
    payload = {"q": query, "location": f"{location}, United States", "gl": "us", "hl": "en", "num": 20}
    headers = {"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"}
    for attempt in range(retries):
        try:
            resp = requests.post("https://google.serper.dev/maps", json=payload, headers=headers, timeout=20)
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            break
        except requests.RequestException:
            if attempt == retries - 1:
                return []
            time.sleep(2 ** (attempt + 1))
    out = []
    for p in resp.json().get("places", []):
        types = p.get("types") or []
        out.append({
            "name": p.get("title", ""),
            "address": p.get("address", ""),
            "type": p.get("type", ""),
            "types": ", ".join(types) if isinstance(types, list) else "",
            "website": p.get("website", ""),
            "phone": p.get("phoneNumber", ""),
            "rating": p.get("rating"),
            "review_count": p.get("ratingCount", 0),
            "opening_hours": json.dumps(p["openingHours"]) if p.get("openingHours") else "",
            "cid": p.get("cid", ""),
        })
    return out


def lookup(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})

    def one(row) -> dict:
        name, city, state = str(row["name"]), str(row["city"]), str(row["state"])
        results = _search(f"{name} {city} {state}", f"{city}, {state}")
        best, best_score = None, 0.0
        target = _norm_name(name)
        for p in results[:5]:
            score = SequenceMatcher(None, target, _norm_name(p["name"])).ratio()
            _, st = parse_town_state(p.get("address", ""))
            if st and st != state:
                score -= 0.3
            if score > best_score:
                best, best_score = p, score
        if not best or best_score < 0.6:
            return {"maps_match": "none", "maps_match_score": round(best_score, 2)}
        return {"maps_match": "ok", "maps_match_score": round(best_score, 2), **_maps_fields(best)}

    with ThreadPoolExecutor(8) as ex:
        found = list(ex.map(one, [r for _, r in df.iterrows()]))
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(found)], axis=1)


def discover_new(max_cities: int = 0) -> pd.DataFrame:
    cities = CITIES[:max_cities] if max_cities else CITIES
    tasks = [(q, c) for c in cities for q in CRAFT_QUERIES]
    print(f"{len(tasks)} Maps searches", file=sys.stderr)

    def one(t):
        q, c = t
        rows = _search(q, c)
        for r in rows:
            r["search_query"], r["search_city"] = q, c
        return rows

    rows = []
    with ThreadPoolExecutor(8) as ex:
        for i, batch in enumerate(ex.map(one, tasks), 1):
            rows.extend(batch)
            if i % 100 == 0:
                print(f"  {i}/{len(tasks)}", file=sys.stderr, flush=True)

    out = []
    for r in rows:
        f = _maps_fields(r)
        f["name"], f["website"] = f["maps_name"], f["maps_website"]
        f["city"], f["state"] = f["maps_city"], f["maps_state"]
        f["search_query"], f["search_city"] = r["search_query"], r["search_city"]
        out.append(f)
    df = pd.DataFrame(out)
    raw = len(df)
    df = df[df.cid != ""].drop_duplicates("cid")
    df = df[~df.state.isin(BANNED_STATES) & (df.state != "")]
    df = df[df.maps_type.str.contains(MEAT_TYPES, na=False) | df.maps_types.str.contains(MEAT_TYPES, na=False)]
    df = df[~df.name.map(is_chain)]
    print(f"{raw} raw results -> {len(df)} unique meat listings in allowed states, non-chain", file=sys.stderr)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lookup")
    a.add_argument("input")
    a.add_argument("output")
    b = sub.add_parser("discover")
    b.add_argument("output")
    b.add_argument("--max-cities", type=int, default=0)
    args = ap.parse_args()

    load_dotenv()
    if args.cmd == "lookup":
        out = lookup(pd.read_csv(args.input, dtype=str))
        print(out.maps_match.value_counts().to_string(), file=sys.stderr)
    else:
        out = discover_new(args.max_cities)
    out.to_csv(args.output, index=False)
    print(f"wrote {len(out)} rows to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
