"""
Clean the Wave 2 unified master.

Each channel produces a different shape of noise:

- **job_boards** (Indeed/Sevenrooms SERP-snippets): location strings
  ("Atlanta, GA 30303"), job-title fragments ("Sommelier Blossom"),
  generic terms ("Airport").
- **ig_seed_graph**: IG handles (lowercase, no spaces) that are chef
  personals, media accounts (michelinguide, forbestravelguide), brands
  (airfrance), photographers — not actual restaurants.
- **d2c_marketplaces** (Goldbelly): category landing pages
  ("America's Best Seafood", "Cheese Sampler") mixed with real merchants.
- **somm_credentialing**: wholesale/educator employers that the keyword
  filter didn't catch.
- **all channels**: chain restaurants (Marriott bars, Hilton restaurants,
  Chipotle, Shake Shack).

Strategy:
  1. Drop rows by hard rules (location strings, job-title fragments, bare
     IG handles, chain keywords, generic category names).
  2. Normalize name + city + state.
  3. Tier-rank by `n_sources` — cross-channel matches are kept regardless.
  4. Emit:
       output/wave2_master_clean_<stamp>.csv  — cleaned set
       output/wave2_master_rejected_<stamp>.csv — dropped rows + reason

Usage:
    python scripts/clean_wave2_master.py
    python scripts/clean_wave2_master.py --stamp 20260525
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


# -- Regex patterns ---------------------------------------------------------

# "Atlanta, GA 30303", "New York, NY", "Brooklyn, NY 11249", "Boston MA"
_LOCATION_NAME = re.compile(
    r"^\s*[A-Z][a-zA-Z'.\- ]+,?\s+[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?\s*$"
)

# "Wine Director", "Beverage Director", "Sommelier", "GM" — job-title fragments
_JOB_TITLES = {
    "sommelier", "wine director", "beverage director", "head sommelier",
    "wine buyer", "beverage program manager", "wine manager",
    "general manager", "executive chef", "head chef", "chef de cuisine",
    "f&b director", "food and beverage director", "bar manager",
    "wine director jobs", "sommelier jobs",
}

# Bare-handle test: all lowercase, no spaces, no punctuation other than _.
# These come from IG taggedAccounts and are not venues.
_IG_HANDLE_PATTERN = re.compile(r"^[a-z0-9_.]+$")

# Generic / category / non-venue names
_GENERIC_NAMES = {
    "airport", "restaurants", "bakery", "bakeries", "butcher", "butchers",
    "cheese shops", "wine shops", "wine stores", "cafe", "deli",
    "the restaurant", "the bar", "bar", "kitchen", "the kitchen",
    "menu", "home", "homepage",
}

# Category landing pages from Goldbelly
_CATEGORY_PHRASES = (
    r"^America's Best\b",
    r"^Best of\b",
    r"\bSampler$",
    r"\bGift Box\b",
    r"\bGift Card\b",
)
_CATEGORY_RE = re.compile("|".join(_CATEGORY_PHRASES), re.IGNORECASE)

# Chains we never want (the CHAIN_KEYWORDS list in config.py is more
# exhaustive — this is a shorter on-name-only blacklist for cleanup).
_CHAIN_KEYWORDS = {
    "chipotle", "shake shack", "panera", "starbucks", "subway",
    "domino's", "pizza hut", "papa john's", "mcdonald's", "burger king",
    "taco bell", "kfc", "wendy's", "applebee's", "olive garden",
    "red lobster", "outback steakhouse", "chili's", "tgi friday",
    "buffalo wild wings", "ihop", "denny's", "hard rock cafe",
    "p.f. chang", "cheesecake factory", "ruth's chris",
    "morton's", "fleming's", "capital grille", "del frisco",
    "marriott", "hilton", "hyatt", "sheraton", "westin", "ritz-carlton",
    "four seasons", "intercontinental", "doubletree",
    "the restaurant at", "restaurant at the",  # generic hotel-restaurant naming
    "courtyard by", "embassy suites", "holiday inn", "hampton inn",
}

# Known IG-handle non-venues (media, brands, chefs personal, photographers)
# These showed up in the 5-seed test run with frequency > 1 — keep growing
# this set as we scale to the full 50-seed run.
_IG_NON_VENUE = {
    "michelinguide", "forbestravelguide", "lesgrandestablesdumonde",
    "relaischateaux", "laliste1000", "airfrance", "michelin",
    "thefork", "opentable", "resy",
    # Chef personal handles
    "danielboulud", "ericripert", "thomaskeller", "alainducasse",
    "grantachatz", "davidchang", "nancysilverton", "jeanfrancois_piege",
    "bobbystuckey", "aldosohm", "raj_parr", "pascaline_lepeltier",
    "chefjoseandres", "ankurjain", "christophe_bellanca",
    "danielasotoinnes", "elena_reygadas", "ghayaoliveira", "ejlagasse",
    "emeril", "amaurybouhours", "lerouxeddy", "guedouarkarim",
    "willoughby.brian21", "shvelez", "katalina_pastry", "chef_julien",
    "moresaltandlard", "cheesefamilyandfriends", "ignaciomattos",
    "sebastiensilvestri", "joelrobuchon", "nigelparryportrait",
    "orlando_jsoto", "cityharvestnyc", "lebernardinprive",
    "lebernardinny", "restaurantdaniel",  # these are actually the restaurants but the handle vs name varies
    # Brand-only handles
    "ritzcarltoncaymancookout", "chefmicheletenzone",
    "blueboxcafenyc", "benoitny",
}

# Wholesale / educator employers slipping through the somm CMS filter
_NON_RESTAURANT_KEYWORDS_FUZZY = (
    "wine consulting", "wine education", "wine school", "court of master",
    "guildsomm", "wine sales", "wine spirits", "wine and spirits",
    "wine & spirits", "winery", "vineyard", "winemaker", "wine importer",
    "wine distribut", "wine wholesale", "distributor",
)


# -- Cleaning logic ---------------------------------------------------------


def _normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    # Trim trailing punctuation/markup
    s = s.strip(".,;:")
    return s


def _reject_reason(name: str, channels: str, business_type: str, blurb: str) -> str | None:
    """Return a short reason string if the row should be dropped, else None."""
    if not name or len(name) < 3:
        return "name_too_short"
    if len(name) > 100:
        return "name_too_long"

    low = name.lower()

    # Bare-handle test: only flag when this comes from the IG-graph channel.
    if "ig_seed_graph" in channels and _IG_HANDLE_PATTERN.match(name) and " " not in name:
        # Mid-confidence: handle could be a real restaurant (e.g. 'lilianyc')
        # but the noise floor is too high. Drop unless on the whitelist.
        if low in _IG_NON_VENUE:
            return "ig_non_venue_handle"
        # If the handle is all lowercase no-spaces AND not in our IG known-non-venue
        # set, drop conservatively. Restaurant venues that ONLY surface here
        # would be lost; that's acceptable for the cleaned set (the raw stays).
        return "ig_bare_handle"

    if low in _IG_NON_VENUE:
        return "non_venue_handle"

    if _LOCATION_NAME.match(name):
        return "location_string"

    if low in _GENERIC_NAMES:
        return "generic_name"

    if _CATEGORY_RE.search(name):
        return "category_landing_page"

    # Job-title fragments: the SERP-snippet parser sometimes captured the
    # role text as the name.
    if low in _JOB_TITLES:
        return "job_title_fragment"
    for jt in _JOB_TITLES:
        if low.startswith(jt + " ") or low.endswith(" " + jt):
            return "job_title_in_name"

    # Chains
    for chain in _CHAIN_KEYWORDS:
        if chain in low:
            return f"chain:{chain}"

    # Somm-credentialing wholesale slip-throughs
    if "somm_credentialing" in channels:
        for w in _NON_RESTAURANT_KEYWORDS_FUZZY:
            if w in low:
                return f"non_restaurant:{w}"

    # Strange Indeed snippet captures: "City, ST <ZIP>" or "Indeed <stuff>"
    if low.startswith("indeed "):
        return "indeed_snippet_fragment"

    # Pure-state suffix anomalies like ", FL"
    if re.match(r"^\s*,\s*[A-Z]{2}\s*$", name):
        return "bare_state_suffix"

    return None


def clean(stamp: str) -> tuple[Path, Path]:
    src = OUT / f"wave2_master_{stamp}.csv"
    if not src.exists():
        raise SystemExit(f"input not found: {src}")
    df = pd.read_csv(src, dtype=str).fillna("")
    print(f"  [clean] input: {len(df)} rows")

    df["name"] = df["name"].apply(_normalize_name)
    df["city"] = df["city"].apply(lambda s: re.sub(r"\s+", " ", s).strip())
    df["state"] = df["state"].apply(lambda s: s.strip().upper()[:2])

    keep: list[dict] = []
    rejects: list[dict] = []
    for row in df.to_dict("records"):
        reason = _reject_reason(row["name"], row.get("channels", ""), row.get("business_type", ""), row.get("blurbs", ""))
        # Always keep cross-channel matches (n_sources >= 2) regardless of name shape —
        # if it surfaced through multiple lenses we should look at it manually.
        try:
            n_sources = int(row.get("n_sources", 0) or 0)
        except (TypeError, ValueError):
            n_sources = 0
        if reason and n_sources < 2:
            row["_reject_reason"] = reason
            rejects.append(row)
            continue
        keep.append(row)

    print(f"  [clean] kept: {len(keep)} rows  ({len(rejects)} dropped)")

    clean_df = pd.DataFrame(keep)
    reject_df = pd.DataFrame(rejects)

    clean_path = OUT / f"wave2_master_clean_{stamp}.csv"
    reject_path = OUT / f"wave2_master_rejected_{stamp}.csv"
    clean_df.to_csv(clean_path, index=False)
    reject_df.to_csv(reject_path, index=False)

    print(f"  [clean] saved: {clean_path}")
    print(f"  [clean] rejects: {reject_path}")
    print()
    if len(reject_df):
        print("  [clean] reject reasons:")
        print(reject_df["_reject_reason"].value_counts().head(15).to_string())
    print()
    print("  [clean] kept per-channel:")
    if len(clean_df):
        exp = clean_df.assign(ch=clean_df["channels"].str.split(", ")).explode("ch")
        print(exp["ch"].value_counts().to_string())
    return clean_path, reject_path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stamp", help="YYYYMMDD stamp to clean", default=datetime.now().strftime("%Y%m%d"))
    args = p.parse_args()
    clean(args.stamp)


if __name__ == "__main__":
    main()
