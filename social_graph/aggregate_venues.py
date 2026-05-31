"""
Aggregate IG post data fetched by `fetch_seed_posts.py` into a venue-level
roll-up.

For each unique venue surfaced via post.locationName / post.locationId /
post.taggedAccounts, count:
  - seed_frequency: how many distinct seeds reference this venue
  - seed_quality:   sum of seed_weight for those seeds
  - last_mention_at: most recent post timestamp

Promotion rule (A-list):
  seed_frequency >= 3 AND seed_quality >= 18

Emit canonical SCHEMA CSV under output/social_graph/.

Strategy: docs/strategies/01_somm_chef_ig_graph.md

Usage:
    python -m social_graph.aggregate_venues
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from awards._lib import (
    ROOT,
    SCHEMA,
    make_row,
    normalize_state,
    to_dataframe,
)

RAW_DIR = ROOT / "output" / "social_graph" / "raw"
OUT_DIR = ROOT / "output" / "social_graph"


def _extract_venue_signals(post: dict) -> list[dict]:
    """Pull venue references from a single post: location, tagged accounts."""
    signals: list[dict] = []
    loc = post.get("locationName") or post.get("location", {}).get("name") if isinstance(post.get("location"), dict) else post.get("locationName")
    loc_id = post.get("locationId") or (post.get("location") or {}).get("id") if isinstance(post.get("location"), dict) else post.get("locationId")
    if loc:
        signals.append({
            "kind": "location",
            "raw_name": str(loc),
            "location_id": str(loc_id) if loc_id else "",
            "ig_handle": "",
        })
    tagged = post.get("taggedAccounts") or post.get("taggedUsers") or []
    if isinstance(tagged, list):
        for t in tagged:
            handle = t.get("username") or t.get("handle") if isinstance(t, dict) else None
            if handle:
                signals.append({
                    "kind": "tagged_account",
                    "raw_name": handle,
                    "location_id": "",
                    "ig_handle": handle,
                })
    return signals


def _city_state_from_text(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = re.search(r"([A-Z][a-zA-Z\s.'\-]+?),\s*([A-Z]{2})\b", text)
    if m:
        return m.group(1).strip(), normalize_state(m.group(2))
    return "", ""


def aggregate() -> pd.DataFrame:
    if not RAW_DIR.exists():
        print(f"  [aggregate] no raw dir at {RAW_DIR}", flush=True)
        return pd.DataFrame(columns=SCHEMA)
    raw_files = sorted(RAW_DIR.glob("*_*.json"))
    if not raw_files:
        print("  [aggregate] no raw seed JSON files yet — run fetch_seed_posts first", flush=True)
        return pd.DataFrame(columns=SCHEMA)
    # venue_key -> {seeds: set, weight: int, last_mention: str, names: set, ig_handles: set}
    agg: dict[str, dict] = defaultdict(lambda: {
        "seeds": set(), "weight": 0, "last_mention": "",
        "names": set(), "ig_handles": set(), "location_ids": set(),
        "raw_text": "",
    })
    for f in raw_files:
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        seed_meta = data.get("seed_meta", {})
        seed_handle = seed_meta.get("handle") or f.stem.split("_")[0]
        seed_weight = int(seed_meta.get("weight") or 5)
        for post in data.get("posts") or []:
            ts = post.get("timestamp") or post.get("takenAt") or ""
            for sig in _extract_venue_signals(post):
                # Normalize the venue key
                key_components = []
                if sig.get("location_id"):
                    key_components.append(f"loc:{sig['location_id']}")
                elif sig.get("ig_handle"):
                    key_components.append(f"ig:{sig['ig_handle'].lower()}")
                else:
                    key_components.append(f"name:{sig['raw_name'].lower().strip()}")
                key = "||".join(key_components)
                bucket = agg[key]
                bucket["seeds"].add(seed_handle)
                bucket["weight"] += seed_weight
                if ts and (not bucket["last_mention"] or ts > bucket["last_mention"]):
                    bucket["last_mention"] = ts
                bucket["names"].add(sig["raw_name"])
                if sig.get("ig_handle"):
                    bucket["ig_handles"].add(sig["ig_handle"])
                if sig.get("location_id"):
                    bucket["location_ids"].add(sig["location_id"])
                if not bucket["raw_text"]:
                    bucket["raw_text"] = sig["raw_name"]
    rows: list[dict] = []
    for key, b in agg.items():
        seed_freq = len(b["seeds"])
        if seed_freq < 2 and b["weight"] < 12:
            continue
        # Choose canonical name (longest non-handle, otherwise first)
        names = [n for n in b["names"] if not n.startswith("@")]
        canonical = max(names, key=len) if names else (next(iter(b["names"])) if b["names"] else "")
        if not canonical:
            continue
        city, state = _city_state_from_text(b["raw_text"])
        rows.append(make_row(
            source="ig_graph_somm_chef",
            tier=1 if (seed_freq >= 3 and b["weight"] >= 18) else 2,
            business_type="restaurant",
            name=canonical,
            city=city,
            state=state,
            country="us",
            distinction=(
                f"IG seed-graph: {seed_freq} distinct seeds, quality {b['weight']}, "
                f"last_mention {b['last_mention'][:10]}"
            ),
            source_url="",
            blurb=(
                f"seed_frequency={seed_freq}; seed_quality={b['weight']}; "
                f"ig_handles={','.join(sorted(b['ig_handles']))[:120]}; "
                f"location_ids={','.join(sorted(b['location_ids']))[:120]}"
            ),
        ))
    return to_dataframe(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=str, default="")
    args = p.parse_args()
    df = aggregate()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = Path(args.out) if args.out else OUT_DIR / f"somm_chef_ig_graph_{stamp}.csv"
    df.to_csv(out, index=False)
    print(f"  Saved {len(df)} aggregated venues -> {out}", flush=True)


if __name__ == "__main__":
    main()
