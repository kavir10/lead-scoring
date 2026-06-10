"""
Sold-out / waitlist demand signals (idea #3 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

"More demand than they can serve through their physical space" is the
strongest cross-vertical ICP theme (docs/ICP.md) — sold-out language on the
merchant's own site is one of the cleanest public buying signals.
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

_DEMAND_PHRASES = [
    "sold out",
    "join the waitlist",
    "next drop",
    "preorder closed",
    "limited quantities",
]

TRIGGERS: dict[str, list[str]] = {
    "bakery": _DEMAND_PHRASES + ["sells out"],
    "butcher": _DEMAND_PHRASES,
    "cheese": _DEMAND_PHRASES,
    "wine": ["allocation list", "join the waitlist", "sold out"],
}

EXTRA_ONPAGE = ["sold out", "waitlist", "back in stock", "notify me"]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="sold_out_demand",
        lane_label="Sold-out / waitlist demand language",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
