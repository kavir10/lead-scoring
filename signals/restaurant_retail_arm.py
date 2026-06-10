"""
Restaurant retail-arm leads (ideas #41, #42 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds restaurants and hospitality groups already selling retail — pasta
kits, butcher boxes, wine bundles, pantry/provisions lines. This is the
bridge from restaurant demand to recurring commerce: they've proven they
can package product, and per docs/ICP.md restaurant-group butcher/retail
arms with a public counter are in-ICP.
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

TRIGGERS: dict[str, list[str]] = {
    "neighbourhood_restaurant": [
        "pasta kit",
        "meal kit",
        "butcher box",
        "wine bundle",
        "pantry items",
        "provisions shop",
        "our market",
        "take home",
    ],
}

EXTRA_ONPAGE = [
    "pantry", "provisions", "market", "retail", "take home", "shop our",
    "to-go kit", "at-home kit",
]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="restaurant_retail_arm",
        lane_label="Restaurant with a retail/pantry arm",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
