"""
Former / paused club recovery leads (idea #52 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Finds merchants whose sites say a club is paused, full, or no longer taking
members. Past belief + likely operational pain is a warmer start than a cold
new-club pitch — the page itself is the outbound hook.
"""
from __future__ import annotations

import pandas as pd

from signals._lib import phrase_lane_scrape

_PAUSE_PHRASES = [
    "club is currently full",
    "not accepting new members",
    "club is paused",
    "subscriptions are paused",
    "membership is closed",
    "club waitlist",
]

TRIGGERS: dict[str, list[str]] = {
    "wine": _PAUSE_PHRASES,
    "butcher": _PAUSE_PHRASES,
    "cheese": _PAUSE_PHRASES,
    "bakery": _PAUSE_PHRASES,
}

EXTRA_ONPAGE = [
    "currently full", "paused", "closed to new members", "join the waitlist",
]


def scrape(**kwargs) -> pd.DataFrame:
    return phrase_lane_scrape(
        slug="former_club_recovery",
        lane_label="Paused/closed club (recovery lead)",
        triggers_by_type=TRIGGERS,
        extra_onpage_phrases=EXTRA_ONPAGE,
        **kwargs,
    )
