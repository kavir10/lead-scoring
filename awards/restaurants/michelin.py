"""
Michelin Guide restaurants — wraps the existing `discover_michelin_direct.py`
output. We don't re-scrape Michelin here; the original pipeline owns that.

Picks up the most recent `output/michelin_direct_us_*.csv` and reshapes it
into the canonical award-row schema.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from awards._lib import SCHEMA, ROOT, normalize_state, to_dataframe

TIER_FROM_DISTINCTION = {
    "3 star": 1,
    "2 star": 1,
    "1 star": 1,
    "bib": 1,
    "green-star": 1,
    "the-plate": 2,  # Selected — softer signal
}

DISTINCTION_LABEL = {
    "3 star": "Michelin 3 Star",
    "2 star": "Michelin 2 Star",
    "1 star": "Michelin 1 Star",
    "bib": "Michelin Bib Gourmand",
    "green-star": "Michelin Green Star",
    "the-plate": "Michelin Selected",
}


def _latest_csv() -> Path | None:
    candidates = sorted((ROOT / "output").glob("michelin_direct_us_*.csv"))
    return candidates[-1] if candidates else None


def scrape(**_kwargs) -> pd.DataFrame:
    path = _latest_csv()
    if not path:
        print("  [michelin] no michelin_direct_us_*.csv found in output/", flush=True)
        return to_dataframe([])
    print(f"  [michelin] sourcing rows from {path.name}", flush=True)
    src = pd.read_csv(path).fillna("")
    rows = []
    for _, r in src.iterrows():
        distinction = str(r.get("distinction", "")).strip().lower()
        tier = TIER_FROM_DISTINCTION.get(distinction, 1)
        rows.append({
            "source": "michelin",
            "tier": tier,
            "business_type": "restaurant",
            "name": str(r.get("name", "")).strip(),
            "city": str(r.get("city", "")).strip(),
            "state": normalize_state(r.get("region", "")),
            "country": "us",
            "distinction": DISTINCTION_LABEL.get(distinction, str(r.get("tier", "")).strip()),
            "year": "",
            "source_url": str(r.get("michelin_url", "")).strip(),
            "blurb": str(r.get("cooking_type", "")).strip(),
        })
    return to_dataframe(rows)
