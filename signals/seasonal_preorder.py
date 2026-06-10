"""
Seasonal preorder leads (idea #22 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Merchants already running holiday/seasonal preorders have proven they can
package products, take prepaid orders, and manage pickup windows — exactly
the muscle a Table22 subscription uses. Outreach lands best 60-90 days
before the seasonal crunch; run this lane on that calendar.
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

TRIGGERS: dict[str, list[str]] = {
    "bakery": [
        "thanksgiving pie preorder", "holiday cookie box", "king cake preorder",
        "panettone preorder", "holiday bread preorder",
    ],
    "butcher": [
        "holiday roast preorder", "thanksgiving turkey preorder",
        "prime rib preorder", "holiday ham preorder", "grilling box",
    ],
    "wine": [
        "holiday case", "thanksgiving wine pairing", "holiday wine bundle",
    ],
    "cheese": [
        "holiday cheese board", "holiday gift box", "party board preorder",
    ],
}

EXTRA_ONPAGE = ["preorder", "pre-order", "holiday", "pickup window", "order deadline"]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="seasonal_preorder",
        lane_label="Seasonal/holiday preorder program",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
