"""
Existing club / subscription transition leads (ideas #1, #18 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds merchants whose own websites already mention club / share / allocation
language. Per docs/ICP.md these are the bullseye "transition" leads: they
already believe in recurring revenue, so Table22 is a switch-the-platform
sale, not a cold-start. Includes the "hidden club" vocabulary (allocation,
standing order, monthly pickup) that merchants use without saying
"subscription".
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

TRIGGERS: dict[str, list[str]] = {
    "wine": [
        "wine club", "wine subscription", "monthly wine club",
        "wine allocation", "case club",
    ],
    "butcher": [
        "meat share", "meat CSA", "butcher subscription", "meat subscription",
        "butcher box", "monthly meat box",
    ],
    "cheese": [
        "cheese club", "cheese subscription", "cheese of the month",
    ],
    "bakery": [
        "bread club", "bread share", "bread subscription", "bake club",
        "pastry subscription",
    ],
    "specialty_grocer": [
        "monthly box", "pantry club", "provisions club",
    ],
    "deli": [
        "sandwich club", "monthly pickup club",
    ],
}

# Synonyms accepted as on-page proof even when a different phrase was searched.
EXTRA_ONPAGE = [
    "join the club", "club members", "monthly pickup", "standing order",
    "members only", "first access", "subscription",
]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="club_transition",
        lane_label="Existing club/subscription program (transition lead)",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
