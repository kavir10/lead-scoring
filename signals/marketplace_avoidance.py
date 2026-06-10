"""
Marketplace-avoidance / order-direct leads (idea #35 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds merchants who publicly reject third-party delivery apps ("no DoorDash",
"order direct", "pickup only"). These owners care about margin, brand
control, and owning the customer relationship — exactly Table22's
not-a-marketplace positioning, and the same fee-fatigue language the bakery
ICP flags as an objection to reverse (docs/ICP.md).
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

_DIRECT_PHRASES = [
    "no third-party delivery",
    "we don't use doordash",
    "not on delivery apps",
    "order directly from us",
    "order direct and save",
    "pickup only",
]

TRIGGERS: dict[str, list[str]] = {
    "neighbourhood_restaurant": _DIRECT_PHRASES,
    "bakery": _DIRECT_PHRASES,
    "butcher": ["order directly from us", "pickup only", "no third-party delivery"],
    "wine": ["order directly from us", "pickup only"],
}

EXTRA_ONPAGE = [
    "order direct", "doordash", "third-party", "third party delivery",
    "support local", "skip the apps",
]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="marketplace_avoidance",
        lane_label="Rejects delivery apps / pushes direct ordering",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
