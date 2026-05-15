"""
Name-based filters. The LLM does the first pass via prompt; these are the
hard backstop.

  - is_chain(name)        -> drop (returns True if name matches a chain).
  - is_large_indie(name)  -> tag (returns True; do NOT drop).
  - is_online_only(name)  -> tag (returns True; do NOT drop).
"""
from __future__ import annotations

from config import CHAIN_KEYWORDS

# Big-box / national chains. Anything here is dropped, no exceptions.
_WINE_CHAIN_BLOCK = {
    "total wine", "bevmo", "binny", "spec's", "specs wine",
    "costco", "whole foods", "trader joe", "wegmans",
    "wine.com", "drizly", "vivino", "saucey", "minibar",
    "sam's club", "walmart", "kroger", "safeway", "albertsons",
    "publix", "h-e-b", "heb ", "target",
}

# Known large independents — kept, but tagged.
_LARGE_INDIE = {
    "k&l wines", "k & l wines", "k&l wine merchants",
    "astor wines", "astor wines & spirits",
    "zachys", "zachy",
    "sherry-lehmann", "sherry lehmann",
    "flatiron wines", "flatiron wines & spirits",
    "italian wine merchants",
    "chambers street wines",
    "moore brothers",
    "wally's", "wallys wine",
    "acker", "acker merrall",
    "hi-time wine cellars", "hi time wine",
    "bounty hunter wine",
    "morrell & company", "morrell and company",
    "park avenue liquor",
    "rare wine co",
    "garagiste",
    "envoyer",
}

# Online-only retailers — kept, but tagged.
_ONLINE_ONLY = {
    "sokolin",          # ambiguous — has physical, but largely online
    "last bottle",
    "wine access",
    "vinfolio",
    "winebid",
    "wtso", "wines till sold out",
    "garagiste",
    "envoyer",
    "underground cellar",
    "vinely",
    "primal wine",
    "the sip society",
    "winc",
    "firstleaf",
    "naked wines",
}


def _name_contains(name: str, needles: set[str] | list[str]) -> bool:
    n = (name or "").lower().strip()
    if not n:
        return False
    return any(needle in n for needle in needles)


def is_chain(name: str) -> bool:
    return _name_contains(name, _WINE_CHAIN_BLOCK) or _name_contains(name, CHAIN_KEYWORDS)


def is_large_indie(name: str) -> bool:
    return _name_contains(name, _LARGE_INDIE)


def is_online_only(name: str) -> bool:
    return _name_contains(name, _ONLINE_ONLY)
