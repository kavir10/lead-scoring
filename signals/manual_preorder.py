"""
Manual preorder workflow pain (idea #2 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds merchants taking orders through Google Forms, DMs, email, or phone.
They already have demand AND a concrete operational pain Table22
systematizes — the outbound angle writes itself.
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

_MANUAL_PHRASES = [
    "order via google form",
    "preorder by email",
    "email us to order",
    "DM to order",
    "call to place your order",
    "order form",
]

TRIGGERS: dict[str, list[str]] = {
    "bakery": _MANUAL_PHRASES,
    "butcher": _MANUAL_PHRASES,
    "cheese": _MANUAL_PHRASES,
    "wine": ["email us to order", "call to reserve", "DM to order"],
    "specialty_grocer": _MANUAL_PHRASES,
}

EXTRA_ONPAGE = [
    "google form", "docs.google.com/forms", "dm us", "email to order",
    "venmo", "order by phone",
]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="manual_preorder",
        lane_label="Manual preorder workflow (Google Form / DM / email)",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
