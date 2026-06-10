"""
Trigger-based signal lanes: lead lists where every business has a *timely
reason to buy*, not just a category match. Strategy + lane catalog in
docs/SIGNALS.md; the idea backlog these were chosen from is
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md.

The orchestrator (`discover_signals.py`) iterates ALL_SOURCES, calls each
module's `scrape()`, writes per-source CSVs to output/signals/, then unions
them into output/signals_all_<YYYYMMDD>.csv.

Module contract mirrors awards/ and directories/: `scrape(**kwargs) ->
DataFrame` in `signals._lib.SIGNAL_SCHEMA` (canonical schema + trigger /
evidence_url / evidence_snippet). Orchestrator kwargs: limit, cities,
verify, dry_run — modules ignore what they don't use.

Lanes deliberately NOT built here (and why):
  - hiring intent       -> already exists in jobs/
  - reservation pain    -> already exists in scarcity/
  - partner adjacency   -> already exists in social_graph/
  - club detection on existing lists -> postprocess detect_clubs*.py
  - Tock/OpenTable Experiences mining (#26) — both surfaces are JS-heavy
    and login/WAF-gated; revisit with a Playwright lane if priority rises.
  - IG/TikTok comment mining (#13, #14) — needs paid Apify comment actors
    at meaningful cost; design first, then build.
"""
from __future__ import annotations

# (slug, category, tier, module_path, business_type, requires_auth)
# business_type "mixed": the module sets it per row.
ALL_SOURCES: list[tuple[str, str, int, str, str, bool]] = [
    # Transition leads — already believe in recurring revenue
    ("club_transition",      "transition", 1, "signals.club_transition",      "mixed", False),
    ("former_club_recovery", "transition", 1, "signals.former_club_recovery", "mixed", False),

    # Operational-pain leads — demand exists, workflow hurts
    ("manual_preorder",      "pain",       1, "signals.manual_preorder",      "mixed", False),

    # Demand leads — more demand than they can serve
    ("sold_out_demand",      "demand",     1, "signals.sold_out_demand",      "mixed", False),
    ("seasonal_preorder",    "demand",     2, "signals.seasonal_preorder",    "mixed", False),

    # Momentum / community leads — LLM-backed, best-effort
    ("press_momentum",       "press",      1, "signals.press_momentum",       "mixed", False),
    ("reddit_demand",        "community",  2, "signals.reddit_demand",        "mixed", False),
]


def by_slug(slug: str) -> tuple | None:
    for row in ALL_SOURCES:
        if row[0] == slug:
            return row
    return None
