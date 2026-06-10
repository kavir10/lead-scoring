"""
Gift-commerce leads (ideas #21, #46 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds premium merchants already using gifting language — gift boxes,
corporate/client gifts, holiday gifting. Gift behavior converts naturally
into prepaid bundles, seasonal drops, and 3-6 month gift subscriptions
(the bakery ICP calls out the gifting narrative explicitly).
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

_GIFT_PHRASES = [
    "corporate gifting",
    "client gifts",
    "gift box",
    "gift basket",
    "holiday gifting",
    "care package",
]

TRIGGERS: dict[str, list[str]] = {
    "cheese": _GIFT_PHRASES,
    "wine": _GIFT_PHRASES,
    "bakery": _GIFT_PHRASES,
    "butcher": ["gift box", "corporate gifting", "holiday gifting"],
    "specialty_grocer": _GIFT_PHRASES,
}

EXTRA_ONPAGE = ["gift", "gifting", "corporate orders", "bulk orders"]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="gift_commerce",
        lane_label="Active gift-commerce language (bundle/subscription potential)",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
